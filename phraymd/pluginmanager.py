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

import pluginbase
import settings

##todo: need try/except blocks around most of this stuff

'''import user modules containing plugins'''
from plugins import *
from userplugins import * ##todo: add user plugin dir to sys.path

class PluginManager():
    '''
    PluginManager is used by the app to register plugins and notify them
    with callbacks for specific application events
    '''
    def __init__(self):
        self.plugins=dict()
    def instantiate_all_plugins(self):
        for plugin in Plugin.__subclasses__():
            self.plugins[plugin.name]=[plugin(),plugin] if settings.plugin_enabled[plugin.name] else [None,plugin]
    def enable_plugin(self,name):
        self.plugins[name][0]=self.plugins[name][1]()
    def disable_plugin(self,name):
        try:
            self.plugins[name][0].destroy()
            self.plugins[name][0]=None
        except:
            pass
    def plugin_callback(interface_name,*args):
        for name,plugin in self.plugins.iteritems():
            getattr(plugin[0],callback_name)(*args)


