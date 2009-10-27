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


class SimpleCollection(list):
    '''defines a sorted collection of Items'''
    def __init__(self,items=[]): ##todo: store base path for the collection
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


class Collection(list):
    '''defines a sorted collection of Items'''
    def __init__(self,items,image_dirs=[]): ##todo: store base path for the collection
        list.__init__(self)
        self.numselected=0
        self.image_dirs=image_dirs
        self.filename=None
        for item in items:
            self.add(item)
            self.numselected+=item.selected
    def add(self,item):
        self.numselected+=item.selected
        bisect.insort(self,item)
        pluginmanager.mgr.callback('t_collection_item_added',item)
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
            self.numselected-=item.selected
            self.pop(i)
            pluginmanager.mgr.callback('t_collection_item_removed',item)
            return item
        return None
    def __call__(self,ind):
        return self[ind]
#    def __getstate__(self):
#        odict = self.__dict__.copy() # copy the dict since we change it
#        del odict['numselected']
#        del odict['image_dirs']
#        del odict['filename']
#        return odict
#    def __setstate__(self,dict):
#        self.__dict__.update(dict)   # update attributes
#        self.numselected=0
#        self.image_dirs=[]
#        self.filename=None
    def load(self,filename=''):
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
            self.empty()
            return False
    def save(self):
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


def create_empty_file(filename,image_dirs):
    fullpath=os.path.join(settings.collections_dir,filename)
    try:
        f=open(fullpath,'wb')
        cPickle.dump(settings.version,f,-1)
        cPickle.dump(image_dirs,f,-1)
        collection=Collection([])
        cPickle.dump(collection[:],f,-1)
        f.close()
    except:
        print 'failed to open collection for write'
        return False
    return True
