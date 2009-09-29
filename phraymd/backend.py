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

maemo=False

##standard imports
import cPickle
import gobject
import gio
import gtk
import Image
import ImageFile
import threading
import os
import time
import exif
import datetime
import bisect

##phraymd imports
import settings
import imageinfo
import imagemanip
import monitor
import pluginmanager

def del_view_item(view,browser,item):
    browser.lock.acquire()
    view.del_item(item)
    browser.lock.release()


class WorkerJob:
    'Base class for jobs'
    priority=0
    def __init__(self,name=''):
        self.priority=WorkerJob.priority
        self.state=False
        self.name=name
        WorkerJob.priority+=1

    def __nonzero__(self):
        return self.state

    def setevent(self):
        self.state=True

    def unsetevent(self):
        self.state=False

    def __call__(self,jobs,collection,view,browser):
        'subclasses should override this'
        return None


class WorkerJobCollection(dict):
    def __init__(self):
        self.collection=[
            WorkerJob('QUIT'),
            ThumbnailJob(),
            RegisterJobJob(),
            BuildViewJob(),
            MapImagesJob(),
            SelectionJob(),
            EditMetaDataJob(),
            SaveCollectionJob(),
            LoadCollectionJob(),
            RecreateThumbJob(),
            ReloadMetadataJob(),
            CollectionUpdateJob(),
            VerifyImagesJob(),
            WalkDirectoryJob(),
            WalkSubDirectoryJob(),
            SaveViewJob(),
            DirectoryUpdateJob(),
            MakeThumbsJob()
            ]
        for i in range(len(self.collection)):
            self[self.collection[i].name]=self.collection[i]

    def register_job(self,job_class,before_job='BUILDVIEW'):
        ##todo: really shouldn't do this while a job is in progress since jobs frequently access the collection using ishighestpriority
        job_ind=len(self.collection)
        for i in range(job_ind):
            if before_job==self.collection[i].name:
                job_ind=i
                break
        job=job_class()
        self.collection.insert(job_ind,job)
        self[job.name]=self.collection[job_ind]

    def deregister_job(self,job_name):
        ##todo: should wait until no job is running
        job_class=None
        for i in range(len(self.collection)):
            if self.collection[i].name==job_name:
                job_class=self.collection[i].__class__
                del self.collection[i]
                break
        del self[job_name]
        return job_class

    def ishighestpriority(self,job):
        for j in self.collection[0:job.priority]:
            if j.state:
                return False
        return True

    def gethighest(self):
        for j in self.collection:
            if j.state:
                return j
        return None



class ThumbnailJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'THUMBNAIL')
        self.queue_onscreen=[]
        self.queue_fore=[]
        self.queue_back=[]
        self.memthumbs=[]


    def __call__(self,jobs,collection,view,browser):
        cu_job=jobs['COLLECTIONUPDATE']
        cu_job.queue=[]
        cu_job.unsetevent()
        i=0
        while jobs.ishighestpriority(self) and len(self.queue_onscreen)>0:
            item=self.queue_onscreen.pop(0)
            if item.thumb:
                continue
            if not imagemanip.load_thumb(item):
                if not item.cannot_thumb and not imagemanip.has_thumb(item):
                    cu_job.setevent()
                    cu_job.queue.append(item)
                    continue
            i+=1
            if i%20==0:
                gobject.idle_add(browser.redraw_view)
        if len(self.queue_onscreen)==0:
            gobject.idle_add(browser.redraw_view)
            self.unsetevent()


class RegisterJobJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'REGISTERJOB')
        self.register_queue=[]
        self.deregister_queue=[]

    def __call__(self,jobs,collection,view,browser):
        while jobs.ishighestpriority(self) and len(self.deregister_queue)+len(self.register_queue)>0:
            if len(self.deregister_queue)>0:
                j=self.deregister_queue.pop(0)
                job_class=jobs.deregister_job(j)
                gobject.idle_add(pluginmanager.mgr.callback,'plugin_job_deregistered',job_class)
            if len(self.register_queue)>0:
                j=self.register_queue.pop(0)
                jobs.register_job(j)
                gobject.idle_add(pluginmanager.mgr.callback,'plugin_job_registered',j)
            print 'register job'
        print 'register job done'
        if len(self.deregister_queue)+len(self.register_queue)==0:
            self.unsetevent()


class CollectionUpdateJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'COLLECTIONUPDATE')
        self.queue=[]

    def __call__(self,jobs,collection,view,browser):
        while len(self.queue)>0 and jobs.ishighestpriority(self):
            item=self.queue.pop(0)
            if item.meta==None:
                if view.del_item(item):
                    imagemanip.load_metadata(item)
                    view.add_item(item)
                    gobject.idle_add(browser.refresh_view)
            if not imagemanip.has_thumb(item):
                imagemanip.make_thumb(item)
                gobject.idle_add(browser.refresh_view)
        if len(self.queue)==0:
            self.unsetevent()


class RecreateThumbJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'RECREATETHUMB')
        self.queue=[]

    def __call__(self,jobs,collection,view,browser):
        while len(self.queue)>0 and jobs.ishighestpriority(self):
            gobject.idle_add(browser.update_status,1.0/(1+len(self.queue)),'Recreating thumbnails')
            item=self.queue.pop(0)
            if item.meta==None:
                browser.lock.acquire()
                if view.del_item(item):
                    imagemanip.load_metadata(item)
                    view.add_item(item)
                browser.lock.release()
            if item.meta!=None:
                imagemanip.make_thumb(item,None,True) ##force creation of thumbnail (3rd arg = True)
                imagemanip.load_thumb(item)
                gobject.idle_add(browser.refresh_view)
        if len(self.queue)==0:
            gobject.idle_add(browser.update_status,2.0,'Recreating thumbnails done')
            self.unsetevent()


class ReloadMetadataJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'RELOADMETADATA')
        self.queue=[]

    def __call__(self,jobs,collection,view,browser):
        while len(self.queue)>0 and jobs.ishighestpriority(self):
            gobject.idle_add(browser.update_status,1.0/(1+len(self.queue)),'Reloading metadata')
            item=self.queue.pop(0)
            browser.lock.acquire()
            if view.del_item(item):
                item.meta=None
                imagemanip.load_metadata(item)
                print 'loaded metadata',item
                view.add_item(item)
            browser.lock.release()
#            if item.meta!=None:
#                imagemanip.make_thumb(item)
#                imagemanip.load_thumb(item)
#                gobject.idle_add(browser.refresh_view)
        if len(self.queue)==0:
            gobject.idle_add(browser.update_status,2.0,'Reloading metadata')
            self.unsetevent()


class LoadCollectionJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'LOADCOLLECTION')
        self.pos=0
        self.monitor=None
        self.collection_file=''

    def __call__(self,jobs,collection,view,browser):
        if settings.active_collection!=None:
            print 'SAVING CURRENTLY OPEN COLLECTION AND DISCONNECTING MONITOR BEOFRE LOADING'
            self.monitor.stop(collection.image_dirs[0])
            savejob=SaveCollectionJob()
            savejob(jobs,collection,view,browser)
            browser.lock.acquire()
            collection.empty()
            del view[:] ##todo: send plugin notification?
            browser.lock.release()
            settings.active_collection=None
            collection.filename=None
        print 'ABOUT TO LOAD',self.collection_file
        if not self.collection_file:
            self.collection_file=settings.active_collection_file
        print 'ABOUT TO LOAD2',self.collection_file
        browser.lock.acquire()
        if collection.load(self.collection_file):
            settings.active_collection=collection
            settings.active_collection_file=self.collection_file
            if os.path.exists(collection.image_dirs[0]):
                self.monitor.start(collection.image_dirs[0])
                jobs['BUILDVIEW'].setevent()
                jobs['WALKDIRECTORY'].setevent()
            pluginmanager.mgr.callback('t_collection_loaded') ##todo: plugins need to know if collection on/offline?
        else:
            settings.active_collection=None
            settings.action_collection_file=''
        browser.lock.release()
        self.unsetevent()
        self.collection_file=''


class SaveCollectionJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'SAVECOLLECTION')

    def __call__(self,jobs,collection,view,browser):
        print 'saving'
        collection.save()
        self.unsetevent()


class WalkDirectoryJob(WorkerJob):
    '''this walks the collection directory adding new items the collection (but not the view)'''
    def __init__(self):
        WorkerJob.__init__(self,'WALKDIRECTORY')
        self.collection_walker=None
        self.notify_items=[]
        self.done=False

    def __call__(self,jobs,collection,view,browser):
        self.last_update_time=time.time()
        try:
            if not self.collection_walker:
                scan_dir=collection.image_dirs[0]
                self.collection_walker=os.walk(scan_dir)
        except StopIteration:
            self.notify_items=[]
            self.collection_walker=None
            self.unsetevent()
            print 'aborted directory walk'
            return
        print 'starting directory walk'
        while jobs.ishighestpriority(self):
            try:
                root,dirs,files=self.collection_walker.next()
            except StopIteration:
                self.done=True
                break
            i=0
            while i<len(dirs):
                if dirs[i].startswith('.'):
                    dirs.pop(i)
                else:
                    i+=1

            gobject.idle_add(browser.update_status,-1,'Scanning for new images')
            for p in files: #may need some try, except blocks
                r=p.rfind('.')
                if r<=0:
                    continue
                fullpath=os.path.normcase(os.path.join(root, p))
                ifile=gio.File(fullpath)
                info=ifile.query_info(gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE)
                mimetype=info.get_content_type()
                if not mimetype.lower().startswith('image'):
                    print 'invalid mimetype',fullpath,mimetype
                    continue
                mtime=os.path.getmtime(fullpath)
                st=os.stat(fullpath)
                if os.path.isdir(fullpath):
                    print '*** WALK DIR: ITEM IS A DIRECTORY!!!***'
                    continue
                item=imageinfo.Item(fullpath,mtime)
                if collection.find(item)<0:
                    self.notify_items.append(item)
            # once we have found enough items add to collection and notify browser
            if time.time()>self.last_update_time+1.0 or len(self.notify_items)>100:
                self.last_update_time=time.time()
                browser.lock.acquire()
                for item in self.notify_items:
                    collection.add(item)
                browser.lock.release()
                gobject.idle_add(browser.refresh_view)
                self.notify_items=[]
        if self.done:
            print 'walk directory done'
            gobject.idle_add(browser.refresh_view)
            gobject.idle_add(browser.update_status,2,'Search complete')
            if self.notify_items:
                browser.lock.acquire()
                for item in self.notify_items:
                    collection.add(item)
                browser.lock.release()
                gobject.idle_add(browser.refresh_view)
            self.notify_items=[]
            self.collection_walker=None
            self.unsetevent()
            pluginmanager.mgr.callback('t_collection_modify_complete_hint')
            jobs['VERIFYIMAGES'].setevent()
        else:
            print 'pausing directory walk'


class WalkSubDirectoryJob(WorkerJob):
    '''this walks a sub-folder in the collection directory adding new items to both view and collection'''
    def __init__(self):
        WorkerJob.__init__(self,'WALKSUBDIRECTORY')
        self.collection_walker=None
        self.notify_items=[]
        self.done=False
        self.sub_dir=''

    def __call__(self,jobs,collection,view,browser):
        self.last_update_time=time.time()
        try:
            if not self.collection_walker:
                scan_dir=self.sub_dir
                self.collection_walker=os.walk(scan_dir)
        except StopIteration:
            print 'aborted subdirectory walk'
            self.notify_items=[]
            self.collection_walker=None
            self.unsetevent()
            return
        print 'starting subdirectory walk'
        while jobs.ishighestpriority(self):
            try:
                root,dirs,files=self.collection_walker.next()
            except StopIteration:
                self.done=True
                break
            i=0
            while i<len(dirs):
                if dirs[i].startswith('.'):
                    dirs.pop(i)
                else:
                    i+=1
            gobject.idle_add(browser.update_status,-1,'Scanning for new images')
            for p in files: #may need some try, except blocks
                r=p.rfind('.')
                if r<=0:
                    continue
                fullpath=os.path.normcase(os.path.join(root, p))
                ifile=gio.File(fullpath)
                info=ifile.query_info(gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE)
                mimetype=info.get_content_type()
                if not mimetype.lower().startswith('image'):
                    print 'invalid mimetype',fullpath,mimetype
                    continue
                mtime=os.path.getmtime(fullpath)
                st=os.stat(fullpath)
                if os.path.isdir(fullpath):
                    print '*** WALK DIR: ITEM IS A DIRECTORY!!!***'
                    continue
                item=imageinfo.Item(fullpath,mtime)
                if collection.find(item)<0:
                    browser.lock.acquire()
                    collection.add(item)
                    browser.lock.release()
                    del_view_item(view,browser,item)
                    imagemanip.load_metadata(item) ##todo: check if exists already
                    browser.lock.acquire()
                    view.add_item(item)
                    browser.lock.release()
                    gobject.idle_add(browser.refresh_view)
        if self.done:
            print 'walk subdirectory done'
            gobject.idle_add(browser.refresh_view)
            gobject.idle_add(browser.update_status,2,'Search complete')
            if self.notify_items:
                browser.lock.acquire()
                for item in self.notify_items:
                    collection.add(item)
                browser.lock.release()
                gobject.idle_add(browser.refresh_view)
            self.notify_items=[]
            self.collection_walker=None
            self.unsetevent()
            pluginmanager.mgr.callback('t_collection_modify_complete_hint')
        else:
            print 'pausing subdirectory walk'


def parse_filter_text(text):
    ch_loc=0
    filters=[]
    while 0<=ch_loc<len(text):
        i=text[ch_loc:].find(' ')
        j=text[ch_loc:].find('"')
        if i<j:
            filters.append(text[ch_loc:i])
            ch_loc=i+1
        else:
            k=ch_loc
            ch_loc=text[ch_loc:].find('"')
            if ch_loc>=0:
                ch_loc+=1
                filters.append(text[k:ch_loc])
    return filters


class BuildViewJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'BUILDVIEW')
        self.pos=0
        self.cancel=False
        self.sort_key='Date Last Modified'
        self.filter_text=''
        self.superset=None

    def cancel_job(self):
        self.cancel=True

    def __call__(self,jobs,collection,view,browser):
        i=self.pos
        browser.lock.acquire()
        if i==0:
            view.key_cb=imageinfo.sort_keys[self.sort_key]
            view.filters=None
            filter_text=self.filter_text.strip()
            if filter_text.startswith('lastview&'):
                filter_text=filter_text[9:]
                self.superset=view.copy()
            else:
                self.superset=collection
            if filter_text.strip():
                view.set_filter(filter_text)
            else:
                view.clear_filter(filter_text)
            del view[:] ##todo: create a view method to empty the view
            pluginmanager.mgr.callback('t_view_emptied')
            gobject.idle_add(browser.update_view)
        lastrefresh=i
        browser.lock.release()
        while i<len(self.superset) and jobs.ishighestpriority(self) and not self.cancel:
            item=self.superset(i)
            if item.meta!=None:
                browser.lock.acquire()
                view.add_item(item)
                browser.lock.release()
                if i-lastrefresh>200:
                    lastrefresh=i
                    gobject.idle_add(browser.refresh_view)
                    gobject.idle_add(browser.update_status,1.0*i/len(self.superset),'Rebuilding image view - %i of %i'%(i,len(self.superset)))
            i+=1
        if i<len(self.superset) and not self.cancel:
            self.pos=i
        else:
            self.pos=0
            self.cancel=False
            self.unsetevent()
            gobject.idle_add(browser.refresh_view)
            gobject.idle_add(browser.update_status,2,'View rebuild complete')
            gobject.idle_add(browser.post_build_view)
            pluginmanager.mgr.callback('t_collection_modify_complete_hint')


class MapImagesJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'MAPIMAGES')
        self.pos=0
        self.cancel=False
        self.limit_to_view=True
        self.update_callback=None
        self.pblist=[]
        self.region=(0,0,0,0)
        self.max_images=50
        self.im_count=0
        self.restart=False

    def __call__(self,jobs,collection,view,browser):
        i=self.pos
        print 'map job',i
        if self.limit_to_view:
            listitems=view
        else:
            listitems=collection
        while i<len(listitems) and jobs.ishighestpriority(self) and self.im_count<self.max_images and not self.cancel:
            item=listitems(i)
            if imageinfo.item_in_region(item,*self.region):
                imagemanip.load_thumb(item)
                if item.thumb:
                    pb=imagemanip.scale_pixbuf(item.thumb,40)
                    self.pblist.append((item,pb))
                    self.im_count+=1
            if self.update_callback and i%100==0:
                gobject.idle_add(self.update_callback,self.pblist)
                self.pblist=[]
            i+=1
        if i<len(listitems) and self.im_count<self.max_images and not self.cancel:
            self.pos=i
        else:
            gobject.idle_add(self.update_callback,self.pblist)
            self.pblist=[]
            self.pos=0
            self.cancel=False
            if not self.restart:
                self.unsetevent()
            self.restart=False
            self.im_count=0
        print 'map job end',i



SELECT=0
DESELECT=1
INVERT_SELECT=2

class SelectionJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'SELECTION')
        self.pos=0
        self.cancel=False
        self.limit_to_view=True
        self.mode=SELECT

    def __call__(self,jobs,collection,view,browser):
        i=self.pos
        select=self.mode==SELECT
        if self.limit_to_view:
            listitems=view
        else:
            listitems=collection
        while i<len(listitems) and jobs.ishighestpriority(self) and not self.cancel:
            item=listitems(i)
            prev=item.selected
            if self.mode==INVERT_SELECT:
                item.selected=not prev
            else:
                item.selected=select
            collection.numselected+=item.selected-prev
            if i%100==0:
                gobject.idle_add(browser.update_status,1.0*i/len(listitems),'Selecting images - %i of %i'%(i,len(listitems)))
            i+=1
        if i<len(listitems) and not self.cancel:
            self.pos=i
        else:
            gobject.idle_add(browser.update_status,1.0*i/len(listitems),'Selecting images - %i of %i'%(i,len(listitems)))
            gobject.idle_add(browser.refresh_view)
            self.pos=0
            self.cancel=False
            self.unsetevent()

ADD_KEYWORDS=1
REMOVE_KEYWORDS=2
TOGGLE_KEYWORDS=3
RENAME_KEYWORDS=4
CHANGE_META=5

EDIT_COLLECTION=1
EDIT_VIEW=2
EDIT_SELECTION=3

class EditMetaDataJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'EDITMETADATA')
        self.pos=0
        self.cancel=False
        self.mode=0
        self.scope=EDIT_SELECTION
        self.keyword_string=''
        self.meta=None

    def __call__(self,jobs,collection,view,browser):
        i=self.pos
        items=collection if self.scope==EDIT_COLLECTION else view
        if self.mode==ADD_KEYWORDS:
            tags=exif.tag_split(self.keyword_string)
            tags_lower=[t.lower() for t in tags]
            while i<len(items) and jobs.ishighestpriority(self) and not self.cancel:
                item=items(i)
                if (self.scope!=EDIT_SELECTION or item.selected) and item.meta!=None and item.meta!=False:
                    meta=item.meta.copy()
                    try:
                        tags_kw=meta['Keywords']
                    except:
                        tags_kw=[]
                    tags_kw_lower=[t.lower() for t in tags_kw]
                    new_tags=list(tags_kw)
                    for j in range(len(tags)):
                        if tags_lower[j] not in tags_kw_lower:
                            new_tags.append(tags[j])
                    if len(new_tags)==0:
                        del meta['Keywords']
                    else:
                        meta['Keywords']=new_tags
                    item.set_meta(meta)
                if i%100==0:
                    gobject.idle_add(browser.update_status,1.0*i/len(items),'Selecting images - %i of %i'%(i,len(items)))
                i+=1
        if self.mode==RENAME_KEYWORDS:
            tags=exif.tag_split(self.keyword_string)
            find_tag=tags[0].lower()
            repl_tag=tags[1]
            while i<len(items) and jobs.ishighestpriority(self) and not self.cancel:
                item=items(i)
                if (self.scope!=EDIT_SELECTION or item.selected) and item.meta!=None and item.meta!=False:
                    meta=item.meta.copy()
                    try:
                        tags_kw=meta['Keywords']
                    except:
                        tags_kw=[]
                    tags_kw_lower=[t.lower() for t in tags_kw]
                    new_tags=list(tags_kw)
                    for j in range(len(tags_kw_lower)):
                        if find_tag==tags_kw_lower[j]:
                            new_tags[j]=repl_tag
                    if new_tags!=list(tags_kw):
                        if len(new_tags)==0 and 'Keywords' in meta:
                            del meta['Keywords']
                        else:
                            meta['Keywords']=new_tags
                        item.set_meta(meta)
                if i%100==0:
                    gobject.idle_add(browser.update_status,1.0*i/len(items),'Selecting images - %i of %i'%(i,len(items)))
                i+=1
        if self.mode==TOGGLE_KEYWORDS:
            tags=exif.tag_split(self.keyword_string)
            while i<len(items) and jobs.ishighestpriority(self) and not self.cancel:
                item=items(i)
                if (self.scope!=EDIT_SELECTION or item.selected) and item.meta!=None and item.meta!=False:
                    imageinfo.toggle_tags(item,tags)
                if i%100==0:
                    gobject.idle_add(browser.update_status,1.0*i/len(items),'Selecting images - %i of %i'%(i,len(items)))
                i+=1
        if self.mode==REMOVE_KEYWORDS:
            tags=exif.tag_split(self.keyword_string)
            tags_lower=[t.lower() for t in tags]
            while i<len(items) and jobs.ishighestpriority(self) and not self.cancel:
                item=items(i)
                if (self.scope!=EDIT_SELECTION or item.selected) and item.meta!=None and item.meta!=False:
                    meta=item.meta.copy()
                    try:
                        tags_kw=list(meta['Keywords'])
                        tags_kw_lower=[t.lower() for t in tags_kw]
                        new_tags=[]
                        for j in range(len(tags_kw)):
                            if tags_kw_lower[j] not in tags_lower:
                                new_tags.append(tags_kw[j])
                        if len(new_tags)==0:
                            del meta['Keywords']
                        else:
                            meta['Keywords']=new_tags
                        item.set_meta(meta)
                    except:
                        pass
                if i%100==0:
                    gobject.idle_add(browser.update_status,1.0*i/len(items),'Removing keywords - %i of %i'%(i,len(items)))
                i+=1

        if self.mode==CHANGE_META:
            while i<len(items) and jobs.ishighestpriority(self) and not self.cancel:
                item=items(i)
                if (self.scope!=EDIT_SELECTION or item.selected) and item.meta!=None and item.meta!=False:
                    for k,v in self.meta.iteritems():
                        item.set_meta_key(k,v)
                if i%100==0:
                    gobject.idle_add(browser.update_status,1.0*i/len(items),'Setting keywords - %i of %i'%(i,len(items)))
                i+=1

        if i<len(items) and not self.cancel:
            self.pos=i
        else:
            gobject.idle_add(browser.update_status,2.0,'Metadata edit complete - %i of %i'%(i,len(items)))
            gobject.idle_add(browser.refresh_view)
            self.pos=0
            self.cancel=False
            pluginmanager.mgr.callback('t_collection_modify_complete_hint')
            self.unsetevent()


class SaveViewJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'SAVEVIEW')
        self.pos=0
        self.cancel=False
        self.selected_only=False
        self.save=True

    def __call__(self,jobs,collection,view,browser):
        i=self.pos
        listitems=view
        while i<len(listitems) and jobs.ishighestpriority(self) and not self.cancel:
            item=listitems(i)
            if not self.selected_only or listitems(i).selected:
                if self.save:
                    if item.meta_changed:
                        imagemanip.save_metadata(item)
                        gobject.idle_add(browser.refresh_view)
                        gobject.idle_add(browser.update_status,1.0*i/len(listitems),'Saving changed images in view - %i of %i'%(i,len(listitems)))
                else:
                    if item.meta_changed:
                        try:
                            orient=item.meta['Orientation']
                        except:
                            orient=None
                        try:
                            orient_backup=item.meta_backup['Orientation']
                        except:
                            orient_backup=None
                        item.meta_revert()
                        ##todo: need to recreate thumb if orientation changed
                        if orient!=orient_backup:
                            item.thumb=None
                            job=jobs['RECREATETHUMB']
                            job.queue.append(item)
                            job.setevent()
                        gobject.idle_add(browser.refresh_view)
                        gobject.idle_add(browser.update_status,1.0*i/len(listitems),'Reverting images in view - %i of %i'%(i,len(listitems)))
            if i%100==0:
                if self.save:
                    gobject.idle_add(browser.update_status,1.0*i/len(listitems),'Saving changed images in view - %i of %i'%(i,len(listitems)))
                else:
                    gobject.idle_add(browser.update_status,1.0*i/len(listitems),'Reverting images in view - %i of %i'%(i,len(listitems)))
            i+=1
        if i<len(listitems) and not self.cancel:
            self.pos=i
        else:
            gobject.idle_add(browser.update_status,2.0,'Saving images complete')
            gobject.idle_add(browser.refresh_view)
            self.pos=0
            self.cancel=False
            self.unsetevent()


class VerifyImagesJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'VERIFYIMAGES')
        self.countpos=0

    def __call__(self,jobs,collection,view,browser):
        i=self.countpos  ##todo: make sure this gets initialized
        while i<len(collection) and jobs.ishighestpriority(self):
            item=collection[i]
            if i%20==0:
                gobject.idle_add(browser.update_status,1.0*i/len(collection),'Verifying images in collection - %i of %i'%(i,len(collection)))
            if item.meta==None:
                del_view_item(view,browser,item)
                imagemanip.load_metadata(item) ##todo: check if exists already
                browser.lock.acquire()
                view.add_item(item)
                browser.lock.release()
                gobject.idle_add(browser.refresh_view)
            ##print 'verifying',item.filename,os.path.isdir(item.filename)
            if not os.path.exists(item.filename) or os.path.isdir(item.filename) or item.filename!=os.path.normcase(item.filename):
                browser.lock.acquire()
                collection.numselected-=collection[i].selected
                del collection[i]
                browser.lock.release()
                del_view_item(view,browser,item)
                gobject.idle_add(browser.refresh_view)
                ##TODO: Notify viewer/browser of update
                continue
            mtime=os.path.getmtime(item.filename)
            if mtime!=item.mtime:
                del_view_item(view,browser,item)
                item.mtime=mtime
                item.image=None
                item.qview=None
                item.qview_size=None
                imagemanip.load_metadata(item)
                item.thumb=None
                item.thumburi=None
                browser.lock.acquire()
                view.add_item(item)
                browser.lock.release()
                gobject.idle_add(browser.refresh_view)
            i+=1
        self.countpos=i
        if i>=len(collection):
            self.unsetevent()
            self.countpos=0
            gobject.idle_add(browser.update_status,2,'Verification complete')
            print 'image verification complete'
            pluginmanager.mgr.callback('t_collection_modify_complete_hint')
            jobs['MAKETHUMBS'].setevent()


class MakeThumbsJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'MAKETHUMBS')
        self.countpos=0

    def __call__(self,jobs,collection,view,browser):
        i=self.countpos  ##todo: make sure this gets initialized
        while i<len(collection) and jobs.ishighestpriority(self):
            item=collection[i]
            if i%20==0:
                gobject.idle_add(browser.update_status,1.0*i/len(collection),'Validating and creating missing thumbnails - %i of %i'%(i,len(collection)))
            if not imagemanip.has_thumb(item):
                imagemanip.make_thumb(item)
                gobject.idle_add(browser.refresh_view)
                gobject.idle_add(browser.update_status,1.0*i/len(collection),'Validating and creating missing thumbnails - %i of %i'%(i,len(collection)))
            i+=1
        self.countpos=i
        if i>=len(collection):
            self.unsetevent()
            self.countpos=0
            gobject.idle_add(browser.update_status,2,'Thumbnailing complete')


class DirectoryUpdateJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'DIRECTORYUPDATE')
        self.queue=[]
        self.deferred=[]
        self.deflock=threading.Lock()

    def __call__(self,jobs,collection,view,browser):
        #todo: make sure job.queue has been initialized
        #todo: acquire and release collection lock
        while jobs.ishighestpriority(self) and len(self.queue)>0:
            fullpath,action=self.queue.pop(0)
            if action in ('DELETE','MOVED_FROM'):
                print 'deleting',fullpath
                if not os.path.exists(fullpath):
                    browser.lock.acquire()
                    j=collection.find([fullpath])
                    print 'delete item coll index',j
                    if j>=0:
                        item=collection[j]
                        collection.numselected-=collection[j].selected
                        del collection[j]
                        view.del_item(item)
                    browser.lock.release()
                    gobject.idle_add(browser.refresh_view)
            if action in ('MOVED_TO','MODIFY','CREATE'):
                if os.path.exists(fullpath) and os.path.isfile(fullpath):
                    ifile=gio.File(fullpath)
                    info=ifile.query_info(gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE)
                    mimetype=info.get_content_type()
                    if not mimetype.startswith('image'): ##todo: move this to the else clause below
                        continue
                    i=collection.find([fullpath])
                    if i>=0:
                        if os.path.getmtime(fullpath)!=collection[i].mtime:
                            item=collection[i]
                            browser.lock.acquire()
                            view.del_item(item)
                            browser.lock.release()
                            item.mtime=os.path.getmtime(fullpath)
                            imagemanip.load_metadata(item)
                            imagemanip.make_thumb(item)
                            browser.lock.acquire()
                            view.add_item(item)
                            browser.lock.release()
                            gobject.idle_add(browser.refresh_view)
                    else:
                        item=imageinfo.Item(fullpath,os.path.getmtime(fullpath))
                        imagemanip.load_metadata(item)
                        browser.lock.acquire()
                        collection.add(item)
                        view.add_item(item)
                        browser.lock.release()
                        if not imagemanip.has_thumb(item):
                            imagemanip.make_thumb(item)
                        gobject.idle_add(browser.refresh_view)
                if os.path.exists(fullpath) and os.path.isdir(fullpath):
                    if action=='MOVED_TO':
                        job=jobs['WALKSUBDIRECTORY']
                        job.sub_dir=fullpath
                        job.setevent()

        if len(self.queue)==0:
            pluginmanager.mgr.callback('t_collection_modify_complete_hint')
            self.unsetevent()



class Worker:
    def __init__(self,browser):
        self.collection=imageinfo.Collection([])
        self.view_key=imageinfo.get_mtime
        self.view=imageinfo.Index(self.view_key,[])
        self.jobs=WorkerJobCollection()
        self.event=threading.Event()
        self.browser=browser
        self.lock=threading.Lock()
        self.exit=False
        self.thread=threading.Thread(target=self._loop)
        self.dirtimer=None ##threading.Timer(2,self.request_dir_update)

    def start(self):
        self.thread.start()

    def _loop(self):
        self.monitor=monitor.Monitor(self.directory_change_notify)
        self.jobs['LOADCOLLECTION'].setevent()
        self.jobs['LOADCOLLECTION'].monitor=self.monitor
        while 1:
            if not self.jobs.gethighest():
                self.event.clear()
                self.event.wait()
            if self.jobs['QUIT']:
                if len(self.collection.image_dirs)>0:
                    self.monitor.stop(self.collection.image_dirs[0])
                if self.dirtimer!=None:
                    self.dirtimer.cancel()
                savejob=SaveCollectionJob()
                savejob(self.jobs,self.collection,self.view,self.browser)
                print 'end worker loop'
                return
            job=self.jobs.gethighest()
            if job:
                job(self.jobs,self.collection,self.view,self.browser)

    def deferred_dir_update(self):
        print 'deferred dir event'
        job=self.jobs['DIRECTORYUPDATE']
        job.deflock.acquire()
        for j in job.deferred:
            job.queue.append(j)
        del job.deferred[:]
        self.dirtimer=None
        job.deflock.release()
        job.setevent()
        self.event.set()

    def directory_change_notify(self,path,action,isdir):
        homedir=os.path.normpath(settings.active_collection.image_dirs[0])
        path=os.path.normcase(path)
        #ignore notifications on files in a hidden dir or not in the image dir
        if os.path.normpath(os.path.commonprefix([path,homedir]))!=homedir:
            print 'change_notify invalid',path,action
            return
        ppath=path
        while ppath!=homedir:
            ppath,name=os.path.split(ppath)
            ppath=os.path.normpath(ppath)
            if name.startswith('.') or name=='':
                print 'change_notify invalid',path,action
                return
        if isdir:
            print 'dir action',path,action
            if action in ('MOVED_FROM','DELETE'):
                #queue a verify job since we won't get individual image removal notifications
                self.jobs['VERIFYIMAGES'].countpos=0
                self.jobs['VERIFYIMAGES'].setevent()
                return
        #valid file or a moved directory, so queue the update
        #(modify and create notifications are
        #only processed after some delay because many events may be generated
        #before the files are closed)
        ##todo: respond to file close events instead of modify/create events??
        job=self.jobs['DIRECTORYUPDATE']
        job.deflock.acquire()
        if self.dirtimer!=None:
            self.dirtimer.cancel()
        self.dirtimer=threading.Timer(3,self.deferred_dir_update)
        self.dirtimer.start()
        job.deferred.append((path,action))
        job.deflock.release()
        print 'file event',action,' on',path

    def save_collection(self,filename):
        self.jobs['SAVECOLLECTION'].setevent()
        self.event.set()

    def load_collection(self,filename):
        print 'got request to load collection'
        loadjob=self.jobs['LOADCOLLECTION']
        loadjob.collection_file=filename
        loadjob.setevent()
        self.event.set()

    def scan_and_verify(self):
        self.jobs['WALKDIRECTORY'].setevent()
        self.event.set()

    def quit(self):
        self.jobs['QUIT'].setevent()
        self.event.set()
        while self.thread.isAlive():
            time.sleep(0.1)

    def queue_job(self,job):
        self.jobs[job_name].setevent()
        self.event.set()

    def request_map_images(self,region,callback):
        job=self.jobs['MAPIMAGES']
        job.restart=True
        job.cancel=True
        job.region=region
        job.update_callback=callback
        job.setevent()
        self.event.set()

    def register_job(self,job_class):
        job=self.jobs['REGISTERJOB']
        job.register_queue.append(job_class)
        job.setevent()
        self.event.set()

    def deregister_job(self,job_name):
        job=self.jobs['REGISTERJOB']
        job.deregister_queue.append(job_name)
        job.setevent()
        self.event.set()

    def request_thumbnails(self,itemlist):
        job=self.jobs['THUMBNAIL']
        ## todo: should lock before changing queue_onscreen (most likely unnecessary)
        job.queue_onscreen=itemlist
        job.setevent()
        self.event.set()

    def recreate_thumb(self,item):
        job=self.jobs['RECREATETHUMB']
        job.queue.append(item)
        job.setevent()
        self.event.set()

    def reload_metadata(self,item):
        job=self.jobs['RELOADMETADATA']
        if job.state:
            return False
        job.queue.append(item)
        job.setevent()
        self.event.set()

    def recreate_selected_thumbs(self):
        job=self.jobs['RECREATETHUMB']
        if job.state:
            return False
        job.queue[:]=self.view.get_selected_items()
        job.setevent()
        self.event.set()

    def reload_selected_metadata(self):
        job=self.jobs['RELOADMETADATA']
        job.queue[:]=self.view.get_selected_items()
        job.setevent()
        self.event.set()

    def select_all_items(self,mode=SELECT,view=True):
        job=self.jobs['SELECTION']
        if job.state:
            return False
        job.pos=0
        job.mode=mode
        job.limit_to_view=view
        job.setevent()
        self.event.set()
        return True

    def info_edit(self,meta):
        job=self.jobs['EDITMETADATA']
        if job.state:
            return False
        job.pos=0
        job.keyword_string=None
        job.meta=meta
        job.mode=CHANGE_META
        job.setevent()
        self.event.set()
        return True

    def keyword_edit(self,keyword_string,toggle=False,remove=False,replace=False,scope=EDIT_SELECTION):
        job=self.jobs['EDITMETADATA']
        if job.state:
            return False
        job.pos=0
        job.keyword_string=keyword_string
        job.scope=scope
        if toggle:
            job.mode=TOGGLE_KEYWORDS
        elif remove:
            job.mode=REMOVE_KEYWORDS
        elif replace:
            job.mode=RENAME_KEYWORDS
        else:
            job.mode=ADD_KEYWORDS
        job.setevent()
        self.event.set()
        return True

    def rebuild_view(self,sort_key,filter_text=''):
        job=self.jobs['BUILDVIEW']
        if job.state:
            job.cancel_job()
        job.sort_key=sort_key
        job.filter_text=filter_text
        job.setevent()
        self.event.set()

    def save_or_revert_view(self,save=True,selected_only=False):
        job=self.jobs['SAVEVIEW']
        if job.state:
            return False
        job.pos=0
        job.selected_only=selected_only
        job.save=save
        job.setevent()
        self.event.set()

