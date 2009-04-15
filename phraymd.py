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
sys.path.append('/usr/share/phraymd') ##private module location on installed version


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
    def __init__(self,worker,click_callback=None):
        gtk.VBox.__init__(self)
        self.il=ImageLoader(self)
        self.imarea=gtk.DrawingArea()
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

        self.imarea.connect("realize",self.Render)
        self.imarea.connect("configure_event",self.Configure)
        self.imarea.connect("expose_event",self.Expose)
        self.button_save.connect("clicked",self.MetadataSave)
        self.button_revert.connect("clicked",self.MetadataRevert)
        self.connect("destroy", self.Destroy)
        self.imarea.add_events(gtk.gdk.SCROLL_MASK)
        self.imarea.add_events(gtk.gdk.BUTTON_MOTION_MASK)
        if not click_callback:
            self.imarea.connect("button-press-event",self.ButtonPress)
        else:
            self.imarea.connect("button-press-event",click_callback)

        self.imarea.set_size_request(300,200)
        self.imarea.show()
        f.show()
        self.item=None
        self.ImageNormal()

    def AddMetaRow(self,table,data_items,key,label,data,row,writable=False):
        child1=gtk.Label(label)
        table.attach(child1, left_attach=0, right_attach=1, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)
        child2=gtk.Label(data)
#        if writable:
#            child2=gtk.Entry()
#            child2.set_text(data)
#            child2.connect("changed",self.MetadataChanged,key)
#        else:
#            child2=gtk.Label(data)
        table.attach(child2, left_attach=1, right_attach=2, top_attach=row, bottom_attach=row+1,
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
            self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)
        else:
            print 'sized wrong item'

    def ImageLoaded(self,item):
        pass

    def SetItem(self,item):
        self.item=item
        self.il.set_item(item,(self.width,self.height))
        self.UpdateMetaTable(item)
        if not self.imarea.window:
            return
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)
        #self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def Configure(self,obj,event):
        self.width=event.width
        self.height=event.height
        self.il.update_image_size(self.width,self.height)
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def Expose(self,event,arg):
        self.Render(event)

    def Render(self,event):
        drawable = self.imarea.window
        gc = drawable.new_gc()
        colormap=drawable.get_colormap()
        black = colormap.alloc('black')
        drawable.set_background(black)
        drawable.clear()
        if self.item and self.item.qview:
            (iw,ih)=self.item.qview_size
            x=(self.width-iw)/2
            y=(self.height-ih)/2
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
            x=(self.width-iw)/2
            y=(self.height-ih)/2
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
        self.Config()
        self.lock=threading.Lock()
        self.tm=backend.Worker(self)
        self.neededitem=None
        self.iv=ImageViewer(self.tm,self.ButtonPress_iv)
        self.is_fullscreen=False
        self.is_iv_fullscreen=False

        self.info_bar=gtk.Label('Loading.... please wait')
        self.info_bar.show()

        self.pixbuf_thumb_fail=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,True,8,128,128)
        self.pixbuf_thumb_load=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,True,8,128,128)
        self.pixbuf_thumb_fail.fill(0xC0000080)
        self.pixbuf_thumb_load.fill(0xFFFFFF20)

        self.offsety=0
        self.offsetx=0
        self.ind_view_first=0
        self.ind_view_last=1
        self.ind_viewed=-1
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
        for s in imageinfo.sort_keys:
            self.sort_order.append_text(s)
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

        self.toolbar=gtk.Toolbar()
        self.toolbar.append_item("Save Changes", "Saves all changes to metadata for images in the current view (description, tags, image orientation etc)", None,
            gtk.ToolButton(gtk.STOCK_SAVE), self.save_all_changes, user_data=None)
        self.toolbar.append_item("Revert Changes", "Reverts all unsaved changes to metadata for all images in the current view (description, tags, image orientation etc)", None,
            gtk.ToolButton(gtk.STOCK_REVERT_TO_SAVED), self.revert_all_changes, user_data=None)
        self.toolbar.append_space()
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.selection_menu_button, None,"Perform operations on selections", None,
            None, None, None)
#        self.toolbar.append_item("Select All", "Selects all images in the current view", None,
#            gtk.ToolButton(gtk.STOCK_ADD), self.select_all, user_data=None)
#        self.toolbar.append_item("Select None", "Deselects all images in the current view", None,
#            gtk.ToolButton(gtk.STOCK_CANCEL), self.select_none, user_data=None)
#        self.toolbar.append_item("Upload Selected", "Uploads the selected images", None,
#            gtk.ToolButton(gtk.STOCK_CONNECT), self.select_upload, user_data=None)
#        self.toolbar.append_item("Copy Selected", "Copies the selected images in the current view to a new folder location", None,
#            gtk.ToolButton(gtk.STOCK_COPY), self.select_copy, user_data=None)
#        self.toolbar.append_item("Move Selected", "Moves the selected images in the current view to a new folder location", None,
#            gtk.ToolButton(gtk.STOCK_CUT), self.select_move, user_data=None)
#        self.toolbar.append_item("Delete Selected", "Deletes the selected images in the current view", None,
#            gtk.ToolButton(gtk.STOCK_DELETE), self.select_delete, user_data=None)
        self.toolbar.append_space()
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.sort_order, "Sort Order", "Set the image attribute that determines the order images appear in", None, None,
            None, None)
        ## TODO: toggle the icon and tooltip depending on whether we are currently showing ascending or descending order
        self.toolbar.append_item("Reverse Sort Order", "Reverse the order that images appear in", None,
            gtk.ToolButton(gtk.STOCK_SORT_ASCENDING), self.reverse_sort_order, user_data=None)
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.filter_entry, "Filter", "Filter the view to images that contain the search text, press enter to activate", None, None,
            None, None)
#        self.toolbar.append_item("Add Filter", "Adds additional criteria that items in the current view must satisfy", None,
#            gtk.ToolButton(gtk.STOCK_FIND), self.add_filter, user_data=None)
#        self.toolbar.append_item("Show Filters", "Show the toolbar for the currently active filters", None,
#            gtk.ToolButton(gtk.STOCK_FIND_AND_REPLACE), self.show_filters, user_data=None)
#        self.toolbar.append_space()
        self.toolbar.show()

        self.imarea=gtk.DrawingArea()
        self.imarea.set_property("can-focus",True)
        self.Resize(160,200)
        self.scrolladj=gtk.Adjustment()
        self.vscroll=gtk.VScrollbar(self.scrolladj)

        self.vbox=gtk.VBox()
        self.status_bar=gtk.ProgressBar()
        self.status_bar.set_pulse_step(0.01)
#        self.vbox.pack_start(self.toolbar,False)
        self.vbox.pack_start(self.imarea)
        self.vbox.pack_start(self.status_bar,False)
        self.vbox.pack_start(self.info_bar,False)
        self.vbox.show()

        self.hbox=gtk.HBox()
        self.hbox.show()
        self.hbox.pack_start(self.vbox)
        self.hbox.pack_start(self.vscroll,False)
        self.hpane=gtk.HPaned()
        self.hpane.add1(self.hbox)
        self.hpane.add2(self.iv)
        self.hpane.show()
        self.hpane.set_position(self.thumbwidth+2*self.pad)
        self.pack_start(self.toolbar,False,False)
        self.pack_start(self.hpane)
        self.connect("destroy", self.Destroy)
        self.imarea.connect("realize",self.Render)
        self.imarea.connect("configure_event",self.Configure)
        self.imarea.connect("expose_event",self.Expose)
        self.imarea.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.imarea.connect("motion-notify-event",self.MouseMotion)
        self.scrolladj.connect("value-changed",self.ScrollSignal)
        self.imarea.add_events(gtk.gdk.SCROLL_MASK)
        self.imarea.connect("scroll-event",self.ScrollSignalPane)
        self.imarea.add_events(gtk.gdk.BUTTON_MOTION_MASK)
        self.imarea.connect("button-press-event",self.ButtonPress)
        self.imarea.grab_focus()

        self.imarea.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.imarea.connect("key-press-event",self.KeyPress)

        #self.set_flags(gtk.CAN_FOCUS)

#        self.vscroll.add_events(gtk.gdk.KEY_PRESS_MASK)
#        self.vscroll.set_flags(gtk.CAN_FOCUS)
#        self.vscroll.grab_focus()

        self.imarea.show()
        self.last_width=2*self.pad+self.thumbwidth
        self.vscroll.show()

        #self.Resize(600,300)

    def selection_popup(self,widget):
        self.selection_menu.popup(parent_menu_shell=None, parent_menu_item=None, func=None, button=1, activate_time=0, data=0)
        #m.attach(gtk.MenuItem())

    def save_all_changes(self,widget):
        self.tm.save_or_revert_view()

    def revert_all_changes(self,widget):
        self.tm.save_or_revert_view(False)

    def select_invert(self,widget):
        pass

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
        pass

    def select_all(self,widget):
        self.tm.select_all_items()

    def select_none(self,widget):
        self.tm.select_all_items(False)

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
        if self.ind_viewed>=0:
            self.ind_viewed=len(self.tm.view)-1-self.ind_viewed
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

    def KeyPress(self,obj,event):
        if event.keyval==65535: #del key
            fileops.worker.delete(self.tm.view,self.UpdateStatus)
        elif event.keyval==65307: #escape
            self.ind_viewed=-1
            self.iv.hide()
            self.iv.ImageNormal()
            self.vbox.show()
            self.vscroll.show()
            self.toolbar.show()
        elif (settings.maemo and event.keyval==65475) or event.keyval==65480: #f6 on settings.maemo or f11
            if self.is_fullscreen:
                self.window.unfullscreen()
                self.is_fullscreen=False
            else:
                self.window.fullscreen()
                self.is_fullscreen=True
        elif event.keyval==92: #backslash
            if self.ind_viewed>=0:
                self.ind_viewed=len(self.tm.view)-1-self.ind_viewed
            self.tm.view.reverse=not self.tm.view.reverse
            self.AddImage([])
        elif event.keyval==65293: #enter
            if self.ind_viewed>=0:
                if self.is_iv_fullscreen:
                    self.ViewImage(self.ind_viewed)
                    self.iv.ImageNormal()
                    self.vbox.show()
                    self.toolbar.show()
                    self.vscroll.show()
                    self.is_iv_fullscreen=False
                else:
                    self.ViewImage(self.ind_viewed)
                    self.iv.ImageFullscreen()
                    self.toolbar.hide()
                    self.vbox.hide()
                    self.vscroll.hide()
                    self.is_iv_fullscreen=True
        elif event.keyval==65361: #left
            if self.ind_viewed>0:
                self.ViewImage(self.ind_viewed-1)
        elif event.keyval==65363: #right
            if self.ind_viewed<len(self.tm.view)-1:
                self.ViewImage(self.ind_viewed+1)
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
        return True

    def ViewImage(self,ind):
        self.ind_viewed=ind
        self.iv.show()
        self.iv.SetItem(self.tm.view(ind))
        self.offsety=max(0,ind*(self.thumbheight+self.pad)/self.horizimgcount)#-self.width/2)
        self.UpdateDimensions()
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def ButtonPress_iv(self,obj,event):
        if self.is_iv_fullscreen:
            self.ViewImage(self.ind_viewed)
            self.iv.ImageNormal()
            self.vbox.show()
            self.toolbar.show()
            self.hbox.show()
            self.is_iv_fullscreen=False
        else:
            self.ViewImage(self.ind_viewed)
            self.iv.ImageFullscreen()
            self.vbox.hide()
            self.toolbar.hide()
            self.hbox.hide()
            self.is_iv_fullscreen=True

    def get_hover_command(self, ind, x, y):
        offset=ind-self.ind_view_first
        left=(offset%self.horizimgcount)*(self.thumbwidth+self.pad)
        left+=self.pad/4
        top=self.ind_view_first*(self.thumbheight+self.pad)/self.horizimgcount-int(self.offsety)
        top+=offset/self.horizimgcount*(self.thumbheight+self.pad)
        top+=self.pad/4
        for i in range(len(self.hover_cmds)):
            right=left+self.hover_cmds[i][1].get_width()
            bottom=top+self.hover_cmds[i][1].get_height()
            if left<x<=right and top<y<=bottom:
                return i
            left+=self.hover_cmds[i][1].get_width()+self.pad/4
        return -1

    def save_item(self,ind):
        item=self.tm.view(ind)
        if item.meta_changed:
            imagemanip.save_metadata(item)

    def revert_item(self,ind):
        item=self.tm.view(ind)
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
        self.RefreshView()


    def select_item(self,ind):
        if 0<=ind<len(self.tm.view):
            item=self.tm.view(ind)
            if item.selected:
                self.tm.collection.numselected-=1
            else:
                self.tm.collection.numselected+=1
            item.selected=not item.selected
            self.RefreshView()

    def launch_item(self,ind):
        item=self.tm.view(ind)
        print 'launching',settings.edit_command_line+" "+item.filename
        subprocess.Popen(settings.edit_command_line+" "+item.filename,shell=True)

    def edit_item(self,ind):
        item=self.tm.view(ind)
        self.dlg=MetaDialog(item)
        self.dlg.show()

    def rotate_item_left(self,ind):
        ##TODO: put this task in the background thread (using the recreate thumb job)
        item=self.tm.view(ind)
        imagemanip.rotate_left(item)
        self.UpdateThumbReqs()
        if ind==self.ind_viewed:
            self.ViewImage(self.ind_viewed)

    def rotate_item_right(self,ind):
        ##TODO: put this task in the background thread (using the recreate thumb job)
        item=self.tm.view(ind)
        imagemanip.rotate_right(item)
        self.UpdateThumbReqs()
        if ind==self.ind_viewed:
            self.ViewImage(self.ind_viewed)

    def delete_item(self,ind):
        item=self.tm.view(ind)
        fileops.worker.delete([item],None,False)

    def ButtonPress(self,obj,event):
        self.imarea.grab_focus()
        self.lock.acquire()
        ind=(int(self.offsety)+int(event.y))/(self.thumbheight+self.pad)*self.horizimgcount
        ind+=min(self.horizimgcount,int(event.x)/(self.thumbwidth+self.pad))
        ind=max(0,min(len(self.tm.view)-1,ind))
        if event.x>=(self.thumbheight+self.pad)*self.horizimgcount:
            ind=-1
        else:
            if event.type==gtk.gdk._2BUTTON_PRESS:
                self.ViewImage(ind)
            if event.type==gtk.gdk.BUTTON_PRESS:
                cmd=self.get_hover_command(ind,event.x,event.y)
                if cmd>=0:
                    self.hover_cmds[cmd][0](ind)
                else:
                    self.select_item(ind)
##todo: if double left click then view image
##todo: if right click spawn a context menu
#            self.ViewImage(ind)
        self.lock.release()

    def recalc_hover_ind(self,x,y):
        ind=(int(self.offsety)+int(y))/(self.thumbheight+self.pad)*self.horizimgcount
        ind+=min(self.horizimgcount,int(x)/(self.thumbwidth+self.pad))
        ind=max(0,min(len(self.tm.view)-1,ind))
        if x>=(self.thumbheight+self.pad)*self.horizimgcount:
            ind=-1
        return ind

    def MouseMotion(self,obj,event):
        ind=self.recalc_hover_ind(event.x,event.y)
        if self.hover_ind!=ind:
            self.hover_ind=ind
            self.RefreshView()

    def Destroy(self,event):
        self.tm.quit()
        return False

    def Thumb_cb(self,item):
        ##TODO: Check if image is still on screen
#        if item.thumb:
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def RefreshView(self):
        if self.ind_view_first<0 or self.ind_view_first>=len(self.tm.view):
            self.UpdateView()
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)
        self.info_bar.set_label('%i images in collection (%i selected, %i in view)'%(len(self.tm.collection),self.tm.collection.numselected,len(self.tm.view)))
#        if self.ind_viewed>=0:
#            self.iv.SetItem(self.tm.view(self.ind_viewed))

    def UpdateView(self):
        self.offsety=0
        self.UpdateDimensions()
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)
        self.info_bar.set_label('%i images selected, %i images in the current view, %i images in the collection'%(self.tm.collection.numselected,len(self.tm.view),len(self.tm.collection)))

    def AddImages(self,items):
#        for item in items:
#            self.tm.view.add(item)
        self.UpdateDimensions()
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def AddImage(self,item):
#        self.tm.view.add(item)
        self.UpdateDimensions()
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def ScrollSignalPane(self,obj,event):
        if event.direction==gtk.gdk.SCROLL_UP:
            self.ScrollUp(max(1,self.thumbheight+self.pad)/5)
        if event.direction==gtk.gdk.SCROLL_DOWN:
            self.ScrollDown(max(1,self.thumbheight+self.pad)/5)

    def ScrollSignal(self,obj):
        self.offsety=self.scrolladj.get_value()
        self.UpdateFirstLastIndex()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def UpdateScrollbar(self):
        upper=len(self.tm.view)/self.horizimgcount
        if len(self.tm.view)%self.horizimgcount!=0:
            upper+=1
        upper=upper*(self.thumbheight+self.pad)
        self.scrolladj.set_all(value=self.offsety, lower=0,
                upper=upper,
                step_increment=max(1,self.thumbheight+self.pad)/5,
                page_increment=self.height, page_size=self.height)

    def Config(self):
        self.width=160
        self.height=400
        self.thumbwidth=128
        self.thumbheight=128
        if settings.maemo:
            self.pad=20
        else:
            self.pad=30

    def Resize(self,x,y):
        self.imarea.set_size_request(x, y)
        self.width=x
        self.height=y
        self.horizimgcount=(self.width/(self.thumbwidth+self.pad))
        self.maxoffsety=len(self.tm.view)*(self.thumbheight+self.pad)/self.horizimgcount

    def ScrollUp(self,step=10):
        self.vscroll.set_value(self.vscroll.get_value()-step)

    def ScrollDown(self,step=10):
        self.vscroll.set_value(self.vscroll.get_value()+step)

    def UpdateFirstLastIndex(self):
        self.ind_view_first = int(self.offsety)/(self.thumbheight+self.pad)*self.horizimgcount
        self.ind_view_last = self.ind_view_first+self.horizimgcount*(2+self.height/(self.thumbheight+self.pad))
#        self.ind_view_last = min(len(self.tm.view),self.ind_view_first+self.horizimgcount*(2+self.height/(self.thumbheight+self.pad)))

    def UpdateDimensions(self):
        self.offsety=self.offsety*self.horizimgcount
        self.horizimgcount=max(self.width/(self.thumbwidth+self.pad),1)
        self.maxoffsety=len(self.tm.view)*(self.thumbheight+self.pad)/self.horizimgcount
        self.offsety=self.offsety/self.horizimgcount
        if self.ind_viewed>=0:
            self.ind_view_first=max(self.ind_viewed-self.height/2/(self.thumbwidth+self.pad)*self.horizimgcount,0)
            self.offsety=self.ind_view_first*(self.thumbheight+self.pad)/self.horizimgcount
        self.UpdateFirstLastIndex()
        self.offsety=self.ind_view_first*(self.thumbheight+self.pad)/self.horizimgcount

    def Configure(self,obj,event):
        self.width=event.width
        self.height=event.height
        self.UpdateDimensions()
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

#    def on_set_pane(self,obj,event)
#
#    def config_pane(self,obj,event):
#        self.hpane.set_position(event.width-self.last_width)

    def Expose(self,event,arg):
        self.Render(event)

    def UpdateThumbReqs(self):
        ## DATA NEEDED
        count=self.ind_view_last-self.ind_view_first
#        first=max(0,self.ind_view_first-count)
#        last=min(len(self.tm.view),self.ind_view_last+count)
        onscreen_items=self.tm.view.get_items(self.ind_view_first,self.ind_view_last)
#        onscreen_items+=self.tm.view.get_items(first,self.ind_view_first)
#        onscreen_items+=self.tm.view.get_items(self.ind_view_last,last)
        self.tm.request_thumbnails(onscreen_items) ##todo: caching ,fore_items,back_items

    def Render(self,event):
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
        drawable.set_background(black)

        (mx,my)=self.imarea.get_pointer()
        if 0<=mx<drawable.get_size()[0] and 0<=my<drawable.get_size()[1]:
            self.hover_ind=self.recalc_hover_ind(mx,my)
        else:
            self.hover_ind=-1

        ##TODO: USE draw_drawable to shift screen for small moves in the display (scrolling)
        display_space=True
        imgind=self.ind_view_first
        x=0
        y=imgind*(self.thumbheight+self.pad)/self.horizimgcount-int(self.offsety)
        drawable.clear()
        i=imgind
        neededitem=None
        while i<self.ind_view_last:
            if 0<=i<len(self.tm.view):
                item=self.tm.view(i)
            else:
                break
            if item.selected:
                drawable.draw_rectangle(gc_s, True, x+self.pad/8, y+self.pad/8, self.thumbwidth+self.pad*3/4, self.thumbheight+self.pad*3/4)
            if self.ind_viewed==i:
                try:
                    (thumbwidth,thumbheight)=self.tm.view(i).thumbsize
                    adjy=self.pad/2+(128-thumbheight)/2-3
                    adjx=self.pad/2+(128-thumbwidth)/2-3
                    drawable.draw_rectangle(gc_v, True, x+adjx, y+adjy, thumbwidth+6, thumbheight+6)
                except:
                    pass
#            drawable.draw_rectangle(gc, True, x+self.pad/4, y+self.pad/4, self.thumbwidth+self.pad/2, self.thumbheight+self.pad/2)
            fail_item=False
            if item.thumb:
                (thumbwidth,thumbheight)=self.tm.view(i).thumbsize
                adjy=self.pad/2+(128-thumbheight)/2
                adjx=self.pad/2+(128-thumbwidth)/2
                drawable.draw_pixbuf(gc, item.thumb, 0, 0,x+adjx,y+adjy)
            elif item.cannot_thumb:
                adjy=self.pad/2
                adjx=self.pad/2
                drawable.draw_pixbuf(gc, self.pixbuf_thumb_fail, 0, 0,x+adjx,y+adjy)
            else:
                adjy=self.pad/2
                adjx=self.pad/2
                drawable.draw_pixbuf(gc, self.pixbuf_thumb_load, 0, 0,x+adjx,y+adjy)
            if self.hover_ind==i or item.meta_changed or item.selected or fail_item:
                if self.hover_ind==i or item.selected:
                    a,b=imageinfo.text_descr(item)
                    l=self.imarea.create_pango_layout('')
                    l.set_markup('<b><big>'+a+'</big></b>\n'+b)
                    drawable.draw_layout(gc,x+self.pad/4,y+self.pad+self.thumbheight-l.get_pixel_size()[1]-self.pad/4,l,white)
#                    print imageinfo.text_descr(item)
                l=len(self.hover_cmds)
                offx=self.pad/4
                offy=self.pad/4
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
                    offx+=self.hover_cmds[j][1].get_width()+self.pad/4
            i+=1
            x+=self.thumbwidth+self.pad
            if x+self.thumbwidth+self.pad>=self.width:
                y+=self.thumbheight+self.pad
                if y>=self.height+self.pad:
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
#        self.window.connect("key-press-event",self.drawing_area.KeyPress)

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
