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
import gtk
gobject.threads_init()
gtk.gdk.threads_init()

## local imports
import settings
import viewer
import backend
import dialogs
import register_icons
import browser
import pluginmanager
import pluginimporter
import io
import overlaytools
import searchbox
import dbusserver
import collectionmanager
import floats
from widget_tools import *


##todo: don't want these dependencies here, should all be in backend and done in the worker
import imagemanip
import baseobjects
import viewsupport
import fileops


class MainFrame(gtk.VBox):
    '''
    this is the main widget box containing all of the gui widgets
    '''
    __gsignals__={
        'activate-item':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,gobject.TYPE_INT,gobject.TYPE_PYOBJECT)),
        'context-click-item':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,gobject.TYPE_INT,gobject.TYPE_PYOBJECT)),
        'view-changed':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,)),
        'view-rebuild-complete':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,)),
        'status-updated':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,gobject.TYPE_FLOAT,gobject.TYPE_GSTRING)),
        'tag-row-dropped':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT)),
        'uris-dropped':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT))
        }

    def __init__(self,window):
        gtk.VBox.__init__(self)
        self.toplevel_window_state = ()
        self.toplevel_window_max =''
        self.lock=threading.Lock()
        self.hover_cmds=overlaytools.OverlayGroup(self,gtk.ICON_SIZE_MENU)
        self.volume_monitor=io.VolumeMonitor()
        self.volume_monitor.connect_after("mount-added",self.mount_added)
        self.volume_monitor.connect_after("mount-removed",self.mount_removed)
        self.coll_set=collectionmanager.CollectionSet()
        self.active_collection=None
        self.collections_init()
        self.float_mgr=floats.FloatingPanelManager(self)

        ## thank you to tadeboro http://www.gtkforums.com/post-10694.html#10694
        gtk.rc_parse_string ('''
                    style "tab-close-button-style"
                    {
                      GtkWidget::focus-padding = 0
                      GtkWidget::focus-line-width = 0
                      xthickness = 0
                      ythickness = 0
                    }
                    widget "*.tab-close-button" style "tab-close-button-style"
                    ''');
        ##

        ##plugin-todo: instantiate plugins
        self.plugmgr=pluginmanager.mgr
        self.plugmgr.instantiate_all_plugins()

        ##todo: register the right click menu options (a tuple)
        ##todo: this has to be registered after instantiation of browser.
        def show_on_hover(item,hover):
            return hover-1
        def show_on_hover_if_not_deleted(item,hover):
            return (hover and item.is_meta_changed()!=2)-1
        def show_and_changed(item,hover):
            return (hover and item.is_meta_changed())-1
        tools=[
                        ##callback action,callback to test whether to show item,bool to determine if render always or only on hover,Icon
                        ('Save',self.save_item,lambda item,hover:item.is_meta_changed()-1,[gtk.STOCK_SAVE,gtk.STOCK_DELETE],'Main','Save changes to the metadata in this image or delete the image if marked for deletion'),
                        ('Revert',self.revert_item,show_and_changed,[gtk.STOCK_REVERT_TO_SAVED,gtk.STOCK_UNDELETE],'Main','Revert changes to the metadata in this image or cancel the deletion of the image'),
#                        ('Launch',self.launch_item,show_on_hover,[gtk.STOCK_EXECUTE],'Main','Open with the default editor (well...  GIMP)'),
                        ('Edit Metadata',self.edit_item,show_on_hover,[gtk.STOCK_EDIT],'Main','Edit the descriptive metadata for this image'),
                        ('Rotate Left',self.rotate_item_left,show_on_hover,['phraymd-rotate-left'],'Main','Rotate the image 90 degrees counter-clockwise'),
                        ('Rotate Right',self.rotate_item_right,show_on_hover,['phraymd-rotate-right'],'Main','Rotate the image 90 degrees clockwise'),
                        ('Delete',self.delete_item,show_on_hover_if_not_deleted,[gtk.STOCK_DELETE],'Main','Mark the item for deletion (not final confirmed)')
                        ]
        for tool in tools:
            self.hover_cmds.register_tool(*tool)
        self.plugmgr.callback('browser_register_shortcut',self.hover_cmds)

        self.viewer_hover_cmds=overlaytools.OverlayGroup(self,gtk.ICON_SIZE_LARGE_TOOLBAR)
        viewer_tools=[
                        ##callback action,callback to test whether to show item,bool to determine if render always or only on hover,Icon
                        ('Close',self.close_viewer,show_on_hover,[gtk.STOCK_CLOSE],'Main','Hides the image viewer'),
                        ('Locate in Browser',self.show_viewed_item,show_on_hover,[gtk.STOCK_HOME],'Main','Locate the image in the browser'),
                        ('Save',self.save_item,show_and_changed,[gtk.STOCK_SAVE,gtk.STOCK_DELETE],'Main','Save changes to the metadata in this image'),
                        ('Revert',self.revert_item,show_and_changed,[gtk.STOCK_REVERT_TO_SAVED,gtk.STOCK_UNDELETE],'Main','Revert changes to the metadata in this image'),
                        ('Delete',self.delete_item,show_on_hover_if_not_deleted,[gtk.STOCK_DELETE],'Main','Mark for deletion (not final until confirmed)'),
                        ('Launch',self.launch_item,show_on_hover,[gtk.STOCK_EXECUTE],'Main','Open with the default editor (well...  GIMP)'),
                        ('Edit Metadata',self.edit_item,show_on_hover,[gtk.STOCK_EDIT],'Main','Edit the descriptive metadata for this image'),
                        ('Rotate Left',self.rotate_item_left,show_on_hover,['phraymd-rotate-left'],'Main','Rotate the image 90 degrees counter-clockwise'),
                        ('Rotate Right',self.rotate_item_right,show_on_hover,['phraymd-rotate-right'],'Main','Rotate the image 90 degrees clockwise'),
                        ('Zoom Fit',self.zoom_item_fit,show_on_hover,[gtk.STOCK_ZOOM_FIT],'Main','Zoom the image to fit available space'),
                        ('Zoom 100%',self.zoom_item_100,show_on_hover,[gtk.STOCK_ZOOM_100],'Main','Zoom to 100% size'),
                        ('Zoom In',self.zoom_item_in,show_on_hover,[gtk.STOCK_ZOOM_IN],'Main','Zoom in'),
                        ('Zoom Out',self.zoom_item_out,show_on_hover,[gtk.STOCK_ZOOM_OUT],'Main','Zoom out'),
                        ('Stub',None,lambda item,hover:False,[],'Main',''),
                        ]
        for tool in viewer_tools:
            self.viewer_hover_cmds.register_tool(*tool)
        self.plugmgr.callback('viewer_register_shortcut',self.viewer_hover_cmds)

        self.browser_nb=gtk.Notebook()
        self.browser_nb.set_show_tabs(False)
        self.browser_nb.set_scrollable(True)
        self.browser_nb.show()

        self.startpage=collectionmanager.CollectionStartPage(self.coll_set)
        self.startpage.connect("collection-open",self.collection_open_cb)
        self.startpage.connect("collection-new",self.create_new_collection)
        self.startpage.connect("collection-context-menu",self.collection_context_menu)
        self.startpage.connect("folder-open",self.browse_dir_as_collection)

        self.browser_nb.append_page(self.startpage,gtk.image_new_from_stock(gtk.STOCK_ADD,gtk.ICON_SIZE_MENU))

        self.tm=backend.Worker(self.coll_set)

        self.neededitem=None
        self.iv=viewer.ImageViewer(self.tm,self.viewer_hover_cmds,self.button_press_image_viewer,self.key_press_signal)
        self.is_fullscreen=False
        self.is_iv_fullscreen=False
        self.is_iv_showing=False

        self.info_bar=gtk.Label('Loading.... please wait')
        self.info_bar.show()

        self.sort_order=gtk.combo_box_new_text()
        self.sort_order.set_property("can-focus",False)
        self.sort_order.connect("changed",self.set_sort_key)
        self.sort_order.show()

        self.filter_entry=searchbox.SearchBox()
        self.filter_entry.entry.connect("activate",self.set_filter_text)
        self.filter_entry.entry.connect("changed",self.filter_text_changed)
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

        self.selection_menu.show()

        self.toolbar1=gtk.Toolbar()
        self.sidebar_toggle=gtk.ToggleToolButton('phraymd-sidebar')
        add_item(self.toolbar1,self.sidebar_toggle,self.activate_sidebar,"Sidebar","Toggle the Sidebar")
        add_item(self.toolbar1,gtk.ToolButton(gtk.STOCK_PREFERENCES),self.open_preferences,"Preferences","Open the global settings and configuration dialog")
        self.toolbar1.add(gtk.SeparatorToolItem())
        self.connect_toggle=gtk.ToggleToolButton(gtk.STOCK_CONNECT)
        add_item(self.toolbar1,self.connect_toggle,self.connect_toggled,"Connect to Source", "Connect or disconnect to the source of the images in this collection (you can only read from and modify the collection when connected)")
        self.refresh_button=gtk.ToolButton(gtk.STOCK_REFRESH)
        add_item(self.toolbar1,self.refresh_button,self.collection_rescan,"Rescan Collection", "Rescan the source for changes to images")
        self.save_button=gtk.ToolButton(gtk.STOCK_SAVE)
        add_item(self.toolbar1,self.save_button,self.save_all_changes,"Save Changes", "Saves all changes to metadata for images in the current view (description, tags, image orientation etc)")
        self.revert_button=gtk.ToolButton(gtk.STOCK_UNDO)
        add_item(self.toolbar1,self.revert_button,self.revert_all_changes,"Revert Changes", "Reverts all unsaved changes to metadata for all images in the current view (description, tags, image orientation etc)") ##STOCK_REVERT_TO_SAVED

        self.toolbar1.add(gtk.SeparatorToolItem())
        add_widget(self.toolbar1,gtk.Label("Search: "),None,None,None)
        if self.filter_entry.entry_no_icons:
            add_widget(self.toolbar1,self.filter_entry,None,None, "Enter keywords or an expression to restrict the view to images in the active collection matching the expression or choose from the list of common searches in the drop-down list",True)
            add_item(self.toolbar1,gtk.ToolButton(gtk.STOCK_CLEAR),self.clear_filter,None, "Reset the filter and display all images in collection",False)
        else:
            self.filter_entry.entry.connect("icon-press",self.clear_filter)
            add_widget(self.toolbar1,self.filter_entry,None,None, "Enter keywords or an expression to restrict the view to images in the active collection matching the expression or choose from the list of common searches in the drop-down list",True)
        self.toolbar1.add(gtk.SeparatorToolItem())
        add_widget(self.toolbar1,gtk.Label("Sort: "),None,None,None)
        add_widget(self.toolbar1,self.sort_order,None,None,"Set the image attribute that determines the order images appear in")
        self.sort_toggle=gtk.ToggleToolButton(gtk.STOCK_SORT_ASCENDING)
        add_item(self.toolbar1,self.sort_toggle,self.reverse_sort_order,"Reverse Sort Order", "Reverse the order that images appear in")
        self.toolbar1.add(gtk.SeparatorToolItem())
        self.toolbar1.show_all()

        accel_group = gtk.AccelGroup()
        window.add_accel_group(accel_group)
        self.filter_entry.add_accelerator("grab-focus", accel_group, ord('F'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        self.sort_order.add_accelerator("popup", accel_group, ord('O'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        accel_group.connect_group(ord('B'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE,self.sidebar_accel_callback)

        self.accel_group=accel_group


        self.status_bar=gtk.ProgressBar()
        self.status_bar.set_pulse_step(0.01)

        self.hpane=gtk.HPaned()
        self.hpane_ext=gtk.HPaned()
        self.sidebar=gtk.Notebook() ##todo: make the sidebar a class and embed pages in a scrollable to avoid ugly rendering when the pane gets small
        self.sidebar.set_scrollable(True)

##        self.hpane_ext.add1(self.browser_nb)
##        self.hpane_ext.add2(self.iv)
##        self.hpane_ext.show()

        ##self.browser.show() #don't show the browser by default (it will be shown when a collection is activated)
        self.browser_box=gtk.VBox()
        self.browser_box.pack_start(self.browser_nb,True)
        self.browser_box.pack_start(self.status_bar,False)
        self.browser_box.show()

        self.hpane.add1(self.sidebar)
        self.hpane.add2(self.browser_box)
        self.hpane.show()
        self.hpane_ext.set_position(150)#self.browser.geo_thumbwidth+2*self.browser.geo_pad

        self.pack_start(self.toolbar1,False,False)
        self.pack_start(self.hpane)
        self.pack_start(self.info_bar,False)

        self.connect("destroy", self.destroy)
        self.plugmgr.init_plugins(self)

        if len(settings.layout)>0:
            self.set_layout(settings.layout)
        self.do_nothing_at_startup=False
        if not self.toplevel_window_max:
            self.toplevel_window_max = False
        if not self.toplevel_window_state:
            self.toplevel_window_state = (640, 400, 0, 0)

        dbusserver.start()
        self.tm.start()

        self.browser_nb.connect("switch-page",self.browser_page_switch)
        self.browser_nb.connect("page-reordered",self.browser_page_reorder)

        self.show_sig_id=self.sort_toggle.connect_after("realize",self.on_show) ##this is a bit of a hack to ensure the main window shows before a collection is activated or the user is prompted to create a new one

    def on_show(self,widget):
        self.sort_toggle.disconnect(self.show_sig_id)
        ##open last used collection or
        ##todo: device or directory specified at command line.
#        self.open_uri('file:///home/damien/Pictures/dining_after.jpg')
        ##only open something if a collection is not already open
        if self.do_nothing_at_startup:
            return
        for c in self.coll_set:
            if c.is_open:
                return
        id=None
        if settings.active_collection_id:
            c=self.coll_set[settings.active_collection_id]
            if c!=None:
                id=c.id
        if id:
            self.collection_open(c.id)

    def activate_starttab(self,button):
        pass #todo: look for the starttab in the browser notebook. if not found, add it.

    def destroy(self,event):
        for coll in self.coll_set:
            if coll.is_open:
                sj=backend.SaveCollectionJob(self.tm,coll,self)
                sj.priority=1050
                self.tm.queue_job_instance(sj)
        try:
            settings.layout=self.get_layout()
            settings.save()
        except:
            print 'Error saving settings'
            import sys,traceback
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print tb_text
        self.tm.quit()
        pluginmanager.mgr.callback('plugin_shutdown',True)
        return False

    def add_browser(self,collection):
        c=collection
        c.browser=browser.ImageBrowser(self.hover_cmds) ##todo: create thread manager here and assign to the browser
        c.browser.tm=self.tm
        c.browser.active_collection=c
        c.browser.active_view=c.get_active_view()
        c.browser.connect("activate-item",self.activate_item)
        c.browser.connect("context-click-item",self.popup_item)
        c.browser.connect("status-updated",self.update_status)
        c.browser.connect("view-changed",self.view_changed)
        c.browser.connect("collection-online-state",self.update_connection_state)
##        self.browser.connect("view-rebuild-complete",self.view_rebuild_complete)

        c.browser.add_events(gtk.gdk.KEY_PRESS_MASK)
        c.browser.add_events(gtk.gdk.KEY_RELEASE_MASK)
        c.browser.connect("key-press-event",self.key_press_signal,c.browser)
        c.browser.connect("key-release-event",self.key_press_signal,c.browser)
        c.browser.show_all()

        browser_signals=['activate-item','context-click-item','view-changed',
            'view-rebuild-complete','status-updated','tag-row-dropped','uris-dropped']

        for sig in browser_signals:
            c.browser.connect(sig,self.browser_signal_notify,sig)

        tab_label=gtk.HBox()
        tab_label.set_spacing(5)
        tab_label.pack_start(gtk.image_new_from_pixbuf(c.pixbuf),False,False)
        tab_label.pack_start(gtk.Label(c.name),False,False)
        cbut=gtk.Button()
        cbut.set_name("tab-close-button")
        cbut.set_relief(gtk.RELIEF_NONE)
        cbut.set_image(gtk.image_new_from_stock(gtk.STOCK_CLOSE,gtk.ICON_SIZE_MENU))
        cbut.connect("clicked",self.collection_close,c.browser)
        tab_label.pack_start(cbut,False,False)
        tab_label.show_all()
        self.browser_nb.insert_page(c.browser,tab_label,self.browser_nb.get_n_pages()-1)
        self.browser_nb.set_current_page(self.browser_nb.page_num(c.browser))
        if self.browser_nb.get_n_pages()>1:
            self.browser_nb.set_show_tabs(True)
        self.browser_nb.set_tab_reorderable(c.browser,True)
        return c.browser

    def browser_signal_notify(self,*args):
        self.emit(args[-1],*args[:-1])

    def open_uri(self,uri):
        print 'Received external request to open',uri
        self.get_toplevel().deiconify()
        self.do_nothing_at_startup=True
        impath=io.get_path_from_uri(uri)
        if not os.path.exists(impath):
            return
        mimetype=io.get_mime_type(impath)
        prefs={}
        if mimetype.startswith('image'):
            path=os.path.split(impath)[0]
            prefs['path_to_open']=impath
            prefs['mainframe']=self
        else:
            path=impath
        prefs['type']='LOCALDIR'
        prefs['image_dirs']=[path]
        prefs['recursive']=False
        self.coll_set.add_directory(path,prefs)
        self.collection_open(path)

    def browse_dir_as_collection(self,combo):
        #prompt for path
        old_id=''
        if self.active_collection is not None:
            old_id=self.active_collection.id
        dialog=dialogs.NewCollectionDialog(type='LOCALDIR',title='Browse A Directory',button_label='Browse')
        response=dialog.run()
        prefs=dialog.get_values()
        dialog.destroy()
        if response==gtk.RESPONSE_ACCEPT:
            c=self.coll_set.new_collection(prefs)
            if c==False:
                print 'Create localdir failed'
                return False
            self.collection_open(c.id)

    def create_new_collection(self,combo,first_start=False):
        old_id=''
        if self.active_collection is not None:
            old_id=self.active_collection.id
        dialog=dialogs.NewCollectionDialog()
        response=dialog.run()
        prefs=dialog.get_values()
        dialog.destroy()
        if response==gtk.RESPONSE_ACCEPT:
            c=self.coll_set.new_collection(prefs)
            if c!=False:
                self.collection_open(c.id)
            else:
                dialogs.prompt_dialog("Error Creating Collection","The collection could not be created",["_Close"])


    def collections_init(self):
        ##now fill the collection manager with
        ##1/ localstore collections
        self.coll_set.init_localstores()
        ##2/ mounted devices
        mi=self.volume_monitor.get_mount_info()
        self.coll_set.init_mounts(mi)
        ##3/ local directory if specified as a command line args
        ##set and open active collection (by default the last used localstore, otherwise

    def browser_page_reorder(self,notebook,page,page_num):
        if page_num==self.browser_nb.get_n_pages()-1:
            self.browser_nb.reorder_child(page,page_num-1)

    def browser_page_switch(self,notebook,page,page_num):
        print 'SWITCH',page_num,self.browser_nb.get_current_page()
        id=None
        if page_num>=0:
            page=self.browser_nb.get_nth_page(page_num)
            if page==self.startpage:
                id=None
            else:
                id=page.active_collection.id

        curpagenum=self.browser_nb.get_current_page()
        curpage=self.browser_nb.get_nth_page(curpagenum)
        if page_num!=curpagenum:
            if curpage!=self.startpage:
                curpage.remove_viewer(self.iv)
            if page!=self.startpage:
                page.add_viewer(self.iv)


        if id is None:
            self.active_collection=None
            self.tm.set_active_collection(None)
            self.filter_entry.set_text('')
            self.sort_order.set_active(-1)
            self.sort_toggle.set_active(False)
            self.update_widget_states()
            return

        coll=self.coll_set[id]
        self.active_collection=coll
        self.tm.set_active_collection(coll)

        if coll.persistent:
            settings.active_collection_id=coll.id

        self.sort_order.handler_block_by_func(self.set_sort_key)
        sort_model=self.sort_order.get_model()
        sort_model.clear()
        for s in self.active_collection.browser_sort_keys:
            self.sort_order.append_text(s)
        for i in xrange(len(sort_model)):
            if page.active_view.sort_key_text==sort_model[i][0]: ##NEED TO ADD A VIEW TO  OPEN COLLS
                self.sort_order.set_active(i)
                break
        self.sort_order.handler_unblock_by_func(self.set_sort_key)
        self.sort_toggle.handler_block_by_func(self.reverse_sort_order)
        self.sort_toggle.set_active(page.active_view.reverse)
        self.sort_toggle.handler_unblock_by_func(self.reverse_sort_order)
        self.filter_entry.entry.set_text(page.active_view.filter_text)
        self.connect_toggle.handler_block_by_func(self.connect_toggled)
        self.connect_toggle.set_active(self.active_collection.online)
        self.connect_toggle.handler_unblock_by_func(self.connect_toggled)
        self.view_changed2(page)
        self.update_widget_states()
        pluginmanager.mgr.callback('collection_activated',coll)
        page.grab_focus()

    def update_widget_states(self):
        if self.active_collection is not None:
            online=self.active_collection.online
            coll=True
        else:
            online=False
            coll=False
        self.save_button.set_sensitive(online)
        self.refresh_button.set_sensitive(online)

        self.connect_toggle.set_sensitive(coll)
        self.revert_button.set_sensitive(coll)
        self.sort_order.set_sensitive(coll)
        self.sort_toggle.set_sensitive(coll)
        self.filter_entry.set_sensitive(coll)

    def collection_rescan(self,widget):
        coll=self.active_collection
        if coll==None:
            return
        coll.rescan(self.tm)

    def collection_open(self,id):
        c=self.coll_set[id]
        if c!=None:
            if c.browser!=None:
                self.browser_nb.set_current_page(self.browser_nb.page_num(c.browser))
                return
            browser=self.add_browser(c)
            c.open(self.tm,browser)
            self.update_widget_states()

    def collection_open_cb(self,widget,id):
        self.collection_open(id)

    def collection_close_cb(self,widget,coll_id):
        c=self.coll_set[coll_id]
        if c!=None:
            if c.browser!=None:
                self.collection_close(widget,c.browser)

    def collection_delete_cb(self,widget,coll_id):
        c=self.coll_set[coll_id]
        if c!=None and c.browser==None and not c.is_open:
            del self.coll_set[coll_id]

    def collection_properties_cb(self,widget,coll_id):
        c=self.coll_set[coll_id]
        if c==None:
            return
        if c.browser!=None or c.is_open:
            return
        old_prefs=c.get_prefs().copy()
        dialog=dialogs.PrefDialog(c)
        response=dialog.run()
        prefs=dialog.get_values()
        dialog.destroy()
        if response==gtk.RESPONSE_ACCEPT:
            self.coll_set.change_prefs(c,prefs)

    def collection_context_menu(self,widget,coll_id):
        menu=gtk.Menu()
        def menu_add(menu,text,callback,*args):
            item=gtk.MenuItem(text)
            item.connect("activate",callback,*args)
            menu.append(item)
            item.show()
        c=self.coll_set[coll_id]
        if c==None:
            return
        menu_add(menu,"Open",self.collection_open_cb,coll_id)
        if c.is_open:
            menu_add(menu,"Close",self.collection_close_cb,coll_id)
        if c!=None and c.persistent and c.type!='DEVICE' and not c.is_open:
            menu_add(menu,"Delete",self.collection_delete_cb,coll_id)
        if c!=None and c.browser==None and c.pref_widget and not c.is_open:
            menu_add(menu,"Properties...",self.collection_properties_cb,coll_id)
        if len(menu.get_children())>0:
            menu.popup(parent_menu_shell=None, parent_menu_item=None, func=None, button=1, activate_time=0, data=0)

    def collection_close(self,widget,browser=None):
        if not browser:
            browser=self.active_browser()
        coll=browser.active_collection
        ind=self.browser_nb.page_num(browser)
        if ind>=0:
            cur_page_ind=self.browser_nb.get_current_page()
            self.browser_nb.remove_page(ind)
            if self.browser_nb.get_n_pages()<2:
                self.browser_nb.set_show_tabs(False)
            if cur_page_ind!=self.browser_nb.get_n_pages():
                self.browser_nb.set_current_page(0)
        if coll==None:
            return
        coll.browser=None
        browser.active_collection=None
        browser.active_view=None
        if not coll.is_open:
            return
        sj=backend.SaveCollectionJob(self.tm,coll,self)
        sj.priority=1050
        self.tm.queue_job_instance(sj)

    def mount_added(self,monitor,name,icon_names,path):
        coll=self.coll_set.add_mount(path,name,icon_names)
        self.plugmgr.callback('media_connected',coll.id)

    def mount_removed(self,monitor,name,icon_names,path):
        collection=self.coll_set[path]
        self.plugmgr.callback('media_disconnected',collection.id)
        self.coll_set.remove(path)
        if collection.is_open and collection.browser:
            self.collection_close(None,collection.browser)

    def sidebar_accel_callback(self, accel_group, acceleratable, keyval, modifier):
        self.sidebar_toggle.set_active(not self.sidebar_toggle.get_active())

    def set_layout(self,layout):
        sort_model=self.sort_order.get_model()

        for c in self.coll_set.iter_coll():
            try:
                c.get_active_view().reverse=layout['collection'][c.id]['sort direction']
                keys=c.browser_sort_keys
                so=layout['collection'][c.id]['sort order']
                if so in keys:
                    c.get_active_view().sort_key_text=so
            except KeyError:
                pass

        if layout['sidebar active']:
            self.sidebar_toggle.handler_block_by_func(self.activate_sidebar)
            self.sidebar.show()
            self.sidebar_toggle.set_active(True)
            self.sidebar_toggle.handler_unblock_by_func(self.activate_sidebar)
        for i in range(self.sidebar.get_n_pages()):
            if layout['sidebar tab']==self.sidebar.get_tab_label_text(self.sidebar.get_nth_page(i)):
                self.sidebar.set_current_page(i)
                self.hpane.set_position(layout['sidebar width'])
                break

#       Restore last window size if values exist in layout, else use defaults
        try:
            self.toplevel_window_state =  layout['toplevel_window_state']
        except:
            self.toplevel_window_state =  (640, 400, 0, 0)

        try:
            self.toplevel_window_max = layout['toplevel_window_max']
        except:
            self.toplevel_window_max = 'False'

    def get_layout(self):
        layout=dict()
        layout['toplevel_window_max'] = self.toplevel_window_max
        layout['toplevel_window_state'] = self.toplevel_window_state
        ##layout['window size']=self.window.get_size()
        ##layout['window maximized']=self.window.get_size()
#        layout['sort order']=self.sort_order.get_active_text()
#        layout['sort direction']=self.browser.active_view.reverse
        layout['collection']={}
        for c in self.coll_set.iter_coll():
            layout['collection'][c.id]={
                'sort direction':c.get_active_view().reverse,
                'sort order':c.get_active_view().sort_key_text
                }
#        layout['viewer active']=self.is_iv_showing
#        if self.is_iv_showing:
#            layout['viewer width']=self.hpane.get_position()
#            layout['viewed item']=self.iv.item.uid
        layout['sidebar active']=self.sidebar.get_property("visible")
        layout['sidebar width']=self.hpane.get_position()
        layout['sidebar tab']=self.sidebar.get_tab_label_text(self.sidebar.get_nth_page(self.sidebar.get_current_page()))
        return layout

    def activate_item(self,browser,ind,item):
        self.view_image(item)

    def open_preferences(self,widget):
        self.plugmgr.callback('app_config_dialog')


    def activate_sidebar(self,widget):
        if widget.get_active():
            self.sidebar.show()
        else:
            self.sidebar.hide()
        self.browser_focus()

    def browser_focus(self):
        if self.browser_nb.get_current_page()>=0:
            self.browser_nb.get_nth_page(self.browser_nb.get_current_page()).grab_focus()

    def active_browser(self):
        if self.browser_nb.get_current_page()>=0:
            return self.browser_nb.get_nth_page(self.browser_nb.get_current_page())
        else:
            return None


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
        self.filter_entry.entry.set_text("selected")
        self.filter_entry.entry.activate()

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
        if browser==self.active_browser():
            if browser!=None:
                self.info_bar.set_label('%i images in collection (%i selected, %i in view)'%(len(browser.active_collection),browser.active_collection.numselected,len(browser.active_view)))
            else:
                self.info_bar.set_label('No collection open')

    def view_changed2(self,browser):
        '''refresh the info bar (status bar that displays number of images etc)'''
        if browser!=None:
            self.info_bar.set_label('%i images in collection (%i selected, %i in view)'%(len(browser.active_collection),browser.active_collection.numselected,len(browser.active_view)))
        else:
            self.info_bar.set_label('No collection open')

    def select_keyword_add(self,widget):
        keyword_string=self.entry_dialog("Add Tags","Enter tags")
        if keyword_string:
            self.tm.keyword_edit(keyword_string)

    def select_keyword_remove(self,widget):
        keyword_string=self.entry_dialog("Remove Tags","Enter Tags")
        if keyword_string:
            self.tm.keyword_edit(keyword_string,False,True)

    def select_set_info(self,widget):
        item=baseobjects.Item('stub',None)
        item.meta={}
        dialog=dialogs.BatchMetaDialog(item)
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
        pass

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
        fileops.worker.copy(self.active_browser().active_view,sel_dir,self.update_status)

    def select_move(self,widget):
        sel_dir=self.dir_pick('Move Selection: Select destination folder')
        fileops.worker.move(self.active_browser().active_view,sel_dir,self.update_status)

    def select_delete(self,widget):
        fileops.worker.delete(self.active_browser().active_collection,self.active_browser().active_view,self.update_status)

    def select_reload_metadata(self,widget):
        self.tm.reload_selected_metadata()

    def select_recreate_thumb(self,widget):
        self.tm.recreate_selected_thumbs()

    def select_rotate_left(self,widget):
        self.tm.rotate_selected_thumbs(True)

    def select_rotate_right(self,widget):
        self.tm.rotate_selected_thumbs(False)

    def filter_text_changed(self,widget):
        if self.active_collection is not None:
            self.active_collection.get_active_view().filter_text=widget.get_text()

    def set_filter_text(self,widget):
        self.active_browser().grab_focus()
        key=self.sort_order.get_active_text()
        filter_text=self.filter_entry.entry.get_text()
        if self.active_collection is not None and self.active_browser().active_view!=None:# and self.browser.active_view.filter_text!=filter_text:
            self.tm.rebuild_view(key,filter_text)

    def clear_filter(self,widget,*args):
        self.filter_entry.entry.set_text('')
        self.set_filter_text(widget)

    def set_sort_key(self,widget):
        if self.active_browser() in (None,self.startpage):
            return
        self.active_browser().grab_focus()
        key=self.sort_order.get_active_text()
        filter_text=self.filter_entry.entry.get_text()
        if self.active_collection is not None and self.active_browser().active_view!=None and (self.active_browser().active_view.sort_key_text!=key):
            self.tm.rebuild_view(key,filter_text)

    def add_filter(self,widget):
        print 'add_filter',widget

    def show_filters(self,widget):
        print 'show_filters',widget

    def reverse_sort_order(self,widget):
        c=self.active_collection
        if c:
            c.get_active_view().reverse=widget.get_active()#not self.browser.active_view.reverse
            self.active_browser().resize_and_refresh_view(c)

    def update_status(self,widget,progress,message):
        self.status_bar.show()
        if 1.0>progress>=0.0:
            self.status_bar.set_fraction(progress)
        if progress<0.0:
            self.status_bar.pulse()
        if progress>=1.0:
            self.status_bar.hide()
        self.status_bar.set_text(message)

    def connect_toggled(self,widget):
        if self.active_collection is not None:
            job=backend.SetOnlineStatusJob(self.tm,self.active_collection,self.active_browser(),widget.get_active())
            self.tm.queue_job_instance(job)

    def update_connection_state(self,browser,collection,coll_state):
        if collection==self.active_collection:
            self.connect_toggle.handler_block_by_func(self.connect_toggled)
            self.connect_toggle.set_active(coll_state)
            self.connect_toggle.handler_unblock_by_func(self.connect_toggled)
            self.update_widget_states()

    def key_press_signal(self,obj,event,browser=None):
        keyname = gtk.gdk.keyval_name(event.keyval)
        print 'KEYPRESS',event.keyval,keyname
        b=self.active_browser()
        if event.type==gtk.gdk.KEY_PRESS:
            if event.keyval==65535: #del key, deletes selection
                fileops.worker.delete(self.active_browser().active_view,self.update_status)
            elif event.keyval==65307: #escape
                    if self.is_iv_fullscreen:
                        ##todo: merge with view_image/hide_image code (using extra args to control full screen stuff)
                        self.iv.ImageNormal()
                        self.view_image(self.iv.item)
                        if self.active_collection is not None:
                            self.active_browser().show()
                        self.hpane_ext.show()
                        self.toolbar1.show()
                        self.info_bar.show()
                        self.browser_nb.show()
                        if self.sidebar_toggle.get_active():
                            self.sidebar.show()
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
                self.active_browser().active_view.reverse=not self.active_browser().active_view.reverse
                self.active_browser().resize_and_refresh_view(self.active_collection)
            elif event.keyval==65293: #enter
                if self.iv.item:
                    if self.is_iv_fullscreen:
                        ##todo: merge with view_image/hide_image code (using extra args to control full screen stuff)
                        self.iv.ImageNormal()
                        if self.is_fullscreen:
                            self.window.unfullscreen()
                            self.is_fullscreen=False
                        self.view_image(self.iv.item)
                        self.hpane_ext.show()
                        self.info_bar.show()
                        self.browser_nb.show()
                        if self.sidebar_toggle.get_active():
                            self.sidebar.show()
                        self.toolbar1.show()
                        self.is_iv_fullscreen=False
                    else:
                        self.iv.ImageFullscreen()
                        self.view_image(self.iv.item)
                        self.toolbar1.hide()
                        self.info_bar.hide()
                        self.browser_nb.hide()
                        self.sidebar.hide()
                        self.is_iv_fullscreen=True
                        if not self.is_fullscreen:
                            self.window.fullscreen()
                            self.is_fullscreen=True
                self.active_browser().imarea.grab_focus() ##todo: should focus on the image viewer if in full screen and trap its key press events
            elif event.keyval==65361: #left
                if self.iv.item:
                    if self.iv.zoom_level!='fit':
                        self.iv.pan_image('left')
                        return True
                    ind=self.active_browser().item_to_view_index(self.iv.item)
                    if len(self.active_browser().active_view)>ind>0:
                        self.view_image(self.active_browser().active_view(ind-1))
            elif event.keyval==65363: #right
                if self.iv.item:
                    if self.iv.get_property("visible") and self.iv.zoom_level!='fit':
                        self.iv.pan_image('right')
                        return True
                    ind=self.active_browser().item_to_view_index(self.iv.item)
                    if len(self.active_browser().active_view)-1>ind>=0:
                        self.view_image(self.active_browser().active_view(ind+1))
            elif event.keyval==65362: #up
                if self.iv.get_property("visible") and self.iv.zoom_level!='fit':
                    self.iv.pan_image('up')
                    return True
                b.scroll('up')
            elif event.keyval==65364: #dn
                if self.iv.get_property("visible") and self.iv.zoom_level!='fit':
                    self.iv.pan_image('down')
                    return True
                b.scroll('dn')
            elif event.keyval==65365: #pgup
                b.scroll('pgup')
            elif event.keyval==65366: #pgdn
                b.scroll('pgdn')
            elif event.keyval==65360: #home
                b.scroll('home')
            elif event.keyval==65367: #end
                b.scroll('end')
            elif keyname=='plus' or keyname=='equal':
                if self.iv.get_property("visible"):
                    self.iv.set_zoom('in')
            elif keyname=='minus':
                if self.iv.get_property("visible"):
                    self.iv.set_zoom('out')
            elif keyname=='1':
                if self.iv.get_property("visible"):
                    self.iv.set_zoom(1)
            elif keyname=='0' or keyname=='asterisk':
                if self.iv.get_property("visible"):
                    self.iv.set_zoom('fit')
        return True


#    def resize_browser_pane(self):
#        w,h=self.hpane.window.get_size()
#        if self.sidebar.get_property('visible'):
#            if self.browser.geo_thumbwidth+2*self.browser.geo_pad+self.hpane_ext.get_position()>=w:
#                self.hpane.set_position(w/2)
#            else:
#                self.hpane.set_position(self.browser.geo_thumbwidth+2*self.browser.geo_pad+self.hpane_ext.get_position())
#        else:
#            if self.browser.geo_thumbwidth+2*self.browser.geo_pad>=w:
#                self.hpane.set_position(w/2)
#            else:
#                self.hpane.set_position(self.browser.geo_thumbwidth+2*self.browser.geo_pad)


    def close_viewer(self,widget,item):
        self.hide_image()

    def show_viewed_item(self,widget,item):
        b=self.active_browser()
        if b!=self.iv.browser:
            ind=self.browser_nb.page_num(self.iv.browser)
            if ind<0:
                return
            self.browser_nb.set_current_page(ind)
        b=self.iv.browser
        b.update_geometry(True)
        if self.iv.item!=None:
            ind=b.item_to_view_index(self.iv.item)
            if ind<0:
                return
            b.center_view_offset(ind)
            b.update_scrollbar()
            b.update_required_thumbs()
            b.focal_item=item
            b.resize_and_refresh_view(self.active_collection)

    def view_image(self,item,fullwindow=False):
        browser=self.active_browser()
        visible=self.iv.get_property('visible')
        self.iv.show()
        self.iv.SetItem(item,browser,self.active_collection)
        self.is_iv_showing=True
        browser.update_geometry(True)
        if not visible:
            self.resize_browser_pane()
        if self.iv.item!=None:
            ind=browser.item_to_view_index(self.iv.item)
            browser.center_view_offset(ind)
        browser.update_scrollbar()
        browser.update_required_thumbs()
        browser.resize_and_refresh_view(self.active_collection)
        browser.focal_item=item
        browser.grab_focus()

    def hide_image(self):
        browser=self.active_browser()
        self.iv.ImageNormal()
        self.iv.hide()
        self.browser_nb.show()
        self.toolbar1.show()
        if self.sidebar_toggle.get_active():
            self.sidebar.show()
        self.info_bar.show()
        self.is_iv_fullscreen=False
        if self.is_fullscreen:
            self.window.unfullscreen()
            self.is_fullscreen=False
        browser.grab_focus()

    def button_press_image_viewer(self,obj,event):
        browser=self.active_browser()
        if event.button==1 and event.type==gtk.gdk._2BUTTON_PRESS:
            self.iv.set_zoom('in',event.x,event.y)
        if event.button==2 and event.type==gtk.gdk._2BUTTON_PRESS:
            self.iv.set_zoom('out',event.x,event.y)

    def popup_item(self,browser,ind,item):
        ##todo: neeed to create a custom signal to hook into
        def menu_add(menu,text,callback,*args):
            item=gtk.MenuItem(text)
            item.connect("activate",callback,*args)
            menu.append(item)
#            item.show()
        try:
            itype=io.get_mime_type(self.active_collection.get_path(item)) ##todo: need a collection based method to handle this
        except:
            itype='unknown'
        launch_menu=gtk.Menu()
        if itype in settings.custom_launchers:
            for app in settings.custom_launchers[itype]:
                menu_add(launch_menu,app[0],self.custom_mime_open,app[1],item)
        launch_menu.append(gtk.SeparatorMenuItem())
        for app in io.app_info_get_all_for_type(itype):
            menu_add(launch_menu,app.get_name(),self.mime_open,app,io.get_uri(self.active_collection.get_path(item)))
        for app in settings.custom_launchers['default']:
            menu_add(launch_menu,app[0],self.custom_mime_open,app[1],item)

        menu=gtk.Menu()
        launch_item=gtk.MenuItem("Open with")
        launch_item.show()
        launch_item.set_submenu(launch_menu)
        menu.append(launch_item)
        if item.is_meta_changed():
            menu_add(menu,'Save Metadata Changes',self.save_item,item)
            menu_add(menu,'Revert Metadata Changes',self.revert_item,item)
        menu_add(menu,'Edit Metadata',self.edit_item,item)
        menu_add(menu,'Rotate Clockwise',self.rotate_item_right,item)
        menu_add(menu,'Rotate Anti-Clockwise',self.rotate_item_left,item)
        menu_add(menu,'Delete Image',self.delete_item,item)
        menu_add(menu,'Recreate Thumbnail',self.item_make_thumb,item)
        menu_add(menu,'Reload Metadata',self.item_reload_metadata,item)
        if browser.command_highlight_ind>=0 or not item.selected:
            menu.append(gtk.SeparatorMenuItem())
            menu_add(menu,"Select _All",self.select_all)
            menu_add(menu,"Select _None",self.select_none)
            menu_add(menu,"_Invert Selection",self.select_invert)
            menu.show_all()
            menu.popup(parent_menu_shell=None, parent_menu_item=None, func=None, button=1, activate_time=0, data=0)
            return

        rootmenu=gtk.Menu()

        launch_menu=gtk.Menu()
        for app in io.app_info_get_all_for_type(itype):
            menu_add(launch_menu,app.get_name(),self.mime_open,app,None)

        smenu=rootmenu
        launch_item=gtk.MenuItem("Open with")
        launch_item.show()
        launch_item.set_submenu(launch_menu)
        smenu.append(launch_item)

        fmenu_item=gtk.MenuItem("File Operations")
        fmenu=gtk.Menu()
        menu_add(fmenu,"_Copy...",self.select_copy)
        menu_add(fmenu,"_Move...",self.select_move)
        menu_add(fmenu,"_Delete",self.select_delete)
        fmenu_item.set_submenu(fmenu)
        rootmenu.append(fmenu_item)

        rmenu_item=gtk.MenuItem("Rotate")
        rmenu=gtk.Menu()
        menu_add(rmenu,"Anti-clockwise",self.select_rotate_left)
        menu_add(rmenu,"Clockwise",self.select_rotate_left)
        rmenu_item.set_submenu(rmenu)
        rootmenu.append(rmenu_item)

        menu_add(smenu,"Show All _Selected",self.select_show)
        menu_add(smenu,"Add _Tags",self.select_keyword_add)
        menu_add(smenu,"_Remove Tags",self.select_keyword_remove)
        menu_add(smenu,"Set Descriptive _Info",self.select_set_info)
        menu_add(smenu,"Re_load Metadata",self.select_reload_metadata)
        menu_add(smenu,"Recreate Thumb_nails",self.select_recreate_thumb)

        rootmenu.append(gtk.SeparatorMenuItem())
        menu_add(rootmenu,"Select _All",self.select_all)
        menu_add(rootmenu,"Select _None",self.select_none)
        menu_add(rootmenu,"_Invert Selection",self.select_invert)
        rootmenu.show_all()
        rootmenu.popup(parent_menu_shell=None, parent_menu_item=None, func=None, button=1, activate_time=0, data=0)

    def item_make_thumb(self,widget,item):
        self.tm.recreate_thumb(item)

    def item_reload_metadata(self,widget,item):
        self.tm.reload_metadata(item)

    def mime_open(self,widget,app_cmd,uri):
        if uri:
            app_cmd.launch_uris([uri])
        else:
            app_cmd.launch_uris([io.get_uri(self.active_collection.get_path(item))
                    for item in browser.active_view.get_selected_items()])

    def custom_mime_open(self,widget,app_cmd_template,item):
        from string import Template
        fullpath=self.active_collection.get_path(item)
        directory,fullname=os.path.split(fullpath)
        name,ext=os.path.splitext(fullname)
        app_cmd=Template(app_cmd_template).substitute(
            {'FULLPATH':fullpath,'DIR':directory,'FULLNAME':fullname,'NAME':name,'EXT':ext})
        subprocess.Popen(app_cmd,shell=True)

    def save_item(self,widget,item):
        if item.is_meta_changed()==2:
            browser=self.active_browser()
            fileops.worker.delete(browser.active_collection,[item],None,False)
            if self.is_iv_showing and self.iv.item==item:
                self.hide_image()
        elif item.is_meta_changed():
            self.active_collection.write_metadata(item)
        self.active_browser().redraw_view()

    def revert_item(self,widget,item):
        if not item.is_meta_changed():
            return
        if item.is_meta_changed()==2:
            item.delete_revert()
            self.active_browser().redraw_view()
            return
        try:
            orient=item.meta['Orientation']
        except:
            orient=None
        try:
            orient_backup=item.meta_backup['Orientation']
        except:
            orient_backup=None
        item.meta_revert(self.active_collection)
        if orient!=orient_backup:
            item.thumb=None
            self.tm.recreate_thumb(item)
        self.active_browser().redraw_view()

    def launch_item(self,widget,item):
        fullpath=self.active_collection.get_path(item)
        uri=io.get_uri(fullpath)
        mime=io.get_mime_type(fullpath)
        cmd=None
        if mime in settings.custom_launchers:
            for app in settings.custom_launchers[mime]:
                from string import Template
                fullpath=self.active_collection.get_path(item)
                directory,fullname=os.path.split(fullpath)
                name,ext=os.path.splitext(fullname)
                cmd=Template(app[1]).substitute(
                    {'FULLPATH':fullpath,'DIR':directory,'FULLNAME':fullname,'NAME':name,'EXT':ext})
                if cmd:
                    print 'Running Command:',cmd
                    subprocess.Popen(cmd,shell=True)
                    return
        app=io.app_info_get_default_for_type(mime)
        if app:
            app.launch_uris([fullpath]) ##TODO: Does this want a uri or a path (does it matter?)
        else:
            print 'Error: no known command for',item.uid,'with mimetype',mime

    def edit_item(self,widget,item):
#        dlg=dialogs.MetaDialog(item,self.active_collection)
#        dlg.show()
        if self.active_collection.metadata_widget:
            self.dlg=self.active_collection.metadata_widget(item,self.active_collection)
            self.dlg.show()

    def rotate_item_left(self,widget,item):
        ##TODO: put this task in the background thread (using the recreate thumb job)
        browser=self.active_browser()
        imagemanip.rotate_left(item,self.active_collection)
        browser.update_required_thumbs()
        if item==self.iv.item:
            self.view_image(item)

    def rotate_item_right(self,widget,item):
        ##TODO: put this task in the background thread (using the recreate thumb job)
        browser=self.active_browser()
        imagemanip.rotate_right(item,self.active_collection)
        browser.update_required_thumbs()
        if item==self.iv.item:
            self.view_image(item)

    def delete_item(self,widget,item):
        item.delete_mark()

    def zoom_item_fit(self,widget,item):
        self.iv.set_zoom('fit')
    def zoom_item_100(self,widget,item):
        self.iv.set_zoom(1)
    def zoom_item_in(self,widget,item):
        self.iv.set_zoom('in')
    def zoom_item_out(self,widget,item):
        self.iv.set_zoom('out')

gobject.type_register(MainFrame)
