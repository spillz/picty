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

##base plugin class
class Plugin(object):
    '''base plugin class
    All plugins must derive from this class
    the plugin must implement a class attribute name, which must be unique
    plugins can implement any of the callbacks below
    in the future, the callbacks may not be implemented in the base, and instead
    the manager will scan each plugin for their definition at instantiation so as
     to avoid redundant calls.

    Methods prefixed with name t are called from a worker thread.
    Do not try to interact with gtk widgets on the main thread.
    Instead call: gobject.idle_add(callback,args)

    In addition to these callbacks, plugins can into the gtk signals associated
    with the widgets in the main application.
    Each plugin receives the core application widges - use with care
    '''
    name='BASE'
    def __init__(self): ##todo: pass collection,view,browser,viewer,pluginmgr??
        pass
    '''CALLBACKS'''
    '''collection'''
    def t_collection_item_added(self,item):
        pass
    def t_collection_item_removed(self,item):
        pass
    def t_collection_item_metadata_changed(self,item):
        pass
    def t_collection_item_changed(self,item):
        pass
    def t_collection_item_added_to_view(self,item):
        pass
    def t_collection_item_removed_from_view(self,item):
        pass
    '''browser'''
    def browser_view_rebuilt(self,item)
        '''the view has finished rebuild after a filter has been applied to the collection'''
        pass
    def browser_register_shortcut(self):
        '''called by the framework to register shortcut on mouse over commands'''
        pass
    def browser_register_command(self):
        '''called by the framework to register shortcut on context (right click) menu'''
        pass
    '''viewer'''
    def viewer_register_shortcut(self):
        '''called by the framework to register shortcut on mouse over commands'''
        pass
    def viewer_register_command(self):
        '''return a tuple of commands'''
        pass
    def viewer_item_opening(self,item):
        '''image is about to be opened in the viewer, return False to prevent'''
        return True
    def viewer_item_opened(self,item):
        '''image has been opened and displayed in the viewer'''
        pass
    def viewer_item_closing(self,item):
        pass
    def viewer_item_closed(self,item):
        pass
    '''image loader'''
    def t_loader_supported_mimetypes(self):
        '''return a tuple of supported mimetypes'''
        return None
    def t_loader_open_image(self,item):
        '''return False is image cannot be created'''
        return False
    def t_loader_create_thumbnail(self,item):
        return False
    '''sidebar'''
    def sidebar_register_pane(self):
        return None

