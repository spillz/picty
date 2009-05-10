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

import gobject
import gnomevfs
import gtk

gobject.threads_init()
gtk.gdk.threads_init()


import threading
import os
import os.path
import subprocess
import time
import datetime
import bisect

import sys
sys.path.insert(0,'/usr/share') ##private module location on installed version


try:
    import gnome.ui
    import gnomevfs
    import pyexiv2
except:
    print 'missing modules... exiting!'
    import sys
    sys.exit()

from phraymd import settings
from phraymd import backend
from phraymd import imagemanip
from phraymd import imageinfo
from phraymd import fileops
from phraymd import exif
from phraymd import register_icons
from phraymd import tagui

settings.init() ##todo: make this call on first import inside the module

class BatchMetaDialog(gtk.Dialog):
    def __init__(self,item):
        gtk.Dialog.__init__(self,flags=gtk.DIALOG_NO_SEPARATOR|gtk.DIALOG_MODAL,
                         buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        self.set_title('Batch Tag Manipulation')
        tags=[t[0:2] for t in exif.apptags if t[2]]
        rows=len(tags)
        table = gtk.Table(rows=rows, columns=3, homogeneous=False)
        self.item=item
        r=0
        print item.meta
        for k,v in tags:
            try:
                print k,v
                val=exif.app_key_to_string(k,item.meta[k])
                if not val:
                    val=''
                print 'item',k,val
            except:
                val=''
                print 'item err',k,val
            self.add_meta_row(table,k,v,val,r)
            r+=1
        table.show_all()
        hbox=gtk.HBox()
        hbox.pack_start(table)
        hbox.show_all()
        self.vbox.pack_start(hbox)
        file_label=gtk.Label()
        file_label.set_label("Only checked items will be changed")
        file_label.show()
        self.vbox.pack_start(file_label)
        self.set_default_response(gtk.RESPONSE_ACCEPT)
    def meta_changed(self,widget,key):
        value=exif.app_key_from_string(key,widget.get_text())
        self.item.set_meta_key(key,value)
    def toggled(self,widget,entry_widget,key):
        if widget.get_active():
            entry_widget.set_sensitive(True)
            value=exif.app_key_from_string(key,entry_widget.get_text())
            self.item.set_meta_key(key,value)
        else:
            entry_widget.set_sensitive(False)
            try:
                del self.item.meta[key]
            except:
                pass
    def add_meta_row(self,table,key,label,data,row,writable=True):
        child1=gtk.CheckButton()
        child1.set_active(False)
        table.attach(child1, left_attach=0, right_attach=1, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)
        child2=gtk.Label(label)
        table.attach(child2, left_attach=1, right_attach=2, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)
        child3=gtk.Entry()
        child3.set_property("activates-default",True)
        child3.set_text(data)
        child3.set_sensitive(False)
        child3.connect("changed",self.meta_changed,key)
        child1.connect("toggled",self.toggled,child3,key)
        table.attach(child3, left_attach=2, right_attach=3, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.EXPAND|gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)


class MetaDialog(gtk.Dialog):
    def __init__(self,item):
        gtk.Dialog.__init__(self,flags=gtk.DIALOG_NO_SEPARATOR|gtk.DIALOG_MODAL)
        self.set_title('Edit Descriptive Info')
        tags=[t[0:2] for t in exif.apptags if t[2]]
        rows=len(tags)
        table = gtk.Table(rows=rows, columns=2, homogeneous=False)
        self.item=item
        r=0
        print item.meta
        for k,v in tags:
            try:
                print k,v
                val=exif.app_key_to_string(k,item.meta[k])
                if not val:
                    val=''
                print 'item',k,val
            except:
                val=''
                print 'item err',k,val
            self.add_meta_row(table,k,v,val,r)
            r+=1
        table.show_all()
        hbox=gtk.HBox()
        if item.thumb: ##todo: should actually retrieve the thumb (via callback) if not present
            self.thumb=gtk.Image()
            self.thumb.set_from_pixbuf(item.thumb)
            hbox.pack_start(self.thumb)
        hbox.pack_start(table)
        hbox.show_all()
        self.vbox.pack_start(hbox)
        file_label=gtk.Label()
        file_label.set_label(item.filename)
        file_label.show()
        self.vbox.pack_start(file_label)
    def meta_changed(self,widget,key):
        value=exif.app_key_from_string(key,widget.get_text())
        self.item.set_meta_key(key,value)
    def add_meta_row(self,table,key,label,data,row,writable=True):
        child1=gtk.Label(label)
        table.attach(child1, left_attach=0, right_attach=1, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)
        if writable:
            child2=gtk.Entry()
            child2.set_text(data)
            child2.connect("changed",self.meta_changed,key)
        else:
            child2=gtk.Label(data)
        table.attach(child2, left_attach=1, right_attach=2, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.EXPAND|gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)


class ImageLoader:
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
                    try:
                        if len(value)==2:
                            value='%4.3f'%(1.0*value[0]/value[1])
                        else:
                            value=str(value)
                    except:
                        value=str(value)
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
        #import datetime
        d=datetime.datetime.fromtimestamp(item.mtime)
        #import exif
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
        #self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)

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

#class StatusBar(gtk.VBox):
#    def __init__():
#        gtk.HBox.__init__(self)
#        gtk.ProgressBar()

class ImageBrowser(gtk.VBox):
    '''
    a widget designed to rapidly display a collection of objects
    from an image cache
    '''
    def __init__(self):
        gtk.VBox.__init__(self)
        self.configure_geometry()
        self.lock=threading.Lock()
        self.tm=backend.Worker(self)
        self.neededitem=None
        self.iv=ImageViewer(self.tm,self.button_press_image_viewer,self.key_press_signal)
        self.is_fullscreen=False
        self.is_iv_fullscreen=False
        self.is_iv_showing=False

        self.info_bar=gtk.Label('Loading.... please wait')
        self.info_bar.show()

        self.pressed_ind=-1
        self.pressed_item=None
        self.last_selected_ind=-1
        self.last_selected=None

        self.shift_state=False

        self.pixbuf_thumb_fail=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,True,8,128,128)
        self.pixbuf_thumb_load=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,True,8,128,128)
        self.pixbuf_thumb_fail.fill(0xC0000080)
        self.pixbuf_thumb_load.fill(0xFFFFFF20)

        self.geo_view_offset=0
        self.offsetx=0
        self.geo_ind_view_first=0
        self.geo_ind_view_last=1
        self.hover_ind=-1
        self.hover_cmds=[
                        (self.save_item,self.render_icon(gtk.STOCK_SAVE, gtk.ICON_SIZE_MENU)),
                        (self.revert_item,self.render_icon(gtk.STOCK_REVERT_TO_SAVED, gtk.ICON_SIZE_MENU)),
                        (self.launch_item,self.render_icon(gtk.STOCK_EXECUTE, gtk.ICON_SIZE_MENU)),
                        (self.edit_item,self.render_icon(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)),
                        (self.rotate_item_left,self.render_icon('phraymd-rotate-left', gtk.ICON_SIZE_MENU)),
                        (self.rotate_item_right,self.render_icon('phraymd-rotate-right', gtk.ICON_SIZE_MENU)),
                        (self.delete_item,self.render_icon(gtk.STOCK_DELETE, gtk.ICON_SIZE_MENU))
                        ]

        self.sort_order=gtk.combo_box_new_text()
        i=0
        for s in imageinfo.sort_keys:
            self.sort_order.append_text(s)
            if s=='Relevance':
                self.sort_order_relevance_ind=i
            i+=1
        self.sort_order.set_active(0)
        self.sort_order.set_property("can-focus",False)
        self.sort_order.connect("changed",self.set_sort_key)
        self.sort_order.show()

        self.filter_entry=gtk.Entry()
        self.filter_entry.connect("activate",self.set_filter_text)
        self.filter_entry.show()

        self.selection_menu_button=gtk.Button('_Selection')
        self.selection_menu_button.connect("clicked",self.selection_popup)
        self.selection_menu_button.show()
        self.selection_menu=gtk.Menu()
        def menu_add(menu,text,callback):
            item=gtk.MenuItem(text)
            item.connect("activate",callback)
            menu.append(item)
            item.show()
        menu_add(self.selection_menu,"Select _All",self.select_all)
        menu_add(self.selection_menu,"Select _None",self.select_none)
        menu_add(self.selection_menu,"_Invert Selection",self.select_invert)
        menu_add(self.selection_menu,"Show All _Selected",self.select_show)
        menu_add(self.selection_menu,"_Copy Selection...",self.select_copy)
        menu_add(self.selection_menu,"_Move Selection...",self.select_move)
        menu_add(self.selection_menu,"_Delete Selection...",self.select_delete)
        menu_add(self.selection_menu,"Add _Tags",self.select_keyword_add)
        menu_add(self.selection_menu,"_Remove Tags",self.select_keyword_remove)
        menu_add(self.selection_menu,"Set Descriptive _Info",self.select_set_info)
        menu_add(self.selection_menu,"_Batch Manipulation",self.select_batch)

##        self.selection_menu_item.set_submenu(self.selection_menu)
        self.selection_menu.show()
##        self.selection_menu_item.show()

        self.tag_menu_button=gtk.ToggleButton('_Tag')
        self.tag_menu_button.connect("clicked",self.activate_tag_frame)
        self.tag_menu_button.show()

        self.toolbar=gtk.Toolbar()
        self.toolbar.append_item("Save Changes", "Saves all changes to metadata for images in the current view (description, tags, image orientation etc)", None,
            gtk.ToolButton(gtk.STOCK_SAVE), self.save_all_changes, user_data=None)
        self.toolbar.append_item("Revert Changes", "Reverts all unsaved changes to metadata for all images in the current view (description, tags, image orientation etc)", None,
            gtk.ToolButton(gtk.STOCK_REVERT_TO_SAVED), self.revert_all_changes, user_data=None)
        self.toolbar.append_space()
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.selection_menu_button, None,"Perform operations on selections", None,
            None, None, None)
        self.toolbar.append_space()
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.sort_order, "Sort Order", "Set the image attribute that determines the order images appear in", None, None,
            None, None)
        ## TODO: toggle the icon and tooltip depending on whether we are currently showing ascending or descending order
        self.toolbar.append_item("Reverse Sort Order", "Reverse the order that images appear in", None,
            gtk.ToolButton(gtk.STOCK_SORT_ASCENDING), self.reverse_sort_order, user_data=None)
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.filter_entry, "Filter", "Filter the view to images that contain the search text, press enter to activate", None, None,
            None, None)
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.tag_menu_button, None,"Toggle the tag panel", None,
            None, None, None)
#        self.toolbar.append_item("Add Filter", "Adds additional criteria that items in the current view must satisfy", None,
#            gtk.ToolButton(gtk.STOCK_FIND), self.add_filter, user_data=None)
#        self.toolbar.append_item("Show Filters", "Show the toolbar for the currently active filters", None,
#            gtk.ToolButton(gtk.STOCK_FIND_AND_REPLACE), self.show_filters, user_data=None)
#        self.toolbar.append_space()
        self.toolbar.show()

        self.imarea=gtk.DrawingArea()
        self.imarea.set_property("can-focus",True)
        self.scrolladj=gtk.Adjustment()
        self.vscroll=gtk.VScrollbar(self.scrolladj)
        self.vscroll.set_property("has-tooltip",True)
        self.vscroll.connect("query-tooltip",self.scroll_tooltip_query)

        self.tagframe=tagui.TagFrame(self.tm,self)
        #self.tagframe.show_all()

        self.vbox=gtk.VBox()
        self.status_bar=gtk.ProgressBar()
        self.status_bar.set_pulse_step(0.01)
#        self.vbox.pack_start(self.toolbar,False)
        self.vbox.pack_start(self.imarea)
        self.vbox.show()

        self.hbox=gtk.HBox()
        self.hbox.show()
        self.hbox.pack_start(self.vbox)
        self.hbox.pack_start(self.vscroll,False)
        self.hpane=gtk.HPaned()
        self.hpane_ext=gtk.HPaned()
        self.hpane.add1(self.hpane_ext)
        self.hpane.add2(self.iv)
        self.hpane_ext.add1(self.tagframe)
        self.hpane_ext.add2(self.hbox)
        self.hpane_ext.show()
        self.hpane.show()
        self.hpane.set_position(self.geo_thumbwidth+2*self.geo_pad)
        self.pack_start(self.toolbar,False,False)
        self.pack_start(self.hpane)
        self.pack_start(self.status_bar,False)
        self.pack_start(self.info_bar,False)
        self.connect("destroy", self.Destroy)
        self.imarea.connect("realize",self.realize_signal)
        self.imarea.connect("configure_event",self.configure_signal)
        self.imarea.connect("expose_event",self.expose_signal)
        self.imarea.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.imarea.connect("motion-notify-event",self.mouse_motion_signal)
        self.scrolladj.connect("value-changed",self.ScrollSignal)
        self.imarea.add_events(gtk.gdk.SCROLL_MASK)
        self.imarea.connect("scroll-event",self.ScrollSignalPane)
        self.imarea.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.imarea.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
        self.imarea.connect("button-press-event",self.button_press)
        self.imarea.connect("button-release-event",self.button_press)
        self.imarea.grab_focus()

        self.imarea.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.imarea.add_events(gtk.gdk.KEY_RELEASE_MASK)
        self.imarea.connect("key-press-event",self.key_press_signal)
        self.imarea.connect("key-release-event",self.key_press_signal)

        #self.set_flags(gtk.CAN_FOCUS)

#        self.vscroll.add_events(gtk.gdk.KEY_PRESS_MASK)
#        self.vscroll.set_flags(gtk.CAN_FOCUS)
#        self.vscroll.grab_focus()

        self.imarea.show()
        self.last_width=2*self.geo_pad+self.geo_thumbwidth
        self.vscroll.show()


    def Destroy(self,event):
        self.tm.quit()
        return False

    def activate_tag_frame(self,widget):
        if widget.get_active():
            self.tagframe.show_all()
        else:
            self.tagframe.hide()
        self.imarea.grab_focus()


    def selection_popup(self,widget):
        self.selection_menu.popup(parent_menu_shell=None, parent_menu_item=None, func=None, button=1, activate_time=0, data=0)
        #m.attach(gtk.MenuItem())

    def save_all_changes(self,widget):
        self.tm.save_or_revert_view()

    def revert_all_changes(self,widget):
        self.tm.save_or_revert_view(False)

    def select_invert(self,widget):
        self.tm.select_all_items(backend.INVERT_SELECT)
##        dlg=gtk.MessageDialog(flags=gtk.DIALOG_MODAL,buttons=gtk.BUTTONS_CLOSE)
##        dlg.text='Not implemented yet'
##        dlg.run()
##        dlg.destroy()

    def scroll_tooltip_query(self,widget,x, y, keyboard_mode, tooltip):
        height=widget.window.get_size()[1]
        yscroll=y*self.scrolladj.upper/height
        ind=min(len(self.tm.view),max(0,int(yscroll)/(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count))
        key=self.sort_order.get_active_text()
        key_fn=imageinfo.sort_keys_str[key]
        item=self.tm.view(ind)
        tooltip.set_text(key+': '+str(key_fn(item)))
        return True

    def select_show(self,widget):
        self.filter_entry.set_text("+selected")
        self.filter_entry.activate()

    def entry_dialog(self,title,prompt,default=''):
        dialog = gtk.Dialog(title,None,gtk.DIALOG_MODAL,
                         (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        prompt_label=gtk.Label()
        prompt_label.set_label(prompt)
        entry=gtk.Entry()
        entry.set_text(default)
        hbox=gtk.HBox()
        hbox.pack_start(prompt_label,False)
        hbox.pack_start(entry)
        hbox.show_all()
        dialog.vbox.pack_start(hbox)
        entry.set_property("activates-default",True)
        dialog.set_default_response(gtk.RESPONSE_ACCEPT)
        response=dialog.run()
        if response==gtk.RESPONSE_ACCEPT:
            ret_val=entry.get_text()
        else:
            ret_val=None
        dialog.destroy()
        return ret_val

    def select_keyword_add(self,widget):
        keyword_string=self.entry_dialog("Add Tags","Enter tags")
        if keyword_string:
            self.tm.keyword_edit(keyword_string)

    def select_keyword_remove(self,widget):
        keyword_string=self.entry_dialog("Remove Tags","Enter Tags")
        if keyword_string:
            self.tm.keyword_edit(keyword_string,True)

    def select_set_info(self,widget):
        item=imageinfo.Item('stub',None)
        item.meta={}
        dialog=BatchMetaDialog(item)
        response=dialog.run()
        dialog.destroy()
        if response==gtk.RESPONSE_ACCEPT:
            self.tm.info_edit(item.meta)

    def select_batch(self,widget):
        dlg=gtk.MessageDialog('gtk.DIALOG_MODAL',buttons=gtk.BUTTONS_CLOSE)
        dlg.text='Not implemented yet'
        dlg.run()
        dlg.destroy()

    def select_all(self,widget):
        self.tm.select_all_items()

    def select_none(self,widget):
        self.tm.select_all_items(backend.DESELECT)

    def select_upload(self,widget):
        print 'upload',widget

    def dir_pick(self,prompt):
        sel_dir=''
        fcd=gtk.FileChooserDialog(title=prompt, parent=None, action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK), backend=None)
        fcd.set_current_folder(os.environ['HOME'])
        response=fcd.run()
        if response == gtk.RESPONSE_OK:
            sel_dir=fcd.get_filename()
        fcd.destroy()
        return sel_dir

    def select_copy(self,widget):
        sel_dir=self.dir_pick('Copy Selection: Select destination folder')
        fileops.worker.copy(self.tm.view,sel_dir,self.UpdateStatus)

    def select_move(self,widget):
        sel_dir=self.dir_pick('Move Selection: Select destination folder')
        fileops.worker.move(self.tm.view,sel_dir,self.UpdateStatus)

    def select_delete(self,widget):
        fileops.worker.delete(self.tm.view,self.UpdateStatus)

    def set_filter_text(self,widget):
        self.set_sort_key(widget)

    def set_sort_key(self,widget):
       self.imarea.grab_focus()
       key=self.sort_order.get_active_text()
       filter_text=self.filter_entry.get_text()
       print 'sort&filter',key,filter_text
       self.tm.rebuild_view(key,filter_text)

    def add_filter(self,widget):
        print 'add_filter',widget

    def show_filters(self,widget):
        print 'show_filters',widget

    def reverse_sort_order(self,widget):
        self.tm.view.reverse=not self.tm.view.reverse
        self.RefreshView()

    def UpdateStatus(self,progress,message):
        self.status_bar.show()
        if 1.0>progress>=0.0:
            self.status_bar.set_fraction(progress)
        if progress<0.0:
            self.status_bar.pulse()
        if progress>=1.0:
            self.status_bar.hide()
        self.status_bar.set_text(message)

    def key_press_signal(self,obj,event):
        print event.keyval
        if event.type==gtk.gdk.KEY_PRESS:
            if event.keyval==65535: #del key
                fileops.worker.delete(self.tm.view,self.UpdateStatus)
            elif event.keyval==65307: #escape
                self.hide_image()
            elif (settings.maemo and event.keyval==65475) or event.keyval==65480: #f6 on settings.maemo or f11
                if self.is_fullscreen:
                    self.window.unfullscreen()
                    self.is_fullscreen=False
                else:
                    self.window.fullscreen()
                    self.is_fullscreen=True
            elif event.keyval==92: #backslash
                self.tm.view.reverse=not self.tm.view.reverse
                self.RefreshView()
            elif event.keyval==65293: #enter
                if self.iv.item:
                    if self.is_iv_fullscreen:
                        ##todo: merge with view_image/hide_image code (using extra args to control full screen stuff)
                        self.view_image(self.iv.item)
                        self.iv.ImageNormal()
                        self.vbox.show()
                        self.hpane_ext.show()
                        self.toolbar.show()
                        self.vscroll.show()
                        self.is_iv_fullscreen=False
                    else:
                        self.view_image(self.iv.item)
                        self.iv.ImageFullscreen()
                        self.toolbar.hide()
                        self.vbox.hide()
                        self.hpane_ext.hide()
                        self.vscroll.hide()
                        self.is_iv_fullscreen=True
            elif event.keyval==65361: #left
                if self.iv.item:
                    ind=self.item_to_view_index(self.iv.item)
                    if len(self.tm.view)>ind>0:
                        self.view_image(self.tm.view(ind-1))
            elif event.keyval==65363: #right
                if self.iv.item:
                    ind=self.item_to_view_index(self.iv.item)
                    if len(self.tm.view)-1>ind>=0:
                        self.view_image(self.tm.view(ind+1))
            elif event.keyval==65362: #up
                self.vscroll.set_value(self.vscroll.get_value()-self.scrolladj.step_increment)
            elif event.keyval==65364: #dn
                self.vscroll.set_value(self.vscroll.get_value()+self.scrolladj.step_increment)
            elif event.keyval==65365: #pgup
                self.vscroll.set_value(self.vscroll.get_value()-self.scrolladj.page_increment)
            elif event.keyval==65366: #pgdn
                self.vscroll.set_value(self.vscroll.get_value()+self.scrolladj.page_increment)
            elif event.keyval==65360: #home
                self.vscroll.set_value(self.scrolladj.lower)
            elif event.keyval==65367: #end
                self.vscroll.set_value(self.scrolladj.upper)
            elif event.keyval==65505: #shift
                self.redraw_view()
            elif event.keyval==65507: #control
                self.redraw_view()
        if event.type==gtk.gdk.KEY_RELEASE:
            if event.keyval==65505: #shift
                self.redraw_view()
            elif event.keyval==65507: #control
                self.redraw_view()
        return True

    def view_image(self,item,fullwindow=False):
        self.iv.show()
        self.iv.SetItem(item)
        self.is_iv_showing=True
        self.update_geometry(True)
        if self.iv.item!=None:
            ind=self.item_to_view_index(self.iv.item)
            self.center_view_offset(ind)
        self.UpdateScrollbar()
        self.update_required_thumbs()
        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)

    def hide_image(self):
        self.iv.hide()
        self.iv.ImageNormal()
        self.vbox.show()
        self.hbox.show()
        self.toolbar.show()
        self.vscroll.show()
        self.is_iv_fullscreen=False
        self.is_iv_showing=False

    def button_press_image_viewer(self,obj,event):
        if self.is_iv_fullscreen:
            self.iv.ImageNormal()
            self.vbox.show()
            self.toolbar.show()
            self.hpane_ext.show()
            self.info_bar.show()
            self.is_iv_fullscreen=False
        else:
            self.iv.ImageFullscreen()
            self.vbox.hide()
            self.toolbar.hide()
            self.hpane_ext.hide()
            self.info_bar.hide()
            self.is_iv_fullscreen=True

    def get_hover_command(self, ind, x, y):
        offset=ind-self.geo_ind_view_first
        left=(offset%self.geo_horiz_count)*(self.geo_thumbwidth+self.geo_pad)
        left+=self.geo_pad/4
        top=self.geo_ind_view_first*(self.geo_thumbheight+self.geo_pad)/self.geo_horiz_count-int(self.geo_view_offset)
        top+=offset/self.geo_horiz_count*(self.geo_thumbheight+self.geo_pad)
        top+=self.geo_pad/4
        for i in range(len(self.hover_cmds)):
            right=left+self.hover_cmds[i][1].get_width()
            bottom=top+self.hover_cmds[i][1].get_height()
            if left<x<=right and top<y<=bottom:
                return i
            left+=self.hover_cmds[i][1].get_width()+self.geo_pad/4
        return -1

    def popup_item(self,item):
        def menu_add(menu,text,callback,*args):
            item=gtk.MenuItem(text)
            item.connect("activate",callback,*args)
            menu.append(item)
            item.show()
        uri=gnomevfs.get_uri_from_local_path(item.filename)
        mime=gnomevfs.get_mime_type(uri)
        launch_menu=gtk.Menu()
        if mime in settings.custom_launchers:
            for app in settings.custom_launchers[mime]:
                menu_add(launch_menu,app[0],self.custom_mime_open,app[1],item)
        launch_menu.append(gtk.SeparatorMenuItem())
        for app in gnomevfs.mime_get_all_applications(mime):
            menu_add(launch_menu,app[1],self.mime_open,app[2],item)
        ##menu_add(menu,"Select _None",self.select_none)
        for app in settings.custom_launchers['default']:
            menu_add(launch_menu,app[0],self.custom_mime_open,app[1],item)
        menu_add(launch_menu,'Edit External Launchers...',self.edit_custom_mime_apps,item)

        menu=gtk.Menu()
        launch_item=gtk.MenuItem("Open with")
        launch_item.show()
        launch_item.set_submenu(launch_menu)
        menu.append(launch_item)
        if item.meta_changed:
            menu_add(menu,'Save Metadata Changes',self.save_item,item)
            menu_add(menu,'Revert Metadata Changes',self.revert_item,item)
        menu_add(menu,'Edit Metadata',self.edit_item,item)
        menu_add(menu,'Rotate Clockwise',self.rotate_item_right,item)
        menu_add(menu,'Rotate Anti-Clockwise',self.rotate_item_left,item)
        menu_add(menu,'Delete Image',self.delete_item,item)
        menu_add(menu,'Recreate Thumbnail',self.item_make_thumb,item)
        menu.popup(parent_menu_shell=None, parent_menu_item=None, func=None, button=1, activate_time=0, data=0)

    def edit_custom_mime_apps(self,widget,item):
        pass

    def item_make_thumb(self,widget,item):
        self.tm.recreate_thumb(item)

    def mime_open(self,widget,app_cmd,item):
        print 'mime_open',app_cmd,item
        subprocess.Popen(app_cmd+' "'+item.filename+'"',shell=True)

    def custom_mime_open(self,widget,app_cmd_template,item):
        from string import Template
        fullpath=item.filename
        directory=os.path.split(item.filename)[0]
        fullname=os.path.split(item.filename)[1]
        name=os.path.splitext(fullname)[0]
        ext=os.path.splitext(fullname)[1]
        app_cmd=Template(app_cmd_template).substitute(
            {'FULLPATH':fullpath,'DIR':directory,'FULLNAME':fullname,'NAME':name,'EXT':ext})
        print 'mime_open',app_cmd,item
        subprocess.Popen(app_cmd,shell=True)

    def save_item(self,widget,item):
        if item.meta_changed:
            imagemanip.save_metadata(item)

    def revert_item(self,widget,item):
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
        if orient!=orient_backup:
            item.thumb=None
            self.tm.recreate_thumb(item)
        self.redraw_view()

    def launch_item(self,widget,item):
        uri=gnomevfs.get_uri_from_local_path(item.filename)
        mime=gnomevfs.get_mime_type(uri)
        cmd=None
        if mime in settings.custom_launchers:
            for app in settings.custom_launchers[mime]:
                from string import Template
                fullpath=item.filename
                directory=os.path.split(item.filename)[0]
                fullname=os.path.split(item.filename)[1]
                name=os.path.splitext(fullname)[0]
                ext=os.path.splitext(fullname)[1]
                cmd=Template(app[1]).substitute(
                    {'FULLPATH':fullpath,'DIR':directory,'FULLNAME':fullname,'NAME':name,'EXT':ext})
                break
        if not cmd:
            for app in gnomevfs.mime_get_all_applications(mime):
                cmd=app[2]+' "%s"'%(item.filename,)
        if cmd:
            print 'mime_open',cmd
            subprocess.Popen(cmd,shell=True)
        else:
            print 'no known command for ',item.filename,' mimetype',mime

    def edit_item(self,widget,item):
        self.dlg=MetaDialog(item)
        self.dlg.show()

    def rotate_item_left(self,widget,item):
        ##TODO: put this task in the background thread (using the recreate thumb job)
        imagemanip.rotate_left(item)
        self.update_required_thumbs()
        if item==self.iv.item:
            self.view_image(item)

    def rotate_item_right(self,widget,item):
        ##TODO: put this task in the background thread (using the recreate thumb job)
        imagemanip.rotate_right(item)
        self.update_required_thumbs()
        if item==self.iv.item:
            self.view_image(item)

    def delete_item(self,widget,item):
        fileops.worker.delete([item],None,False)
        ind=self.tm.view.find_item(item)
        if ind>=0:
            self.tm.view.del_item(item)
            if self.is_iv_showing:
                ind=min(ind,len(self.tm.view)-1)
                self.view_image(self.tm.view(ind))
        elif self.is_iv_showing:
            self.hide_image()
        self.RefreshView()

    def item_to_view_index(self,item):
        return self.tm.view.find_item(item)

    def item_to_scroll_value(self,item):
        ind=self.item_to_view_index(item)
        return max(0,ind*(self.geo_thumbheight+self.geo_pad)/self.geo_horiz_count)#-self.geo_width/2)

    def multi_select(self,ind_from,ind_to,select=True):
        self.tm.lock.acquire()
        print 'multi select',select
##        select=self.tm.view(ind_from).selected
        if ind_to>ind_from:
            for x in range(ind_from,ind_to+1):
                item=self.tm.view(x)
                if not item.selected and select:
                    self.tm.collection.numselected+=1
                if item.selected and not select:
                    self.tm.collection.numselected-=1
                item.selected=select
        else:
            for x in range(ind_from,ind_to-1,-1):
                item=self.tm.view(x)
                if not item.selected and select:
                    self.tm.collection.numselected+=1
                if item.selected and not select:
                    self.tm.collection.numselected-=1
                item.selected=select
        self.tm.lock.release()
        self.redraw_view()

    def select_item(self,ind):
        if 0<=ind<len(self.tm.view):
            item=self.tm.view(ind)
            if item.selected:
                self.tm.collection.numselected-=1
            else:
                self.tm.collection.numselected+=1
            item.selected=not item.selected
            self.last_selected=item
            self.last_selected_ind=ind
            self.redraw_view()

    def button_press(self,obj,event):
        print 'press',event.button,event.type
        self.imarea.grab_focus()
        self.lock.acquire()
        ind=(int(self.geo_view_offset)+int(event.y))/(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count
        ind+=min(self.geo_horiz_count,int(event.x)/(self.geo_thumbwidth+self.geo_pad))
        ind=max(0,min(len(self.tm.view)-1,ind))
        item=self.tm.view(ind)
        if event.button==1 and event.type==gtk.gdk._2BUTTON_PRESS:
#            if ind==self.pressed_ind and self.tm.view(ind)==self.pressed_item and event.x<=(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count:
                self.view_image(item)
        elif event.button==1 and event.type==gtk.gdk.BUTTON_RELEASE:
                cmd=self.get_hover_command(ind,event.x,event.y)
                if cmd>=0:
                    if ind==self.pressed_ind and item==self.pressed_item and event.x<=(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count:
                        self.hover_cmds[cmd][0](None,self.pressed_item)
                else:
                    print 'multi selecting',event.state&gtk.gdk.SHIFT_MASK,event.state&gtk.gdk.CONTROL_MASK
                    if self.last_selected and event.state&(gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                        ind=self.item_to_view_index(self.last_selected)
                        if ind>=0:
                            self.multi_select(ind,self.pressed_ind,bool(event.state&gtk.gdk.SHIFT_MASK))
                    else:
                        self.select_item(self.pressed_ind)
        elif event.button==3 and event.type==gtk.gdk.BUTTON_RELEASE:
            self.popup_item(item)
        if event.button==1 and event.type in (gtk.gdk.BUTTON_PRESS,gtk.gdk._2BUTTON_PRESS):
            self.pressed_ind=ind
            self.pressed_item=self.tm.view(ind)
        else:
            self.pressed_ind=-1
            self.pressed_item=None
        self.lock.release()

    def recalc_hover_ind(self,x,y):
        ind=(int(self.geo_view_offset)+int(y))/(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count
        ind+=min(self.geo_horiz_count,int(x)/(self.geo_thumbwidth+self.geo_pad))
        ind=max(0,min(len(self.tm.view)-1,ind))
        if x>=(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count:
            ind=-1
        return ind

    def mouse_motion_signal(self,obj,event):
        ind=self.recalc_hover_ind(event.x,event.y)
        if self.hover_ind!=ind:
            self.hover_ind=ind
            self.redraw_view()

    def redraw_view(self):
        '''redraw the view without recomputing geometry or changing position'''
#        self.RefreshView()
        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)

    def RefreshView(self):
        '''update geometry, scrollbars, redraw the thumbnail view'''
        self.update_geometry()
        self.update_required_thumbs()
        self.UpdateScrollbar()
        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)
        self.info_bar.set_label('%i images in collection (%i selected, %i in view)'%(len(self.tm.collection),self.tm.collection.numselected,len(self.tm.view)))

    def post_build_view(self):
        print 'post build',self.tm.view.tag_cloud
        self.tagframe.refresh(self.tm.view.tag_cloud)

    def UpdateView(self):
        '''reset position, update geometry, scrollbars, redraw the thumbnail view'''
        self.geo_view_offset=0
        self.RefreshView()

    def ScrollSignalPane(self,obj,event):
        '''scrolls the view on mouse wheel motion'''
        if event.direction==gtk.gdk.SCROLL_UP:
            self.ScrollUp(max(1,self.geo_thumbheight+self.geo_pad)/5)
        if event.direction==gtk.gdk.SCROLL_DOWN:
            self.ScrollDown(max(1,self.geo_thumbheight+self.geo_pad)/5)

    def ScrollSignal(self,obj):
        '''signal response when the scroll position changes'''
        self.geo_view_offset=self.scrolladj.get_value()
        self.update_view_index_range()
        self.update_required_thumbs()
        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)
        self.vscroll.trigger_tooltip_query()

    def UpdateScrollbar(self):
        '''called to resync the scrollbar to changes in view geometry'''
        upper=len(self.tm.view)/self.geo_horiz_count
        if len(self.tm.view)%self.geo_horiz_count!=0:
            upper+=1
        upper=upper*(self.geo_thumbheight+self.geo_pad)
        self.scrolladj.set_all(value=self.geo_view_offset, lower=0,
                upper=upper,
                step_increment=max(1,self.geo_thumbheight+self.geo_pad)/5,
                page_increment=self.geo_height, page_size=self.geo_height)

    def ScrollUp(self,step=10):
        self.vscroll.set_value(self.vscroll.get_value()-step)

    def ScrollDown(self,step=10):
        self.vscroll.set_value(self.vscroll.get_value()+step)

    def configure_geometry(self):
        '''first time initialization of geometry (called from __init__)'''
        self.geo_thumbwidth=128
        self.geo_thumbheight=128
        if settings.maemo:
            self.geo_pad=20
        else:
            self.geo_pad=30
        self.geo_view_offset=0
        self.geo_screen_offset=0
        self.geo_ind_view_first=0
        self.geo_ind_view_last=0
        self.geo_horiz_count=1

    def update_view_index_range(self):
        '''computes the first and last indices in the view'''
        self.geo_ind_view_first = int(self.geo_view_offset/(self.geo_thumbheight+self.geo_pad))*self.geo_horiz_count
        self.geo_ind_view_last = self.geo_ind_view_first+self.geo_horiz_count*(2+self.geo_height/(self.geo_thumbheight+self.geo_pad))

    def update_geometry(self,recenter=False):
        '''recompute the changeable parts of the geometry (usually called in response to window
           size changes, or changes to the number of items in the collection'''
        nudge=self.calc_screen_offset()
        self.geo_horiz_count=max(int(self.geo_width/(self.geo_thumbwidth+self.geo_pad)),1)
        self.geo_view_offset_max=max(1,(self.geo_thumbheight+self.geo_pad)+(len(self.tm.view)-1)*(self.geo_thumbheight+self.geo_pad)/self.geo_horiz_count)
        self.geo_view_offset=max(0,min(self.geo_view_offset_max-self.geo_height,self.geo_view_offset))
        if recenter:
            if self.iv.item!=None:
                ind=self.item_to_view_index(self.iv.item)
            else:
                ind=-1
            if self.geo_ind_view_first<=ind<=self.geo_ind_view_last:
                self.center_view_offset(ind)
            else:
                self.set_view_offset(self.geo_ind_view_first)
                self.geo_view_offset-=nudge
        #print 'geo',self.geo_view_offset
        self.update_view_index_range()

    def update_required_thumbs(self):
        onscreen_items=self.tm.view.get_items(self.geo_ind_view_first,self.geo_ind_view_last)
        self.tm.request_thumbnails(onscreen_items) ##todo: caching ,fore_items,back_items

    def calc_screen_offset(self):
        '''computes how much to offset the first item in the view from the top of the screen (this should be negative)'''
        return int(self.geo_ind_view_first/self.geo_horiz_count)*(self.geo_pad+self.geo_thumbheight)-self.geo_view_offset

    def set_view_offset(self,index):
        '''reset the view offset position to keep the first item on screen after a window size change'''
        self.geo_view_offset=int(index/self.geo_horiz_count)*(self.geo_pad+self.geo_thumbheight)+self.geo_screen_offset
        self.geo_view_offset=max(0,min(self.geo_view_offset_max-self.geo_height,self.geo_view_offset))

    def center_view_offset(self,index):
        '''center the view on particular item in the view (receives an index)'''
        self.geo_screen_offset=0
        self.geo_view_offset=int(index/self.geo_horiz_count)*(self.geo_pad+self.geo_thumbheight)-self.geo_height/2+(self.geo_pad+self.geo_thumbheight)/2
        self.geo_view_offset=max(0,min(self.geo_view_offset_max-self.geo_height,self.geo_view_offset))

    def configure_signal(self,obj,event):
        '''received when the window size of the drawing area changes'''
        self.geo_width=event.width
        self.geo_height=event.height
        self.update_geometry(True)
        self.UpdateScrollbar()
        self.update_required_thumbs()
##        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)

    def expose_signal(self,event,arg):
        '''received when part of the drawing area needs to be shown'''
        self.realize_signal(event)

    def realize_signal(self,event):
        '''renders the view - received when the drawing area needs to be shown'''
        self.lock.acquire()
        drawable = self.imarea.window
        gc = drawable.new_gc()
        colormap=drawable.get_colormap()
        grey = colormap.alloc('grey')
        gc_s = drawable.new_gc(foreground=grey,background=grey)
        white = colormap.alloc('white')
        gc_v = drawable.new_gc(foreground=white)
        colormap=drawable.get_colormap()
        black = colormap.alloc('black')
        green = colormap.alloc('green')
        gc_g = drawable.new_gc(foreground=green)
        red= colormap.alloc('red')
        gc_r = drawable.new_gc(foreground=red)

        drawable.set_background(black)

        (mx,my)=self.imarea.get_pointer()
        if 0<=mx<drawable.get_size()[0] and 0<=my<drawable.get_size()[1]:
            self.hover_ind=self.recalc_hover_ind(mx,my)
        else:
            self.hover_ind=-1

        ##TODO: USE draw_drawable to shift screen for small moves in the display (scrolling)
        display_space=True
        imgind=self.geo_ind_view_first
        x=0
        y=self.calc_screen_offset()
        drawable.clear()
        i=imgind
        neededitem=None
        while i<self.geo_ind_view_last:
            if 0<=i<len(self.tm.view):
                item=self.tm.view(i)
            else:
                break
            if self.last_selected_ind>=0 and self.hover_ind>=0 and (self.last_selected_ind>=i>=self.hover_ind or self.last_selected_ind<=i<=self.hover_ind):
                key_mods=gtk.gdk.display_get_default().get_pointer()[3]
                if key_mods&(gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                    if self.last_selected:
                        if key_mods&gtk.gdk.SHIFT_MASK:
                            drawable.draw_rectangle(gc_g, True, x+self.geo_pad/16, y+self.geo_pad/16, self.geo_thumbwidth+self.geo_pad*7/8, self.geo_thumbheight+self.geo_pad*7/8)
                        else:
                            drawable.draw_rectangle(gc_r, True, x+self.geo_pad/16, y+self.geo_pad/16, self.geo_thumbwidth+self.geo_pad*7/8, self.geo_thumbheight+self.geo_pad*7/8)
            if item.selected:
                drawable.draw_rectangle(gc_s, True, x+self.geo_pad/8, y+self.geo_pad/8, self.geo_thumbwidth+self.geo_pad*3/4, self.geo_thumbheight+self.geo_pad*3/4)
            if item==self.iv.item:
                try:
                    (thumbwidth,thumbheight)=self.tm.view(i).thumbsize
                    adjy=self.geo_pad/2+(128-thumbheight)/2-3
                    adjx=self.geo_pad/2+(128-thumbwidth)/2-3
                    drawable.draw_rectangle(gc_v, True, x+adjx, y+adjy, thumbwidth+6, thumbheight+6)
                except:
                    pass
#            drawable.draw_rectangle(gc, True, x+self.geo_pad/4, y+self.geo_pad/4, self.geo_thumbwidth+self.geo_pad/2, self.geo_thumbheight+self.geo_pad/2)
            fail_item=False
            if item.thumb:
                (thumbwidth,thumbheight)=self.tm.view(i).thumbsize
                adjy=self.geo_pad/2+(128-thumbheight)/2
                adjx=self.geo_pad/2+(128-thumbwidth)/2
                drawable.draw_pixbuf(gc, item.thumb, 0, 0,x+adjx,y+adjy)
            elif item.cannot_thumb:
                adjy=self.geo_pad/2
                adjx=self.geo_pad/2
                drawable.draw_pixbuf(gc, self.pixbuf_thumb_fail, 0, 0,x+adjx,y+adjy)
            else:
                adjy=self.geo_pad/2
                adjx=self.geo_pad/2
                drawable.draw_pixbuf(gc, self.pixbuf_thumb_load, 0, 0,x+adjx,y+adjy)
            if self.hover_ind==i or item.meta_changed or item.selected or fail_item:
                if self.hover_ind==i or item.selected:
                    a,b=imageinfo.text_descr(item)
                    l=self.imarea.create_pango_layout('')
                    l.set_markup('<b><big>'+a+'</big></b>\n'+b)
                    drawable.draw_layout(gc,x+self.geo_pad/4,y+self.geo_pad+self.geo_thumbheight-l.get_pixel_size()[1]-self.geo_pad/4,l,white)
#                    print imageinfo.text_descr(item)
                l=len(self.hover_cmds)
                offx=self.geo_pad/4
                offy=self.geo_pad/4
                show=[True for r in range(l)]
                if self.hover_ind!=i:
                    for q in (1,2,3,4,5,6):
                        show[q]=False
                if not item.meta_changed:
                    show[0]=False
                    show[1]=False
                for j in range(l):
                    if show[j]:
                        drawable.draw_pixbuf(gc,self.hover_cmds[j][1],0,0,x+offx,y+offy)
                    offx+=self.hover_cmds[j][1].get_width()+self.geo_pad/4
            i+=1
            x+=self.geo_thumbwidth+self.geo_pad
            if x+self.geo_thumbwidth+self.geo_pad>=self.geo_width:
                y+=self.geo_thumbheight+self.geo_pad
                if y>=self.geo_height+self.geo_pad:
                    break
                else:
                    x=0
        self.lock.release()


class MainWindow:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_default_size(680, 400)
        self.window.set_title("PHRAYMD Photo Manager")
        self.window.connect("delete_event", self.delete_event)
        self.window.connect("destroy", self.destroy)
        sett=gtk.settings_get_default()
        sett.set_long_property("gtk-toolbar-icon-size",gtk.ICON_SIZE_SMALL_TOOLBAR,"phraymd:main") #gtk.ICON_SIZE_MENU
        sett.set_long_property("gtk-toolbar-style",gtk.TOOLBAR_ICONS,"phraymd:main")

#        self.imcache=ImageCache()
        self.drawing_area = ImageBrowser()

#        self.window.add_events(gtk.gdk.KEY_PRESS_MASK)
#        self.window.connect("key-press-event",self.drawing_area.key_press_signal)

        vb=gtk.VBox()
        vb.pack_start(self.drawing_area)
        self.window.add(vb)

        self.window.show()
        vb.show()
        self.drawing_area.show()
#        self.window.add_events(gtk.gdk.STRUCTURE_MASK)
#        self.window.connect("configure-event",self.drawing_area.config_pane)

    def on_down(self, widget, data=None):
        self.drawing_area.ScrollDown()

    def on_up(self, widget, data=None):
        self.drawing_area.ScrollUp()

    def delete_event(self, widget, event, data=None):
        return False #allows the window to be destroyed

    def destroy(self, widget, data=None):
        print "destroy signal occurred"
        gtk.main_quit()

    def main(self):
        gtk.main()

if __name__ == "__main__":
    wnd = MainWindow()
    wnd.main()
