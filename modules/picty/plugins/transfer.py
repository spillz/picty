#!/usr/bin/python

'''

    picty Import plugin
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

'''
photo importer
in gnome:
    all devices are mounted into the filesystem
    an import source is a collection (typically a directory, if a device then  a directory mounted by gio gphoto interface)
    the import destination is somewhere in the destination collection directory
    an import operation is a copy or move from source to destination
    the most basic import just copies all supported files across to a destination in the collection directory
    option to obey directory structure of source
    option to remove images from the source
    option to copy images into a date based folder structure using exif date taken
    nameclash option: don't copy or use an alternate name
    option to select images to import or import all -- use the internal browser to handle this
    dbus interface to handle user plugging in camera/device containing images (open sidebar and make device the import source)
    todo:
    * ability to set metadata
    * keep an import log -- full src and dest path of every file copied or moved + names of files ignored
    * a custom filter in the browser for viewing the most recent import
    if user browses the volume then the full scan/verify/create thumb steps are going to happen. once the users chooses which images to import we don't want to have to redo that step -- should just be able to copy the item objects across (and rename them appropriately) and reuse the thumbnails.

maybe need a gphoto alternative for non-gnome desktops
'''

import os
import os.path
import threading
import tempfile
import string
import datetime
import re

import gtk
import gobject

from picty import settings
from picty import pluginbase
from picty import pluginmanager
from picty import imagemanip
from picty.fstools import io
from picty import viewsupport
from picty import metadata
from picty import backend
from picty import collectionmanager
from picty import baseobjects
from picty.uitools import dialogs
from picty.uitools import widget_builder as wb


class TransferImportJob(backend.WorkerJob):
    def __init__(self,worker,collection,browser,plugin,collection_src,collection_dest,prefs):
        backend.WorkerJob.__init__(self,'TRANSFER',780,worker,collection,browser)
        self.plugin=plugin
        self.collection_src=collection_src
        self.collection_dest=collection_dest
        self.stop=False
        self.countpos=0
        self.items=None
        self.prefs=prefs
##        self.plugin.mainframe.tm.queue_job_instance(self)

    def cancel(self,shutdown=False):
        if not shutdown:
            gobject.idle_add(self.plugin.transfer_cancelled)

    def __call__(self):
        jobs=self.worker.jobs
        worker=self.worker
        i=self.countpos
        if not self.collection_dest.is_open or not self.collection_src.is_open:
            gobject.idle_add(self.plugin.transfer_cancelled)
            return True
        collection=self.collection_dest
        if self.items==None:
            pluginmanager.mgr.suspend_collection_events(self.collection_dest)
            if self.prefs['transfer_all']:
                self.items=self.collection_src.get_all_items()
                print 'transferring all',len(self.items)
            else:
                self.items=self.collection_src.get_active_view().get_selected_items()
            self.count=len(self.items)
        print 'transferring',len(self.items),'items'
#        if not os.path.exists(self.base_dest_dir): ##TODO: move this to localstore collection (should only call once)
#            os.makedirs(self.base_dest_dir)
        while len(self.items)>0 and jobs.ishighestpriority(self) and not self.stop:
            item=self.items.pop()
            ##todo: must set prefs
            if self.browser:
                gobject.idle_add(self.browser.update_status,1.0*i/self.count,'Transferring media - %i of %i'%(i,self.count))
            prefs=self.prefs
#            prefs={
#                'move_files':self.move_files,
#                'upload_size':None,
#                'metadata_strip':False,
#            }
            collection.copy_item(self.collection_src,item,prefs)
###            if self.browser!=None:
###                self.browser.lock.acquire()
###            print 'transferring item',item.uid,'to',collection.id
###            collection.add(item)
###            if self.browser!=None:
###                self.browser.lock.release()
            ##todo: log success
            i+=1
            if self.browser:
                gobject.idle_add(self.browser.resize_and_refresh_view)
        self.countpos=i
        if len(self.items)==0 or self.stop:
            if self.browser:
                gobject.idle_add(self.browser.update_status,2,'Transfer Complete')
            gobject.idle_add(self.plugin.transfer_completed)
            pluginmanager.mgr.resume_collection_events(self.collection)
            self.collection_src=None
            self.collection_dest=None
            #jobs['VERIFYIMAGES'].setevent()
            if self.stop:
                gobject.idle_add(self.plugin.transfer_cancelled)
            else:
                gobject.idle_add(self.plugin.transfer_completed)
            return True
        return False


class TransferPlugin(pluginbase.Plugin):
    name='Transfer'
    display_name='Image Transfer'
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
                hbox.pack_start(widget[0],widget[1])
                if widget[2]:
                    widget[0].connect(*widget[2:])
            box.pack_start(hbox,False)
            return tuple([hbox]+[widget[0] for widget in widget_data])

        self.src_combo=collectionmanager.CollectionCombo(mainframe.coll_set.add_model('SELECTOR'),mainframe.coll_set)
        self.dest_combo=collectionmanager.CollectionCombo(mainframe.coll_set.add_model('OPEN_SELECTOR'),mainframe.coll_set)
        self.vbox=gtk.VBox(False,8)
        combos=wb.LabeledWidgets([
                ('src','From:',wb.HBox([('combo',self.src_combo),('view',gtk.Button("View"),False)],False,8)),
                ('dest','To:',wb.HBox([('combo',self.dest_combo),('view',gtk.Button("View"),False)],False,8)),
            ])
        self.vbox.pack_start(combos)
        self.src_combo.connect("collection-changed",self.src_changed)
        self.dest_combo.connect("collection-changed",self.dest_changed)
        combos['src']['view'].connect("clicked",self.src_view)
        combos['dest']['view'].connect("clicked",self.dest_view)

        ##TRANSFER OPTIONS
        self.transfer_box=gtk.VBox()
        self.transfer_widget=None
        self.options_boxes={} #holds a unique transfer widget for each collection ##TODO: This is a leak, should delete entries after some condtions are met (e.g. collection removed)
        self.vbox.pack_start(self.transfer_box)

        self.copy_radio=gtk.RadioButton(None,"_Copy",True)
        self.move_radio=gtk.RadioButton(self.copy_radio,"_Move",True)
        box_add(self.vbox,[(self.copy_radio,True,None),(self.move_radio,True,None)],"Transfer Operation: ")

#        self.vbox.pack_start(self.transfer_frame,False)

        self.transfer_action_box,self.cancel_button,self.start_transfer_all_button,self.start_transfer_button=box_add(self.vbox,
            [(gtk.Button("Cancel"),True,"clicked",self.cancel_transfer),
             (gtk.Button("Transfer All"),True,"clicked",self.start_transfer,True),
             (gtk.Button("Transfer Selected"),True,"clicked",self.start_transfer,False)],
            "")

        self.cancel_button.set_sensitive(False)

        self.scrolled_window=gtk.ScrolledWindow() ##todo: use a custom Notebook to embed all pages in a scrolled window automatically
        self.scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        self.scrolled_window.add_with_viewport(self.vbox)
        self.scrolled_window.show_all()

        self.dialog=self.mainframe.float_mgr.add_panel('Transfer','Show or hide the transfer panel (use it to transfer photos between collection, devices and local folders)','picty-transfer')
        self.dialog.set_default_size(450,300)
        self.dialog.vbox.pack_start(self.scrolled_window)

    def plugin_shutdown(self,app_shutdown):
        if not app_shutdown:
            self.mainframe.float_mgr.remove_panel('Transfer')
            self.scrolled_window.destroy()
            del self.transfer_job
            ##todo: delete references to widgets

    def src_view(self,button):
        id=self.src_combo.get_active()
        if id:
            self.mainframe.collection_open(id)
##        self.mainframe.grab_focus() ##todo: add mainframe method "restore_focus"

    def dest_view(self,button):
        id=self.dest_combo.get_active()
        if id:
            self.mainframe.collection_open(id)
##        self.mainframe.grab_focus() ##todo: add mainframe method "restore_focus"

    def src_changed(self,combo,id):
        coll=combo.get_active_coll()
        if coll==None:
            return
        if coll==self.dest_combo.get_active_coll():
            self.dest_combo.set_active(None)

    def dest_changed(self,combo,id):
        coll=combo.get_active_coll()
        if coll!=None and coll==self.src_combo.get_active_coll():
            self.src_combo.set_active(None)
        if self.transfer_widget:
            self.transfer_box.remove(self.transfer_widget)
        if coll!=None and coll.transfer_widget!=None:
            if coll not in self.options_boxes:
                self.options_boxes[coll]=coll.transfer_widget(coll)
            self.transfer_widget=self.options_boxes[coll]
            self.transfer_widget.show_all()
        else:
            self.transfer_widget=None
        if self.transfer_widget!=None:
            self.transfer_box.pack_start(self.options_boxes[coll])

    def transfer_cancelled(self):
        '''
        called from the transfer job thread to indicate the job has been cancelled
        '''
        ##todo: give visual indication of cancellation
        self.transfer_box.set_sensitive(True)
        self.src_combo.set_sensitive(True)
        self.dest_combo.set_sensitive(True)
        self.start_transfer_button.set_sensitive(True)
        self.start_transfer_all_button.set_sensitive(True)
        self.cancel_button.set_sensitive(False)

    def transfer_completed(self):
        '''
        called from the transfer job thread to indicate the job has completed
        '''
        ##todo: give visual indication of completion
        self.transfer_box.set_sensitive(True)
        self.src_combo.set_sensitive(True)
        self.dest_combo.set_sensitive(True)
        self.start_transfer_button.set_sensitive(True)
        self.start_transfer_all_button.set_sensitive(True)
        self.cancel_button.set_sensitive(False)


#    def transfer_now(self,button):
#        self.start_transfer_button.set_sensitive(False)
#        worker=self.mainframe.tm
#        transfer_job.start_transfer(params)

    def cancel_transfer(self,button):
        self.mainframe.tm.job_queue.clear(TransferImportJob)

    def start_transfer(self,button,all):
        coll_src=self.src_combo.get_active_coll()
        coll_dest=self.dest_combo.get_active_coll()
        if coll_src==None or coll_dest==None:
            return
        self.start_transfer_button.set_sensitive(False)
        worker=self.mainframe.tm
        params={}
        if self.transfer_widget!=None:
            params=self.transfer_widget.get_options()
        params['transfer_all']=all
        params['move_files']=self.move_radio.get_active()
        params['metadata_strip']=False
        params['upload_size']=None
        if not coll_src.is_open:
            coll_src.open(self.mainframe.tm)
        ij=TransferImportJob(self.mainframe.tm,None,coll_dest.browser,self,coll_src,coll_dest,params)
        self.mainframe.tm.queue_job_instance(ij)
        self.cancel_button.set_sensitive(True)
        self.start_transfer_all_button.set_sensitive(False)
        self.start_transfer_button.set_sensitive(False)
        self.transfer_box.set_sensitive(False)

    def media_connected(self,uri): ##todo: ensure that uri is actually a local path and if so rename the argument
        print 'media connected event for',uri
        sidebar=self.mainframe.sidebar
        sidebar.set_current_page(sidebar.page_num(self.scrolled_window))
        self.mainframe.sidebar_toggle.set_active(True)
        self.src_combo.set_active(uri)
        if self.mainframe.active_collection!=None:
            self.dest_combo.set_active(self.mainframe.active_collection.id)
#        if self.src_combo.get_editable():
#            self.transfer_source_combo.set_path(io.get_path_from_uri(uri))

    def open_uri(self,uri):
        self.mainframe.open_uri(uri)

    def open_device(self,device):
        self.mainframe.open_device(device)
