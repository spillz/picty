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

'''
photo importer
in gnome:
    all devices are mounted into the filesystem
    an import source is just a directory
    the import destination is somewhere in the collection directory
    an import operation is a copy or move from source to destination
    the most basic import just copies all supported files across to a destination in the collection directory
    option to obey directory structure of source
    option to remove images from the source
    option to copy images into a date based folder structure using exif date taken
    nameclash option: don't copy or use an alternate name
    ability to set metadata
    keep an import log -- full src and dest path of every file copied or moved + names of files ignored
    option to select images to import or import all -- use the internal browser to handle this
    a custom filter in the browser for viewing the most recent import
    dbus interface to handle user plugging in camera/device containing images (should open sidebar and make src dir the volume)
    if user browses the volume then the full scan/verify/create thumb steps are going to happen. once the users chooses which images to import we don't want to have to redo that step -- should just be able to copy the item objects across (and rename them appropriately) and reuse the thumbnails.

maybe need a gphoto alternative for non-gnome desktops
'''

import os
import os.path
import threading

import gtk
import gobject

from phraymd import metadatadialogs
from phraymd import settings
from phraymd import pluginbase
from phraymd import imageinfo
from phraymd import imagemanip
from phraymd import io
from phraymd import collections
from phraymd import metadata

import webupload_services as services



class ImportPlugin(pluginbase.Plugin):
    name='Import'
    display_name='Import Sidebar'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        pass

    def plugin_init(self,mainframe,app_init):
        self.mainframe=mainframe

        def box_add(box,widget_data,label_text):
            hbox=gtk.HBox()
            if label_text:
                label=gtk.Label(label_text)
                hbox.pack_start(label,False)
            for widget in widget_data:
                hbox.pack_start(widget[0],True)
                widget[0].connect(widget[1],widget[2])
            box.pack_start(hbox,False)
            return tuple([hbox]+[widget[0] for widget in widget_data])

        self.vbox=gtk.VBox()
        box,self.import_source_entry,self.browse_dir_button=box_add(self.vbox,
            [(gtk.Entry(),"changed",self.import_source_changed),
            (gtk.Button("..."),"clicked",self.import_source_browse_dir)],
            "Import from")
        self.mode_box,button1,button2=box_add(self.vbox,
            [(gtk.Button("Import Now"),"clicked",self.import_now),
            (gtk.Button("Browse Now"),"clicked",self.browse_now)],
            "")
        button1.set_sensitive(False)
        self.import_box,button1,button2=box_add(self.vbox,
            [(gtk.Button("Cancel"),"clicked",self.cancel_import),
            (gtk.Button("Import Selected"),"clicked",self.start_import)],
            "")
        button2.set_sensitive(False)

        self.scrolled_window=gtk.ScrolledWindow() ##use a custom Notebook to embed all pages in a scrolled window automatically
        self.scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        self.scrolled_window.add_with_viewport(self.vbox)
        self.scrolled_window.show_all()
        self.import_box.hide()

        self.collection_copy=None
        self.view_copy=None
        self.mainframe.sidebar.append_page(self.scrolled_window,gtk.Label("Import"))

    def plugin_shutdown(self,app_shutdown):
        if not app_shutdown:
            self.scrolled_window.destroy()
            ##todo: delete references to widgets
        else:
            if self.collection_copy!=None:
                self.restore(False)
            ##restore the collection and view files if import browse is active

    def import_now(self,button):
        pass

    def browse_now(self,button):
        ##todo: this needs to be moved to a worker job
        self.mode_box.hide()
        self.import_box.show()
        self.import_source_entry.set_editable(False)
        self.browse_dir_button.set_sensitive(False)

        collection=self.mainframe.tm.collection
        view=self.mainframe.tm.view
        self.collection_copy=collection.copy()
        self.view_copy=view.copy()
        self.mainframe.tm.monitor.stop(collection.image_dirs[0])

        collection.empty()
        collection.image_dirs=[self.import_source_entry.get_text()]
        collection.filename=''
        self.mainframe.tm.monitor.start(collection.image_dirs[0])
        del view[:]
        self.mainframe.tm.scan_and_verify()

    def cancel_import(self,button):
        self.import_source_entry.set_editable(True)
        self.browse_dir_button.set_sensitive(True)
        self.mode_box.show()
        self.import_box.hide()
        self.restore()

    def start_import(self,button):
        pass

    def restore(self,restore_monitor=True):
        collection=self.mainframe.tm.collection
        view=self.mainframe.tm.view
        self.mainframe.tm.monitor.stop(collection.image_dirs[0])
        collection.image_dirs=self.collection_copy.image_dirs
        collection.filename=self.collection_copy.filename
        collection[:]=self.collection_copy[:]
        view[:]=self.view_copy[:]
        if restore_monitor:
            self.mainframe.tm.monitor.start(collection.image_dirs[0])
        self.mainframe.browser.refresh_view()
        self.collection_copy=None
        self.view_copy=None

        ##todo:restore collection, view and monitor

    def do_import(self):
        pass
        ##for selected images
        ##copy the image record to self.collection_copy (take account of rename)
        ##copy/move each image to destination (adjusting relevant details appropriately e.g. item.filename, item.mtime)
        ##rename the thumbnail image appropriately
        ##restore collection, view and monitor

    def add_signal(self, widget):
        name=self.plugin.mainframe.entry_dialog('New Collection','Name:')
        if not name:
            return
        coll_dir=settings.user_add_dir()
        if len(coll_dir)>0:
            if imageinfo.create_empty_file(name,coll_dir):
                self.model.append((name,400))

    def import_source_changed(self,entry):
        pass

    def import_source_browse_dir(self,button):
        path=metadatadialogs.directory_dialog("Choose Import Source Directory")
        if path:
            self.import_source_entry.set_text(path)

    def media_connected(self,uri):
        sidebar=self.mainframe.sidebar
        sidebar.set_current_page(sidebar.page_num(self.scrolled_window))
        if self.collection_copy==None:
            self.import_source_entry.set_text(io.get_path_from_uri(uri))
        self.mainframe.sidebar_toggle.set_active(True)



