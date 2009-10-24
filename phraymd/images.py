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

'''
this module defines the image item (Item) class and related functions
'''

##standard imports
import datetime
import os.path
import re
import datetime

##phraymd imports
import pluginmanager


class Item(list):
    '''An item is a class describing an image, including filename, pixbuf representations and related metadata'''
    def __init__(self,filename,mtime):
        filename=os.path.normcase(filename) ##todo: remove this - doesn't do anything and might break stuff in future
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
        self.relevance=0
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
        if self.meta==False or self.meta==None:
            return None
        old=self.meta.copy()
        if not self.meta_changed:
            self.meta_backup=self.meta.copy()
            self.meta_changed=True
        if key in self.meta and key not in self.meta_backup and value=='':
            del self.meta[key]
        else:
            self.meta[key]=value
        pluginmanager.mgr.callback('t_collection_item_metadata_changed',self,old)
        if self.meta==self.meta_backup:
            del self.meta_backup
            self.meta_changed=False
        return self.meta_changed
    def set_meta(self,meta):
        if not self.meta_changed:
            self.meta_backup=self.meta.copy()
            self.meta_changed=True
        old=self.meta
        self.meta=meta
        pluginmanager.mgr.callback('t_collection_item_metadata_changed',self,old)
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
        del odict['relevance']
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
        self.relevance=0
        #todo: eventually delete this -- for legacy support to prevent loading loading keyword metadata as a tuple
        try:
            self.meta['Keywords']=list(self.meta['Keywords'])
        except:
            pass
        try:
            self.meta_backup['Keywords']=list(self.meta_backup['Keywords'])
        except:
            pass

def toggle_tags(item,tags):
    try:
        tags_lower=[t.lower() for t in tags]
        meta=item.meta.copy()
        try:
            tags_kw=meta['Keywords']
        except:
            tags_kw=[]
        tags_kw_lower=[t.lower() for t in tags_kw]
        new_tags=list(tags_kw)
        all_present=reduce(bool.__and__,[t in tags_kw_lower for t in tags_lower],True)
        if all_present:
            print 'removing tags',new_tags,tags_kw_lower,tags_lower
            j=0
            while j<len(new_tags):
                if tags_kw_lower[j] in tags_lower:
                    new_tags.pop(j)
                    tags_kw_lower.pop(j)
                else:
                    j+=1
        else:
            for j in range(len(tags)):
                if tags_lower[j] not in tags_kw_lower:
                    new_tags.append(tags[j])
        if len(new_tags)==0:
            try:
                del meta['Keywords']
            except:
                pass
        else:
            meta['Keywords']=new_tags
        item.set_meta(meta)
    except:
        pass

def add_tags(item,tags):
    try:
        tags_lower=[t.lower() for t in tags]
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
            try:
                del meta['Keywords']
            except:
                pass
        else:
            meta['Keywords']=new_tags
        item.set_meta(meta)
    except:
        pass

def remove_tags(item,tags):
    try:
        tags_lower=[t.lower() for t in tags]
        meta=item.meta.copy()
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

def set_tags(item,tags):
    try:
        meta=item.meta.copy()
        meta['Keywords']=tags
        item.set_meta(meta)
    except:
        pass

def get_coords(item):
    '''retrieve a pair of latitude longitude coordinates in degrees from item'''
    try:
        return item.meta['LatLon']
    except:
        return None

def set_coords(item,lat,lon):
    '''set the latitude and longitude in degrees to the item's exif metadata'''
    item.set_meta_key('LatLon',(lat,lon))

def item_in_region(item,lat0,lon0,lat1,lon1):
    '''returns true if the item's geolocation is contained in the rectangular region (lat0,lon0),(lat1,lon1)'''
    c=get_coords(item)
    if c and lat1<=c[0]<=lat0 and lon0<=c[1]<=lon1:
            return True
    return False

