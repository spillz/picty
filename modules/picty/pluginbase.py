#!/usr/bin/python

'''

    picty
    Copyright (C) 2013  Damien Moore

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

api_version='0.1.0' ##this is the current version of the API
import backend

##TODO: callbacks related to changing the view or collection should also pass the view/collection

##base plugin class
class Plugin(object):
    '''base plugin class
    All plugins must derive from this class
    the plugin the following class attributes:
        * name, which must be unique
        * version, plugin API version that they were built for

    plugins can implement any of the callbacks below
    in the future, the callbacks may not be implemented in the base, and instead
    the manager will scan each plugin for their definition at instantiation, and
    add the defined callbacks to a list/dict for faster retrieval.

    Methods prefixed with name t are called from the main worker thread.
    Do not try to interact with gtk widgets on the worker thread.
    Instead call: gobject.idle_add(callback,args)

    In addition to these callbacks, plugins can connect to the gtk signals associated
    with the widgets in the main application.
    Each plugin can access all of the application widgets - use with care
    '''
    name='BASE' ##don't localize
    def __init__(self): ##todo: pass browser,viewer,worker,pluginmgr??
        '''when overriding __init__ keep in mind that the gui is NOT ready at this point.
        save gui initialization until plugin_init'''
        pass
    def run_as_job(self,task_cb,complete_cb,task_priority=900,*args):
        '''
        a simple interface for running task_cb as a background task on the worker thread
        task_cb is a callback defined as task_cb(job, item, continue_cb, *args)
        complete_cb is a callback defined as task_cb(job, item, continue_cb, *args)
        make sure task_priority is below 1000 (compare with other tasks in backend.py for an appropriate value, 900 is high)
        args will be pass to task_cb
        continue_cb is a function that returns True until the worker wants the thread to pause for another job (or to quit)
        don't use this if your task can't be broken up into chunks and needs to be guaranteed it can finish
        '''
        mainframe=self.mainframe
        j = backend.FlexibleJob(mainframe.tm,mainframe.active_collection,mainframe.active_browser(),task_cb,complete_cb,*args)
        j.priority = task_priority
        self.mainframe.tm.queue_job_instance(j)
    '''CALLBACKS'''
    '''application'''
    def plugin_init(self,mainframe,app_init):
        '''
        do your plugin initialization here
        if app_init is true, the main application gui is ready,
        but the worker thread has yet to start. (this is because the app has just started)
        if app_init is false, the app is already running
        '''
        self.mainframe = mainframe
    def plugin_job_registered(self,plugin_class):
        '''
        A plugin has been registered
        '''
        pass
    def plugin_job_deregistered(self,plugin_class):
        '''
        A plugin has been deregistered
        '''
        pass
    def plugin_shutdown(self,app_shutdown):
        '''the main app wants the plugin to shutdown. plugins must comply. If extensive processing
        is required on shutdown, use the worker thread -- the app will wait on that thread without
        blocking the gui'''
        pass
    def app_config_dialog(self):
        '''
        the user wants to configure app settings - the first plugin that can handle this event
        should show a modal dialog and return True when done
        '''
        return False
    '''collection'''
    def collection_activated(self,collection):
        '''browser has been switched to a different collection'''
        pass
    def t_collection_item_added(self,collection,item):
        '''item was added to the collection'''
        pass
    def t_collection_item_removed(self,collection,item):
        '''item was removed from the collection'''
        pass
    def t_collection_item_metadata_changed(self,collection,item,old_metadata):
        '''item metadata has changed'''
        pass
    def t_collection_item_changed(self,collection,item): ##
        '''other item characteristics have changed (mtime, size etc)'''
        pass
    def t_collection_item_added_to_view(self,collection,view,item):
        '''item in collection was added to view'''
        pass
    def t_collection_item_removed_from_view(self,collection,view,item):
        '''item in collection was removed from view'''
        pass
    def t_collection_modify_start_hint(self,collection):
        '''the collection_item* methods have started editing the batch of images.
        use this to hint to gui plugins that it should wait for the complete_hint before refreshing'''
        pass
    def t_collection_modify_complete_hint(self,collection):
        '''the collection_item* methods have completed on the batch of images.
        use this to hint to gui plugins that it is time to refresh'''
        pass
    def t_view_emptied(self,collection,view):
        '''the view has been flushed'''
        pass
    def t_view_updated(self,collection,view):
        '''the view has been updated'''
        pass
    def t_active_view_changed(self,collection,old_view,view):
        ''''the active view has been changed from old_view to new view'''
        pass
    def t_active_collection_changed(self,old_collection,collection):
        ''''the active colleciton has been changed from old_collecion to collection'''
        pass
    def t_collection_loaded(self,collection):
        '''collection has been loaded'''
        pass
    def t_collection_closed(self,collection):
        '''collection has been closed'''
        pass
    '''browser'''
    def browser_register_shortcut(self,shortcut_toolbar):
        '''
        called by the framework to register shortcut on mouse over commands
        append a tuple containing the shortcut commands
        `shortcut_toolbar` is the overlay_tools.OverlayGroup instance
        '''
        pass
    def browser_popup_menu(self,context_menu,item,selection):
        '''
        add menu items to the browser right click context menu
        `context_menu` is an instance of context_menu.ContextMenu, which has a simple interface for adding menu items
        `item` is the selected item
        `selection` is True if a multiple items have been selected, otherwise False
        '''
        pass
    def browser_menu_command(self):
        '''called by the framework to register shortcut on context (right click) menu'''
        pass
    '''viewer'''
    def t_viewer_sizing(self,size,zoom,item):
        '''
        viewer worker thread is about to scale the fullsize image for display in viewer. return True to prevent
        note that size is the the size of the scaled image and not necessarily the size of the window
        '''
        pass
    def t_viewer_sized(self,size,zoom,item):
        '''
        viewer worker thread has sized the image in item (only called if all t_viewer_sizing calls return None or False)
        note that size is the the size of the scaled image and not necessarily the size of the window
        '''
        pass
    def viewer_register_shortcut(self,shortcut_toolbar):
        '''
        called by the framework to register shortcut on mouse over commands
        append a tuple containing the shortcut commands
        '''
        pass
    def viewer_render_start(self,drawable,gc,item):
        '''
        the viewer has just cleared the view and the plugin can now draw on the drawable using the gc
        return False to prevent the viewer from drawing normally
        '''
        pass
    def viewer_render_end(self,drawable,gc,item):
        '''
        the viewer has just finished rendering the image in the viewer.
        The plugin can do additonal drawing on the drawable using the gc
        '''
        pass
    def viewer_menu_command(self): ##
        '''return a tuple of commands'''
        pass
    def viewer_item_opening(self,item): ##
        '''image is about to be opened in the viewer, return False to prevent'''
        return True
    def viewer_item_opened(self,item): ##
        '''image has been opened and displayed in the viewer'''
        pass
    def viewer_item_closing(self,item): ##
        pass
    def viewer_item_closed(self,item): ##
        pass
    def viewer_release(self,force=False): ##
        '''user has navigated away from the image -- plugin should cancel any outstanding operations'''
        pass
    '''image loader''' ##TODO: these aren't yet called on the appplication side
    def t_loader_supported_mimetypes(self): ##
        '''return a tuple of supported mimetypes'''
        return None
    def t_loader_open_image(self,item): ##
        '''
        open the image and store it in item.image
        return False if image cannot be created
        '''
        return False
    def t_loader_size_image(self,item): ##
        '''
        open the image and store it in item.image
        return False if image cannot be created
        '''
        return False
    def t_loader_create_thumbnail(self,item): ##
        '''
        plugin should create a 32bit 128x128 pixbuf thumbnail for the
        item as attribute item.thumb
        '''
        return False
    '''sidebar'''
    def sidebar_register_pane(self): ##
        '''register a panel in the sidebar -- not sure this is needed'''
        return None
    def media_connected(self,uri):
        '''a plugin that handles media connection (e.g. import) should respond to this callback'''
        pass
    def media_disconnected(self,uri):
        '''a plugin that handles media connection (e.g. import) should respond to this callback'''
        pass
    def open_uri(self,uri):
        pass
    def open_device(self,device):
        pass
