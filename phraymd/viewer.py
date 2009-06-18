#!/usr/bin/python2.5

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

import sys
sys.path.insert(0,'/usr/share') ##private module location on installed version

import gobject
import gnomevfs
import gtk

gobject.threads_init()
gtk.gdk.threads_init()


import settings
import imagemanip
import imageinfo
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
        self.memimages=[]
        self.max_memimages=2
        self.vlock=threading.Lock()
        self.viewer=viewer
        self.event=threading.Event()
        self.exit=False
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

    def set_item(self,item,sizing=None):
        self.vlock.acquire()
        self.item=item
        self.sizing=sizing
        self.vlock.release()
        self.event.set()

    def _background_task(self):
        self.vlock.acquire()
        while 1:
            if self.sizing or self.item and not self.item.image:
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
                imagemanip.load_image(item,interrupt_cb)
                gobject.idle_add(self.viewer.ImageLoaded,item)
                if not item.image:
                    self.vlock.acquire()
                    continue
            self.vlock.acquire()
            if self.sizing:
                imagemanip.size_image(item,self.sizing)
                gobject.idle_add(self.viewer.ImageSized,item)
                self.sizing=None


class ImageViewer(gtk.VBox):
    def __init__(self,worker,click_callback=None,key_press_callback=None):
        gtk.VBox.__init__(self)
        self.il=ImageLoader(self)
        self.imarea=gtk.DrawingArea()
        self.imarea.set_property("can-focus",True)
        self.meta_table=self.CreateMetaTable()
        self.worker=worker

        self.change_block=False

        self.meta_box=gtk.VBox()
        self.button_save=gtk.Button("Save",gtk.STOCK_SAVE)
        self.button_revert=gtk.Button("Revert",gtk.STOCK_REVERT_TO_SAVED)
        self.button_save.set_sensitive(False)
        self.button_revert.set_sensitive(False)
        buttons=gtk.HBox()
        buttons.pack_start(self.button_revert,True,False)
        buttons.pack_start(self.button_save,True,False)
        self.meta_box.pack_start(self.meta_table,True)
#        self.meta_box.pack_start(buttons,False)
        self.meta_box.show_all()

        f=gtk.VPaned()
        f.add1(self.meta_box)
        f.add2(self.imarea)
        f.set_position(0)
        self.pack_start(f)

        self.imarea.connect("realize",self.realize_signal)
        self.imarea.connect("configure_event",self.configure_signal)
        self.imarea.connect("expose_event",self.expose_signal)
        self.button_save.connect("clicked",self.MetadataSave)
        self.button_revert.connect("clicked",self.MetadataRevert)
        self.connect("destroy", self.Destroy)
        self.imarea.add_events(gtk.gdk.SCROLL_MASK)
        self.imarea.add_events(gtk.gdk.BUTTON_MOTION_MASK)

        self.imarea.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.imarea.add_events(gtk.gdk.KEY_RELEASE_MASK)

        if not click_callback:
            self.imarea.connect("button-press-event",self.ButtonPress)
        else:
            self.imarea.connect("button-press-event",click_callback)
        if key_press_callback:
            self.imarea.connect("key-press-event",key_press_callback)
            self.imarea.connect("key-release-event",key_press_callback)

        self.imarea.set_size_request(300,200)
        self.imarea.show()
        f.show()
        self.item=None
        self.ImageNormal()

    def AddMetaRow(self,table,data_items,key,label,data,row,writable=False):
        child1=gtk.Label(label)
        align=gtk.Alignment(0,0.5,0,0)
        align.add(child1)
        table.attach(align, left_attach=0, right_attach=1, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)
        child2=gtk.Label(data)
        align=gtk.Alignment(0,0.5,0,0)
        align.add(child2)
#        if writable:
#            child2=gtk.Entry()
#            child2.set_text(data)
#            child2.connect("changed",self.MetadataChanged,key)
#        else:
#            child2=gtk.Label(data)
        table.attach(align, left_attach=1, right_attach=2, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.EXPAND|gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)
        data_items[key]=(child1,child2)

    def CreateMetaTable(self):
        rows=2
        rows+=len(exif.apptags)
        stable=gtk.ScrolledWindow()
        stable.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        table = gtk.Table(rows=rows, columns=2, homogeneous=False)
        stable.data_items=dict()
        self.AddMetaRow(table, stable.data_items,'FullPath','Full Path','',0)
        self.AddMetaRow(table, stable.data_items,'UnixLastModified','Last Modified','',1)
        r=2
        for t in exif.apptags:
            k=t[0]
            v=t[1]
            w=t[2]
            try:
                self.AddMetaRow(table,stable.data_items,k,v,'',r,w)
            except:
                None
            r+=1
        table.show_all()
        stable.add_with_viewport(table)
        stable.set_focus_chain(tuple())
        return stable

    def UpdateMetaTable(self,item):
        self.change_block=True
        try:
            enable=item.meta_changed
            self.button_save.set_sensitive(enable)
            self.button_revert.set_sensitive(enable)
        except:
            self.button_save.set_sensitive(False)
            self.button_revert.set_sensitive(False)
        self.meta_table.data_items['FullPath'][1].set_text(item.filename)
        d=datetime.datetime.fromtimestamp(item.mtime)
        self.meta_table.data_items['UnixLastModified'][1].set_text(d.isoformat(' '))
        for t in exif.apptags:
            k=t[0]
            v=t[1]
            w=t[2]
            value=''
            if not item.meta:
                self.meta_table.data_items[k][1].set_text('')
            else:
                try:
                    value=item.meta[k]
                    value=exif.app_key_to_string(k,value)
                except:
                    value=''
                try:
                    self.meta_table.data_items[k][1].set_text(value)
                except:
                    print 'error updating meta table'
                    print 'values',value,type(value)
        self.change_block=False

    def MetadataChanged(self,widget,key):
        if self.change_block:
            return
        enable=self.item.set_meta_key(key,widget.get_text())
        self.button_save.set_sensitive(enable)
        self.button_revert.set_sensitive(enable)
        print key,widget.get_text()

    def MetadataSave(self,widget):
        item=self.item
        if item.meta_changed:
            imagemanip.save_metadata(item)
        self.button_save.set_sensitive(False)
        self.button_revert.set_sensitive(False)
        self.UpdateMetaTable(item)

    def MetadataRevert(self,widget):
        item=self.item
        if not item.meta_changed:
            return
        try:
            orient=item.meta['Orientation']
        except:
            orient=None
        try:
            orient_backup=item.meta_backup['Orientation']
        except:
            orient_backup=None
        item.meta_revert()
        ##todo: need to recreate thumb if orientation changed
        if orient!=orient_backup:
            item.thumb=None
            self.worker.recreate_thumb(item)
            self.SetItem(item)
        self.button_save.set_sensitive(False)
        self.button_revert.set_sensitive(False)
        self.UpdateMetaTable(item)

    def CreateMetadataFrame(self):
        item=self.item
        rows=2
        d=datetime.datetime.fromtimestamp(item.mtime)
        if item.meta:
            rows+=len(exif.apptags)
        stable=gtk.ScrolledWindow()
        stable.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        table = gtk.Table(rows=rows, columns=2, homogeneous=False)
        self.AddMetaRow(table,'Full Path',item.filename,0)
        self.AddMetaRow(table,'Last Modified',d.isoformat(' '),1)
        r=2
        for t in exif.apptags:
            k=t[0]
            v=t[1]
            w=t[2]
            try:
                self.AddMetaRow(table,v,str(item.meta[k]),r)
            except:
                None
            r+=1
        table.show_all()
        stable.add_with_viewport(table)
        return stable

    def ImageFullscreen(self):
        try:
            self.meta_box.hide()
        except:
            None
        self.fullscreen=True

    def ImageNormal(self):
        try:
            self.meta_box.show()
        except:
            None
        self.fullscreen=False

    def ButtonPress(self,obj,event):
        self.ImageNormal()
        self.hide()

    def Destroy(self,event):
        self.il.quit()
        return False

    def ImageSized(self,item):
        if not self.imarea.window:
            return
        if item.filename==self.item.filename:
            self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)
        else:
            print 'sized wrong item'

    def ImageLoaded(self,item):
        pass

    def SetItem(self,item):
        self.item=item
        self.il.set_item(item,(self.geo_width,self.geo_height))
        self.UpdateMetaTable(item)
        if not self.imarea.window:
            return
        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)

    def configure_signal(self,obj,event):
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
        if self.item and self.item.qview:
            (iw,ih)=self.item.qview_size
            x=(self.geo_width-iw)/2
            y=(self.geo_height-ih)/2
            #if x>=0 and y>=0:
            if self.item.imagergba:
                try:
                    drawable.draw_rgb_32_image(gc,x,y,iw,ih,
                       gtk.gdk.RGB_DITHER_NONE,
                       self.item.qview, -1, 0, 0)
                except:
                    None
            else:
                try:
                    drawable.draw_rgb_image(gc,x,y,iw,ih,
                           gtk.gdk.RGB_DITHER_NONE,
                           self.item.qview, -1, 0, 0)
                except:
                    None
        elif self.item and self.item.thumb:
            (iw,ih)=self.item.thumbsize
            x=(self.geo_width-iw)/2
            y=(self.geo_height-ih)/2
            drawable.draw_pixbuf(gc, self.item.thumb, 0, 0,x,y)
##            if self.item.thumbrgba:
##                try:
##                    drawable.draw_rgb_32_image(gc,x,y,iw,ih,
##                           gtk.gdk.RGB_DITHER_NONE,
##                           self.item.thumb, -1, 0, 0)
##                except:
##                    None
##            else:
##                try:
##                    drawable.draw_rgb_image(gc,x,y,iw,ih,
##                           gtk.gdk.RGB_DITHER_NONE,
##                           self.item.thumb, -1, 0, 0)
##                except:
##                    None

