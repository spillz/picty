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
import dbusserver
import collectionmanager


##todo: don't want these dependencies here, should all be in backend and done in the worker
import imagemanip
import imageinfo
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
        self.lock=threading.Lock()
        self.hover_cmds=overlaytools.OverlayGroup(self,gtk.ICON_SIZE_MENU)
        self.volume_monitor=io.VolumeMonitor()
        self.volume_monitor.connect_after("mount-added",self.mount_added)
        self.volume_monitor.connect_after("mount-removed",self.mount_removed)
        self.coll_set=collectionmanager.CollectionSet()
        self.active_collection=None
        self.collections_init()

        print 'SETTING RC STRING'
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
        print 'SET RC STRING'

        ##plugin-todo: instantiate plugins
        self.plugmgr=pluginmanager.mgr
        self.plugmgr.instantiate_all_plugins()

        ##todo: register the right click menu options (a tuple)
        ##todo: this has to be registered after instantiation of browser.
        def show_on_hover(item,hover):
            return hover
        tools=[
                        ##callback action,callback to test whether to show item,bool to determine if render always or only on hover,Icon
                        ('Save',self.save_item,lambda item,hover:item.meta_changed,gtk.STOCK_SAVE,'Main','Save changes to the metadata in this image'),
                        ('Revert',self.revert_item,lambda item,hover:hover and item.meta_changed,gtk.STOCK_REVERT_TO_SAVED,'Main','Revert changes to the metadata in this image'),
                        ('Launch',self.launch_item,show_on_hover,gtk.STOCK_EXECUTE,'Main','Open with the default editor (well...  GIMP)'),
                        ('Edit Metadata',self.edit_item,show_on_hover,gtk.STOCK_EDIT,'Main','Edit the descriptive metadata for this image'),
                        ('Rotate Left',self.rotate_item_left,show_on_hover,'phraymd-rotate-left','Main','Rotate the image 90 degrees counter-clockwise'),
                        ('Rotate Right',self.rotate_item_right,show_on_hover,'phraymd-rotate-right','Main','Rotate the image 90 degrees clockwise'),
                        ('Delete',self.delete_item,show_on_hover,gtk.STOCK_DELETE,'Main','Move this image to the collection trash folder')
                        ]
        for tool in tools:
            self.hover_cmds.register_tool(*tool)
        self.plugmgr.callback('browser_register_shortcut',self.hover_cmds)

        self.viewer_hover_cmds=overlaytools.OverlayGroup(self,gtk.ICON_SIZE_LARGE_TOOLBAR)
        viewer_tools=[
                        ##callback action,callback to test whether to show item,bool to determine if render always or only on hover,Icon
                        ('Close',self.close_viewer,show_on_hover,gtk.STOCK_CLOSE,'Main','Hides the image viewer'),
                        ('Locate in Browser',self.show_viewed_item,show_on_hover,gtk.STOCK_HOME,'Main','Locate the image in the browser'),
                        ('Save',self.save_item,lambda item,hover:item.meta_changed,gtk.STOCK_SAVE,'Main','Save changes to the metadata in this image'),
                        ('Revert',self.revert_item,lambda item,hover:hover and item.meta_changed,gtk.STOCK_REVERT_TO_SAVED,'Main','Revert changes to the metadata in this image'),
                        ('Launch',self.launch_item,show_on_hover,gtk.STOCK_EXECUTE,'Main','Open with the default editor (well...  GIMP)'),
                        ('Edit Metadata',self.edit_item,show_on_hover,gtk.STOCK_EDIT,'Main','Edit the descriptive metadata for this image'),
                        ('Rotate Left',self.rotate_item_left,show_on_hover,'phraymd-rotate-left','Main','Rotate the image 90 degrees counter-clockwise'),
                        ('Rotate Right',self.rotate_item_right,show_on_hover,'phraymd-rotate-right','Main','Rotate the image 90 degrees clockwise'),
                        ('Delete',self.delete_item,show_on_hover,gtk.STOCK_DELETE,'Main','Move this image to the collection trash folder')
                        ]
        for tool in viewer_tools:
            self.viewer_hover_cmds.register_tool(*tool)
        self.plugmgr.callback('viewer_register_shortcut',self.viewer_hover_cmds)

        self.browser_nb=gtk.Notebook()
        self.browser_nb.set_show_tabs(False)
        self.browser_nb.show()

        self.startpage=collectionmanager.CollectionStartPage(self.coll_set)
        self.startpage.connect("collection-open",self.collection_open_cb)
        self.startpage.connect("collection-new",self.create_local_store)
        self.startpage.connect("collection-context-menu",self.collection_context_menu)
        self.startpage.connect("folder-open",self.browse_dir_collection)

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
        self.filter_entry.connect("changed",self.filter_text_changed)
        self.filter_entry.show()


        try:
            self.filter_entry.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY,gtk.STOCK_CLEAR)
            self.filter_entry.connect("icon-press",self.clear_filter)
            entry_no_icons=False
        except:
            print 'ERROR SETTING FILTER ENTRY'
            import sys,traceback
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print tb_text
            entry_no_icons=True
        #self.filter_entry.set_width_chars(40)

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

#        self.sidebar_menu_button=gtk.ToggleButton('Side_bar')
#        self.sidebar_menu_button.connect("clicked",self.activate_sidebar)
#        self.sidebar_menu_button.show()

        self.toolbar1=gtk.Toolbar()
        def add_item(toolbar,widget,callback,label=None,tooltip=None,expand=False):
            toolbar.add(widget)
            if callback:
                widget.connect("clicked", callback)
            if tooltip:
                widget.set_tooltip_text(tooltip)
            if label:
                widget.set_label(label)
            if expand:
                widget.set_expand(True)
        def add_widget(toolbar,widget,callback,label=None,tooltip=None,expand=False):
            item=gtk.ToolItem()
            item.add(widget)
            toolbar.add(item)
            if callback:
                widget.connect("clicked", callback)
            if tooltip:
                widget.set_tooltip_text(tooltip)
            if label:
                item.set_label(label)
            if expand:
                item.set_expand(True)
        def set_item(widget,callback,label,tooltip):
            if callback:
                widget.connect("clicked", callback)
            if tooltip:
                widget.set_tooltip_text(tooltip)
            if label:
                widget.set_label(label)
            return widget
        def add_frame(toolbar,label,items,expand=False):
            item=gtk.ToolItem()
            frame=gtk.Frame(label)
            box=gtk.HBox()
            item.add(frame)
            frame.add(box)
            for i in items:
                if len(i)==5:
                    box.pack_start(set_item(*i[:4]),i[4])
                else:
                    box.pack_start(set_item(*i))
            toolbar.add(item)
            if expand:
                item.set_expand(True)
#            add_widget(self.toolbar,gtk.Label("Sidebar: "),None,None,None)
        self.sidebar_toggle=gtk.ToggleToolButton('phraymd-sidebar')
        add_item(self.toolbar1,self.sidebar_toggle,self.activate_sidebar,"Sidebar","Toggle the Sidebar")
#        add_item(self.toolbar1,gtk.ToolButton(gtk.STOCK_OPEN),self.activate_starttab,"Open Collection","Open a photo collection")
        add_item(self.toolbar1,gtk.ToolButton(gtk.STOCK_PREFERENCES),self.open_preferences,"Preferences","Open the global settings and configuration dialog")
        self.toolbar1.add(gtk.SeparatorToolItem())
#            add_widget(self.toolbar,gtk.Label("Changes: "),None,None,None)
        add_item(self.toolbar1,gtk.ToolButton(gtk.STOCK_SAVE),self.save_all_changes,"Save Changes", "Saves all changes to metadata for images in the current view (description, tags, image orientation etc)")
        add_item(self.toolbar1,gtk.ToolButton(gtk.STOCK_UNDO),self.revert_all_changes,"Revert Changes", "Reverts all unsaved changes to metadata for all images in the current view (description, tags, image orientation etc)") ##STOCK_REVERT_TO_SAVED
        self.toolbar1.add(gtk.SeparatorToolItem())
        add_widget(self.toolbar1,gtk.Label("Search: "),None,None,None)
        if entry_no_icons:
            add_widget(self.toolbar1,self.filter_entry,None,None, "Enter keywords or an expression to restrict the view to images in the collection that match the expression",True)
            add_item(self.toolbar1,gtk.ToolButton(gtk.STOCK_CLEAR),self.clear_filter,None, "Reset the filter and display all images in collection",False)
        else:
            add_widget(self.toolbar1,self.filter_entry,None,None, "Enter keywords or an expression to restrict the view to images in that collection the match the expression")
        self.toolbar1.add(gtk.SeparatorToolItem())
        add_widget(self.toolbar1,gtk.Label("Sort: "),None,None,None)
        add_widget(self.toolbar1,self.sort_order,None,None,"Set the image attribute that determines the order images appear in")
        self.sort_toggle=gtk.ToggleToolButton(gtk.STOCK_SORT_ASCENDING)
        add_item(self.toolbar1,self.sort_toggle,self.reverse_sort_order,"Reverse Sort Order", "Reverse the order that images appear in")

        self.toolbar1.show_all()

##        insert_item(self.toolbar,gtk.ToolButton(gtk.STOCK_SAVE),self.save_all_changes,0,"Save Changes", "Saves all changes to metadata for images in the current view (description, tags, image orientation etc)")
##        insert_item(self.toolbar,gtk.ToolButton(gtk.STOCK_REVERT_TO_SAVED),self.revert_all_changes,1,"Revert Changes", "Reverts all unsaved changes to metadata for all images in the current view (description, tags, image orientation etc)")
##        insert_item(self.toolbar,gtk.SeparatorToolItem(),None,2,None,None)
##        insert_item(self.toolbar,gtk.ToggleToolButton(gtk.STOCK_LEAVE_FULLSCREEN),self.activate_sidebar,3,None,"Toggle the Sidebar")
##        insert_item(self.toolbar,gtk.SeparatorToolItem(),None,4)
##        item=gtk.ToolItem()
##        item.add(self.sort_order)
##        insert_item(self.toolbar,item,None,5,None, "Set the image attribute that determines the order images appear in")
##        insert_item(self.toolbar,gtk.ToggleToolButton(gtk.STOCK_SORT_ASCENDING),self.reverse_sort_order,6,"Reverse Sort Order", "Reverse the order that images appear in")
##        insert_item(self.toolbar,gtk.SeparatorToolItem(),None,7)
##        item=gtk.ToolItem()
##        item.add(self.filter_entry)
##        insert_item(self.toolbar,item,None,8,None,"Filter the view to images that contain the search text, press enter to activate")
##        insert_item(self.toolbar,gtk.ToolButton(gtk.STOCK_CLEAR),self.clear_filter,9,"Clear Filter","Clear the filter and reset the view to the entire collection")

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

        self.hpane_ext.add1(self.browser_nb)
        self.hpane_ext.add2(self.iv)
        self.hpane_ext.show()

        ##self.browser.show() #don't show the browser by default (it will be shown when a collection is activated)
        self.browser_box=gtk.VBox()
        self.browser_box.show()
        self.browser_box.pack_start(self.hpane_ext,True)
        self.browser_box.pack_start(self.status_bar,False)

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

        dbusserver.start()
        self.tm.start()

        self.browser_nb.connect("switch-page",self.browser_page_switch)
        self.browser_nb.connect("page-reordered",self.browser_page_reorder)

        self.show_sig_id=self.sort_toggle.connect_after("realize",self.on_show) ##this is a bit of a hack to ensure the main window shows before a collection is activated or the user is prompted to create a new one

    def on_show(self,widget):
        self.sort_toggle.disconnect(self.show_sig_id)
        ##open last used collection or
        ##todo: device or directory specified at command line.
        id=None
        if settings.active_collection_file:
            c=self.coll_set[settings.active_collection_file]
            if c!=None:
                id=c.id
        if not id:
            self.create_local_store(None,True)
        else:
            print 'opening collection',id
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
        self.tm.quit()
        pluginmanager.mgr.callback('plugin_shutdown',True)
        print 'main frame destroyed'
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

    def browse_dir_collection(self,combo):
        #prompt for path
        old_id=''
        if self.active_collection:
            old_id=self.active_collection.id
        dialog=dialogs.BrowseDirectoryDialog()
        response=dialog.run()
        prefs=dialog.get_values()
        dialog.destroy()
        if response==gtk.RESPONSE_ACCEPT:
            path=prefs['image_dirs'][0]
            self.coll_set.add_directory(path,prefs)
            self.collection_open(path)

    def create_local_store(self,combo,first_start=False):
        #prompt name and path
        old_id=''
        if self.active_collection:
            old_id=self.active_collection.id
        dialog=dialogs.AddLocalStoreDialog()
        if first_start:
            prefs=dialog.get_values()
            prefs['name']='main'
            prefs['image_dirs']=os.path.join(os.environ['$HOME'],'Pictures')
            dialog.set_values(prefs)
        response=dialog.run()
        prefs=dialog.get_values()
        dialog.destroy()
        if response==gtk.RESPONSE_ACCEPT:
            name=prefs['name']
            image_dir=prefs['image_dirs'][0]
            if len(name)>0 and len(image_dir)>0:
                if imageinfo.create_empty_file(name,prefs):
                    c=self.coll_set.add_localstore(name)
                    self.collection_open(c.id)
                    return
                dialogs.prompt_dialog("Error Creating Collection","The collection could not be created, you must use a valid filename",["_Close"])

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
        id=None
        if page_num>=0:
            page=self.browser_nb.get_nth_page(page_num)
            if page==self.startpage:
                id=None
            else:
                id=page.active_collection.id

        if not id:
            self.active_collection=None
            self.tm.set_active_collection(None)
            self.filter_entry.set_text('')
            self.sort_order.set_active(-1)
            self.sort_toggle.set_active(False)
            return

        coll=self.coll_set[id]
        self.active_collection=coll
        self.tm.set_active_collection(coll)

        if coll.filename:
            settings.active_collection_file=coll.filename
#        ind=self.browser_nb.get_current_page()
#        need_ind=self.browser_nb.page_num(coll.browser)
#        if ind!=need_ind:
#            self.browser_nb.set_current_page(need_ind)

        sort_model=self.sort_order.get_model()
        for i in xrange(len(sort_model)):
            if page.active_view.sort_key_text==sort_model[i][0]:
                self.sort_order.handler_block_by_func(self.set_sort_key)
                self.sort_order.set_active(i)
                self.sort_order.handler_unblock_by_func(self.set_sort_key)
                break
        self.sort_toggle.handler_block_by_func(self.reverse_sort_order)
        self.sort_toggle.set_active(page.active_view.reverse)
        self.sort_toggle.handler_unblock_by_func(self.reverse_sort_order)
        self.filter_entry.set_text(page.active_view.filter_text)
        self.view_changed2(page)

        pluginmanager.mgr.callback('collection_activated',coll)
        page.grab_focus()


    def collection_open(self,id):
        c=self.coll_set[id]
        if c!=None:
            if c.browser!=None:
                self.browser_nb.set_current_page(self.browser_nb.page_num(c.browser))
                return
            browser=self.add_browser(c)
            j=backend.LoadCollectionJob(self.tm,c,browser)
            self.tm.queue_job_instance(j)

#    def collection_changed(self,widget,id):
#        if id==None:
#            ##add start page if not already persent
#            page=self.startpage
#            num=self.browser_nb.page_num(page)
#            if num<0:
#                self.browser_nb.append_page(page)
#        else:
#            coll=self.coll_set[id]
#            if coll!=None:
#                page=coll.browser
#            else:
#                print 'ERROR! unknown collection with id',id
#                return
#            if page==None:
#                self.add_browser(coll)
#                self.tm.load_collection(coll)
#        self.browser_nb.set_current_page(self.browser_nb.page_num(page))

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
        if c!=None:
            dialog=dialogs.PrefDialog(c.get_prefs())
            response=dialog.run()
            prefs=dialog.get_values()
            dialog.destroy()
            if response==gtk.RESPONSE_ACCEPT:
                print 'PREFERENCE DIALOG: made some changes'

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
        if c!=None and c.type=="LOCALSTORE" and not c.is_open:
            menu_add(menu,"Delete",self.collection_delete_cb,coll_id)
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
        self.coll_set.remove(path)
        print 'removed',collection,collection.filename
        if collection.is_open:
            sj=backend.SaveCollectionJob(self.tm,collection,self)
            sj.priority=1050
            self.tm.queue_job_instance(sj)
        self.plugmgr.callback('media_disconnected',collection.id)

    def sidebar_accel_callback(self, accel_group, acceleratable, keyval, modifier):
        self.sidebar_toggle.set_active(not self.sidebar_toggle.get_active())

    def set_layout(self,layout):
        sort_model=self.sort_order.get_model()

        for c in self.coll_set.iter_coll():
            try:
                c.get_active_view().reverse=layout['collection'][c.id]['sort direction']
                for i in range(len(sort_model)):
                    if layout['collection'][c.id]['sort order']==sort_model[i][0]:
                        c.get_active_view().sort_key_text=sort_model[i][0]
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
                self.hpane_ext.set_position(layout['sidebar width'])
                break

    def get_layout(self):
        layout=dict()
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
#            layout['viewed item']=self.iv.item.filename
        layout['sidebar active']=self.sidebar.get_property("visible")
        layout['sidebar width']=self.hpane_ext.get_position()
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
        item=imageinfo.Item('stub',None)
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
        if self.active_collection!=None:
            self.active_collection.get_active_view().filter_text=self.filter_entry.get_text()

    def set_filter_text(self,widget):
        self.active_browser().grab_focus()
        key=self.sort_order.get_active_text()
        filter_text=self.filter_entry.get_text()
        if self.active_collection!=None and self.active_browser().active_view!=None:# and self.browser.active_view.filter_text!=filter_text:
            self.tm.rebuild_view(key,filter_text)

    def clear_filter(self,widget,*args):
        self.filter_entry.set_text('')
        self.set_filter_text(widget)

    def set_sort_key(self,widget):
        if self.active_browser() in (None,self.startpage):
            return
        self.active_browser().grab_focus()
        key=self.sort_order.get_active_text()
        filter_text=self.filter_entry.get_text()
        if self.active_collection!=None and self.active_browser().active_view!=None and (self.active_browser().active_view.sort_key_text!=key):
            self.tm.rebuild_view(key,filter_text)

    def add_filter(self,widget):
        print 'add_filter',widget

    def show_filters(self,widget):
        print 'show_filters',widget

    def reverse_sort_order(self,widget):
        c=self.active_collection
        if c:
            c.get_active_view().reverse=widget.get_active()#not self.browser.active_view.reverse
#        self.sort_toggle.handler_block_by_func(self.reverse_sort_order)
#        widget.set_active(self.browser.active_view.reverse)
#        self.sort_toggle.handler_unblock_by_func(self.reverse_sort_order)
            self.active_browser().refresh_view()

    def update_status(self,widget,progress,message):
        self.status_bar.show()
        if 1.0>progress>=0.0:
            self.status_bar.set_fraction(progress)
        if progress<0.0:
            self.status_bar.pulse()
        if progress>=1.0:
            self.status_bar.hide()
        self.status_bar.set_text(message)

    def key_press_signal(self,obj,event,browser=None):
        if event.type==gtk.gdk.KEY_PRESS:
            if event.keyval==65535: #del key, deletes selection
                fileops.worker.delete(self.active_browser().active_view,self.update_status)
            elif event.keyval==65307: #escape
                    if self.is_iv_fullscreen:
                        ##todo: merge with view_image/hide_image code (using extra args to control full screen stuff)
                        self.iv.ImageNormal()
                        self.view_image(self.iv.item)
                        if self.active_collection:
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
                self.active_browser().refresh_view()
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
                    ind=self.active_browser().item_to_view_index(self.iv.item)
                    if len(self.active_browser().active_view)>ind>0:
                        self.view_image(self.active_browser().active_view(ind-1))
            elif event.keyval==65363: #right
                if self.iv.item:
                    ind=self.active_browser().item_to_view_index(self.iv.item)
                    if len(self.active_browser().active_view)-1>ind>=0:
                        self.view_image(self.active_browser().active_view(ind+1))
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

    def resize_browser_pane(self):
        w,h=self.hpane_ext.window.get_size()
        if self.active_browser().geo_thumbwidth+2*self.active_browser().geo_pad>=w:
            self.hpane_ext.set_position(w/2)
        else:
            self.hpane_ext.set_position(self.active_browser().geo_thumbwidth+2*self.active_browser().geo_pad)

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
            b.refresh_view()


    def view_image(self,item,fullwindow=False):
        browser=self.active_browser()
        visible=self.iv.get_property('visible')
        self.iv.show()
        self.iv.SetItem(item,browser)
        self.is_iv_showing=True
        browser.update_geometry(True)
        if not visible:
            self.resize_browser_pane()
        if self.iv.item!=None:
            ind=browser.item_to_view_index(self.iv.item)
            browser.center_view_offset(ind)
        browser.update_scrollbar()
        browser.update_required_thumbs()
        browser.refresh_view()
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


#        self.iv.ImageNormal()
#        if self.active_collection:
#            self.active_browser().show()
#        #self.hbox.show()
#        #self.toolbar1.show()
#        self.hpane_ext.show()
#        self.info_bar.show()
#        self.is_iv_fullscreen=False
#        self.is_iv_showing=False
#        browser.grab_focus()

    def button_press_image_viewer(self,obj,event):
        browser=self.active_browser()
        if event.button==1 and event.type==gtk.gdk._2BUTTON_PRESS:
            if self.is_iv_fullscreen:
                self.iv.ImageNormal()
                self.browser_nb.show()
                self.toolbar1.show()
                if self.sidebar_toggle.get_active():
                    self.sidebar.show()
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
                self.browser_nb.hide()
                self.toolbar1.hide()
                self.sidebar.hide()
                self.info_bar.hide()
                self.is_iv_fullscreen=True
                print self.window.get_size()
            browser.imarea.grab_focus() ##todo: should focus on the image viewer if in full screen and trap its key press events

    def popup_item(self,browser,ind,item):
        ##todo: neeed to create a custom signal to hook into
        def menu_add(menu,text,callback,*args):
            item=gtk.MenuItem(text)
            item.connect("activate",callback,*args)
            menu.append(item)
#            item.show()
        itype=io.get_mime_type(item.filename)
        launch_menu=gtk.Menu()
        if itype in settings.custom_launchers:
            for app in settings.custom_launchers[itype]:
                menu_add(launch_menu,app[0],self.custom_mime_open,app[1],item)
        launch_menu.append(gtk.SeparatorMenuItem())
        for app in io.app_info_get_all_for_type(itype):
            menu_add(launch_menu,app.get_name(),self.mime_open,app,io.get_uri(item.filename))
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

        #menu_add(smenu,"_Batch Manipulation",self.select_batch)

#        smenu_item=gtk.MenuItem("Selected")
#        smenu_item.show()
#        smenu_item.set_submenu(smenu)
#        rootmenu.append(smenu_item)

#        menu_item=gtk.MenuItem("This Image")
#        menu_item.show()
#        menu_item.set_submenu(menu)
#        rootmenu.append(menu_item)

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
        print 'mime_open',app_cmd,uri
        if uri:
            app_cmd.launch_uris([uri])
        else:
            app_cmd.launch_uris([io.get_uri(item.filename) for item in browser.active_view.get_selected_items()])

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
        self.active_browser().redraw_view()

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
        self.active_browser().redraw_view()

    def launch_item(self,widget,item):
        uri=io.get_uri(item.filename)
        mime=io.get_mime_type(item.filename)
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
                if cmd:
                    print 'mime_open',cmd
                    subprocess.Popen(cmd,shell=True)
                    return
        app=io.app_info_get_default_for_type(mime)
        if app:
            app.launch_uris([item.filename])
        else:
            print 'no known command for ',item.filename,' mimetype',mime

    def edit_item(self,widget,item):
        self.dlg=dialogs.MetaDialog(item,self.active_collection)
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
        browser=self.active_browser()
        fileops.worker.delete(browser.active_collection,[item],None,False)
        ind=browser.active_view.find_item(item)
        if ind>=0:
            browser.active_view.del_item(item)
            if self.is_iv_showing:
                ind=min(ind,len(browser.active_view)-1)
                self.view_image(browser.active_view(ind))
        elif self.is_iv_showing:
            self.hide_image()
        browser.refresh_view()

gobject.type_register(MainFrame)
