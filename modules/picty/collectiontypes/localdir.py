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

##standard imports
import bisect
import datetime
import os
import os.path
import re
import datetime
import cPickle

import gobject
import gtk

##picty imports
from picty import pluginmanager
from picty import settings
from picty import viewsupport
from picty import baseobjects
from picty import simple_parser as sp
from picty import imagemanip
from picty import io
from picty import dialogs
import localstorebin

class NewLocalDirWidget(gtk.VBox):
    def __init__(self,main_dialog,value_dict=None):
        gtk.VBox.__init__(self)
        self.main_dialog=main_dialog
        label=gtk.Label()
        label.set_markup("<b>Directory Browsing Settings</b>")
        self.pack_start(label,False)
        self.path_entry=dialogs.PathnameEntry('','Path: ','Choose a Directory',directory=True)
        self.pack_start(self.path_entry,False)
        self.recursive_button=gtk.CheckButton('Include sub-directories')
        self.recursive_button.set_active(True)
        self.path_entry.path_entry.connect("changed",self.path_changed)

        self.a_frame=gtk.Expander("Advanced Options")
        self.a_box=gtk.VBox()
        self.a_frame.add(self.a_box)
        self.load_meta_check=gtk.CheckButton("Load Metadata")
        self.load_meta_check.set_active(True)
        self.use_internal_thumbnails_check=gtk.CheckButton("Use Embedded Thumbnails if Available")
        self.use_internal_thumbnails_check.set_active(True)
        self.store_thumbnails_check=gtk.CheckButton("Store Thumbnails in Cache") #todo: need to implement in backend
        self.store_thumbnails_check.set_active(True)
        self.a_box.pack_start(self.load_meta_check,False)
        self.a_box.pack_start(self.use_internal_thumbnails_check,False)
        #self.a_box.pack_start(self.store_thumbnails_check,False) ##todo: switch this back on and implement in backend/imagemanip

        self.pack_start(self.recursive_button,False)
        self.pack_start(self.a_frame,False)

        if value_dict:
            self.set_values(value_dict)

    def activate(self):
        sensitive=len(self.name_entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename
        self.main_dialog.create_button.set_sensitive(sensitive)

    def path_changed(self,entry):
        sensitive=len(entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename
        self.main_dialog.create_button.set_sensitive(sensitive)

    def get_values(self):
        path=self.path_entry.get_path()
        return {
                'id':path,
                'name':os.path.split(path)[1],
                'image_dirs': [path],
                'recursive': self.recursive_button.get_active(),
                'load_meta':self.load_meta_check.get_active(),
                'load_embedded_thumbs':self.use_internal_thumbnails_check.get_active(),
                'load_preview_icons':self.use_internal_thumbnails_check.get_active() and not self.load_meta_check.get_active(),
                'store_thumbnails':self.store_thumbnails_check.get_active(),
                }

    def set_values(self,val_dict):
        if len(val_dict['image_dirs'])>0:
            self.path_entry.set_path(val_dict['image_dirs'][0])
        self.recursive_button.set_active(val_dict['recursive'])
        self.load_meta_check.set_active(val_dict['load_meta'])
        self.use_internal_thumbnails_check.set_active(val_dict['load_embedded_thumbs'])
        self.store_thumbnails_check.set_active(val_dict['store_thumbnails'])


class LocalDirPrefWidget(gtk.VBox):
    def __init__(self,value_dict=None):
        gtk.VBox.__init__(self)
        self.path_entry=dialogs.PathnameEntry('','Path: ','Choose a Directory',directory=True)
        self.pack_start(self.path_entry,False)
        self.recursive_button=gtk.CheckButton('Include sub-directories')
        self.recursive_button.set_active(True)
        self.path_entry.path_entry.connect("changed",self.path_changed)

        self.a_frame=gtk.Expander("Advanced Options")
        self.a_box=gtk.VBox()
        self.a_frame.add(self.a_box)
        self.load_meta_check=gtk.CheckButton("Load Metadata")
        self.load_meta_check.set_active(True)
        self.use_internal_thumbnails_check=gtk.CheckButton("Use Embedded Thumbnails if Available")
        self.use_internal_thumbnails_check.set_active(True)
        self.store_thumbnails_check=gtk.CheckButton("Store Thumbnails in Cache") #todo: need to implement in backend
        self.store_thumbnails_check.set_active(True)
        self.a_box.pack_start(self.load_meta_check,False)
        self.a_box.pack_start(self.use_internal_thumbnails_check,False)

        self.pack_start(self.recursive_button,False)
        self.pack_start(self.a_frame,False)

        self.show_all()
        self.cname=None
        self.cid=None
        if value_dict:
            self.set_values(value_dict)

    def path_changed(self,entry):
        sensitive=len(entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename

    def get_values(self):
        return {
                'name': self.cname,
                'id': self.cid,
                'image_dirs': [self.path_entry.get_path()],
                'recursive': self.recursive_button.get_active(),
                'load_meta':self.load_meta_check.get_active(),
                'load_embedded_thumbs':self.use_internal_thumbnails_check.get_active(),
                'load_preview_icons':self.use_internal_thumbnails_check.get_active() and not self.load_meta_check.get_active(),
#                'store_thumbnails':self.store_thumbnails_check.get_active(),
                }

    def set_values(self,val_dict):
        self.cname=val_dict['name']
        self.cid=val_dict['id']
        if len(val_dict['image_dirs'])>0:
            self.path_entry.set_path(val_dict['image_dirs'][0])
        self.recursive_button.set_active(val_dict['recursive'])
        self.load_meta_check.set_active(val_dict['load_meta'])
        self.use_internal_thumbnails_check.set_active(val_dict['load_embedded_thumbs'])
#        self.store_thumbnails_check.set_active(val_dict['store_thumbnails'])



class LocalDir(localstorebin.Collection):
    '''defines a sorted collection of Items with
    callbacks to plugins when the contents of the collection change'''
    ##todo: do more plugin callbacks here instead of the job classes?
    type='LOCALDIR'
    type_descr='Local Directory'
    pref_widget=LocalDirPrefWidget
    add_widget=NewLocalDirWidget
    user_creatable=False
    persistent=False
    pref_items=baseobjects.CollectionBase.pref_items+('image_dirs','recursive','verify_after_walk','load_meta','load_embedded_thumbs',
                'load_preview_icons','trash_location','thumbnail_cache','monitor_image_dirs','store_thumbs_with_images','use_sidecars')
    def __init__(self,prefs): #todo: store base path for the collection
        ##runtime attributes
        baseobjects.CollectionBase.__init__(self)
#        ##the collection consists of an array of entries for images, which are cached in the collection file
        self.items=[] #the image/video items

        ##and has the following properties (which are stored in the collection file if it exists)
        self.image_dirs=[]
        self.recursive=True
        self.verify_after_walk=False
        self.load_meta=True #image will be loaded into the collection and view without metadata
        self.load_embedded_thumbs=True #only relevant if load_metadata is true
        self.load_preview_icons=False #only relevant if load_metadata is false
        self.trash_location='OPEN-DESKTOP' #none defaults to <collection dir>/.trash
        self.thumbnail_cache=None #use gnome/freedesktop or put in the image folder
        self.monitor_image_dirs=True
        self.rescan_at_open=True
        self.store_thumbs_with_images=False
        self.online=True
        self.use_sidecars=True

        ## the collection optionally has a filesystem monitor and views (i.e. subsets) of the collection of images
        self.monitor=None
        self.monitor_master_callback=None
        self.browser=None

        if prefs:
            self.set_prefs(prefs)

        self.path_to_open=prefs['path_to_open'] if 'path_to_open' in prefs else None
        self.mainframe=prefs['mainframe'] if 'mainframe' in prefs else None

    def create_store(self):
        return True

    def _open(self):
        return True

    def delete_store(self):
        return True



class Device(LocalDir):
    type='DEVICE'
    type_descr='Device'
    pref_widget=LocalDirPrefWidget
    add_widget=None
    def __init__(self,prefs):
        LocalDir.__init__(self,prefs)
        self.pixbuf=prefs['pixbuf'] #device pixbuf varies depending on the device
        self.monitor_image_dirs=False
    def _open(self):
        return True
#    def start_monitor(self,callback):
#        if self.monitor_image_dirs:
#            self.monitor_master_callback=callback
#            self.monitor=monitor.Monitor(self.image_dirs,self.recursive,self.monitor_callback)

baseobjects.register_collection('LOCALDIR',LocalDir)
baseobjects.register_collection('DEVICE',Device)
