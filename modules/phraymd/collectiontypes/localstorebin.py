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

##standard imports
import bisect
from datetime import datetime
import io
import os
import os.path
import re
import cPickle

import gtk

##phraymd imports
from phraymd import pluginmanager
from phraymd import settings
from phraymd import monitor2 as monitor
from phraymd import viewsupport
from phraymd import baseobjects
from phraymd import simple_parser as sp
from phraymd import dialogs
from phraymd import imagemanip
from phraymd import backend
import simpleview

class LocalStorePrefWidget(gtk.VBox):
    def __init__(self,value_dict=None):
        gtk.VBox.__init__(self)
        box,self.name_entry=dialogs.box_add(self,[(gtk.Entry(),True,None)],'Collection Name: ')
        self.path_entry=dialogs.PathnameEntry('','Path to Images: ','Choose a Directory',directory=True)
        self.pack_start(self.path_entry,False)
        self.name_entry.connect("changed",self.name_changed)
        self.path_entry.path_entry.connect("changed",self.path_changed)

        self.a_frame=gtk.Expander("Advanced Options")
        self.a_box=gtk.VBox()
        self.a_frame.add(self.a_box)
        self.recursive_button=gtk.CheckButton('Recurse sub-directories')
        self.recursive_button.set_active(True)
        self.load_meta_check=gtk.CheckButton("Load Metadata")
        self.load_meta_check.set_active(True)
        self.use_internal_thumbnails_check=gtk.CheckButton("Use Embedded Thumbnails if Available")
        self.use_internal_thumbnails_check.set_active(False)
        self.store_thumbnails_check=gtk.CheckButton("Store Thumbnails in Cache") #todo: need to implement in backend
        self.store_thumbnails_check.set_active(True)
        self.a_box.pack_start(self.recursive_button,False)
        self.a_box.pack_start(self.load_meta_check,False)
        self.a_box.pack_start(self.use_internal_thumbnails_check,False)
        self.pack_start(self.a_frame,False)
        self.show_all()
        if value_dict:
            self.set_values(value_dict)

    def path_changed(self,entry):
        sensitive=len(self.name_entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename

    def name_changed(self,entry):
        sensitive=len(entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename

    def get_values(self):
        return {
                'name': self.name_entry.get_text().replace('/','').strip(),
                'image_dirs': [self.path_entry.get_path()],
                'recursive': self.recursive_button.get_active(),
                'load_meta':self.load_meta_check.get_active(),
                'load_embedded_thumbs':self.use_internal_thumbnails_check.get_active(),
                'load_preview_icons':self.use_internal_thumbnails_check.get_active() and not self.load_meta_check.get_active(),
                'store_thumbnails':self.store_thumbnails_check.get_active(),
                }

    def set_values(self,val_dict):
        self.name_entry.set_text(val_dict['name'])
        if len(val_dict['image_dirs'])>0:
            self.path_entry.set_path(val_dict['image_dirs'][0])
        self.recursive_button.set_active(val_dict['recursive'])
        self.load_meta_check.set_active(val_dict['load_meta'])
        self.use_internal_thumbnails_check.set_active(val_dict['load_embedded_thumbs'])


class NewLocalStoreWidget(gtk.VBox):
    def __init__(self,main_dialog,value_dict):
        gtk.VBox.__init__(self)
        self.main_dialog=main_dialog
        label=gtk.Label()
        label.set_markup("<b>Local Store Settings</b>")
        self.pack_start(label,False)
        box,self.name_entry=dialogs.box_add(self,[(gtk.Entry(),True,None)],'Collection Name: ')
        self.path_entry=dialogs.PathnameEntry('','Path to Images: ','Choose a Directory',directory=True)
        self.pack_start(self.path_entry,False)
        self.name_entry.connect("changed",self.name_changed)
        self.path_entry.path_entry.connect("changed",self.path_changed)

        self.a_frame=gtk.Expander("Advanced Options")
        self.a_box=gtk.VBox()
        self.a_frame.add(self.a_box)
        self.recursive_button=gtk.CheckButton('Recurse sub-directories')
        self.recursive_button.set_active(True)
        self.load_meta_check=gtk.CheckButton("Load Metadata")
        self.load_meta_check.set_active(True)
        self.use_internal_thumbnails_check=gtk.CheckButton("Use Embedded Thumbnails if Available")
        self.use_internal_thumbnails_check.set_active(False)
        self.store_thumbnails_check=gtk.CheckButton("Store Thumbnails in Cache") #todo: need to implement in backend
        self.store_thumbnails_check.set_active(True)
        self.monitor_images_check=gtk.CheckButton("Monitor Image Folders for Changes") #todo: need to implement in backend
        self.monitor_images_check.set_active(True)
        self.a_box.pack_start(self.recursive_button,False)
        self.a_box.pack_start(self.load_meta_check,False)
        self.a_box.pack_start(self.use_internal_thumbnails_check,False)
        self.a_box.pack_start(self.monitor_images_check,False)
        #self.a_box.pack_start(self.store_thumbnails_check,False) ##todo: switch this back on and implement in backend/imagemanip

        self.pack_start(self.a_frame,False)
        self.show_all()

#        self.main_dialog.create_button.set_sensitive(False)
        if value_dict:
            self.set_values(value_dict)

    def activate(self):
        sensitive=len(self.name_entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename
        self.main_dialog.create_button.set_sensitive(sensitive)

    def path_changed(self,entry):
        sensitive=len(self.name_entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename
        self.main_dialog.create_button.set_sensitive(sensitive)

    def name_changed(self,entry):
        sensitive=len(entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename
        self.main_dialog.create_button.set_sensitive(sensitive)

#    def path_changed(self,entry):

    def get_values(self):
        return {
                'name': self.name_entry.get_text().strip(),
                'image_dirs': [self.path_entry.get_path()],
                'recursive': self.recursive_button.get_active(),
                'load_meta':self.load_meta_check.get_active(),
                'load_embedded_thumbs':self.use_internal_thumbnails_check.get_active(),
                'load_preview_icons':self.use_internal_thumbnails_check.get_active() and not self.load_meta_check.get_active(),
                'monitor_image_dirs':self.monitor_images_check.get_active(),
                'store_thumbnails':self.store_thumbnails_check.get_active(),
                }

    def set_values(self,val_dict):
        self.name_entry.set_text(val_dict['name'])
        if len(val_dict['image_dirs'])>0:
            self.path_entry.set_path(val_dict['image_dirs'][0])
        self.recursive_button.set_active(val_dict['recursive'])
        self.load_meta_check.set_active(val_dict['load_meta'])
        self.use_internal_thumbnails_check.set_active(val_dict['load_embedded_thumbs'])
        self.monitor_images_check.set_active(val_dict['monitor_image_dirs'])
        self.store_thumbnails_check.set_active(val_dict['store_thumbnails'])


def create_empty_localstore(name,prefs,overwrite_if_exists=False):
    col_dir=os.path.join(settings.collections_dir,name)
    pref_file=os.path.join(os.path.join(settings.collections_dir,name),'prefs')
    data_file=os.path.join(os.path.join(settings.collections_dir,name),'data')
    if not overwrite_if_exists:
        if os.path.exists(col_dir):
            return False
    try:
        if not os.path.exists(col_dir):
            os.makedirs(col_dir)
        f=open(pref_file,'wb')
        cPickle.dump(settings.version,f,-1)
        d={}
        for p in Collection.pref_items:
            if p in prefs:
                d[p]=prefs[p]
        cPickle.dump(d,f,-1)
        f.close()
        f=open(data_file,'wb')
        cPickle.dump(settings.version,f,-1)
        cPickle.dump([],f,-1) #empty list of items
        f.close()
    except:
        print 'Error writing empty collection to ',col_dir
        import traceback,sys
        tb_text=traceback.format_exc(sys.exc_info()[2])
        print tb_text
        return False
    return True




class Collection(baseobjects.CollectionBase):
    '''
    Defines a persistent collection of images on the local filesystem
    '''
    ##todo: do more plugin callbacks here instead of the job classes?
    type='LOCALSTORE'
    type_descr='Local Store'
    pref_widget=LocalStorePrefWidget
    add_widget=NewLocalStoreWidget
    persistent=True
    user_creatable=True
    view_class=simpleview.SimpleView
    pref_items=baseobjects.CollectionBase.pref_items+('image_dirs','recursive','verify_after_walk','load_meta','load_embedded_thumbs',
                'load_preview_icons','trash_location','thumbnail_cache','monitor_image_dirs')
    def __init__(self,prefs): #todo: store base path for the collection
        ##the following attributes are set at run-time by the owner
        baseobjects.CollectionBase.__init__(self,prefs)

#        ##the collection consists of an array of entries for images, which are cached in the collection file
        self.items=[] #the image/video items

        ##and has the following properties (which are stored in the collection file if it exists)
        self.image_dirs=[]
        self.recursive=True
        self.verify_after_walk=True
        self.load_meta=True #image will be loaded into the collection and view without metadata
        self.load_embedded_thumbs=False #only relevant if load_metadata is true
        self.load_preview_icons=False #only relevant if load_metadata is false
        self.trash_location=None #none defaults to <collection dir>/.trash
        self.thumbnail_cache=None #use gnome/freedesktop or put in the image folder
        self.monitor_image_dirs=True

        ## the collection optionally has a filesystem monitor and views (i.e. subsets) of the collection of images
        self.monitor=None
        self.monitor_master_callback=None
        self.browser=None

        if prefs:
            self.set_prefs(prefs)

        self.id=self.name

    ''' ************************************************************************
                            PREFERENCES, OPENING AND CLOSING
        ************************************************************************'''

    def delete_store(self):
        col_dir=os.path.join(settings.collections_dir,self.name)
        try:
            if os.path.isdir(col_dir):
                for root, dirs, files in os.walk(col_dir, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(col_dir)
            elif os.path.isfile(col_dir):
                io.remove_file(col_dir)
            return True
        except IOError:
            print 'Error removing collection data files in',col_dir
            import sys,traceback
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print tb_text
            return False

    def create_store(self):
        return create_empty_localstore(self.name,self.get_prefs())

    def open(self,thread_manager,browser=None):
        j=backend.LoadCollectionJob(thread_manager,self,browser)
        thread_manager.queue_job_instance(j)

    def _open(self):
        '''
        load the collection from a binary pickle file
        '''
        col_dir=os.path.join(settings.collections_dir,self.name)
        if self.is_open:
            return True
        try:
            if os.path.isfile(col_dir):
                return self.legacy_open(col_dir)
            f=open(self.data_file(),'rb')
            version=cPickle.load(f)
            print 'Loaded collection version',version
            if version>='0.5':
                self.items=cPickle.load(f)
            self.numselected=0
            return True
        except:
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print "Error Loading Collection",self.name
            print tb_text
            self.empty()
            return False

    def close(self):
        '''
        save the collection to a binary pickle file using the filename attribute of the collection
        '''
        if self.type!='FLICKR':
            return True
        print 'started close',self.name
        if not self.is_open:
            return True
        if self.type!='FLICKR':
            return False
        print 'starting close',self.name
        try:
            col_dir=os.path.join(settings.collections_dir,self.name)
            print 'closing',col_dir
            if os.path.isfile(col_dir):
                print 'removing',col_dir
                os.remove(col_dir)
            if not os.path.exists(col_dir):
                print 'make dir',col_dir
                os.makedirs(col_dir)
            #self.save_prefs()
            f=open(self.data_file(),'wb')
            cPickle.dump(settings.version,f,-1)
            cPickle.dump(self.items,f,-1)
            f.close()
            self.empty()
        except:
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print "Error Writing Collection",self.name
            print tb_text
            return False
        return True

    ''' ************************************************************************
                            MONITORING THE COLLECTION
        ************************************************************************'''

    def start_monitor(self,callback):
        if self.monitor_image_dirs:
            self.monitor_master_callback=callback
            self.monitor=monitor.Monitor(self.image_dirs,self.recursive,self.monitor_callback)

    def end_monitor(self):
        if self.monitor!=None and self.monitor_image_dirs:
            self.monitor.stop()
            self.monitor=None

    def monitor_callback(self,path,action,is_dir):
        self.monitor_master_callback(self,path,action,is_dir)



    ''' ************************************************************************
                            MANAGING THE LIST OF COLLECTION ITEMS
        ************************************************************************'''

    def add(self,item,add_to_view=True):
        '''
        add an item to the collection and notify plugin
        '''
        try:
            ind=bisect.bisect_left(self.items,item)
            if len(self.items)>ind>0 and self.items[ind]==item:
                raise LookupError
            self.items.insert(ind,item)
            self.numselected+=item.selected
            pluginmanager.mgr.callback_collection('t_collection_item_added',self,item)
            if add_to_view:
                for v in self.views:
                    v.add_item(item)
            return True
        except LookupError:
            print 'WARNING: tried to add',item,ind,'to collection',self.id,'but an item with this id was already present'
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print tb_text
            return False

    def delete(self,item,delete_from_view=True):
        '''
        delete an item from the collection, returning the item to the caller if present
        notifies plugins if the item is remmoved
        '''
        i=self.find(item)
        if i>=0:
            item=self.items[i]
            self.numselected-=item.selected
            self.items.pop(i)
            pluginmanager.mgr.callback_collection('t_collection_item_removed',self,item)
            for v in self.views:
                v.del_item(item)
            return item
        return None

    def find(self,item):
        '''
        find an item in the collection and return its index
        '''
        i=bisect.bisect_left(self,item)
        if i>=len(self.items) or i<0:
            return -1
        if self.items[i]==item:
            return i
        return -1

    def __call__(self,ind):
        return self.items[ind]

    def __getitem__(self,ind):
        return self.items[ind]

    def get_all_items(self):
        return self.items[:]

    def empty(self,empty_views=True):
        del self.items[:]
        self.numselected=0
        if empty_views:
            for v in self.views:
                v.empty()

    def __len__(self):
        return len(self.items)

    ''' ************************************************************************
                            MANIPULATING INDIVIDUAL ITEMS
        ************************************************************************'''
    def copy_item(self,src_collection,src_item):
        'copy an item from another collection source'
        try:
            uid=''###TODO: Establish a uid
            dest_item=baseobjects.Item(uid)
            self.add(dest_item)
            stream=src_collection.get_file_data(src_item)
            self.write_file_data(item,stream)
            item.mtime=io.get_mtime()
        except:
            print 'Error copying src item'
    def delete_item(self,item):
        'remove the item from the underlying store'
        try:
            io.remove_file(item.uid)
            return True
        except:
            print 'Error deleting',item.uid
            return False
    def load_thumbnail(self,item):
        'load the thumbnail from the local cache'
        if self.load_preview_icons:
            if imagemanip.load_thumb_from_preview_icon(item):
                return
        return imagemanip.load_thumb(item)
    def has_thumbnail(self,item):
        return imagemanip.has_thumb(item)
    def make_thumbnail(self,item,interrupt_fn=None,force=False):
        'create a cached thumbnail of the image'
        if not force and (self.load_embedded_thumbs or self.load_preview_icons):
            return False
        imagemanip.make_thumb(item,interrupt_fn,force)
        imagemanip.update_thumb_date(item)
        return
    def item_metadata_update(self,item):
        'collection will receive this call when item metadata has been changed'
        pass
    def load_metadata(self,item):
        'retrieve metadata for an item from the source'
        if self.load_embedded_thumbs:
            result=imagemanip.load_metadata(item,self,None,True)
        else:
            result=imagemanip.load_metadata(item,self,None,False)
        if self.load_embedded_thumbs and not item.thumb:
            item.thumb=False
        return result
    def write_metadata(self,item):
        'write metadata for an item to the source'
        return imagemanip.save_metadata(item)
    def load_image(self,item,interrupt_fn=None,size_bound=None):
        'load the fullsize image, up to maximum size given by the (width, height) tuple in size_bound'
        draft_mode=False
        return imagemanip.load_image(item,interrupt_fn,draft_mode)
    def get_file_stream(self,item):
        'return a stream read the entire photo file from the source (as binary stream)'
        return open(item.uid,'rb')
    def write_file_data(self,dest_item,src_stream):
        'write the entire photo file (as a stream) to the source (as binary stream)'
        try:
            f=open(dest_item.uid,'wb')
            f.write(src_stream.read())
            f.close()
            return True
        except:
            print 'Error writing file data',dest_item
    def get_browser_text(self,item):
        header=''
        if settings.overlay_show_title:
            try:
                header=item.meta['Title']
            except:
                header=os.path.split(item.uid)[1]
        details=''
        if settings.overlay_show_path:
            details+=os.path.split(item.uid)[0]
        if settings.overlay_show_tags:
            val=viewsupport.get_keyword(item)
            if val:
                if details and not details.endswith('\n'):
                    details+='\n'
                val=str(val)
                if len(val)<90:
                    details+='Tags: '+val
                else:
                    details+=val[:88]+'...'
        if settings.overlay_show_date:
            val=viewsupport.get_ctime(item)
            if val>datetime(1900,1,1):
                if details and not details.endswith('\n'):
                    details+='\n'
                details+='Date: '+str(val)
    #    else:
    #        details+='Mod: '+str(get_mtime(item))
        if settings.overlay_show_exposure:
            val=viewsupport.get_focal(item)
            exposure=u''
            if val:
                exposure+='%imm '%(int(val),)
            val=viewsupport.get_aperture(item)
            if val:
                exposure+='f/%3.1f'%(val,)
            val=viewsupport.get_speed_str(item)
            if val:
                exposure+=' %ss'%(val,)
            val=viewsupport.get_iso_str(item)
            if val:
                exposure+=' iso%s'%(val,)
            if exposure:
                if details and not details.endswith('\n'):
                    details+='\n'
                details+=exposure
        return (header,details)

    def get_viewer_text(self,item,size=None,zoom=None):
        ##HEADER TEXT
        header=''
        #show title
        path,filename=os.path.split(item.uid)
        try:
            header=item.meta['Title']
            title=True
        except:
            header+=filename
            title=False

        ##DETAIL TEXT
        details=''
        #show filename and path to image
        if title:
            details+=filename+'\n'
        details+=path
        #show tags
        val=viewsupport.get_keyword(item)
        if val:
            if details and not details.endswith('\n'):
                details+='\n'
            val=str(val)
            if len(val)<90:
                details+='Tags: '+val
            else:
                details+=val[:88]+'...'
        #date information
        if details and not details.endswith('\n'):
            details+='\n'
        val=viewsupport.get_ctime(item)
        if val>datetime(1900,1,1):
            details+='Date: '+str(val)+'\n'
    ###    details+='Date Modified: '+str(get_mtime(item))
        if item.meta!=None and 'Model' in item.meta:
            details+='Model: '+str(item.meta['Model'])+'\n'
        #Exposure details
        val=viewsupport.get_focal(item)
        exposure=u''
        if val:
            exposure+='%imm '%(int(val),)
        val=viewsupport.get_aperture(item)
        if val:
            exposure+='f/%3.1f'%(val,)
        val=get_speed_str(item)
        if val:
            exposure+=' %ss'%(val,)
        val=viewsupport.get_iso_str(item)
        if val:
            exposure+=' iso%s'%(val,)
        if exposure:
            if details and not details.endswith('\n'):
                details+='\n'
            details+='Exposure: '+exposure
        #IMAGE SIZE AND ZOOM LEVEL
        if size:
            if details and not details.endswith('\n'):
                details+='\n'
            details+='Image Dimensions: %i x %i'%size
        if zoom:
            if details and not details.endswith('\n'):
                details+='\n'
            if zoom!='fit':
                details+='Zoom: %3.2f%%'%(zoom*100,)
            else:
                details+='Zoom: Fit'

        return (header,details)


baseobjects.register_collection('LOCALSTORE',Collection)
