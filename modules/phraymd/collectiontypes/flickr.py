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


#TODO: Handle offline mode (can't view fullsize, can't write changes etc)
#TODO: Fix image sync (must be interruptable, check for deleted + changed images)
#TODO: Login authentication


##standard imports
import bisect
import datetime
import os
import os.path
import re
from datetime import datetime
import cPickle
import urllib2
import time
import tempfile

##beej's flickr API
import flickrapi

##gtk imports
import gtk
import gobject

##phraymd imports
from phraymd import pluginmanager
from phraymd import settings
from phraymd import baseobjects
from phraymd import simple_parser as sp
from phraymd import dialogs
from phraymd import backend
from phraymd import imagemanip
from phraymd import metadata
from phraymd import viewsupport
from phraymd import io
import simpleview


privacy_levels=[
'PUBLIC',
'FRIENDS AND FAMILY',
'FRIENDS',
'FAMILY',
'PRIVATE'
]

PRIVACY_PUBLIC=0
PRIVACY_FRIENDS_AND_FAMILY=1
PRIVACY_FRIENDS=2
PRIVACY_FAMILY=3
PRIVACY_PRIVATE=4


class LoadFlickrCollectionJob(backend.WorkerJob):
    def __init__(self,worker,collection,browser):
        backend.WorkerJob.__init__(self,'LOADFLICKRCOLLECTION',890,worker,collection,browser)
        self.pos=0
        self.full_rescan=True

    def __call__(self):
        jobs=self.worker.jobs
        jobs.clear(None,self.collection,self)
        collection=self.collection
#        log.info('Loading collection '+self.collection_file)
        gobject.idle_add(self.browser.update_status,0.66,'Loading Collection: %s'%(collection.name,))
        print 'OPENING COLLECTION',collection.id,collection.type
        if collection._open():
            self.worker.queue_job_instance(backend.BuildViewJob(self.worker,self.collection,self.browser))
            gobject.idle_add(collection.login,self.worker,self.browser)
            pluginmanager.mgr.callback_collection('t_collection_loaded',self.collection)
            gobject.idle_add(self.worker.coll_set.collection_opened,collection.id)
#            log.info('Loaded collection with '+str(len(collection))+' images')
        else:
            pass
#            log.error('Load collection failed')
        return True

datefmt="%Y-%m-%d %H:%M:%S"


class FlickrSyncJob(backend.WorkerJob):
    def __init__(self,worker,collection,browser):
        backend.WorkerJob.__init__(self,'FLICKRSYNC',700,worker,collection,browser)
        self.started=False

    def __call__(self):
        jobs=self.worker.jobs
        collection=self.collection
        flickr_client=collection.flickr_client
        recently_updated=False
        if not self.started:
            self.page=0
            self.pages=1
            self.photodata=[]
            self.counter=0
            self.started=True
        new_time=time.time()
        while jobs.ishighestpriority(self) and self.page<=self.pages:
#            supported_extras='''description, license, date_upload, date_taken, owner_name, icon_server, original_format,
#                    last_update, geo, tags, machine_tags, o_dims, views, media, path_alias, url_sq, url_t, url_s, url_m,
#                    url_z, url_l, url_o'''
#            photos=flickr_client.people_getPhotos(user_id="me",page=page, extras='description,license,geo,tags,date_upload,date_taken,last_update,url_t,original_format')
            if self.counter>=len(self.photodata):
                self.page+=1
                self.counter=0
                pct=(1.0*(self.page-1)*500+self.counter)/(self.pages*500)
                gobject.idle_add(self.browser.update_status,pct,'Syncing with Flickr')
                if recently_updated: ##TODO: This isn't going to work if recentlyUpdated doesn't report deleted images
                    photos=flickr_client.people_recentlyUpdated(user_id="me",page=self.page, min_date=self.last_update_time, extras='description,license,geo,tags,date_upload,date_taken,last_update,url_s,url_o,original_format')
                else:
                    photos=flickr_client.people_getPhotos(user_id="me",page=self.page, per_page=500, extras='description,license,geo,tags,date_upload,date_taken,last_update,url_s,url_o,original_format')
                photos=photos.find('photos')
                self.page=int(photos.attrib['page'])
                self.pages=int(photos.attrib['pages'])
                self.photodata=photos.findall('photo')
            while self.counter<len(self.photodata) and jobs.ishighestpriority(self):
                pct=(1.0*(self.page-1)*500+self.counter)/(self.pages*500)
                print '***',pct,self.page,self.pages,self.counter
                gobject.idle_add(self.browser.update_status,pct,'Syncing with Flickr')
                ph=self.photodata[self.counter]
                self.counter+=1
                uid=ph.attrib['id']
                print 'uid',uid
                item=baseobjects.Item(uid)
                ind=collection.find(item)
                if ind>=0:
                    item=collection[ind]
                item.sync=True
                datemod=datetime.fromtimestamp(float(ph.attrib['lastupdate']))
                if item.meta==None or datemod!=item.meta['DateModified']:
#                    item.secret=ph.attrib['secret']
#                    item.server=ph.attrib['server']
#                    item.thumburl=ph.attrib['url_s']
#                    item.imageurl=ph.attrib['url_o']
                    collection.load_metadata(item)
                if ind<0:
                    self.collection.add(item,self.collection)
                gobject.idle_add(self.browser.resize_and_refresh_view,self.collection)
        if self.page>self.pages:
            collection.last_update_time=new_time
            gobject.idle_add(self.browser.update_status,2.0,'Syncing Complete')

            ##todo: this should be interruptable
            print 'REMOVING DELETED ITEMS'
            items_to_del=[]
            for i in range(len(collection)):
                item=collection[i]
                if 'sync' in item.__dict__:
                    del item.sync
                else:
                    items_to_del.append(item)
            for item in items_to_del:
                self.browser.lock.acquire()
                collection.delete(item)
                self.browser.lock.release()
                gobject.idle_add(self.browser.resize_and_refresh_view,self.collection)
            return True
        return False


class FlickrPrefWidget(gtk.VBox):
    def __init__(self,value_dict=None):
        gtk.VBox.__init__(self)
        box,self.name_entry=dialogs.box_add(self,[(gtk.Entry(),True,None)],'Collection Name: ')
        self.name_entry.connect("changed",self.name_changed)

        self.show_all()
        if value_dict:
            self.set_values(value_dict)

    def name_changed(self,entry):
        sensitive=len(entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename

    def get_values(self):
        name=self.name_entry.get_text().replace('/','').strip()
        return {
                'name': name,
                'verify_after_walk': True,
                }

    def set_values(self,val_dict):
        self.name_entry.set_text(val_dict['name'])


class NewFlickrAccountWidget(gtk.VBox):
    def __init__(self,main_dialog,value_dict):
        gtk.VBox.__init__(self)
        self.main_dialog=main_dialog
        label=gtk.Label()
        label.set_markup("<b>Flickr Settings</b>")
        self.pack_start(label,False)
        box,self.name_entry=dialogs.box_add(self,[(gtk.Entry(),True,None)],'Collection Name: ')
        self.name_entry.connect("changed",self.name_changed)
        self.show_all()

        if value_dict:
            self.set_values(value_dict)

    def activate(self):
        sensitive=len(self.name_entry.get_text().strip())>0 ##todo: also check that name is a valid filename
        self.main_dialog.create_button.set_sensitive(sensitive)

    def path_changed(self,entry):
        sensitive=len(self.name_entry.get_text().strip())>0 ##todo: also check that name is a valid filename
        self.main_dialog.create_button.set_sensitive(sensitive)

    def name_changed(self,entry):
        sensitive=len(self.name_entry.get_text().strip())>0 ##todo: also check that name is a valid filename
        self.main_dialog.create_button.set_sensitive(sensitive)

#    def path_changed(self,entry):

    def get_values(self):
        return {
                'name': self.name_entry.get_text().strip(),
                'verify_after_walk': True,
                }

    def set_values(self,val_dict):
        self.name_entry.set_text(val_dict['name'])


def create_empty_collection(name,prefs,overwrite_if_exists=False):
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
        for p in FlickrCollection.pref_items:
            if p in prefs:
                d[p]=prefs[p]
        cPickle.dump(d,f,-1)
        f.close()
        f=open(data_file,'wb')
        cPickle.dump(settings.version,f,-1)
        cPickle.dump([],f,-1) #empty list of items
        f.close()
    except:
        print 'Error writing empty collection to ',fullpath
        import traceback,sys
        tb_text=traceback.format_exc(sys.exc_info()[2])
        print tb_text
        return False
    return True


def get_uid(item):
    return item.uid

def get_utime(item):
    try:
        date=item.meta["DateUploaded"]
        if type(date)==str:
            date=datetime.strptime(date)
        return date
    except:
        return datetime.datetime(1900,1,1)

flickr_sort_keys={
        'Date Taken':viewsupport.get_ctime,
        'Date Uploaded':get_utime,
        'Date Last Modified':viewsupport.get_mtime,
        'Photo ID':get_uid,
        'Orientation':viewsupport.get_orient,
#        'Folder':view_support.get_folder,
#        'Shutter Speed':view_support.get_speed,
#        'Aperture':view_support.get_aperture,
#        'Focal Length':view_support.get_focal,
#        'Relevance':view_support.get_relevance
        }


class FlickrCollection(baseobjects.CollectionBase):
    '''defines a sorted collection of Items with
    callbacks to plugins when the contents of the collection change'''
    ##todo: do more plugin callbacks here instead of the job classes?
    type='FLICKR'
    type_descr='Flickr Account'
    local_filesystem=False
    browser_sort_keys=flickr_sort_keys
    api_key = 'c0ec5403179a50fbbff9f3f65b664b29'
    api_secret = 'd5340e24789b7fd9'
    pref_widget=FlickrPrefWidget
    add_widget=NewFlickrAccountWidget
    persistent=True
    user_creatable=True
    view_class=simpleview.SimpleView
    pref_items=baseobjects.CollectionBase.pref_items+('verify_after_walk',)
    def __init__(self,prefs): #todo: store base path for the collection
        ##the following attributes are set at run-time by the owner
        baseobjects.CollectionBase.__init__(self,prefs)
        self.persistent=True #whether the collection is stored to disk when closed

        ##flickr login + API
        self.login_username=''
        self.login_id=''
        self.flickr_client=None #will be none if not logged in

        self.items=[] #the image/video items

        ##and has the following properties (which are stored in the collection file if it exists)
        self.image_dirs=[]
        self.sync_at_login=True #try to synchronize with Flickr after start up
        self.store_images_locally=False #keep an offline copy of all images in the collections
        self.max_stored_image_size=None
        self.trash_location=None #none defaults to <collection dir>/.trash

        ##collection will be associated with a browser
        self.browser=None

        if prefs:
            self.set_prefs(prefs)
        self.id=self.name
        self.thumbnail_cache_dir=os.path.join(self.coll_dir(),'.thumbnails')#use gnome/freedesktop if none or specify a folder

    ''' ************************************************************************
                            PREFERENCES, OPENING AND CLOSING
        ************************************************************************'''

    def create_store(self):
        if not create_empty_collection(self.name,self.get_prefs()):
            return False
        if not os.path.exists(self.thumbnail_cache_dir):
            os.makedirs(self.thumbnail_cache_dir)
        return True

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

    def open(self,thread_manager,browser=None):
        j=LoadFlickrCollectionJob(thread_manager,self,browser)
        thread_manager.queue_job_instance(j)

    def _open(self):
        '''
        load the cached state of the flickr collection from a binary pickle file
        '''
        col_dir=os.path.join(settings.collections_dir,self.name)
        if self.is_open:
            return True
        try:
            if os.path.isfile(col_dir):
                return self.legacy_open(col_dir)
            f=open(self.data_file(),'rb')
            version=cPickle.load(f)
            print 'Loaded flickr collection version',version
            if version>='0.5':
#                self.flickr_collections=cPickle.load(f)
#                self.flickr_sets=cPickle.load(f)
                self.items=cPickle.load(f)
                for i in range(len(self.items)):
                    if 'filename' in self.items[i].__dict__:
                        self.items[i]=self.items[i].convert()
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
        print 'Closing Flickr Collection',self.name
        if not self.is_open:
            return True
        try:
            col_dir=os.path.join(settings.collections_dir,self.name)
            if os.path.isfile(col_dir):
                os.remove(col_dir)
            if not os.path.exists(col_dir):
                os.makedirs(col_dir)
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


    ''' ********************************************************************
            METHODS TO SYNC THE COLLECTION WITH THE FLICKR ACCOUNT
    ******************************************************************** '''

    def login(self,worker,browser):
        '''
        initialize flickr client object and log into the flickr account
        '''
        print '#########FLICKR LOGIN#########'
        if self.flickr_client!=None:
            return
        self.flickr_client = flickrapi.FlickrAPI(self.api_key, self.api_secret)
        self.flickr_client.token.path = os.path.join(self.coll_dir(),'flickr-token')
        try:
            (self.token, self.frob) = self.flickr_client.get_token_part_one(perms='delete')
            if not self.token:
                from phraymd import dialogs
                result=dialogs.prompt_dialog('Allow Flickr Access','phraymd has opened a Flickr application authentication page in your web browser. Please give phraymd access to your flickr account by accepting the prompt in your web browser. Press "Done" when complete',buttons=('_Done',),default=0)
            self.flickr_client.get_token_part_two((self.token, self.frob))
            login_resp=self.flickr_client.test_login()
            user=login_resp.find('user')
            self.login_username=user.find('username').text
            self.login_id=user.attrib['id']
            self.online=True
            if self.sync_at_login or len(collection)==0:
                worker.queue_job_instance(FlickrSyncJob(worker,self,browser))
                worker.queue_job_instance(backend.MakeThumbsJob(worker,self,browser))
            return True
        except:
            import traceback, sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print 'Error logging into flickr'
            print tb_text
            self.flickr_client=None
            return False

    def get_collections(self):
        try:
            '''
            get the collections from the flickr account
            collections is actually a tree so this doesn't make a lot of sense
            '''
            response=self.flickr_client.collections_getTree()
            collections=response.find('collections')
            collectionsdata=photocollections.findall('collection')
            self.collections=[(co.find('title').text,co) for co in collectionsdata]
            #self.t_notify_albums(alist,'')
        except:
            import traceback, sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print 'Error retrieving collection data',tb_text

    def get_sets(self):
        try:
            response=self.flickr_client.photosets_getList()
            photosets=response.find('photosets')
            sets=photosets.findall('photoset')
            self.sets=[(s.find('title').text,s) for s in sets]
            #self.t_notify_albums(alist,'')
        except:
            import traceback, sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print 'Error retrieving set data',tb_text
            #self.t_notify_albums([],'')

    ''' ************************************************************************
                        MONITORING THE COLLECTION SOURCE FOR CHANGES
                        FOR FLICKR: POLL AT MOST ONCE PER HOUR
        ************************************************************************'''
    def start_monitor(self,callback):
        pass

    def end_monitor(self):
        pass

    ''' ************************************************************************
                            MANAGING THE LIST OF COLLECTION ITEMS
        ************************************************************************'''

    def add(self,item,add_to_view=True):
        '''
        add an item to the collection and notify plugin
        '''
        try:
            ind=bisect.bisect_left(self.items,item)
            if len(self.items)>ind>=0 and self.items[ind]==item:
                raise LookupError
            self.items.insert(ind,item)
            self.numselected+=item.selected
            pluginmanager.mgr.callback_collection('t_collection_item_added',self,item)
            if add_to_view:
                print 'adding to view'
                for v in self.views:
                    print 'adding to view',item
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
    def copy_item(self,src_collection,src_item,prefs):
        'copy an item from another collection source'
        try:
            #get or create suitable copy of the image file for uploading
            name=os.path.split(src_item.uid)[1] ##this could be a problem for some uid's
            temp_filename=''
            temp_dir=''
            src_filename=src_item.uid
            if prefs['dest_name_needs_meta'] and src_item.meta==None or not self.local_filesystem:
                temp_dir=tempfile.mkdtemp('','.image-')
                temp_filename=os.path.join(temp_dir,name)
                try:
                    if src_collection.local_filesystem:
                        io.copy_file(src_item.uid,temp_filename) ##todo: this may be a desirable alternative for local images
                    else:
                        open(temp_filename,'wb').write(src_collection.get_file_stream(src_item))
                except IOError:
                    ##todo: log an error
                    ##todo: maybe better to re-raise the exception here
                    return False
                src_filename=temp_filename
                imagemanip.load_metadata(src_item,src_collection,src_filename)
            filename=imagemanip.get_jpeg_or_png_image_file(src_item,prefs['upload_size'],prefs['metadata_strip'],src_filename)

            #specify metadata
            try:
                title=src_item.meta['Title']
            except:
                title=os.path.split(src_item.uid)[1]
            try:
                tags=metadata.tag_bind(src_item.meta['Keywords'])
            except:
                tags=None
            try:
                description=src_item.meta['ImageDescription']
            except:
                description=None
            try:
                privacy=src_item.meta['Privacy']
            except:
                privacy=PRIVACY_PRIVATE
            public=1 if privacy==PRIVACY_PUBLIC else 0
            family=1 if privacy in [PRIVACY_FRIENDS,PRIVACY_FRIENDS_AND_FAMILY] else 0
            friends=1 if privacy in [PRIVACY_FAMILY,PRIVACY_FRIENDS_AND_FAMILY] else 0

            #do the upload to flickr
            print 'uploading',src_item.uid,'with privacy',public,family,friends
            def progress_cb(progress,done):
                ##send notification
                pass
            photo_id=self.flickr_client.upload(filename=filename,title=title,description=description,tags=tags,
                is_public=public,is_family=family,is_friend=friends,callback=progress_cb)
            photo_id=photo_id.find('photoid').text

##            if album[0]:
##                photoset_id=album[1].attrib['id']
##                self.flickr_client.photosets_addPhoto(photoset_id=photoset_id,photo_id=photo_id)

            #clean up
            try:
                if prefs['move_files']:
                    src_collection.delete_item(src_item)
                if temp_filename!=src_filename:
                    io.remove_file(temp_filename)
                if temp_dir:
                    os.rmdir(temp_dir)
            except:
                print 'Error cleaning up old files'
                print 'Error copying image'
                import traceback,sys
                tb_text=traceback.format_exc(sys.exc_info()[2])
                print tb_text

            #now add the item to the collection
            item=baseobjects.Item(photo_id)
            item.selected=src_item.selected
            self.load_metadata(item)
            self.make_thumbnail(item) ##todo: save time by copying the thumb from src_item
            self.add(item) ##todo: should we lock the image browser rendering updates for this call??
            return True
        except:
            print 'Error copying src item'
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print tb_text
            return False

    def delete_item(self,item):
        'remove the item from the underlying store'
        try:
            print 'Deleting item',item
            self.flickr_client.photos_delete(photo_id=item.uid)
            self.delete(item.uid)
            print 'Deleted item',item
            return True
        except:
            ##todo: should delete item from collection anyway?
            import traceback,sys
            print 'Error deleting item',item
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print tb_text
            return False

    def load_thumbnail(self,item):
        'load the thumbnail from the local cache'
        return imagemanip.load_thumb(item)

    def has_thumbnail(self,item):
        return item.thumburi

    def make_thumbnail(self,item,interrupt_fn=None,force=False):
        'create a cached thumbnail of the image'
        if not force and item.thumburi:
            return True
        print 'Flickr Colleciton: creating thumb for',item
        try:
            thumburi=os.path.join(self.thumbnail_cache_dir,item.uid)+'.jpg'
            try:
                os.makedirs(os.path.split(thumburi)[0])
            except:
                pass
            f=open(thumburi,'wb')
            f.write(urllib2.urlopen(item.thumburl).read())
            item.thumburi=thumburi ##avoid a race condition with imagemanip.load_thumb by setting item.thumburi AFTER the thumb has been created
            return True
        except:
            print 'Failed to retrieve thumbnail for',item
            item.thumburi=False
            item.thumb=False
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print tb_text
            return False

    def item_metadata_update(self,item):
        'collection will receive this call when item metadata has been changed. (Intended for use with database backends)'
        pass

    def load_metadata(self,item,missing_only=False):
        'retrieve metadata for an item from the source'
##        extras='description,license,geo,date_upload,date_taken,last_update,url_s,url_o,original_format'
        result=self.flickr_client.photos_getInfo(photo_id=item.uid)

        ph=result.find('photo')
        if not ph:
            return False
        meta={}
        item.secret=ph.attrib['secret']
        item.server=ph.attrib['server']
        item.farm=ph.attrib['farm']
        originalformat=ph.attrib['originalformat']
        originalsecret=ph.attrib['originalsecret']
        item.thumburl='http://farm%s.static.flickr.com/%s/%s_%s_m.jpg'%(item.farm,item.server,item.uid,item.secret)
        item.imageurl='http://farm%s.static.flickr.com/%s/%s_%s_o.%s'%(item.farm,item.server,item.uid,originalsecret,originalformat)
        title=ph.find('title')
        if title!=None and title.text!=None: meta['Title']=title.text
        desc=ph.find('description')
        if desc!=None and desc.text!=None: meta['Description']=desc.text
        imtype=ph.attrib['originalformat']
        if imtype=='png': meta['imtype']='image/png'
        if imtype=='jpg': meta['imtype']='image/jpeg'
        if imtype=='gif': meta['imtype']='image/gif'
        vis=ph.find('visibility')
        if vis!=None:
            is_public=int(vis.attrib['ispublic'])
            is_friend=int(vis.attrib['isfriend'])
            is_family=int(vis.attrib['isfamily'])
            if is_public:
                privacy=0
            elif is_friend and is_family:
                privacy=1
            elif is_friend:
                privacy=2
            elif is_family:
                privacy=3
            else:
                privacy=4
            meta['Privacy']=privacy
        rotate=ph.attrib['rotation']
        if rotate=='0': meta['Orientation']=1
        if rotate=='90': meta['Orientation']=8
        if rotate=='180': meta['Orientation']=3
        if rotate=='270': meta['Orientation']=6
        dates=ph.find('dates')
        if dates!=None:
            meta['DateUploaded']=datetime.fromtimestamp(float(dates.attrib['posted']))
            meta['DateModified']=datetime.fromtimestamp(float(dates.attrib['lastupdate']))
            meta['DateTaken']=datetime.strptime(dates.attrib['taken'],datefmt)
        perm=ph.find('permissions')
        if perm!=None:
            meta['PermComment']=perm.attrib['permcomment']
            meta['PermAddMeta']=perm.attrib['permaddmeta']
        tags=ph.find('tags')
        if tags!=None:
            tags=tags.findall('tag')
            meta['Keywords']=[t.attrib['raw'] for t in tags]
        print 'Read metadata',meta
        item.init_meta(meta,self)
        '''
        <photo id="2733" secret="123456" server="12"
            isfavorite="0" license="3" rotation="90"
            originalsecret="1bc09ce34a" originalformat="png">
            <owner nsid="12037949754@N01" username="Bees"
                realname="Cal Henderson" location="Bedford, UK" />
            <title>orford_castle_taster</title>
            <description>hello!</description>
            <visibility ispublic="1" isfriend="0" isfamily="0" />
            <dates posted="1100897479" taken="2004-11-19 12:51:19"
                takengranularity="0" lastupdate="1093022469" />
            <permissions permcomment="3" permaddmeta="2" />
            <editability cancomment="1" canaddmeta="1" />
            <comments>1</comments>
            <notes>
                <note id="313" author="12037949754@N01"
                    authorname="Bees" x="10" y="10"
                    w="50" h="50">foo</note>
            </notes>
            <tags>
                <tag id="1234" author="12037949754@N01" raw="woo yay">wooyay</tag>
                <tag id="1235" author="12037949754@N01" raw="hoopla">hoopla</tag>
            </tags>
            <urls>
                <url type="photopage">http://www.flickr.com/photos/bees/2733/</url>
            </urls>
        </photo>
        '''

    def write_metadata(self,item,set_meta=True,set_tags=True,set_perms=True):
        'write metadata for an item to the source'
##TODO: Other metadate that could be set...
##        flickr.photos.setContentType
##        flickr.photos.setDates
##        flickr.photos.setSafetyLevel
        try:
            privacy=item.meta['Privacy']
        except KeyError:
            privacy=PRIVACY_PUBLIC
        is_public=1 if privacy==PRIVACY_PUBLIC else 0
        is_family=1 if privacy in (PRIVACY_FRIENDS,PRIVACY_FRIENDS_AND_FAMILY) else 0
        is_friend=1 if privacy in (PRIVACY_FAMILY,PRIVACY_FRIENDS_AND_FAMILY) else 0
        try:
            perm_comment=item.meta['PermComment']
        except KeyError:
            perm_comment=0
        try:
            perm_addmeta=item.meta['PermAddMeta']
        except KeyError:
            perm_addmeta=0
        try:
            title=item.meta['Title']
        except:
            title=''
        try:
            description=item.meta['Description']
        except:
            description=''
        try:
            tags=metadata.tag_bind(item.meta['Keywords'])
        except:
            tags=''
        if set_meta:
            self.flickr_client.photos_setMeta(photo_id=item.uid,title=title,description=description)
        if set_tags:
            self.flickr_client.photos_setTags(photo_id=item.uid,tags=tags)
        if set_perms:
            self.flickr_client.photos_setPerms(photo_id=item.uid,is_public=is_public,is_friend=is_friend,is_family=is_family,perm_comment=perm_comment,perm_addmeta=perm_addmeta)
        item.mark_meta_saved()

    def load_image(self,item,interrupt_fn=None,size_bound=None):
        'load the fullsize image, up to maximum size given by the (width, height) tuple in size_bound'
        if item.image!=None:
            return
        try:
            import ImageFile
            print 'loading image for view',item.imageurl
            fp = urllib2.urlopen(item.imageurl)
            p = ImageFile.Parser()
            if interrupt_fn==None:
                interrupt_fn=lambda:True
            from cStringIO import StringIO
            sio=StringIO()
            while interrupt_fn():
                s=fp.read(1024)
                if not s:
                    break
                sio.write(s)
                p.feed(s)
            item.image = p.close()
            try:
                import pyexiv2
                im=pyexiv2.ImageMetadata.from_buffer(sio.getvalue())
                im.read()
                orient={'Orientation':im['Exif.Image.Orientation'].value}
            except:
                orient={}
            item.image=imagemanip.orient_image(item.image,orient)
            return True
        except:
            print 'Failed to retrieve fullsize image for',item
            item.image=False
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print tb_text
            return False

    def get_file_stream(self,item):
        'return a stream read the entire photo file from the source (as binary stream)'
        return urllib2.urlopen(item.imageurl)

    def write_file_data(self,dest_item,src_stream):
        'write the entire photo file (as a stream) to the source (as binary stream)'
        pass

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
        if settings.overlay_show_date:
            if item.meta and 'DateUploaded' in item.meta:
                if details and not details.endswith('\n'):
                    details+='\n'
                val=item.meta['DateUploaded']
                details+='Upload: '+str(val)
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
        if details and not details.endswith('\n'):
            details+='\n'
        if item.meta and 'DateUploaded' in item.meta:
            val=item.meta['DateUploaded']
            details+='Uploaded: '+str(val)
        if details and not details.endswith('\n'):
            details+='\n'
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
        val=viewsupport.get_speed_str(item)
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


baseobjects.register_collection('FLICKR',FlickrCollection)
