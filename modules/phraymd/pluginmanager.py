#!/usr/bin/python

'''

    phraymd
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


import pluginbase
import settings

##todo: need try/except blocks around most of this stuff
##todo: have to make the pluginmanager methods threadsafe (plugins member could change in thread while being accessed in another)



class PluginManager():
    '''
    PluginManager is used by the app to register plugins and notify them
    with callbacks for specific application events
    '''
    def __init__(self):
        self.plugins=dict()
        self.mainframe=None
        self.collection_suppress={}
    def instantiate_all_plugins(self):
        ##todo: check for plugin.name conflicts with existing plugins and reject plugin if already present
        print 'instantiating plugins except for',settings.plugins_disabled
        for plugin in pluginbase.Plugin.__subclasses__():
#            try:
                self.plugins[plugin.name]=[plugin(),plugin] if plugin.name not in settings.plugins_disabled else [None,plugin]
#            except:
#                print 'Error initializing plugin',plugin.name
    def enable_plugin(self,name):
        ##todo: check for plugin.name conflicts with existing plugins and reject plugin if already present
        self.plugins[name][0]=self.plugins[name][1]()
        self.plugins[name][0].plugin_init(self.mainframe,False)
        self.plugins[name][0].viewer_register_shortcut(self.mainframe.iv.hover_cmds)

    def disable_plugin(self,name):
        try:
            plugin=self.plugins[name][0]
            self.plugins[name][0]=None
            import overlaytools
            overlaytools.deregister_all_tools_for_plugin(plugin)
            plugin.plugin_shutdown(False)
        except:
            pass

    def init_plugins(self,mainframe,app_init=True):
        self.mainframe=mainframe
        self.callback('plugin_init',mainframe,app_init)
    def callback_plugin(self,plugin_name,interface_name,*args):
        '''
        for each plugin in self.plugins that defines the interface, runs the callback.
        Used in the main app for interfaces that always return None
        '''
        plugin=self.plugins[plugin_name][0]
        if plugin:
            getattr(plugin,interface_name)(*args)
    def callback(self,interface_name,*args):
        '''
        for each plugin in self.plugins that defines the interface, runs the callback.
        Used in the main app for interfaces that always return None
        '''
        for name,plugin in self.plugins.iteritems():
            if plugin[0]:
                getattr(plugin[0],interface_name)(*args)
    def callback_all_until_false(self,interface_name,*args):
        '''
        for each plugin in self.plugins that defines the interface, runs the callback.
        Will stop callbacks after the first instance that returns False
        '''
        a=True
        for name,plugin in self.plugins.iteritems():
            a=a and (plugin[0]==None or getattr(plugin[0],interface_name)(*args))
            if not a:
                break
        return a
    def callback_first(self,interface_name,*args):
        '''
        iterates over each plugin in self.plugins and runs the callback, stopping at the first
        that returns True. Used in cases where there should be exactly one handler
        '''
        for name,plugin in self.plugins.iteritems():
            if plugin[0] and getattr(plugin[0],interface_name)(*args):
                return True
        return False
    def callback_iter(self,interface_name,*args):
        '''
        for each plugin in self.plugins that defines the interface, runs the callback
        and yields the result. Used in the main app for interfaces that return useful results
        '''
        for name,plugin in self.plugins.iteritems():
            yield plugin[0] and getattr(plugin[0],callback_name)(*args)
    def suspend_collection_events(self,collection):
        try:
            self.collection_suppress[collection]+=1
        except:
            self.collection_suppress[collection]=1
            self.callback('t_collection_modify_start_hint',collection)
    def resume_collection_events(self,collection):
        try:
            self.collection_suppress[collection]-=1
        except:
            pass
        if collection in self.collection_suppress and self.collection_suppress[collection]<=0:
            del self.collection_suppress[collection]
            self.callback('t_collection_modify_complete_hint',collection)
    def callback_collection(self,interface_name,collection,*args):
#        try:
#            if self.collection_suppress[collection]>0:
#                return
#        except:
#            pass
        for name,plugin in self.plugins.iteritems():
            if plugin[0]:
                getattr(plugin[0],interface_name)(collection,*args)

mgr=PluginManager()  ##instantiate the manager (there can only be one)
