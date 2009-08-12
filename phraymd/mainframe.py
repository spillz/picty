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


##standard python lib imports
import threading
import os
import os.path
import subprocess
import time
import datetime
import bisect

##gtk libs
import gobject
import gnomevfs ##todo: replace with gio
import gtk
gobject.threads_init()
gtk.gdk.threads_init()

## local imports
import settings
import viewer
import backend
import metadatadialogs
import register_icons
import browser
import pluginmanager
import pluginimporter

##todo: don't want these dependencies here, should all be in backend and done in the worker
import imagemanip
import imageinfo
import fileops


class MainFrame(gtk.VBox):
    '''
    this is the main widget box containing all of the gui widgets
    '''
    def __init__(self):
        gtk.VBox.__init__(self)
        self.lock=threading.Lock()

        ##plugin-todo: instantiate plugins
        self.plugmgr=pluginmanager.mgr
        self.plugmgr.instantiate_all_plugins()

        ##todo: register the right click menu options (a tuple)
        ##todo: this has to be registered after instantiation of browser.
        def show_on_hover(item,hover):
            return True
        self.hover_cmds=[
                        ##callback action,callback to test whether to show item,bool to determine if render always or only on hover,Icon
                        ('Save',self.save_item,lambda item,hover:item.meta_changed,True,self.render_icon(gtk.STOCK_SAVE, gtk.ICON_SIZE_MENU),'Main'),
                        ('Revert',self.revert_item,lambda item,hover:item.meta_changed,False,self.render_icon(gtk.STOCK_REVERT_TO_SAVED, gtk.ICON_SIZE_MENU),'Main'),
                        ('Launch',self.launch_item,show_on_hover,False,self.render_icon(gtk.STOCK_EXECUTE, gtk.ICON_SIZE_MENU),'Main'),
                        ('Edit Metadata',self.edit_item,show_on_hover,False,self.render_icon(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU),'Main'),
                        ('Rotate Left',self.rotate_item_left,show_on_hover,False,self.render_icon('phraymd-rotate-left', gtk.ICON_SIZE_MENU),'Main'),
                        ('Rotate Right',self.rotate_item_right,show_on_hover,False,self.render_icon('phraymd-rotate-right', gtk.ICON_SIZE_MENU),'Main'),
                        ('Delete',self.delete_item,show_on_hover,False,self.render_icon(gtk.STOCK_DELETE, gtk.ICON_SIZE_MENU),'Main')
                        ]
        self.plugmgr.callback('browser_register_shortcut',self.hover_cmds)

        self.browser=browser.ImageBrowser(self.hover_cmds)
        self.tm=self.browser.tm

        self.neededitem=None
        self.iv=viewer.ImageViewer(self.tm,self.button_press_image_viewer,self.key_press_signal)
        self.is_fullscreen=False
        self.is_iv_fullscreen=False
        self.is_iv_showing=False

        self.browser.connect("activate-item",self.activate_item)
        self.browser.connect("context-click-item",self.popup_item)
        self.browser.connect("status-updated",self.update_status)
        self.browser.connect("view-changed",self.view_changed)
##        self.browser.connect("view-rebuild-complete",self.view_rebuild_complete)

        self.browser.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.browser.add_events(gtk.gdk.KEY_RELEASE_MASK)
        self.browser.connect("key-press-event",self.key_press_signal)
        self.browser.connect("key-release-event",self.key_press_signal)

        self.info_bar=gtk.Label('Loading.... please wait')
        self.info_bar.show()

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
        self.filter_entry.set_width_chars(40)

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

        self.selection_menu.show()

        self.sidebar_menu_button=gtk.ToggleButton('Side_bar')
        self.sidebar_menu_button.connect("clicked",self.activate_sidebar)
        self.sidebar_menu_button.show()

        self.toolbar=gtk.Toolbar()
        self.toolbar.append_item("Save Changes", "Saves all changes to metadata for images in the current view (description, tags, image orientation etc)", None,
            gtk.ToolButton(gtk.STOCK_SAVE), self.save_all_changes, user_data=None)
        self.toolbar.append_item("Revert Changes", "Reverts all unsaved changes to metadata for all images in the current view (description, tags, image orientation etc)", None,
            gtk.ToolButton(gtk.STOCK_REVERT_TO_SAVED), self.revert_all_changes, user_data=None)
        self.toolbar.append_space()
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.sidebar_menu_button, None,"Toggle the Sidebar", None,
            None, None, None)
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.selection_menu_button, None,"Perform operations on selections", None,
            None, None, None)
        self.toolbar.append_space()
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.sort_order, "Sort Order", "Set the image attribute that determines the order images appear in", None, None,
            None, None)
        ## TODO: toggle the icon and tooltip depending on whether we are currently showing ascending or descending order
        self.toolbar.append_item("Reverse Sort Order", "Reverse the order that images appear in", None,
            gtk.ToggleToolButton(gtk.STOCK_SORT_ASCENDING), self.reverse_sort_order, user_data=None)
        self.toolbar.append_element(gtk.TOOLBAR_CHILD_WIDGET, self.filter_entry, "Filter", "Filter the view to images that contain the search text, press enter to activate", None, None,
            None, None)
        self.toolbar.append_item("Clear Filter", "Clear the filter and reset the view to the entire collection", None,
            gtk.ToolButton(gtk.STOCK_CLEAR), self.clear_filter, user_data=None)
        self.toolbar.show()

        self.status_bar=gtk.ProgressBar()
        self.status_bar.set_pulse_step(0.01)

        self.browser.show()

        self.hpane=gtk.HPaned()
        self.hpane_ext=gtk.HPaned()
        self.sidebar=gtk.Notebook()

        self.hpane_ext.add1(self.sidebar)
        self.hpane_ext.add2(self.browser)
        self.hpane_ext.show()
        self.hpane.add1(self.hpane_ext)
        self.hpane.add2(self.iv)
        self.hpane.show()
        self.hpane.set_position(self.browser.geo_thumbwidth+2*self.browser.geo_pad)

        self.pack_start(self.toolbar,False,False)
        self.pack_start(self.hpane)
        self.pack_start(self.status_bar,False)
        self.pack_start(self.info_bar,False)

        self.connect("destroy", self.destroy)
        self.plugmgr.init_plugins(self)
        self.tm.start()



    def activate_item(self,browser,ind,item):
        print 'activated',ind,item
        self.view_image(item)

    def destroy(self,event):
        settings.save()
        self.tm.quit()
        pluginmanager.mgr.callback('plugin_shutdown',True)
        return False

    def activate_sidebar(self,widget):
        if widget.get_active():
            self.sidebar.show()
        else:
            self.sidebar.hide()
        self.browser.grab_focus()

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

    def select_show(self,widget):
        self.filter_entry.set_text("selected")
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

    def view_changed(self,browser):
        '''refresh the info bar (status bar that displays number of images etc)'''
        self.info_bar.set_label('%i images in collection (%i selected, %i in view)'%(len(self.tm.collection),self.tm.collection.numselected,len(self.tm.view)))

    def select_keyword_add(self,widget):
        keyword_string=self.entry_dialog("Add Tags","Enter tags")
        if keyword_string:
            self.tm.keyword_edit(keyword_string)

    def select_keyword_remove(self,widget):
        keyword_string=self.entry_dialog("Remove Tags","Enter Tags")
        if keyword_string:
            self.tm.keyword_edit(keyword_string,False,True)

    def select_set_info(self,widget):
        item=imageinfo.Item('stub',None)
        item.meta={}
        dialog=metadatadialogs.BatchMetaDialog(item)
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
        fileops.worker.copy(self.tm.view,sel_dir,self.update_status)

    def select_move(self,widget):
        sel_dir=self.dir_pick('Move Selection: Select destination folder')
        fileops.worker.move(self.tm.view,sel_dir,self.update_status)

    def select_delete(self,widget):
        fileops.worker.delete(self.tm.view,self.update_status)

    def set_filter_text(self,widget):
        self.set_sort_key(widget)

    def clear_filter(self,widget):
        self.filter_entry.set_text('')
        self.set_sort_key(widget)

    def set_sort_key(self,widget):
       self.browser.grab_focus()
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
        self.browser.refresh_view()
        widget.set_active(self.tm.view.reverse)

    def update_status(self,widget,progress,message):
        self.status_bar.show()
        if 1.0>progress>=0.0:
            self.status_bar.set_fraction(progress)
        if progress<0.0:
            self.status_bar.pulse()
        if progress>=1.0:
            self.status_bar.hide()
        self.status_bar.set_text(message)

    def key_press_signal(self,obj,event):
        if event.type==gtk.gdk.KEY_PRESS:
            if event.keyval==65535: #del key, deletes selection
                fileops.worker.delete(self.tm.view,self.update_status)
            elif event.keyval==65307: #escape
                    if self.is_iv_fullscreen:
                        ##todo: merge with view_image/hide_image code (using extra args to control full screen stuff)
                        self.view_image(self.iv.item)
                        self.iv.ImageNormal()
                        self.browser.show()
                        self.hpane_ext.show()
                        self.toolbar.show()
                        self.info_bar.show()
                        self.is_iv_fullscreen=False
                        if self.is_fullscreen:
                            self.window.unfullscreen()
                            self.is_fullscreen=False
                    else:
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
                self.browser.refresh_view()
            elif event.keyval==65293: #enter
                if self.iv.item:
                    if self.is_iv_fullscreen:
                        ##todo: merge with view_image/hide_image code (using extra args to control full screen stuff)
                        if self.is_fullscreen:
                            self.window.unfullscreen()
                            self.is_fullscreen=False
                        self.view_image(self.iv.item)
                        self.iv.ImageNormal()
                        self.browser.show()
                        self.hpane_ext.show()
                        self.info_bar.show()
                        self.toolbar.show()
                        self.is_iv_fullscreen=False
                    else:
                        self.view_image(self.iv.item)
                        self.iv.ImageFullscreen()
                        self.toolbar.hide()
                        self.browser.hide()
                        self.info_bar.hide()
                        self.hpane_ext.hide()
                        self.is_iv_fullscreen=True
                        if not self.is_fullscreen:
                            self.window.fullscreen()
                            self.is_fullscreen=True
                self.browser.imarea.grab_focus() ##todo: should focus on the image viewer if in full screen and trap its key press events
            elif event.keyval==65361: #left
                if self.iv.item:
                    ind=self.browser.item_to_view_index(self.iv.item)
                    if len(self.tm.view)>ind>0:
                        self.view_image(self.tm.view(ind-1))
            elif event.keyval==65363: #right
                if self.iv.item:
                    ind=self.browser.item_to_view_index(self.iv.item)
                    if len(self.tm.view)-1>ind>=0:
                        self.view_image(self.tm.view(ind+1))
        return True


    def resize_browser_pane(self):
        w,h=self.hpane.window.get_size()
        if self.hpane.get_position()<self.browser.geo_thumbwidth+2*self.browser.geo_pad+self.hpane_ext.get_position():
            w,h=self.hpane.window.get_size()
            if w<=self.browser.geo_thumbwidth+2*self.browser.geo_pad+self.hpane_ext.get_position():
                self.hpane.set_position(w/2)
            else:
                self.hpane.set_position(self.browser.geo_thumbwidth+2*self.browser.geo_pad+self.hpane_ext.get_position())


    def view_image(self,item,fullwindow=False):
        self.iv.show()
        self.iv.SetItem(item)
        self.is_iv_showing=True
        self.browser.update_geometry(True)
        self.resize_browser_pane()
        if self.iv.item!=None:
            ind=self.browser.item_to_view_index(self.iv.item)
            self.browser.center_view_offset(ind)
        self.browser.update_scrollbar()
        self.browser.update_required_thumbs()
        self.browser.refresh_view()
        self.browser.focal_item=item
        self.browser.grab_focus()

    def hide_image(self):
        self.iv.hide()
        self.iv.ImageNormal()
        self.browser.show()
        #self.hbox.show()
        self.toolbar.show()
        self.hpane_ext.show()
        self.info_bar.show()
        self.is_iv_fullscreen=False
        self.is_iv_showing=False
        self.browser.grab_focus()

    def button_press_image_viewer(self,obj,event):
        if event.button==1 and event.type==gtk.gdk._2BUTTON_PRESS:
            if self.is_iv_fullscreen:
                self.iv.ImageNormal()
                self.browser.show()
                self.toolbar.show()
                self.hpane_ext.show()
                self.info_bar.show()
                self.is_iv_fullscreen=False
                if self.is_fullscreen:
                    self.window.unfullscreen()
                    self.is_fullscreen=False
            else:
                if not self.is_fullscreen:
                    self.window.fullscreen()
                    self.is_fullscreen=True
                self.iv.ImageFullscreen()
                self.browser.hide()
                self.toolbar.hide()
                self.hpane_ext.hide()
                self.info_bar.hide()
                self.is_iv_fullscreen=True
                print self.window.get_size()
            self.browser.imarea.grab_focus() ##todo: should focus on the image viewer if in full screen and trap its key press events

    def popup_item(self,browser,ind,item):
        ##todo: neeed to create a custom signal to hook into
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
        menu_add(menu,'Reload Metadata',self.item_reload_metadata,item)
        menu.popup(parent_menu_shell=None, parent_menu_item=None, func=None, button=1, activate_time=0, data=0)

    def item_make_thumb(self,widget,item):
        self.tm.recreate_thumb(item)

    def item_reload_metadata(self,widget,item):
        self.tm.reload_metadata(item)

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
        self.browser.redraw_view()

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
        self.dlg=metadatadialogs.MetaDialog(item)
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
        self.browser.refresh_view()

