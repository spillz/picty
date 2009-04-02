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
import subprocess
import time
import exif
import datetime
import bisect

try:
    import gnome.ui
    import gnomevfs
    import pyexiv2
except:
    print 'missing modules... exiting!'
    import sys
    sys.exit()

import settings
import backend
import imagemanip
import imageinfo
import fileops

settings.init() ##todo: make this call on first import inside the module


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

        self.meta_box=gtk.VBox()
        self.button_save=gtk.Button("Save",gtk.STOCK_SAVE)
        self.button_revert=gtk.Button("Revert",gtk.STOCK_REVERT_TO_SAVED)
        self.button_save.set_sensitive(False)
        self.button_revert.set_sensitive(False)
        buttons=gtk.HBox()
        buttons.pack_start(self.button_revert,True,False)
        buttons.pack_start(self.button_save,True,False)
        self.meta_box.pack_start(self.meta_table)
        self.meta_box.pack_start(buttons,False)
        self.meta_box.show_all()

        f=gtk.VPaned()
        f.add1(self.imarea)
        f.add2(self.meta_box)
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
        if writable:
            child2=gtk.Entry()
            child2.set_text(data)
            child2.connect("changed",self.MetadataChanged,key)
        else:
            child2=gtk.Label(data)
        table.attach(child2, left_attach=1, right_attach=2, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.EXPAND|gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)
        data_items[key]=(child1,child2)

    def CreateMetaTable(self):
        rows=2
        rows+=len(exif.tags)
        stable=gtk.ScrolledWindow()
        stable.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        table = gtk.Table(rows=rows, columns=2, homogeneous=False)
        stable.data_items=dict()
        self.AddMetaRow(table, stable.data_items,'FullPath','Full Path','',0)
        self.AddMetaRow(table, stable.data_items,'UnixLastModified','Last Modified','',1)
        r=2
        for k,v,w in exif.tags:
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
        try:
            enable=self.item.meta_backup!=self.item.meta
            self.button_save.set_sensitive(enable)
            self.button_revert.set_sensitive(enable)
        except:
            self.button_save.set_sensitive(False)
            self.button_revert.set_sensitive(False)
        self.meta_table.data_items['FullPath'][1].set_text(item.filename)
        d=datetime.datetime.fromtimestamp(item.mtime)
        self.meta_table.data_items['UnixLastModified'][1].set_text(d.isoformat(' '))
        for k,v,w in exif.tags:
            value=''
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

    def MetadataChanged(self,widget,key):
        if 'meta_backup' not in self.item.__dict__:
            self.item.meta_backup=self.item.meta.copy()
        self.item.meta[key]=widget.get_text()
        if key in self.item.meta and key not in self.item.meta_backup and widget.get_text()=='':
            del self.item.meta[key]
        enable=self.item.meta!=self.item.meta_backup ##TODO: only do the comp on writable keys AND '' == missing
        self.button_save.set_sensitive(enable)
        self.button_revert.set_sensitive(enable)
        print key,widget.get_text()

    def MetadataSave(self,widget):
        item=self.item
        if 'meta_backup' in item.__dict__:
            if item.meta_backup!=item.meta:
                imagemanip.save_metadata(item)
            del item.meta_backup
        self.button_save.set_sensitive(False)
        self.button_revert.set_sensitive(False)
        self.UpdateMetaTable(item)

    def MetadataRevert(self,widget):
        item=self.item
        if 'meta_backup' in item.__dict__:
            if item.meta_backup!=item.meta:
                item.meta=item.meta_backup
            del item.meta_backup
        ##todo: need to recreate thumb if orientation changed
        try:
            orient=item.meta['Exif.Image.Orientation']
        except:
            orient=None
        try:
            orient_backup=item.meta_backup['Exif.Image.Orientation']
        except:
            orient_backup=None
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
            rows+=len(exif.tags)
        stable=gtk.ScrolledWindow()
        stable.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        table = gtk.Table(rows=rows, columns=2, homogeneous=False)
        self.AddMetaRow(table,'Full Path',item.filename,0)
        self.AddMetaRow(table,'Last Modified',d.isoformat(' '),1)
        r=2
        for k,v in exif.tags:
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
            if self.item.thumbrgba:
                try:
                    drawable.draw_rgb_32_image(gc,x,y,iw,ih,
                           gtk.gdk.RGB_DITHER_NONE,
                           self.item.thumb, -1, 0, 0)
                except:
                    None
            else:
                try:
                    drawable.draw_rgb_image(gc,x,y,iw,ih,
                           gtk.gdk.RGB_DITHER_NONE,
                           self.item.thumb, -1, 0, 0)
                except:
                    None

#class StatusBar(gtk.VBox):
#    def __init__():
#        gtk.HBox.__init__(self)
#        gtk.ProgressBar()

class ImageBrowser(gtk.HBox):
    '''
    a widget designed to rapidly display a collection of objects
    from an image cache
    '''
    def __init__(self):
        gtk.HBox.__init__(self)
        self.Config()
        self.lock=threading.Lock()
        self.tm=backend.Worker(self)
        self.neededitem=None
        self.iv=ImageViewer(self.tm,self.ButtonPress_iv)
        self.is_fullscreen=False
        self.is_iv_fullscreen=False

        self.offsety=0
        self.offsetx=0
        self.ind_view_first=0
        self.ind_view_last=1
        self.ind_viewed=-1
        self.hover_ind=-1
        self.hover_cmds=[(self.select_item,self.render_icon(gtk.STOCK_SAVE, gtk.ICON_SIZE_MENU)),
                        (self.view_item,self.render_icon(gtk.STOCK_ZOOM_FIT, gtk.ICON_SIZE_MENU)),
                        (self.edit_item,self.render_icon(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)),
                        (self.rotate_item_left,self.render_icon(gtk.STOCK_GO_UP, gtk.ICON_SIZE_MENU)),
                        (self.rotate_item_right,self.render_icon(gtk.STOCK_GO_DOWN, gtk.ICON_SIZE_MENU)),
                        (self.hide_item,self.render_icon(gtk.STOCK_REVERT_TO_SAVED, gtk.ICON_SIZE_MENU)),
                        (self.delete_item,self.render_icon(gtk.STOCK_DELETE, gtk.ICON_SIZE_MENU))]

        self.sort_order=gtk.combo_box_new_text()
        for s in imageinfo.sort_keys:
            self.sort_order.append_text(s)
        self.sort_order.set_active(0)
        self.sort_order.set_property("can-focus",False)
        self.sort_order.connect("changed",self.set_sort_key)
        self.sort_order.show()

        self.toolbar=gtk.Toolbar()
        self.toolbar.append_item("Save Changes", "Saves all changes to image metadata in the collection (description, tags, image orientation etc)", None,
            gtk.ToolButton(gtk.STOCK_SAVE), self.save_all_changes, user_data=None)
        self.toolbar.append_item("Revert Changes", "Reverts all unsaved changes to image metadata in the collection (description, tags, image orientation etc)", None,
            gtk.ToolButton(gtk.STOCK_REVERT_TO_SAVED), self.revert_all_changes, user_data=None)
        self.toolbar.append_space()
        self.toolbar.append_item("Select All", "Selects all images in the current view", None,
            gtk.ToolButton(gtk.STOCK_ADD), self.select_all, user_data=None)
        self.toolbar.append_item("Select None", "Deselects all images in the current view", None,
            gtk.ToolButton(gtk.STOCK_CANCEL), self.select_none, user_data=None)
        self.toolbar.append_item("Upload Selected", "Uploads the selected images", None,
            gtk.ToolButton(gtk.STOCK_CONNECT), self.select_upload, user_data=None)
        self.toolbar.append_item("Copy Selected", "Copies the selected images in the current view to a new folder location", None,
            gtk.ToolButton(gtk.STOCK_COPY), self.select_copy, user_data=None)
        self.toolbar.append_item("Move Selected", "Moves the selected images in the current view to a new folder location", None,
            gtk.ToolButton(gtk.STOCK_CUT), self.select_move, user_data=None)
        self.toolbar.append_item("Delete Selected", "Deletes the selected images in the current view", None,
            gtk.ToolButton(gtk.STOCK_DELETE), self.select_delete, user_data=None)
        self.toolbar.append_space()
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.sort_order, "Sort Order", "Set the image attribute that determines the order images appear in", None, None,
            None, None)
        self.toolbar.append_item("Reverse Sort Order", "Reverse the order that images appear in", None,
            gtk.ToolButton(gtk.STOCK_SORT_ASCENDING), self.reverse_sort_order, user_data=None)
        self.toolbar.append_item("Add Filter", "Adds additional criteria that items in the current view must satisfy", None,
            gtk.ToolButton(gtk.STOCK_FIND), self.add_filter, user_data=None)
        self.toolbar.append_item("Show Filters", "Show the toolbar for the currently active filters", None,
            gtk.ToolButton(gtk.STOCK_FIND_AND_REPLACE), self.show_filters, user_data=None)
        self.toolbar.append_space()
        self.toolbar.show()

        self.imarea=gtk.DrawingArea()
        self.imarea.set_property("can-focus",True)
        self.Resize(160,200)
        self.scrolladj=gtk.Adjustment()
        self.vscroll=gtk.VScrollbar(self.scrolladj)

        self.vbox=gtk.VBox()
        self.status_bar=gtk.ProgressBar()
        self.vbox.pack_start(self.toolbar,False)
        self.vbox.pack_start(self.imarea)
        self.vbox.pack_start(self.status_bar,False)
        self.vbox.show()

        hpane=gtk.HPaned()
        hpane.add1(self.iv)
        hpane.add2(self.vbox)
        hpane.show()
        self.pack_start(hpane)
        self.pack_start(self.vscroll,False)
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
        self.vscroll.show()
        #self.Resize(600,300)

    def save_all_changes(self,widget):
        self.tm.save_or_revert_view()

    def revert_all_changes(self,widget):
        self.tm.save_or_revert_view(False)

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

    def set_sort_key(self,widget):
       self.imarea.grab_focus()
       key=widget.get_active_text()
       if key:
            self.tm.rebuild_view(key)

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
#        print 'key press',event.keyval
        if event.keyval==65535:
            fileops.worker.delete(self.tm.view,self.UpdateStatus)
        if event.keyval==92: #backslash
            if self.ind_viewed>=0:
                self.ind_viewed=len(self.tm.view)-1-self.ind_viewed
            self.tm.view.reverse=not self.tm.view.reverse
            self.AddImage([])
        if event.keyval==65307: #escape
            self.ind_viewed=-1
            self.iv.hide()
            self.iv.ImageNormal()
            self.vbox.show()
            self.vscroll.show()
        if event.keyval==65293: #enter
            if self.ind_viewed>=0:
                if self.is_iv_fullscreen:
                    self.ViewImage(self.ind_viewed)
                    self.iv.ImageNormal()
                    self.vbox.show()
                    self.vscroll.show()
                    self.is_iv_fullscreen=False
                else:
                    self.ViewImage(self.ind_viewed)
                    self.iv.ImageFullscreen()
                    self.vbox.hide()
                    self.vscroll.hide()
                    self.is_iv_fullscreen=True
        if (settings.maemo and event.keyval==65475) or event.keyval==65480: #f6 on settings.maemo or f11
            if self.is_fullscreen:
                self.window.unfullscreen()
                self.is_fullscreen=False
            else:
                self.window.fullscreen()
                self.is_fullscreen=True
        if event.keyval==65361: #left
            if self.ind_viewed>0:
                self.ViewImage(self.ind_viewed-1)
        if event.keyval==65363: #right
            if self.ind_viewed<len(self.tm.view)-1:
                self.ViewImage(self.ind_viewed+1)
        if event.keyval==65362: #up
            self.vscroll.set_value(self.vscroll.get_value()-self.scrolladj.step_increment)
        if event.keyval==65364: #dn
            self.vscroll.set_value(self.vscroll.get_value()+self.scrolladj.step_increment)
        if event.keyval==65365: #pgup
            self.vscroll.set_value(self.vscroll.get_value()-self.scrolladj.page_increment)
        if event.keyval==65366: #pgdn
            self.vscroll.set_value(self.vscroll.get_value()+self.scrolladj.page_increment)
        if event.keyval==65360: #home
            self.vscroll.set_value(self.scrolladj.lower)
        if event.keyval==65367: #end
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
            self.vscroll.show()
            self.is_iv_fullscreen=False
        else:
            self.ViewImage(self.ind_viewed)
            self.iv.ImageFullscreen()
            self.vbox.hide()
            self.vscroll.hide()
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


    def select_item(self,ind):
        item=self.tm.view(ind)
        item.selected=not item.selected
        self.RefreshView()

    def view_item(self,ind):
        self.ViewImage(ind)

    def edit_item(self,ind):
        item=self.tm.view(ind)
        subprocess.Popen(settings.edit_command_line+" "+item.filename,shell=True)

    def rotate_item_left(self,ind):
        item=self.tm.view(ind)
        if 'meta_backup' not in item.__dict__:
            item.meta_backup=item.meta.copy()
        imagemanip.rotate_left(item)
        self.UpdateThumbReqs()
        if ind==self.ind_viewed:
            self.ViewImage(self.ind_viewed)

    def rotate_item_right(self,ind):
        item=self.tm.view(ind)
        if 'meta_backup' not in item.__dict__:
            item.meta_backup=item.meta.copy()
        imagemanip.rotate_right(item)
        self.UpdateThumbReqs()
        if ind==self.ind_viewed:
            self.ViewImage(self.ind_viewed)

    def hide_item(self,ind):
        item=self.tm.view(ind)
        pass

    def delete_item(self,ind):
        item=self.tm.view(ind)
        fileops.worker.delete([item],None,False)

    def ButtonPress(self,obj,event):
        self.imarea.grab_focus()
        self.lock.acquire()
        ind=(int(self.offsety)+int(event.y))/(self.thumbheight+self.pad)*self.horizimgcount
        ind+=min(self.horizimgcount,int(event.x)/(self.thumbwidth+self.pad))
        ind=max(0,min(len(self.tm.view)-1,ind))
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
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)
        if self.ind_viewed>=0:
            self.iv.SetItem(self.tm.view(self.ind_viewed))

    def UpdateView(self):
        self.UpdateDimensions()
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

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
        self.scrolladj.set_all(value=self.offsety, lower=0,
                upper=len(self.tm.view)*(self.thumbheight+self.pad)/self.horizimgcount,
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
        self.ind_view_last = min(len(self.tm.view),self.ind_view_first+self.horizimgcount*(2+self.height/(self.thumbheight+self.pad)))

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
            if item.thumb:
                (thumbwidth,thumbheight)=self.tm.view(i).thumbsize
                adjy=self.pad/2+(128-thumbheight)/2
                adjx=self.pad/2+(128-thumbwidth)/2
                if item.thumbrgba:
                    try:
                        drawable.draw_rgb_32_image(gc,x+adjx,y+adjy,thumbwidth,thumbheight,
                                   gtk.gdk.RGB_DITHER_NONE,
                                   item.thumb, -1, 0, 0)
                    except:
                        None
                        #print 'thumberror',self.tm.view[i].filename,self.tm.view[i].thumbsize
                else:
                    try:
                        drawable.draw_rgb_image(gc,x+adjx,y+adjy,thumbwidth,thumbheight,
                                   gtk.gdk.RGB_DITHER_NONE,
                                   item.thumb, -1, 0, 0)
                    except:
                        None
                        #print 'thumberror',self.tm.view[i].filename,self.tm.view[i].thumbsize
#            else:
#                item=self.tm.view(i)
                #if not neededitem and not item.thumb and not  item.cannot_thumb:
                #    neededitem=self.tm.view[i]
#                thumbsneeded.insert(0,self.tm.view[i])
            if self.hover_ind==i or ('meta_backup' in item.__dict__) or item.selected:
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
                if 'meta_backup' not in item.__dict__:
                    show[0]=False
                    show[5]=False
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
        self.window.connect("delete_event", self.delete_event)
        self.window.connect("destroy", self.destroy)
        sett=gtk.settings_get_default()
        sett.set_long_property("gtk-toolbar-icon-size",gtk.ICON_SIZE_SMALL_TOOLBAR,"medusa:main") #gtk.ICON_SIZE_MENU
        sett.set_long_property("gtk-toolbar-style",gtk.TOOLBAR_ICONS,"medusa:main")

#        self.imcache=ImageCache()
        self.drawing_area = ImageBrowser()


        vb=gtk.VBox()
        vb.pack_start(self.drawing_area)
        self.window.add(vb)
        self.window.show()
        vb.show()
        self.drawing_area.show()

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
