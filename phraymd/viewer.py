#!/usr/bin/python

'''

    phraymd
    Copyright (C) 2009  Damien Moore

License:

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import threading
import time
import datetime

import gobject
import gtk

gobject.threads_init()
gtk.gdk.threads_init()

import settings
import imagemanip
import imageinfo
import pluginmanager
import exif

class ImageLoader:
    '''
    Class to load full size images into memory on a background thread,
    notifying the viewer on completion
    '''
    def __init__(self,viewer):
        self.thread=threading.Thread(target=self._background_task)
        self.item=None
        self.sizing=None
        self.zoom='fit'
        self.memimages=[]
        self.max_memimages=2
        self.vlock=threading.Lock()
        self.viewer=viewer
        self.event=threading.Event()
        self.exit=False
        self.plugin=None
        self.thread.start()

    def update_image_size(self,width,height):
        self.vlock.acquire()
        self.sizing=(width,height)
        self.vlock.release()
        self.event.set()

    def quit(self):
        self.vlock.acquire()
        self.exit=True
        self.vlock.release()
        self.event.set()
        while self.thread.isAlive():
            time.sleep(0.1)

    def set_item(self,item,sizing=None,zoom='fit'):
        self.vlock.acquire()
        self.item=item
        self.sizing=sizing ##if sizing is none, zoom is ignored
        self.zoom=zoom ##zoom is either 'fit' or a floating point number for scaling, 1= 1 image pixel: 1 screen pixel; 2= 1 image pixel:2 screen pixel; 0.5 = 2 image pixel:1 screen pixel
        self.vlock.release()
        self.event.set()

    def set_plugin(self,plugin):
        self.vlock.acquire()
        self.plugin=plugin
        self.vlock.release()

    def release_plugin(self,plugin):
        self.vlock.acquire()
        if plugin==self.plugin:
            self.plugin=None
        self.vlock.release()

    def _background_task(self):
        ##todo: this code is horrible! clean it up
        self.vlock.acquire()
        while 1:
            if (self.sizing or self.item) and 'image' in dir(self.item) and self.item.image==None:
                self.event.set()
            else:
                self.event.clear()
            self.vlock.release()
            self.event.wait()
            self.vlock.acquire()
            item=self.item
            self.vlock.release()
            if self.exit:
                return
            time.sleep(0.02)
            if not item:
                self.vlock.acquire()
                continue
            if not item.meta:
                imagemanip.load_metadata(item)
            if not item.image:
                def interrupt_cb():
                    return self.item.filename==item.filename
                imagemanip.load_image(item,interrupt_cb) ##todo: load as draft if zoom not required (but need to keep draft status of image to avoid problems)
                gobject.idle_add(self.viewer.ImageLoaded,item)
                if not item.image:
                    self.vlock.acquire()
                    continue
            self.vlock.acquire()
            if self.sizing:
                if not self.plugin or not self.plugin.t_viewer_sizing(self.sizing,self.zoom,item):
                    imagemanip.size_image(item,self.sizing,False,self.zoom)
                    if self.plugin:
                        self.plugin.t_viewer_sized(self.sizing,self.zoom,item)
                gobject.idle_add(self.viewer.ImageSized,item)
                self.sizing=None


class ImageViewer(gtk.VBox):
    #indices into the hover_cmds structure (overlay shortcuts in image browser)
    HOVER_TEXT=0 #text description of the command
    HOVER_CALLBACK=1 #callback when command is clicked
    HOVER_SHOW_CALLBACK=2 #callback  to determine whether callback should be displayed
    HOVER_ALWAYS_SHOW=3 #True if the overlay displays always, False only if mouse cursor is over the image
    HOVER_ICON=4 #the icon for the command
    def __init__(self,worker,hover_cmds,click_callback=None,key_press_callback=None):
        gtk.VBox.__init__(self)
        self.il=ImageLoader(self)
        self.imarea=gtk.DrawingArea()
        self.imarea.set_property("can-focus",True)
        self.worker=worker
        self.geo_width=-1
        self.geo_height=-1
        self.plugin_controller=None
        self.hover_cmds=hover_cmds
        self.mouse_hover=False

        self.freeze_image_refresh=False
        self.change_block=False

        self.image_box=gtk.VBox() ##plugins can add widgets to the box
        self.image_box.pack_start(self.imarea)
        self.image_box.show()

        self.vpane=gtk.VPaned()
        self.vpane.add1(self.image_box) ##plugins can add widgets wiith add2
        self.pack_start(self.vpane)
        self.vpane.show()

        self.imarea.connect("realize",self.realize_signal)
        self.conf_id=self.imarea.connect("configure_event",self.configure_signal)
        self.imarea.connect("expose_event",self.expose_signal)
        self.connect("destroy", self.Destroy)
        #self.imarea.add_events(gtk.gdk.SCROLL_MASK)
        #self.imarea.add_events(gtk.gdk.BUTTON_MOTION_MASK)
        self.imarea.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.imarea.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
        self.imarea.connect("button-press-event",self.button_press)
        self.imarea.connect("button-release-event",self.button_press)

        self.imarea.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.imarea.add_events(gtk.gdk.KEY_RELEASE_MASK)


        self.imarea.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.imarea.add_events(gtk.gdk.ENTER_NOTIFY_MASK)
        self.imarea.connect("enter-notify-event",self.mouse_enter_signal)
        self.imarea.add_events(gtk.gdk.LEAVE_NOTIFY_MASK)
        self.imarea.connect("leave-notify-event",self.mouse_leave_signal)


        if click_callback:
            self.imarea.connect_after("button-press-event",click_callback)
        if key_press_callback:
            self.imarea.connect("key-press-event",key_press_callback)
            self.imarea.connect("key-release-event",key_press_callback)

        self.imarea.set_size_request(128,96)
        self.imarea.show()
        self.item=None
        self.ImageNormal()

    def plugin_request_control(self,plugin,force=False):
        '''
        normally called by plugin to request exclusive access to image rendering and loading events
        '''
        if self.plugin_controller:
            if not self.plugin_controller.viewer_release() and not force:
                return False
        print 'activating plugin',plugin
        self.plugin_controller=plugin
        self.il.set_plugin(plugin)
        self.refresh_view()
        return True

    def request_plugin_release(self,force=False):
        '''
        normally called by framework when user tries to navigate away from image
        plugin will receive request to release drawing control and should normally
        obey the request by calling plugin_release
        '''
        if not self.plugin_controller:
            return True
        if not self.plugin_controller.viewer_release() and not force:
            return False
#        self.plugin_controller=None
#        self.il.release_plugin()
#        self.refresh_view()
        return True

    def plugin_release(self,plugin):
        '''
        called by plugin to relinquish control of the drawing and image loading/sizing events
        '''
        if plugin!=self.plugin_controller:
            return False
        self.plugin_controller=None
        self.il.release_plugin(plugin)
#        self.refresh_view()
        return True

    def ImageFullscreen(self):
        self.fullscreen=True

    def ImageNormal(self):
        self.fullscreen=False

    def Destroy(self,event):
        self.request_plugin_release(True)
        self.il.quit()
        return False

    def ImageSized(self,item):
        if not self.imarea.window:
            return
        if item.image==False:
            return
        if item.filename==self.item.filename:
            self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)
        else:
            print 'sized wrong item'

    def ImageLoaded(self,item):
        pass

    def SetItem(self,item):
        if not self.request_plugin_release():
            return False
        if not pluginmanager.mgr.callback_all_until_false('viewer_item_opening',item):
            return False
        self.item=item
        self.il.set_item(item,(self.geo_width,self.geo_height))
#        self.UpdateMetaTable(item)
        if self.imarea.window:
            self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)
        return True

#    def mouse_motion_signal(self,obj,event):
#        '''callback when mouse moves in the viewer area (updates image overlay as necessary)'''
#        if self.item!=None:
#            if not self.mouse_hover:
#                self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)
#            self.mouse_hover=True

    def mouse_enter_signal(self,obj,event):
        '''callback when mouse moves in the viewer area (updates image overlay as necessary)'''
        if self.item!=None:
            if not self.mouse_hover:
                self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)
            self.mouse_hover=True

    def mouse_leave_signal(self,obj,event):
        '''callback when mouse leaves the viewer area (hides image overlays)'''
        if event.mode!=gtk.gdk.CROSSING_NORMAL:
            return
        if self.item!=None:
            if self.mouse_hover:
                self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)
        self.mouse_hover=False

    def button_press(self,widget,event):
        if self.item!=None and self.item.qview!=None and event.button==1 and event.type==gtk.gdk.BUTTON_RELEASE:
            cmd=self.get_hover_command(event.x,event.y)
            print 'command',cmd,'mouse hover',self.mouse_hover
            if cmd>=0:
                cmd=self.hover_cmds.tools[cmd]
                if cmd.is_active(self.item,self.mouse_hover):
                    cmd.action(self.item)


    def get_hover_command(self, x, y):
        if not self.item.qview or self.plugin_controller:
            return -1
        return self.hover_comands.get_command(x,y,4,4,4)

    def refresh_view(self):
        #forces an image to be resized with a call to the worker thread
        self.il.update_image_size(self.geo_width,self.geo_height)

    def redraw_view(self):
        #forces an image to be resized with a call to the worker thread
        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)


    def configure_signal(self,obj,event):
        if not self.freeze_image_refresh and (self.geo_width!=event.width or self.geo_height!=event.height):
            self.geo_width=event.width
            self.geo_height=event.height
            self.il.update_image_size(self.geo_width,self.geo_height)
        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)

    def expose_signal(self,event,arg):
        self.realize_signal(event)

    def realize_signal(self,event):
        drawable = self.imarea.window
        gc = drawable.new_gc()
        colormap=drawable.get_colormap()
        black = colormap.alloc('black')
        drawable.set_background(black)
        drawable.clear()
        drew_image=False
        if pluginmanager.mgr.callback_first('viewer_render_start',drawable,gc,self.item):
            return
        if self.item and self.item.qview:
            (iw,ih)=(self.item.qview.get_width(),self.item.qview.get_height())
            x=(self.geo_width-iw)/2
            y=(self.geo_height-ih)/2
            drawable.draw_pixbuf(gc,self.item.qview,0,0,x,y)
            drew_image=True
        elif self.item and self.item.thumb:
            (iw,ih)=self.item.thumbsize
            x=(self.geo_width-iw)/2
            y=(self.geo_height-ih)/2
            drawable.draw_pixbuf(gc, self.item.thumb, 0, 0,x,y)
            drew_image=True
        if drew_image and not self.plugin_controller:
            self.hover_cmds.simple_render(self.item,self.mouse_hover,drawable,gc,4,4,4)
        pluginmanager.mgr.callback_first('viewer_render_end',drawable,gc,self.item)

