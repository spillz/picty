'''

    picty - Web Upload (Flickr, Picasa, Facebook etc)
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


import os
import os.path
import threading

import gtk
import gobject

from picty import settings
from picty import pluginbase
from picty import imagemanip
from picty.fstools import io
from picty import metadata

import webupload_services as services



class UploadPlugin(pluginbase.Plugin):
    name='WebUpload'
    display_name='Web Upload Sidebar'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        pass

    def plugin_init(self,mainframe,app_init):
        self.mainframe=mainframe
        def vbox_group(widgets):
            box=gtk.VBox()
            for w in widgets:
                box.pack_start(*w)
            return box
        def hbox_group(widgets):
            box=gtk.HBox()
            for w in widgets:
                box.pack_start(*w)
            return box

        self.service_label=gtk.Label("Service")
        self.service_combo=gtk.combo_box_new_text()
        self.services=dict([(sclass[0], sclass) for sclass in services.services])
        for s in self.services:
            self.service_combo.append_text(s)
        self.service_combo.connect("changed",self.service_combo_changed)

        self.scrolled_window=gtk.ScrolledWindow()
        self.scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        self.viewport=gtk.Viewport()
        self.scrolled_window.add(self.viewport)

        self.dialog=self.mainframe.float_mgr.add_panel('Web Upload','Show or hide the web upload panel (use it to upload photos to web services such as flickr and picasa)','picty-web-upload')
        self.vbox=self.dialog.vbox

        self.service_box=hbox_group([(self.service_label,False),(self.service_combo,True,False)])

        self.warning_label=gtk.Label("THIS PLUGIN HAS NOT BEEN WELL TESTED - USE AT YOUR OWN RISK")

        self.vbox.pack_start(self.service_box,False)
        self.vbox.pack_start(self.scrolled_window,True)
        self.scrolled_window.add_with_viewport(self.warning_label)
        self.vbox.show_all()
#        self.mainframe.sidebar.append_page(self.vbox,gtk.Label("Web Upload"))

    def plugin_shutdown(self,app_shutdown):
        for s in self.services:
            if self.services[s][1]!=None:
                self.services[s][1].service.shutdown()
                self.services[s][1]=None
        del self.services
        if not app_shutdown:
            self.mainframe.float_mgr.remove_panel('Web Upload')
            self.vbox.destroy()
            del self.vbox

    def service_combo_changed(self,widget):
        slist=self.services[widget.get_active_text()]
        if slist[1]==None:
            import webupload_services.serviceui
            slist[1]=services.serviceui.ServiceUI(self.mainframe,slist)
        child=self.viewport.get_child()
        if child:
            self.viewport.remove(child)
        self.viewport.add(slist[1])
#        if not child:
#            self.viewport.show_all()

