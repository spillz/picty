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

import cPickle
import gobject
import gnomevfs
import gtk
import Image
import ImageFile
import threading
import os
import time
import exif
import datetime
import bisect
import settings
import imageinfo
import imagemanip
import monitor

try:
    import gnome.ui
    import gnomevfs
    import pyexiv2
except:
    maemo=True

def del_view_item(view,browser,item):
    browser.lock.acquire()
    view.del_item(item)
    browser.lock.release()


class WorkerJob:
    'Base class for jobs'
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
    priority=0


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
                if not imagemanip.has_thumb(item):
                    cu_job.setevent()
                    cu_job.queue.append(item)
                    continue
            i+=1
            if i%20==0:
                gobject.idle_add(browser.redraw_view)
        if len(self.queue_onscreen)==0:
            gobject.idle_add(browser.redraw_view)
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
                    gobject.idle_add(browser.RefreshView)
            if not imagemanip.has_thumb(item):
                imagemanip.make_thumb(item)
                gobject.idle_add(browser.RefreshView)
        if len(self.queue)==0:
            self.unsetevent()

class RecreateThumbJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'RECREATETHUMB')
        self.queue=[]

    def __call__(self,jobs,collection,view,browser):
        while len(self.queue)>0 and jobs.ishighestpriority(self):
            gobject.idle_add(browser.UpdateStatus,1.0/(1+len(self.queue)),'Recreating thumbnails')
            item=self.queue.pop(0)
            if item.meta==None:
                browser.lock.acquire()
                if view.del_item(item):
                    imagemanip.load_metadata(item)
                    view.add_item(item)
                browser.lock.release()
            if item.meta!=None:
                imagemanip.make_thumb(item)
                imagemanip.load_thumb(item)
                gobject.idle_add(browser.RefreshView)
        if len(self.queue)==0:
            gobject.idle_add(browser.UpdateStatus,2.0,'Recreating thumbnails done')
            self.unsetevent()


class LoadCollectionJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'LOADCOLLECTION')
        self.pos=0

    def __call__2(self,jobs,collection,view,browser):
        del collection[:]
        collect.numselected=0
        del view[:]
        i=self.pos
        if i==0:
            try:
                f=open(settings.collection_file,'rb')
                version=cPickle.load(f)
                self.count=cPickle.load(f)
            except:
                self.unsetevent()
                jobs['WALKDIRECTORY'].setevent()
        try:
            while i<self.count and jobs.ishighestpriority(self):
                collection.append(cPickle.load(f)) #note the append rather than add call (i.e. not wasting cycles sorting an already sorted list)
                i+=1
        except:
            print 'error loading collection data'
            collection=imageinfo.Collection([])
        finally:
            f.close()
        if i==self.count:
            self.pos=i
            self.unsetevent()
            jobs['WALKDIRECTORY'].setevent()

    def __call__(self,jobs,collection,view,browser):
        browser.lock.acquire()
        del collection[:]
        collection.numselected=0
        del view[:]
        browser.lock.release()
        try:
            f=open(settings.collection_file,'rb')
        except:
            self.unsetevent()
            jobs['WALKDIRECTORY'].setevent()
            del collection[:]
            collection.numselected=0
            return
        try:
            version=cPickle.load(f)
            browser.lock.acquire()
            collection[:]=cPickle.load(f)
            browser.lock.release()
        except:
            print 'error loading collection data'
            browser.lock.acquire()
            del collection[:]
            collection.numselected=0
            browser.lock.release()
        finally:
            f.close()
        self.unsetevent()
        jobs['BUILDVIEW'].setevent()
        jobs['WALKDIRECTORY'].setevent()


class SaveCollectionJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'SAVECOLLECTION')

    def __call__(self,jobs,collection,view,browser):
        print 'saving'
        try:
            f=open(settings.collection_file,'wb')
        except:
            print 'failed to open collection for write'
            self.unsetevent()
            return False
        cPickle.dump(settings.version,f,-1)
        cPickle.dump(collection,f,-1)
        f.close()
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
                scan_dir=settings.image_dirs[0]
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

            gobject.idle_add(browser.UpdateStatus,-1,'Scanning for new images')
            for p in files: #may need some try, except blocks
                r=p.rfind('.')
                if r<=0:
                    continue
                fullpath=os.path.normcase(os.path.join(root, p))
                mimetype=gnomevfs.get_mime_type(gnomevfs.get_uri_from_local_path(fullpath))
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
                gobject.idle_add(browser.RefreshView)
                self.notify_items=[]
        if self.done:
            print 'walk directory done'
            gobject.idle_add(browser.RefreshView)
            gobject.idle_add(browser.UpdateStatus,2,'Search complete')
            if self.notify_items:
                browser.lock.acquire()
                for item in self.notify_items:
                    collection.add(item)
                browser.lock.release()
                gobject.idle_add(browser.RefreshView)
            self.notify_items=[]
            self.collection_walker=None
            self.unsetevent()
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

            gobject.idle_add(browser.UpdateStatus,-1,'Scanning for new images')
            for p in files: #may need some try, except blocks
                r=p.rfind('.')
                if r<=0:
                    continue
                fullpath=os.path.normcase(os.path.join(root, p))
                mimetype=gnomevfs.get_mime_type(gnomevfs.get_uri_from_local_path(fullpath))
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
                    gobject.idle_add(browser.RefreshView)
        if self.done:
            print 'walk subdirectory done'
            gobject.idle_add(browser.RefreshView)
            gobject.idle_add(browser.UpdateStatus,2,'Search complete')
            if self.notify_items:
                browser.lock.acquire()
                for item in self.notify_items:
                    collection.add(item)
                browser.lock.release()
                gobject.idle_add(browser.RefreshView)
            self.notify_items=[]
            self.collection_walker=None
            self.unsetevent()
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
            if filter_text.startswith('view:'):
                filter_text=filter_text[5:]
                self.superset=view.copy()
            else:
                self.superset=collection
            if filter_text.strip():
                view.set_filter(filter_text)
            else:
                view.clear_filter(filter_text)
            del view[:] ##todo: create a view method to empty the view
            if view.tag_cloud:
                view.tag_cloud.empty()
            gobject.idle_add(browser.UpdateView)
        lastrefresh=i
        browser.lock.release()
        while i<len(self.superset) and jobs.ishighestpriority(self) and not self.cancel:
            item=self.superset(i)
            if item.meta!=None:
                browser.lock.acquire()
                view.add_item(item)
                browser.lock.release()
            if i-lastrefresh>100:
                lastrefresh=i
                gobject.idle_add(browser.RefreshView)
                gobject.idle_add(browser.UpdateStatus,1.0*i/len(self.superset),'Rebuilding image view - %i of %i'%(i,len(self.superset)))
            i+=1
        if i<len(self.superset) and not self.cancel:
            self.pos=i
        else:
            self.pos=0
            self.cancel=False
            self.unsetevent()
            gobject.idle_add(browser.RefreshView)
            gobject.idle_add(browser.UpdateStatus,2,'View rebuild complete')
            gobject.idle_add(browser.post_build_view)

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
                gobject.idle_add(browser.UpdateStatus,1.0*i/len(listitems),'Selecting images - %i of %i'%(i,len(listitems)))
            i+=1
        if i<len(listitems) and not self.cancel:
            self.pos=i
        else:
            gobject.idle_add(browser.UpdateStatus,1.0*i/len(listitems),'Selecting images - %i of %i'%(i,len(listitems)))
            gobject.idle_add(browser.RefreshView)
            self.pos=0
            self.cancel=False
            self.unsetevent()

ADD_KEYWORDS=1
REMOVE_KEYWORDS=2
CHANGE_META=3

class EditMetaDataJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'EDITMETADATA')
        self.pos=0
        self.cancel=False
        self.mode=0
        self.keyword_string=''
        self.meta=None

    def __call__(self,jobs,collection,view,browser):
        i=self.pos
        if self.mode==ADD_KEYWORDS:
            tags=exif.tag_split(self.keyword_string)
            tags_lower=[t.lower() for t in tags]
            while i<len(view) and jobs.ishighestpriority(self) and not self.cancel:
                item=view(i)
                if item.selected and item.meta!=None and item.meta!=False:
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
                    gobject.idle_add(browser.UpdateStatus,1.0*i/len(view),'Selecting images - %i of %i'%(i,len(view)))
                i+=1
        if self.mode==REMOVE_KEYWORDS:
            tags=exif.tag_split(self.keyword_string)
            tags_lower=[t.lower() for t in tags]
            while i<len(view) and jobs.ishighestpriority(self) and not self.cancel:
                item=view(i)
                if item.selected and item.meta!=None and item.meta!=False:
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
                    gobject.idle_add(browser.UpdateStatus,1.0*i/len(view),'Adding keywords - %i of %i'%(i,len(view)))
                i+=1

        if self.mode==CHANGE_META:
            while i<len(view) and jobs.ishighestpriority(self) and not self.cancel:
                item=view(i)
                if item.selected and item.meta!=None and item.meta!=False:
                    for k,v in self.meta.iteritems():
                        item.set_meta_key(k,v)
                if i%100==0:
                    gobject.idle_add(browser.UpdateStatus,1.0*i/len(view),'Adding keywords - %i of %i'%(i,len(view)))
                i+=1

        if i<len(view) and not self.cancel:
            self.pos=i
        else:
            gobject.idle_add(browser.UpdateStatus,2.0,'Metadata edit complete - %i of %i'%(i,len(view)))
            gobject.idle_add(browser.RefreshView)
            self.pos=0
            self.cancel=False
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
                        gobject.idle_add(browser.RefreshView)
                        gobject.idle_add(browser.UpdateStatus,1.0*i/len(listitems),'Saving changed images in view - %i of %i'%(i,len(listitems)))
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
                        gobject.idle_add(browser.RefreshView)
                        gobject.idle_add(browser.UpdateStatus,1.0*i/len(listitems),'Reverting images in view - %i of %i'%(i,len(listitems)))
            if i%100==0:
                if self.save:
                    gobject.idle_add(browser.UpdateStatus,1.0*i/len(listitems),'Saving changed images in view - %i of %i'%(i,len(listitems)))
                else:
                    gobject.idle_add(browser.UpdateStatus,1.0*i/len(listitems),'Reverting images in view - %i of %i'%(i,len(listitems)))
            i+=1
        if i<len(listitems) and not self.cancel:
            self.pos=i
        else:
            gobject.idle_add(browser.UpdateStatus,2.0,'Saving images complete')
            gobject.idle_add(browser.RefreshView)
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
                gobject.idle_add(browser.UpdateStatus,1.0*i/len(collection),'Verifying images in collection - %i of %i'%(i,len(collection)))
            if item.meta==None:
                del_view_item(view,browser,item)
                imagemanip.load_metadata(item) ##todo: check if exists already
                browser.lock.acquire()
                view.add_item(item)
                browser.lock.release()
                gobject.idle_add(browser.RefreshView)
            ##print 'verifying',item.filename,os.path.isdir(item.filename)
            if not os.path.exists(item.filename) or os.path.isdir(item.filename) or item.filename!=os.path.normcase(item.filename):
                browser.lock.acquire()
                collection.numselected-=collection[i].selected
                del collection[i]
                browser.lock.release()
                del_view_item(view,browser,item)
                gobject.idle_add(browser.RefreshView)
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
                gobject.idle_add(browser.RefreshView)
            i+=1
        self.countpos=i
        if i>=len(collection):
            self.unsetevent()
            self.countpos=0
            gobject.idle_add(browser.UpdateStatus,2,'Verification complete')
            print 'image verification complete'
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
                gobject.idle_add(browser.UpdateStatus,1.0*i/len(collection),'Validating and creating missing thumbnails - %i of %i'%(i,len(collection)))
            if not imagemanip.has_thumb(item):
                imagemanip.make_thumb(item)
                gobject.idle_add(browser.RefreshView)
                gobject.idle_add(browser.UpdateStatus,1.0*i/len(collection),'Validating and creating missing thumbnails - %i of %i'%(i,len(collection)))
            i+=1
        self.countpos=i
        if i>=len(collection):
            self.unsetevent()
            self.countpos=0
            gobject.idle_add(browser.UpdateStatus,2,'Thumbnailing complete')


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
                        it=collection[j]
                        collection.numselected-=collection[j].selected
                        del collection[j]
                        j=view.find_item(it)
                        print 'delete item view index',j,it
                        if j>=0:
                            del view[j]
                    browser.lock.release()
                    gobject.idle_add(browser.RefreshView)
            if action in ('MOVED_TO','MODIFY','CREATE'):
                if os.path.exists(fullpath) and os.path.isfile(fullpath):
                    mimetype=gnomevfs.get_mime_type(gnomevfs.get_uri_from_local_path(fullpath))
                    if not mimetype.startswith('image'):
                        continue
                    i=collection.find([fullpath])
                    if i>=0:
                        if os.path.getmtime(fullpath)!=collection[i].mtime:
                            item=collection[i]
                            browser.lock.acquire()
                            j=view.find_item(item)
                            if j>=0:
                                del view[j]
                            browser.lock.release()
                            item.mtime=os.path.getmtime(fullpath)
                            imagemanip.load_metadata(item)
                            imagemanip.make_thumb(item)
                            browser.lock.acquire()
                            view.add_item(item)
                            browser.lock.release()
                            gobject.idle_add(browser.RefreshView)
                    else:
                        item=imageinfo.Item(fullpath,os.path.getmtime(fullpath))
                        imagemanip.load_metadata(item)
                        browser.lock.acquire()
                        collection.add(item)
                        view.add_item(item)
                        browser.lock.release()
                        if not imagemanip.has_thumb(item):
                            imagemanip.make_thumb(item)
                        gobject.idle_add(browser.RefreshView)
                if os.path.exists(fullpath) and os.path.isdir(fullpath):
                    if action=='MOVED_TO':
                        job=jobs['WALKSUBDIRECTORY']
                        job.sub_dir=fullpath
                        job.setevent()

        if len(self.queue)==0:
            self.unsetevent()


class WorkerJobCollection(dict):
    def __init__(self):
        self.collection=[
            WorkerJob('QUIT'),
            ThumbnailJob(),
            BuildViewJob(),
            SelectionJob(),
            EditMetaDataJob(),
            LoadCollectionJob(),
            RecreateThumbJob(),
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
        self.thread.start()

    def _loop(self):
        print 'starting monitor'
        self.monitor=monitor.Monitor(self.directory_change_notify)
        self.monitor.start(settings.image_dirs[0])
        print 'monitor started'
        self.jobs['LOADCOLLECTION'].setevent()
        while 1:
#            print self.jobs.gethighest()
            if not self.jobs.gethighest():
                self.event.clear()
                self.event.wait()
#            print 'JOB REQUEST:',self.jobs.gethighest()
            if self.jobs['QUIT']:
                self.monitor.stop(settings.image_dirs[0])
                if self.dirtimer!=None:
                    self.dirtimer.cancel()
                savejob=SaveCollectionJob()
                savejob(self.jobs,self.collection,self.view,self.browser)
                print 'end worker loop'
                print self.view.tag_cloud
                return
            job=self.jobs.gethighest()
            if job:
                job(self.jobs,self.collection,self.view,self.browser)

    def deferred_dir_update(self):
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
        homedir=os.path.normpath(settings.image_dirs[0])
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
        self.dirtimer=threading.Timer(1,self.deferred_dir_update)
        self.dirtimer.start()
        job.deferred.append((path,action))
        job.deflock.release()
##
##        if action in ('MODIFY','CREATE'):
##            job.deflock.acquire()
##            if self.dirtimer!=None:
##                self.dirtimer.cancel()
##            self.dirtimer=threading.Timer(1,self.deferred_dir_update)
##            self.dirtimer.start()
##            job.deferred.append((path,action))
##            job.deflock.release()
##        else:
##            job.queue.append((path,action))
##            job.setevent()
##            self.event.set()

    def quit(self):
        self.jobs['QUIT'].setevent()
        self.event.set()
        while self.thread.isAlive():
            time.sleep(0.1)

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

    def keyword_edit(self,keyword_string,remove=False):
        job=self.jobs['EDITMETADATA']
        if job.state:
            return False
        job.pos=0
        job.keyword_string=keyword_string
        if remove:
            job.mode=REMOVE_KEYWORDS
        else:
            job.mode=ADD_KEYWORDS
        job.setevent()
        self.event.set()
        return True

    def rebuild_view(self,sort_key,filter_text=''):
        job=self.jobs['BUILDVIEW']
        if job.state:
            job.cancel_job()
        job.tag_cloud=self.view.tag_cloud
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

