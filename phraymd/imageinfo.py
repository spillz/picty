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

import bisect
import threading
import datetime
import os.path

class Item(list):
    def __init__(self,filename,mtime):
        list.__init__(self,[filename])
        self.filename=filename
        self.mtime=mtime
        self.thumbsize=(0,0)
        self.thumb=None
        self.thumburi=None
        self.meta=None
        self.thumbrgba=False
        self.qview=None
        self.qview_size=None
        self.image=None
        self.cannot_thumb=False
        self.selected=False
        self.meta_changed=False
    def key(self):
        return 1
    def meta_revert(self):
        if self.meta_changed:
            self.meta=self.meta_backup
            del self.meta_backup
        self.meta_changed=False
    def mark_meta_saved(self):
        if self.meta_changed:
            del self.meta_backup
        self.meta_changed=False
    def set_meta_key(self,key,value):
        if not self.meta_changed:
            self.meta_backup=self.meta.copy()
            self.meta_changed=True
        if key in self.meta and key not in self.meta_backup and value=='':
            del self.meta[key]
        else:
            self.meta[key]=value
        if self.meta==self.meta_backup:
            del self.meta_backup
            self.meta_changed=False
        return self.meta_changed
    def __getstate__(self):
        odict = self.__dict__.copy() # copy the dict since we change it
        del odict['thumbsize']
        del odict['thumb']
        del odict['thumbrgba']
        del odict['qview']
        del odict['qview_size']
        del odict['image']
        del odict['selected']
        return odict
    def __setstate__(self,dict):
        self.__dict__.update(dict)   # update attributes
        self.thumbsize=None
        self.thumb=None
        self.thumbrgba=False
        self.qview=None
        self.qview_size=None
        self.image=None
        self.selected=False


class Collection(list):
    def __init__(self,items):
        list.__init__(self)
        self.numselected=0
        for item in items:
            self.add(item)
            self.numselected+=item.selected
    def add(self,item):
        self.numselected+=item.selected
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
            self.numselected-=item.selected
            return self.pop(i)
        return None
    def __call__(self,ind):
        return self[ind]
    def __getstate__(self):
        odict = self.__dict__.copy() # copy the dict since we change it
        del odict['numselected']
        return odict
    def __setstate__(self,dict):
        self.__dict__.update(dict)   # update attributes


def get_mtime(item):
    return item.mtime


def get_ctime(item):
    try:
        date=item.meta["DateTaken"]
        if type(date)==str:
            date=datetime.strptime(date)
        return date
    except:
        return datetime.datetime(1900,1,1)

def get_fname(item):
    return os.path.split(item.filename)[1].lower()

def get_folder(item):
    return item.filename

def try_rational(item,key):
    try:
        value=item.meta[key]
        return 1.0*int(value[0])/int(value[1])
    except:
        return None

def get_speed(item):
    return try_rational(item,'ExposureTime')

def get_aperture(item):
    return try_rational(item,'FNumber')

def get_focal(item):
    return try_rational(item,'FocalLength')

def get_orient(item):
    try:
        orient=int(item.meta['Orientation'])
    except:
        orient=1
    return orient

def get_orient2(item):
    try:
        return int(item.meta['Orientation'])
    except:
        return None

def get_keyword(item):
    try:
        return item.meta['Keywords']
    except:
        return None


def text_descr(item):
    try:
        header=item.meta['Title']
    except:
        header=get_fname(item)
    details=''
    val=get_ctime(item)
    if val>datetime.datetime(1900,1,1):
        details+='Date: '+str(val)
#    else:
#        details+='Mod: '+str(get_mtime(item))
    val=get_focal(item)
    exposure=''
    if val:
        exposure+='%imm '%(int(val),)
    val=get_aperture(item)
    if val:
        exposure+='f/%3.1f'%(val,)
    val=get_speed(item)
    if val:
        exposure+=' %3.1fs'%(val,)
    if exposure:
        details+='\n'+exposure
    val=str(get_keyword(item))
    if val:
        if len(val)<30:
            details=details+'\nTags: '+val
        else:
            details=details+'\n'+val[:28]+'...'
    return (header,details)

sort_keys={
        'Date Taken':get_ctime,
        'Date Last Modified':get_mtime,
        'File Name':get_fname,
        'Orientation':get_orient,
        'Folder':get_folder,
        'Shutter Speed':get_speed,
        'Aperture':get_aperture,
#        'ISO Speed':get_iso,
        'Focal Length':get_focal
        }


def mtime_filter(item,criteria):
    val=get_mtime(item)
    if criteria[0]<=val<=criteria[1]:
        return True
    return False

def ctime_filter(item,criteria):
    val=get_ctime(item)
    if criteria[0]<=val<=criteria[1]:
        return True
    return False

def selected_filter(item,criteria):
    return item.selected==criteria

def keyword_filter(item,criteria):
    test=criteria[1]
    for t in test:
        if t in item.filename.lower():
            return True
    if item.meta:
        for k,v in item.meta.iteritems():
            if v:
                for t in test:
                    if t in str(v).lower():
                        return True
    return False

class Index(list):
    def __init__(self,key_cb=get_mtime,items=[]):
        list.__init__(self)
        for item in items:
            self.add(key_cb(item),item)
        self.key_cb=key_cb
        self.filters=None
##        self.filters=[(keyword_filter,('in','tom'))] #tests out the filtering mechanism
        self.reverse=False
    def add(self,key,item):
        if self.filters:
            for f in self.filters:
                if not f[0](item,f[1]):
                    return
        bisect.insort(self,[key,item])
    def remove(self,key,item):
        ind=bisect.bisect_left(self,[key,item])
        i=list.__getitem__(self,ind)
        if key==i[0]:
            if item==i[1]:
                list.pop(self,ind)
                return
            raise KeyError
    def add_item(self,item):
        self.add(self.key_cb(item),item)
    def find_item(self,item):
        i=bisect.bisect_left(self,[self.key_cb(item),item])
        if i>=len(self) or i<0:
            return -1
        if self[i][1]==item:
            return i
        return -1
    def del_item(self,item):
        ind=self.find_item(item)
        if ind>=0:
            del self[ind]
            return True
        return False
    def __call__(self,index):
        if index>=len(self):
            return
        if self.reverse:
            return self[len(self)-1-index][1]
        else:
            return self[index][1]
    def get_items(self,first,last):
        if self.reverse:
            return [i[1] for i in self[len(self)-last:len(self)-first]]
        else:
            return [i[1] for i in self[first:last]]

if __name__=='__main__':
    a=Index([5,4,1,2])
    print a
    a.add(3,3)
    print a
    a.remove(2,2)
    print a
