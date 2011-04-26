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


#TODO: Load desscriptive metadata and some exif data
#TODO: Write metadata changes to flickr
#TODO: Handle offline mode (can't view fullsize, can't write changes etc)
#TODO: Fix image sync
#TODO: Login authentication
#TODO: Image orientation


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
import simpleview

class LoadFlickrCollectionJob(backend.WorkerJob):
    def __init__(self,worker,collection,browser):
        backend.WorkerJob.__init__(self,'LOADFLICKRCOLLECTION',890,worker,collection,browser)
        self.pos=0
        self.full_rescan=False

    def __call__(self):
        jobs=self.worker.jobs
        jobs.clear(None,self.collection,self)
        collection=self.collection
#        log.info('Loading collection '+self.collection_file)
        gobject.idle_add(self.browser.update_status,0.66,'Loading Collection: %s'%(collection.name,))
        print 'OPENING COLLECTION',collection.id,collection.type
        if collection._open():
            pluginmanager.mgr.callback_collection('t_collection_loaded',self.collection)
            if self.full_rescan or len(collection)==0:
                self.worker.queue_job_instance(FlickrSyncJob(self.worker,self.collection,self.browser))
            self.worker.queue_job_instance(backend.BuildViewJob(self.worker,self.collection,self.browser))
            self.worker.queue_job_instance(backend.MakeThumbsJob(self.worker,self.collection,self.browser))
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
        jobs.clear(None,self.collection,self)
        collection=self.collection
        flickr_client=collection.flickr_client
        recently_updated=False
        if not self.started:
            self.page=1
            self.pages=1
            self.started=True
        new_time=time.time()
        while jobs.ishighestpriority(self) and self.page<=self.pages:
#            supported_extras='''description, license, date_upload, date_taken, owner_name, icon_server, original_format,
#                    last_update, geo, tags, machine_tags, o_dims, views, media, path_alias, url_sq, url_t, url_s, url_m,
#                    url_z, url_l, url_o'''
#            photos=flickr_client.people_getPhotos(user_id="me",page=page, extras='description,license,geo,tags,date_upload,date_taken,last_update,url_t,original_format')
            if recently_updated: ##TODO: This isn't going to work if recentlyUpdated doesn't report deleted images
                photos=flickr_client.people_recentlyUpdated(user_id="me",page=self.page, min_date=self.last_update_time, extras='description,license,geo,tags,date_upload,date_taken,last_update,url_s,url_o,original_format')
            else:
                photos=flickr_client.people_getPhotos(user_id="me",page=self.page, per_page=500, extras='description,license,geo,tags,date_upload,date_taken,last_update,url_s,url_o,original_format')
            gobject.idle_add(self.browser.update_status,1.0*(self.page-1)/self.pages,'Syncing with Flickr')
            photos=photos.find('photos')
            self.page=int(photos.attrib['page'])
            self.pages=int(photos.attrib['pages'])
            photodata=photos.findall('photo')
            for ph in photodata:
                uid=ph.attrib['id']
                print 'uid',uid
                item=baseobjects.Item(uid)
                ind=collection.find(item)
                if ind>=0:
                    item=collection[ind]
                item.secret=ph.attrib['secret']
                item.server=ph.attrib['server']
                meta={}
                meta['Title']=ph.attrib['title']
                d=ph.find('description')
                if d:
                    meta['ImageDescription']=d[0].text
                meta['License']=ph.attrib['license']
                meta['Keywords']=metadata.tag_split(ph.attrib['tags'])
                meta['DateTaken']=datetime.strptime(ph.attrib['datetaken'],datefmt) ##todo: assuming a time stamp, otherwise use datetime.strptime
                meta['DateUploaded']=datetime.fromtimestamp(float(ph.attrib['dateupload']))
                meta['DateModified']=datetime.fromtimestamp(float(ph.attrib['lastupdate']))
                meta['Mimetype']=ph.attrib['originalformat']
                item.thumburl=ph.attrib['url_s']
                item.imageurl=ph.attrib['url_o']
                if ind>=0:
                    item.init_meta(meta,self.collection)
                else:
                    self.collection.add(item,self.collection)
                gobject.idle_add(self.browser.resize_and_refresh_view,self.collection)
            self.page+=1
        if self.page>self.pages:
            collection.last_update_time=new_time
            gobject.idle_add(self.browser.update_status,2.0,'Syncing Complete')
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


class FlickrCollection(baseobjects.CollectionBase):
    '''defines a sorted collection of Items with
    callbacks to plugins when the contents of the collection change'''
    ##todo: do more plugin callbacks here instead of the job classes?
    type='FLICKR'
    type_descr='Flickr Account'
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
        self.sync_on_open=True #try to synchronize with Flickr after start up
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
        self.online=self.login()
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

    def login(self):
        '''
        initialize flickr client object and log into the flickr account
        '''
        self.flickr_client = flickrapi.FlickrAPI(self.api_key, self.api_secret)
        try:
            (self.token, self.frob) = self.flickr_client.get_token_part_one(perms='write')
            if not self.token:
                from phraymd import dialogs
                result=dialogs.prompt_dialog('Allow Flickr Access','phraymd has opened a Flickr application authentication page in your web browser. Please give phraymd access to your flickr account by accepting the prompt in your web browser. Press "Done" when complete',buttons=('_Done',),default=0)
            self.flickr_client.get_token_part_two((self.token, self.frob))
            login_resp=self.flickr_client.test_login()
            user=login_resp.find('user')
            self.login_username=user.find('username').text
            self.login_id=user.attrib['id']
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

    def upload_photo(self,item,album=None,preferences=None):
        try:
            ##TODO: update get_jpeg_or_png_image_file to use collection method get_file_data/get_image
            filename=imagemanip.get_jpeg_or_png_image_file(item,preferences.upload_size,preferences.metadata_strip)
            title=item.meta['Title']
            if not title:
                title=os.path.split(item.uid)[1]
            tags=item.meta['Keywords'] ##TODO: have to convert to space delimited
            description=item.meta['ImageDescription']
            privacy=item.meta['Privacy']
            public=1 if privacy==PRIVACY_PUBLIC else 0
            family=1 if privacy in [PRIVACY_FRIENDS,PRIVACY_FRIENDS_AND_FAMILY] else 0
            friends=1 if privacy in [PRIVACY_FAMILY,PRIVACY_FRIENDS_AND_FAMILY] else 0
            print 'uploading',item.uid,'with privacy',public,family,friends

            def progress_cb(progress,done):
                ##send notification
                pass
            photo_id=self.flickr_client.upload(filename=filename,title=title,description=description,tags=tags,
                is_public=public,is_family=family,is_friend=friends,callback=progress_cb)
            photo_id=photo_id.find('photoid').text

            if album[0]:
                photoset_id=album[1].attrib['id']
                self.flickr_client.photosets_addPhoto(photoset_id=photoset_id,photo_id=photo_id)

            if filename!=item.uid:
                os.remove(filename)
        except:
            import traceback, sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print 'Error on upload',tb_text

    def enumerate_source(self,interrupt_fn,recently_updated=False):
        '''
        get the list of items from the source
        and cache appropriately
        '''

        '''
        see also:
        flickr.photos.recentlyUpdated
            api_key (Required)
                Your API application key. See here for more details.
            min_date (Required)
                A Unix timestamp or any English textual datetime description indicating the date from which modifications should be compared.
            extras (Optional)
                A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: description, license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media, path_alias, url_sq, url_t, url_s, url_m, url_z, url_l, url_o
            per_page (Optional)
                Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.
            page (Optional)
                The page of results to return. If this argument is omitted, it defaults to 1.

        '''

        page=0
        pages=1
        while not interrupt_fn() and page<pages:
            supported_extras='''description, license, date_upload, date_taken, owner_name, icon_server, original_format,
                    last_update, geo, tags, machine_tags, o_dims, views, media, path_alias, url_sq, url_t, url_s, url_m,
                    url_z, url_l, url_o'''
#            photos=flickr_client.people_getPhotos(user_id="me",page=page, extras='description,license,geo,tags,date_upload,date_taken,last_update,url_t,original_format')
            new_time=time.time()
            if recently_updated: ##TODO: This isn't going to work if recentlyUpdated doesn't report deleted images
                photos=flickr_client.people_recentlyUpdated(user_id="me",page=page, min_date=self.last_update_time, extras='description,license,geo,tags,date_upload,date_taken,last_update,url_s,original_format')
            else:
                photos=flickr_client.people_getPhotos(user_id="me",page=page, extras='description,license,geo,tags,date_upload,date_taken,last_update,url_s,original_format')

            self.last_upate=time.time()
            photos=photos.find('photos')
            page=photos.page
            pages=photos.pages
            photodata=photocollections.findall('photo')
            for ph in photodata:
                uid=ph.id
                ##todo: most of these need to be converted to python types
                datefmt="%Y-%m-%d %H:%M:%S"
                item=baseobjects.Item(uid)
                item.secret=ph.secret
                item.server=ph.server
                item.meta['Title']=ph.title
                item.meta['ImageDescription']=ph.description
                item.meta['License']=ph.license
                item.meta['Keywords']=metadata.tag_split(ph.tags)
                item.meta['DateTaken']=datetime.strptime(ph.date_taken,datefmt) ##todo: assuming a time stamp, otherwise use datetime.strptime
                item.meta['DateUploaded']=datetime.fromtimestamp(ph.date_upload)
                item.meta['DateModified']=datetime.fromtimestamp(ph.last_update)
                item.thumburl=ph.url_s
                item.imageurl=ph.url_o
                item.meta['Mimetype']=ph.original_format
                self.add(item)
            self.last_update_time=time.time()

    def sync(self):
        '''
        Synchronize the cache with the online state of the flickr collection
        '''
        pass

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
            if len(self.items)>ind>0 and self.items[ind]==item:
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
    def copy_item(self,src_collection,src_item):
        'copy an item from another collection source'
        pass
    def delete_item(self,item):
        'remove the item from the underlying store'
        pass
    def load_thumbnail(self,item):
        'load the thumbnail from the local cache'
        return imagemanip.load_thumb(item)
    def has_thumbnail(self,item):
        return item.thumburi
    def make_thumbnail(self,item,interrupt_fn=None,force=False):
        'create a cached thumbnail of the image'
        if not force and item.thumburi:
            return True
        print 'creating thumb for ',item
        try:
            item.thumburi=os.path.join(self.thumbnail_cache_dir,item.uid)+'.jpg'
            print 'thumburi',item.thumburi,item.thumburl
            f=open(item.thumburi,'wb')
            f.write(urllib2.urlopen(item.thumburl).read())
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
        'collection will receive when item metadata has been changed'
        pass
    def load_metadata(self,item):
        'retrieve metadata for an item from the source'
        pass
#        result=self.flickr_client.photos_getInfo(item.uid)
#        result=self.flickr_client.photos_getExif(item.uid)
        # flickr.photos.getAllContexts
        # flickr.photos.getContactsPhotos
        # flickr.photos.getContactsPublicPhotos
        # flickr.photos.getContext
        # flickr.photos.getCounts
        # flickr.photos.getExif
        # flickr.photos.getFavorites
        # flickr.photos.getInfo
        # flickr.photos.getNotInSet
        # flickr.photos.getPerms
        # flickr.photos.getRecent
        # flickr.photos.getSizes
        # flickr.photos.getUntagged
        # flickr.photos.getWithGeoData
        # flickr.photos.getWithoutGeoData
    def write_metadata(self,item):
        'write metadata for an item to the source'
#        flickr.photos.setContentType
#        flickr.photos.setDates
#        flickr.photos.setMeta
#        flickr.photos.setPerms
#        flickr.photos.setSafetyLevel
#        flickr.photos.setTags
        pass
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
        pass
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
                details+='Uploaded: '+str(val)
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


baseobjects.register_collection('FLICKR',FlickrCollection)
