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

    Methods prefixed with name t are called from a worker thread.
    Do not try to interact with gtk widgets on the main thread.
    Instead call: gobject.idle_add(callback,args)

    In addition to these callbacks, plugins can into the gtk signals associated
    with the widgets in the main application.
    Each plugin receives the core application widges - use with care
    '''
    name='BASE' ##don't localize
    def __init__(self): ##todo: pass browser,viewer,worker,pluginmgr??
        pass
    '''CALLBACKS'''
    '''collection'''
    def t_collection_item_added(self,item):
        '''item was added to the collection'''
        pass
    def t_collection_item_removed(self,item):
        '''item was removed from the collection'''
        pass
    def t_collection_item_metadata_changed(self,item):
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
    '''application'''
    def app_ready(self,mainframe):
        pass
    '''browser'''
    def browser_register_shortcut(self,shortcut_commands):
        '''
        called by the framework to register shortcut on mouse over commands
        add a tuple
        '''
        pass
    def browser_menu_command(self):
        '''called by the framework to register shortcut on context (right click) menu'''
        pass
    '''viewer'''
    def viewer_register_shortcut(self): ##
        '''called by the framework to register shortcut on mouse over commands'''
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
    '''image loader'''
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

