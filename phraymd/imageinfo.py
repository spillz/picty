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

##this file contains the basic data structures for images, collections, views and tags

import bisect
import threading
import datetime
import os.path
import simple_parser as sp
import exif

import re
import datetime

class TagCloud():
    def __init__(self):
        self.tags=dict()
    def __repr__(self):
        return self.tags.__repr__()
    def empty(self):
        self.tags=dict()
    def tag_add(self,keywords):
        for k in keywords:
            if k in self.tags:
                self.tags[k]+=1
            else:
                self.tags[k]=1
    def tag_remove(self,keywords):
        for k in keywords:
            if k in self.tags:
                self.tags[k]-=1
            else:
                print 'warning: removing item',item,'with keyword',k,'not in tag cloud'
    def add(self,item):
        if item.meta==None or item.meta==False:
            return False
        try:
            self.tag_add(item.meta['Keywords'])
        except:
            return False
        return True
    def remove(self,item):
        if item.meta==None or item.meta==False:
            return False
        try:
            self.tag_remove(item.meta['Keywords'])
        except:
            return False
        return True
    def update(self,item):
        try:
            self.tag_remove(item.meta_backup['Keywords'])
        except:
            pass
        try:
            self.tag_add(item.meta['Keywords'])
        except:
            pass
    def revert(self,item):
        try:
            self.tag_remove(item.meta['Keywords'])
        except:
            pass
        try:
            self.tag_add(item.meta_backup['Keywords'])
        except:
            pass


class Item(list):
    '''An item is a class containing an image, pixbuf representations and related metadata'''
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
    def set_meta(self,meta):
        if not self.meta_changed:
            self.meta_backup=self.meta.copy()
            self.meta_changed=True
        self.meta=meta
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


class Collection(list):
    '''defines a sorted collection of Items'''
    def __init__(self,items):
        list.__init__(self)
        self.numselected=0
        for item in items:
            self.add(item)
            self.numselected+=item.selected
##        self.tag_cloud=TagCloud()
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

def get_mtime_str(item):
    return datetime.datetime.fromtimestamp(item.mtime)

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

def try_rational_str(item,key):
    try:
        value=item.meta[key]
        try:
            num=int(value[0])
            denom=int(value[1])
        except:
            (num,denom)=str(value).split('/')
            num=int(num)
            denom=int(denom)
        if abs(num)<denom:
            for x in xrange(num,0,-1):
                if denom%x==0:
                    return '%i/%i'%(num/x,denom/x)
        if abs(num)>denom:
            return '%3.1f'%(1.0*num/denom,)
        return '1'
    except:
        return None


def get_speed(item):
    return try_rational(item,'ExposureTime')

def get_speed_str(item):
    return try_rational_str(item,'ExposureTime')

def get_aperture(item):
    return try_rational(item,'FNumber')

def get_aperture_str(item):
    return try_rational_str(item,'FNumber')

def get_focal(item):
    return try_rational(item,'FocalLength')

def get_focal_str(item):
    return try_rational_str(item,'FocalLength')

def get_iso_str(item):
    try:
        return str(item.meta['IsoSpeed'])
    except:
        return None

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

def get_relevance(item):
    return item.relevance

def text_descr(item):
    ##TODO: tidy this up using functions above
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
    val=get_speed_str(item)
    if val:
        exposure+=' %ss'%(val,)
    val=get_iso_str(item)
    if val:
        exposure+=' iso%s'%(val,)
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
        'Focal Length':get_focal,
        'Relevance':get_relevance
        }

sort_keys_str={
        'Date Taken':get_ctime,
        'Date Last Modified':get_mtime_str,
        'File Name':get_fname,
        'Orientation':get_orient,
        'Folder':get_folder,
        'Shutter Speed':get_speed_str,
        'Aperture':get_aperture_str,
#        'ISO Speed':get_iso,
        'Focal Length':get_focal_str,
        'Relevance':get_relevance
        }





def mtime_filter(l,r,item):
    val=get_mtime(item)
    if criteria[0]<=val<=criteria[1]:
        return True
    return False

def ctime_filter(l,r,item):
    val=get_ctime(item)
    if criteria[0]<=val<=criteria[1]:
        return True
    return False

def selected_filter(l,r,item):
    return item.selected

def changed_filter(l,r,item):
    return item.meta_changed

def tagged_filter(l,r,item):
    if not item.meta:
        return False
    if 'Keywords' not in item.meta:
        return False
    if not item.meta['Keywords']:
        return False
    if len(item.meta['Keywords'])>0:
        return True

    return item.meta['Keywords']

def keyword_filter(item,test):
    if not test:
        return True
    relevance=0
    item_string=''
    item_string+=item.filename.lower()
    if item.meta:
        for k,v in item.meta.iteritems():
            if v:
                if type(v) in (tuple,list):
                    for vi in v:
                        item_string+=' '+str(vi).lower()
                else:
                    item_string+=' '+str(v).lower()
    item_string=item_string.replace('\n',' ')
    (left,match,right)=item_string.partition(test)
    while match:
        relevance+=1
        if (left=='' and not match or left.endswith(' ')) and (right=='' or right.startswith(' ')):
            relevance+=1
        (left,match,right)=right.partition(test)
    item.relevance=relevance
    return relevance>0

class StringEquals:
    def __init__(self,field,insens=True,exact=True):
        self.field=field
        if exact:
            self.__call__=self.call2 if insens else self.call1
        else:
            self.__call__=self.call4 if insens else self.call3
    def call1(self,l,r,item):
        text=r.strip()
        try:
            if text==item.meta[self.field]:
                return True
        except:
            return False
    def call2(self,l,r,item):
        text=r.strip()
        try:
            if text.lower()==item.meta[self.field].lower():
                return True
        except:
            return False
    def call3(self,l,r,item):
        text=r.strip()
        try:
            if text in item.meta[self.field]:
                return True
        except:
            return False
    def call4(self,l,r,item):
        text=r.strip()
        try:
            if text.lower() in item.meta[self.field].lower():
                return True
        except:
            return False

class RationalCompare:
    def __init__(self,field,op=float.__eq__):
        self.field=field
        self.op=op
    def __call__(self,l,r,item):
        text=r.strip()
        try:
            val=float(text)
            return self.op(exif.app_key_as_sortable(item.meta,self.field),val)
        except:
##            print 'error on item',item,val
##            print exif.app_key_as_sortable(item.meta,self.field)
##            print self.op(val,exif.app_key_as_sortable(item.meta,self.field))
            return False


def eq(int1,int2):
    return int1==int2
def gt(int1,int2):
    return int1>int2
def lt(int1,int2):
    return int1<int2
def ge(int1,int2):
    return int1>=int2
def le(int1,int2):
    return int1<=int2

class IntCompare:
    def __init__(self,field,op=eq):
        self.field=field
        self.op=op
    def __call__(self,l,r,item):
        text=r.strip()
        try:
            val=int(text)
            return self.op(exif.app_key_as_sortable(item.meta,self.field),val)
        except:
            print 'int cmp fail',item,val
            print exif.app_key_as_sortable(item.meta,self.field)
            print self.op(exif.app_key_as_sortable(item.meta,self.field),val)
            return False

date_re=re.compile(r'(\d{4})(?:[\-\/](\d{1,2}))?(?:[\-\/](\d{1,2}))?(?:[;, ](\d{1,2}))?(?:\:(\d{1,2}))?(?:\:(\d{1,2}))?')

class DateCompare:
    def __init__(self,field,op=eq,mdate=False):
        self.field=field
        self.op=op
        if mdate:
            self.__call__=self.__call__2
    def __call__(self,l,r,item):
        text=r.strip()
        try:
            match=date_re.match(text) ##todo: should only need to do this once per search not for every item
            if not match:
                return False
            date_list=[]
            for g in match.groups():
                if g:
                    date_list.append(int(g))
                else:
                    break
            date_list+=[1]*max(0,3-len(date_list))
            val=datetime.datetime(*date_list)
            return self.op(exif.app_key_as_sortable(item.meta,self.field),val)
        except:
            return False
    def __call__2(self,l,r,item):
        text=r.strip()
        try:
            match=date_re.match(text) ##todo: should only need to do this once per search not for every item
            if not match:
                return False
            date_list=[]
            for g in match.groups():
                if g:
                    date_list.append(int(g))
                else:
                    break
            date_list+=[1]*max(0,3-len(date_list))
            val=datetime.datetime(*date_list)
            return self.op(item.mtime,val)
        except:
            return False

def contains_tag(l,r,item):
    try:
        text=r.strip()
        if text in item.meta['Keywords']:
            item.relevance+=3
            return True
    except:
        return False

def _not(l,r,item):
    return not r

def _or(l,r,item):
    return l or r

def _and(l,r,item):
    return l and r


def str2bool(val,item):
    return keyword_filter(item,val)


converter={
(str,bool):str2bool
}



TOKENS=[
(' ',(_or,bool,bool)),
('&',(_and,bool,bool)),
('|',(_or,bool,bool)),
('!',(_not,None,bool)),
('tag=',(contains_tag,None,str)),
('title=',(StringEquals('Title'),None,str)),
('descr=',(StringEquals('ImageDescription'),None,str)),
('artist=',(StringEquals('Artist'),None,str)),
('copyright=',(StringEquals('Copyright'),None,str)),
('album=',(StringEquals('Album'),None,str)),
('title~',(StringEquals('Title',True,False),None,str)),
('descr~',(StringEquals('ImageDescription',True,False),None,str)),
('artist~',(StringEquals('Artist',True,False),None,str)),
('copyright~',(StringEquals('Copyright',True,False),None,str)),
('album~',(StringEquals('Album',True,False),None,str)),
('shutter=',(RationalCompare('ExposureTime'),None,str)),
('shutter>=',(RationalCompare('ExposureTime',float.__ge__),None,str)),
('shutter<=',(RationalCompare('ExposureTime',float.__le__),None,str)),
('shutter>',(RationalCompare('ExposureTime',float.__gt__),None,str)),
('shutter<',(RationalCompare('ExposureTime',float.__lt__),None,str)),
('aperture=',(RationalCompare('FNumber'),None,str)),
('aperture>=',(RationalCompare('FNumber',float.__ge__),None,str)),
('aperture<=',(RationalCompare('FNumber',float.__le__),None,str)),
('aperture>',(RationalCompare('FNumber',float.__gt__),None,str)),
('aperture<',(RationalCompare('FNumber',float.__lt__),None,str)),
('focal=',(RationalCompare('FocalLength'),None,str)),
('focal>=',(RationalCompare('FocalLength',float.__ge__),None,str)),
('focal<=',(RationalCompare('FocalLength',float.__le__),None,str)),
('focal>',(RationalCompare('FocalLength',float.__gt__),None,str)),
('focal<',(RationalCompare('FocalLength',float.__lt__),None,str)),
('iso=',(IntCompare('IsoSpeed'),None,str)),
('iso>=',(IntCompare('IsoSpeed',ge),None,str)),
('iso<=',(IntCompare('IsoSpeed',le),None,str)),
('iso>',(IntCompare('IsoSpeed',gt),None,str)),
('iso<',(IntCompare('IsoSpeed',lt),None,str)),
('date=',(DateCompare('DateTaken'),None,str)),
('date>=',(DateCompare('DateTaken',ge),None,str)),
('date<=',(DateCompare('DateTaken',le),None,str)),
('date>',(DateCompare('DateTaken',gt),None,str)),
('date<',(DateCompare('DateTaken',lt),None,str)),
('mdate=',(DateCompare('DateMod'),None,str)),
('mdate>=',(DateCompare('DateMod',ge),None,str)),
('mdate<=',(DateCompare('DateMod',le),None,str)),
('mdate>',(DateCompare('DateMod',gt),None,str)),
('mdate<',(DateCompare('DateMod',lt),None,str)),
('selected',(selected_filter,None,None)),
('changed',(changed_filter,None,None)),
('tagged',(tagged_filter,None,None))
]


class Index(list):
    def __init__(self,key_cb=get_mtime,items=[]):
        list.__init__(self)
        for item in items:
            self.add(key_cb(item),item)
        self.key_cb=key_cb
        self.filter_tree=None
        self.tag_cloud=TagCloud()
##        self.filters=[(keyword_filter,('in','tom'))] #tests out the filtering mechanism
        self.reverse=False
    def copy(self):
        dup=Index(self.key_cb)
        dup+=self
        return dup
    def set_filter(self,expr):
        self.filter_tree=sp.parse_expr(TOKENS[:],expr)
    def clear_filter(self,expr):
        self.filter_tree=None
    def add(self,key,item):
        if self.filter_tree:
            if not sp.call_tree(bool,self.filter_tree,converter,item):
                return False
        bisect.insort(self,[key,item])
        return True
    def remove(self,key,item):
        ind=bisect.bisect_left(self,[key,item])
        i=list.__getitem__(self,ind)
        if key==i[0]:
            if item==i[1]:
                list.pop(self,ind)
                return
            raise KeyError
    def add_item(self,item):
        if self.add(self.key_cb(item),item):
            self.tag_cloud.add(item)
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
            self.tag_cloud.remove(item)
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
