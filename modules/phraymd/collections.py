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
import datetime
import os.path
import re
import datetime
import cPickle

##phraymd imports
import pluginmanager
import settings
import monitor2 as monitor
import views

class SimpleCollection(list):
    '''defines a sorted collection of Items'''
    def __init__(self,items=[],items_sorted=False): ##todo: store base path for the collection
        if items_sorted:
            list.__init__(self,items[:])
        else:
            list.__init__(self)
            for item in items:
                self.add(item)
    def add(self,item):
        bisect.insort(self,item)
    def find(self,item):
        i=bisect.bisect_left(self,item)
        if i>=len(self) or i<0:
            return -1
        if self[i]==item:
            return i
        return -1
    def delete(self,item):
        i=self.find(item)
        if i>=0:
            self.pop(i)
            return item
        return None
    def __call__(self,ind):
        return self[ind]
    def empty(self):
        del self[:]


## This is the old style collection (ver 0.3.2 and earlier)
## only needed for legacy support
## all collections in phraymd are derived from the Collection2 class
## todo: drop legacy support to reduce cruft.
class Collection(list):
    '''defines a sorted collection of Items with callbacks to plugins when the contents of the collection change'''
    def __init__(self,items,image_dirs=[]): ##todo: store base path for the collection
        list.__init__(self)
        self.numselected=0
        self.image_dirs=image_dirs
        self.filename=None
        self.verify_after_walk=True
        self.load_metadata=True ##image will be loaded into the collection and view without metadata
        self.load_embedded_thumbs=False ##only relevant if load_metadata is true
        self.load_preview_icons=False ##only relevant if load_metadata is false
        self.trash_location=None ## none defaults to <collection dir>/.trash
        self.thumbnail_cache=None ## use gnome/freedesktop or put in the image folder
        ##self.monitor
        for item in items:
            self.add(item)
            self.numselected+=item.selected
    def copy(self):
        dup=Collection([])
        dup+=self
        dup.numselected=self.numselected
        dup.image_dirs=self.image_dirs[:]
        dup.filename=self.filename
        dup.verify_after_walk=self.verify_after_walk
        dup.load_metadata=self.load_metadata
        dup.load_embedded_thumbs=self.load_embedded_thumbs
        dup.load_preview_icons=self.load_preview_icons
        return dup
    def copy_from(self,dup):
        self[:]=dup[:]
        self.numselected=dup.numselected
        self.image_dirs=dup.image_dirs[:]
        self.filename=dup.filename
        self.verify_after_walk=dup.verify_after_walk
        self.load_metadata=dup.load_metadata
        self.load_embedded_thumbs=dup.load_embedded_thumbs
        self.load_preview_icons=dup.load_preview_icons
        return dup
    def simple_copy(self):
        return SimpleCollection(self,True)
    def add(self,item):
        '''
        add an item to the collection and notify plugin
        '''
        self.numselected+=item.selected
        bisect.insort(self,item)
        pluginmanager.mgr.callback('t_collection_item_added',item)
    def find(self,item):
        '''
        find an item in the collection and return its index
        '''
        i=bisect.bisect_left(self,item)
        if i>=len(self) or i<0:
            return -1
        if self[i]==item:
            return i
        return -1
    def delete(self,item):
        '''
        delete an item from the collection, returning the item to the caller if present
        notifies plugins if the item is remmoved
        '''
        i=self.find(item)
        if i>=0:
            self.numselected-=item.selected
            self.pop(i)
            pluginmanager.mgr.callback('t_collection_item_removed',item)
            return item
        return None
    def __call__(self,ind):
        return self[ind]
    def load(self,filename=''):
        '''
        load the collection from a binary pickle file identified by the pathname in the filename argument
        '''
        print 'loading collection',filename
        try:
            if not filename:
                filename=self.filename
            f=open(filename,'rb')
            version=cPickle.load(f)
            if version>='0.3.0':
                self.image_dirs=cPickle.load(f)
            else:
                self.image_dirs=settings.legacy_image_dirs
            self[:]=cPickle.load(f)
            self.filename=filename
            self.numselected=0
            return True
        except:
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print "Error Loading Collection",filename
            print tb_text
            self.empty()
            return False
    def save(self):
        '''
        save the collection to a binary pickle file using the filename attribute of the collection
        '''
        print 'saving collection',self.filename
        try:
            f=open(self.filename,'wb')
        except:
            print 'failed to open collection',self.filename,'for write'
            return False
        cPickle.dump(settings.version,f,-1)
        cPickle.dump(self.image_dirs,f,-1)
        cPickle.dump(self,f,-1)
        f.close()
        return True
    def empty(self):
        del self[:]
        self.numselected=0
        self.filename=''
        self.image_dirs=[]




class Collection2():
    '''defines a sorted collection of Items with
    callbacks to plugins when the contents of the collection change'''
    ##todo: do more plugin callbacks here instead of the job classes?
    def __init__(self,items=[],image_dirs=[],id='',type='LOCALSTORE',name='',pixbuf=None): #todo: store base path for the collection
        self.type=type #either localstore, device or directory (future: webstore?)
        self.name=name #name displayed to the user
        self.pixbuf=pixbuf #icon to display in the interface (maybe need more than one size)
        self.id=id

        self.items=[] #the image/video items
        for item in items:
            self.items.add(item)
            self.numselected+=item.selected
        self.is_open=True if len(items)>0 else False

        self.numselected=0

        self.filename=None
        self.image_dirs=image_dirs
        self.recursive=True

        self.verify_after_walk=True
        self.load_metadata=True #image will be loaded into the collection and view without metadata
        self.load_embedded_thumbs=False #only relevant if load_metadata is true
        self.load_preview_icons=False #only relevant if load_metadata is false
        self.trash_location=None #none defaults to <collection dir>/.trash
        self.thumbnail_cache=None #use gnome/freedesktop or put in the image folder

        self.monitor=None
        self.monitor_master_callback=None #

        self.views=[]  #a view is a sorted subset of the collection (i.e. database notion of a view)
        self.active_view=None

    def copy(self):
        dup=Collection2([])
        dup.items=self.items[:]
        dup.numselected=self.numselected
        dup.image_dirs=self.image_dirs[:]
        dup.filename=self.filename
        dup.verify_after_walk=self.verify_after_walk
        dup.load_metadata=self.load_metadata
        dup.load_embedded_thumbs=self.load_embedded_thumbs
        dup.load_preview_icons=self.load_preview_icons
        dup.monitor=None
        dup.views=[]
        for v in self.views:
            dup.views.append(v.copy())
        return dup
    def copy_from(self,dup):
        self.items[:]=dup.items[:]
        self.numselected=dup.numselected
        self.image_dirs=dup.image_dirs[:]
        self.filename=dup.filename
        self.verify_after_walk=dup.verify_after_walk
        self.load_metadata=dup.load_metadata
        self.load_embedded_thumbs=dup.load_embedded_thumbs
        self.load_preview_icons=dup.load_preview_icons
        del self.views[:]
        for v in dup.views:
            self.views.append(v.copy())
        return dup
    def simple_copy(self):
        return SimpleCollection(self,True)
    def add(self,item,add_to_view=True):
        '''
        add an item to the collection and notify plugin
        '''
        self.numselected+=item.selected
        bisect.insort(self.items,item)
        pluginmanager.mgr.callback_collection('t_collection_item_added',self,item)
        if add_to_view:
            for v in self.views:
                v.add_item(item)
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
    def delete(self,item,delete_from_view=True):
        '''
        delete an item from the collection, returning the item to the caller if present
        notifies plugins if the item is remmoved
        '''
        i=self.find(item)
        if i>=0:
            self.numselected-=item.selected
            self.items.pop(i)
            pluginmanager.mgr.callback_collection('t_collection_item_removed',self,item)
            for v in self.views:
                v.del_item(item)
            return item
        return None
    def __call__(self,ind):
        return self.items[ind]
    def __getitem__(self,ind):
        return self.items[ind]
    def start_monitor(self,callback):
        self.monitor_master_callback=callback
        self.monitor=monitor.Monitor(self.image_dirs,self.recursive,self.monitor_callback)
    def end_monitor(self):
        self.monitor.stop()
        self.monitor=None
    def monitor_callback(self,path,action,is_dir):
        self.monitor_master_callback(self,path,action,is_dir)
    def add_view(self,sort_criteria=views.get_mtime):
        view=views.Index(sort_criteria,self.items,self)
        self.views.append(view)
        if not self.active_view:
            self.active_view=view
        return view
    def remove_view(self,view):
        ind=self.view.find(view)
        if ind>=0:
            del self.views[ind]
            return view
        return False
    def set_active_view(self,view):
        if view in self.views:
            self.active_view=view
    def get_active_view(self):
        return self.active_view
    def open(self,filename=''):
        '''
        load the collection from a binary pickle file identified by the pathname in the filename argument
        '''
        print 'loading collection',filename,self.filename
        self.is_open=True
        try:
            if not filename:
                filename=self.filename
            if not filename: ##if no filename, there's nothing to load (scan instead)
                return True
            f=open(filename,'rb')
            version=cPickle.load(f)
            if version>='0.3.0':
                self.image_dirs=cPickle.load(f)
            else:
                self.image_dirs=settings.legacy_image_dirs
            if version>='0.4.0':
                self.items=cPickle.load(f)
            else:
                f.close()
                c=Collection([])
                c.load(filename)
                self.items[:]=c[:]
            self.filename=filename
            self.numselected=0
            return True
        except:
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print "Error Loading Collection",self.filename
            print tb_text
            self.is_open=False
            self.empty()
            return False
    def close(self):
        '''
        save the collection to a binary pickle file using the filename attribute of the collection
        '''
        self.is_open=False
        if not self.filename: ##no filename assumed to be a temporary collection
            return False
        print 'saving collection',self.filename,self.image_dirs
        try:
            f=open(self.filename,'wb')
        except:
            print 'failed to open collection',self.filename,'for write'
            return False
        cPickle.dump(settings.version,f,-1)
        cPickle.dump(self.image_dirs,f,-1)
        cPickle.dump(self.items,f,-1)
        f.close()
        return True
    def empty(self,empty_views=True):
        del self.items[:]
        self.numselected=0
        if empty_views:
            for v in self.views:
                v.empty()
    def __len__(self):
        return len(self.items)


def create_empty_file(filename,image_dirs):
    fullpath=os.path.join(settings.collections_dir,filename)
    try:
        f=open(fullpath,'wb')
        cPickle.dump(settings.version,f,-1)
        cPickle.dump(image_dirs,f,-1)
#        collection=Collection([])
        cPickle.dump([],f,-1)
        f.close()
    except:
        print 'failed to open collection for write'
        return False
    return True
