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

try:
    import gnome.ui
    import gnomevfs
    import pyexiv2
except:
    maemo=True

import gc


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

    def __call__(self,jobs,collection,browser):
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

        '''
        uri = gnomevfs.get_uri_from_local_path(path)
        mime = gnomevfs.get_mime_type(uri)

        thumbFactory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_LARGE)
            thumbnail = thumbFactory.generate_thumbnail(uri, mime)
            if thumbnail != None:
                thumbFactory.save_thumbnail(thumbnail, uri, 0)
        '''

    def _check_thumb_limit(self):
        if len(self.memthumbs)>settings.max_memthumbs:
            olditem=self.memthumbs.pop(0)
            olditem.thumbsize=(0,0)
            olditem.thumb=None

    def __call__(self,jobs,collection,browser):
        print 'loading thumbs'
        while jobs.ishighestpriority(self) and len(self.queue_onscreen)>0:
            item=self.queue_onscreen.pop(0)
            if item.thumb:
                continue
            if imagemanip.load_thumb(item):
                self.memthumbs.append(item)
                self._check_thumb_limit()
        if len(self.queue_onscreen)==0:
            gobject.idle_add(browser.Thumb_cb,None)
            self.unsetevent()


class LoadCollectionJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'LOADCOLLECTION')

    def __call__(self,jobs,collection,browser):
        try:
            f=open(settings.collection_file,'rb')
        except:
            self.unsetevent()
            jobs['WALKDIRECTORY'].setevent()
            self.collection=imageinfo.Collection([])
            return self.collection
        try:
            settings.version=cPickle.load(f)
            self.collection=cPickle.load(f)
            if len(self.collection)<10:
                print self.collection
            else:
                print self.collection[0:10]
        except:
            print 'error loading collection data'
            self.collection=imageinfo.Collection([])
        finally:
            f.close()
        self.unsetevent()
        jobs['WALKDIRECTORY'].setevent()
        return self.collection


class SaveCollectionJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'SAVECOLLECTION')

    def __call__(self,jobs,collection,browser):
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
#        try:
#            cPickle.dump(settings.version,f,-1)
#            cPickle.dump(self.collection,f,-1)
#        except:
#            print 'error saving collection data'
#        finally:
#            f.close()
        self.unsetevent()


class WalkDirectoryJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'WALKDIRECTORY')
        self.collection_walker=None
        self.notify_items=[]
        self.done=False

    def __call__(self,jobs,collection,browser):
        self.last_update_time=time.time()
        try:
            if not self.collection_walker:
                self.collection_walker=os.walk(settings.image_dirs[0])
        except StopIteration:
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

            for p in files: #may need some try, except blocks
                ##todo: check if the item already exists in the collection
                r=p.rfind('.')
                if r<=0:
                    continue
                if not p[r+1:].lower() in settings.imagetypes:
                    continue
                fullpath=os.path.join(root, p)
                mtime=os.path.getmtime(fullpath)
                st=os.stat(fullpath)
                if os.path.isdir(fullpath):
                    continue
                item=imageinfo.Item(fullpath,mtime)
                if collection.find(item)<0:
#                    print 'found new item',fullpath
                    self.notify_items.append(item)
#                    time.sleep(0.05)
#                else:
#                    print 'item in collection',fullpath
            ## notify viewer(s)
            if time.time()>self.last_update_time+1.0 or len(self.notify_items)>100:
                print '************** NOTIFYING ********************'
                self.last_update_time=time.time()
                browser.lock.acquire()
                for item in self.notify_items:
                    collection.add(item)
                browser.lock.release()
                gobject.idle_add(browser.AddImages,self.notify_items)
                self.notify_items=[]
#            if time.time()>self.last_update_time+1.0 or len(self.notify_items)>100:
#                self.last_update_time=time.time()
#                gobject.idle_add(browser.AddImages,self.notify_items)
#                self.notify_items=[]
        if self.done:
            print 'walk directory done'
            gobject.idle_add(browser.AddImages,self.notify_items)
            self.notify_items=[]
            self.collection_walker=None
            self.unsetevent()
            jobs['VERIFYIMAGES'].setevent()
        else:
            print 'pausing directory walk'


class VerifyImagesJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'VERIFYIMAGES')
        self.countpos=0

    def __call__(self,jobs,collection,browser):
        i=self.countpos  ##todo: make sure this gets initialized
        print 'verifying',len(collection),'images -',i,'done'
        print jobs.gethighest()
        while i<len(collection) and jobs.ishighestpriority(self):
            item=collection[i]
            if not item.meta:
#                print 'loading metadata'
                imagemanip.load_metadata(item) ##todo: check if exists already
            if not imagemanip.has_thumb(item):
#                print 'making thumb...',
                imagemanip.make_thumb(item)
#                print 'done!'
                gobject.idle_add(browser.AddImages,None)
            ##print 'verifying',item.filename
            if not os.path.exists(item.filename):
                browser.lock.acquire()
                del collection[i]
                browser.lock.release()
                ##TODO: Notify viewer/browser of update
                continue
            mtime=os.path.getmtime(item.filename)
            if mtime!=item.mtime:
                item.mtime=mtime
                item.image=None
                item.qview=None
                item.qview_size=None
                browser.lock.acquire()
                imagemanip.load_metadata(item)
                if not imagemanip.has_thumb(item):
                    imagemanip.make_thumb(item)
                ##update mtime, metadata, thumb and image data of the Image
                browser.lock.release()
                i+=1
                ##TODO: Notify viewer/browser of update
                continue
            i+=1
            #time.sleep(0.001)
        self.countpos=i
        if i>=len(collection):
            self.unsetevent()
            print 'image verification complete'


class DirectoryUpdateJob(WorkerJob):
    def __init__(self):
        WorkerJob.__init__(self,'DIRECTORYUPDATE')
        self.queue=[]

    def __call__(self,jobs,collection,browser):
        #todo: make sure job.queue has been initialized
        #todo: acquire and release collection lock
        while self.jobs.ishighestpriority(self) and len(self.queue)>0:
            fullpath,action=queue.pop(0)
            if action=='DELETE' or action=='MOVED_FROM':
                if not os.path.exists(fullpath):
                    browser.lock.acquire()
                    collection.delete([fullpath,0])
                    browser.lock.release()
                #todo: update browser/viewer
            if action=='MOVED_TO' or action=='MODIFY' or action=='CREATE':
                if os.path.exists(fullpath):
                    i=self.collection.find([fullpath,0])
                    if i>=0:
                        collection[i].mtime=os.path.getmtime(fullpath)
                        collection[i][1]=os.path.getmtime(fullpath)
                        item=self.collection[i]
                        imagemanip.load_metadata(item)
                        if not has_thumb(item):
                            imagemanip.make_thumb(item)
                    else:
                        item=imagemanip.Item(fullpath,os.path.getmtime(fullpath))
                        browser.lock.acquire()
                        collection.add(item)
                        browser.lock.release()
                        imagemanip.load_metadata(item)
                        if not has_thumb(item):
                            imagemanip.make_thumb(item)
        if len(self.queue)==0:
            self.unsetevent()
                #todo: update browser/viewer


class WorkerJobCollection(dict):
    def __init__(self):
        self.collection=[
            WorkerJob('QUIT'),
            ThumbnailJob(),
            LoadCollectionJob(),
            VerifyImagesJob(),
            WalkDirectoryJob(),
            DirectoryUpdateJob()
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
        self.jobs=WorkerJobCollection()
        self.event=threading.Event()
        self.browser=browser
        self.lock=threading.Lock()
        self.exit=False
        self.thread=threading.Thread(target=self._loop)
        self.thread.start()

    def _loop(self):
        print 'start worker loop'
        loadjob=LoadCollectionJob()
        print 'loading collection'
        self.collection=loadjob(self.jobs,self.collection,self.browser)
        print 'loading collection done'
        try:
            print self.collection[0]
            print self.collection[0].mtime
            print self.collection[0].meta
        except:
            print self.collection
        gobject.idle_add(self.browser.AddImages,[])
        while 1:
            print self.jobs.gethighest()
            if not self.jobs.gethighest():
                gc.enable()
                self.event.clear()
                self.event.wait()
            print 'JOB REQUEST:',self.jobs.gethighest()
            if self.jobs['QUIT']:
                savejob=SaveCollectionJob()
                print 'saving'
                savejob(self.jobs,self.collection,self.browser)
                return
            job=self.jobs.gethighest()
            if job:
                job(self.jobs,self.collection,self.browser)
            #time.sleep(0.05)

    def quit(self):
        self.jobs['QUIT'].setevent()
        self.event.set()
        while self.thread.isAlive():
            time.sleep(0.1)

    def request_thumbnails(self,itemlist):
        job=self.jobs['THUMBNAIL']
        ## todo: should lock before changing queue_onscreen
        job.queue_onscreen=itemlist[0:]
        job.setevent()
        self.event.set()

    def request_loadandmonitorcollection(self):
        return
#        print 'request load and monitor'
#        job=self.jobs['LOADCOLLECTION'].setevent()
#        self.event.set()
