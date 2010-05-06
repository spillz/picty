'''

    phraymd - Image Crop Plugin
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

import gtk
import Image

from phraymd import imagemanip
from phraymd import settings
from phraymd import pluginbase

class CropPlugin(pluginbase.Plugin):
    name='Crop'
    display_name='Image Crop'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        self.crop_mode=False
        self.crop_anchor=(0,0)
        self.crop_dimensions=(0,0,0,0)
        self.dragging=False
    def plugin_init(self,mainframe,app_init):
        self.viewer=mainframe.iv

        self.aspect_label=gtk.Label("Constraints")
        self.aspect_entry=gtk.ComboBoxEntry()
        self.aspect_entry.connect("changed",self.crop_aspect)
        self.ok_button=gtk.Button("Cro_p")
        self.ok_button.connect("clicked",self.crop_do_callback)
        self.cancel_button=gtk.Button("_Cancel")
        self.cancel_button.connect("clicked",self.crop_cancel_callback)

        self.crop_bar=gtk.HBox()
        self.crop_bar.pack_start(self.aspect_label,False)
        self.crop_bar.pack_start(self.aspect_entry)
        self.crop_bar.pack_start(self.cancel_button,False)
        self.crop_bar.pack_start(self.ok_button,False)
        self.crop_bar.show_all()
    def plugin_shutdown(self,app_shutdown=False):
        #deregister the button in the viewer
        if self.crop_mode:
            self.reset(app_shutdown)
    def viewer_register_shortcut(self,shortcut_commands):
        '''
        called by the framework to register shortcut on mouse over commands
        append a tuple containing the shortcut commands
        '''
        shortcut_commands.register_tool_for_plugin(self,'Crop',self.crop_button_callback,shortcut_commands.default_active_callback,'phraymd-image-crop','Interactively crop this image',40)
    def crop_button_callback(self,cmd,item):
        #the user has entered crop mode
        #hand the plugin exclusive control of the viewer
        if not self.viewer.plugin_request_control(self):
            return
        self.crop_mode=True
        self.viewer.image_box.pack_start(self.crop_bar,False)
        self.viewer.image_box.reorder_child(self.crop_bar,0)
        self.item=item
        self.press_handle=self.viewer.imarea.connect_after("button-press-event",self.button_press)
        self.release_handle=self.viewer.imarea.connect_after("button-release-event",self.button_release)
        self.motion_handle=self.viewer.imarea.connect_after("motion-notify-event",self.mouse_motion_signal)
    def crop_do_callback(self,widget):
        self.crop_mode=False
        wnum=self.item.image.size[0]
        wdenom=self.item.qview.get_width()
        #hscale=1.0*self.item.image.size[1]self.item.qview.get_height()
        image_crop_dimensions=tuple(int(x*wnum/wdenom) for x in self.crop_dimensions)
        self.item.image=self.item.image.crop(image_crop_dimensions)
        self.reset()
    def crop_cancel_callback(self,widget):
        self.reset(True)
    def reset(self,shutdown=False):
        self.crop_anchor=(0,0)
        self.crop_dimensions=(0,0,0,0)
        self.crop_mode=False
        self.item=None
        self.viewer.image_box.remove(self.crop_bar)
        self.viewer.imarea.disconnect(self.press_handle)
        self.viewer.imarea.disconnect(self.release_handle)
        self.viewer.imarea.disconnect(self.motion_handle)
        self.viewer.plugin_release(self)
        if not shutdown:
            self.viewer.refresh_view()
    def viewer_release(self,force=False):
        self.reset()
        return True

    def crop_aspect(self,widget):
        #slider has been shifted, crop the image accordingly (on the background thread?)
        if not self.crop_mode:
            return
        self.viewer.refresh_view()

    def viewer_to_image(self,x,y):
        x-=(self.viewer.imarea.window.get_size()[0]-self.item.qview.get_width())/2
        y-=(self.viewer.imarea.window.get_size()[1]-self.item.qview.get_height())/2
        x=min(max(x,0),self.item.qview.get_width())
        y=min(max(y,0),self.item.qview.get_height())
        return (x,y)

    def button_press(self,widget,event):
        if not self.crop_mode:
            return
        if event.button==1:
            self.dragging=True
            x,y=self.viewer_to_image(event.x,event.y)
            self.crop_anchor=(x,y)
            self.crop_dimensions=(x,y,x,y)
            self.viewer.redraw_view()

    def button_release(self,widget,event):
        if not self.crop_mode:
            return
        if event.button==1 and self.dragging:
            self.dragging=False
            x,y=self.viewer_to_image(event.x,event.y)
            X=(self.crop_anchor[0],x)
            Y=(self.crop_anchor[1],y)
            self.crop_dimensions=(min(X),min(Y),max(X),max(Y))
            self.viewer.redraw_view()

    def mouse_motion_signal(self,obj,event):
        '''callback when mouse moves in the viewer area (updates image overlay as necessary)'''
        if not self.crop_mode:
            return
        if self.dragging:
            x,y=self.viewer_to_image(event.x,event.y)
            X=(self.crop_anchor[0],x)
            Y=(self.crop_anchor[1],y)
            self.crop_dimensions=(min(X),min(Y),max(X),max(Y))
            self.viewer.redraw_view()

    def viewer_relinquish_control(self):
        #user has cancelled the view of the current item, plugin must cancel open operations
        pass

    def viewer_render_end(self,drawable,gc,item):
        if not self.crop_mode:
            return
        if self.crop_dimensions==(0,0,0,0):
            return
        x,y,w,h=self.crop_dimensions
        w-=x
        h-=y
        W,H=self.viewer.imarea.window.get_size()
        x+=(W-self.item.qview.get_width())/2
        y+=(H-self.item.qview.get_height())/2

        #block out the background in red
        fill_gc=drawable.new_gc()
        fill_gc.set_function(gtk.gdk.OR)
        colormap=drawable.get_colormap()
        red= colormap.alloc('red')
        fill_gc.set_foreground(red)
        fill_gc.set_background(red)
        drawable.draw_rectangle(fill_gc,True,0,0,W,y)
        drawable.draw_rectangle(fill_gc,True,0,y,x,y+h)
        drawable.draw_rectangle(fill_gc,True,x+w,y,W,y+h)
        drawable.draw_rectangle(fill_gc,True,0,y+h,W,H)

        #draw drag handles
        handle_gc=drawable.new_gc()
        hlen=10
        vlen=10
        colormap=drawable.get_colormap()
        white= colormap.alloc('white')
        handle_gc.set_foreground(white)
        handle_gc.set_background(white)
        handle_gc.set_line_attributes(3,gtk.gdk.LINE_SOLID,gtk.gdk.CAP_ROUND,gtk.gdk.JOIN_BEVEL)
        x=int(x)-1
        y=int(y)-1
        #top left
        drawable.draw_line(handle_gc,x,y,x+hlen,y)
        drawable.draw_line(handle_gc,x,y,x,y+vlen)

        #top right
        drawable.draw_line(handle_gc,x+w,y,x+w-hlen,y)
        drawable.draw_line(handle_gc,x+w,y,x+w,y+vlen)

        #bottom left
        drawable.draw_line(handle_gc,x,y+h,x+hlen,y+h)
        drawable.draw_line(handle_gc,x,y+h,x,y+h-vlen)

        #bottom right
        drawable.draw_line(handle_gc,x+w,y+h,x+w-hlen,y+h)
        drawable.draw_line(handle_gc,x+w,y+h,x+w,y+h-vlen)
