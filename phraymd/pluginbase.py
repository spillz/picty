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

api_version='0.1.0' ##this is the current version of the API


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
    '''CALLBACKS'''
    '''application'''
    def plugin_init(self,mainframe,app_init):
        '''
        do your plugin initialization here
        if app_init is true, the main application gui is ready,
        but the worker thread has yet to start. (this is because the app has just started)
        if app_init is false, the app is already running
        '''
        pass
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
    '''collection'''
    def t_collection_item_added(self,item):
        '''item was added to the collection'''
        pass
    def t_collection_item_removed(self,item):
        '''item was removed from the collection'''
        pass
    def t_collection_item_metadata_changed(self,item,old_metadata):
        '''item metadata has changed'''
        pass
    def t_collection_item_changed(self,item): ##
        '''other item characteristics have changed (mtime, size etc)'''
        pass
    def t_collection_item_added_to_view(self,item):
        '''item in collection was added to view'''
        pass
    def t_collection_item_removed_from_view(self,item):
        '''item in collection was removed from view'''
        pass
    def t_collection_modify_complete_hint(self):
        '''the collection_item* methods have completed on the batch of images.
        use this to notify the gui rather than notifying the gui for every image change'''
        pass
    def t_view_emptied(self):
        '''the view has been flushed'''
        pass
    def t_collection_loaded(self):
        '''collection has loaded into main frame'''
        pass
    '''browser'''
    def browser_register_shortcut(self,shortcut_commands):
        '''
        called by the framework to register shortcut on mouse over commands
        append a tuple containing the shortcut commands
        '''
        pass
    def browser_menu_command(self):
        '''called by the framework to register shortcut on context (right click) menu'''
        pass
    '''viewer'''
    def t_viewer_sizing(self,size,zoom,item):
        '''
        viewer worker thread is about to scale the fullsize image for display in viewer. return True to prevent
        note that size is the size of the window not necessarily the size of the scaled image
        '''
        pass
    def t_viewer_sized(self,size,zoom,item):
        '''
        viewer worker thread has sized the image in item (only called if all t_viewer_sizing calls return None or False)
        note that size is the size of the window not necessarily the size of the scaled image
        '''
        pass
    def viewer_register_shortcut(self,mainframe,shortcut_commands):
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
    '''image loader''' ##TODO: implement this on the appplication side
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

