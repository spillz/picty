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
this module defines the view class (a sorted subset of the collection of the images)
and helper functions to sort and filter the view
'''


##standard imports
import bisect
import datetime
import os.path
import re
import datetime

##phraymd imports
import pluginmanager
import simple_parser as sp
import metadata


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
        return ', '.join(item.meta['Keywords'])
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
    exposure=u''
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
    val=get_keyword(item)
    #print 'KEYWORDS:',len(val),val,type(val)
    if val:
        val=str(val)
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
            return self.op(metadata.app_key_as_sortable(item.meta,self.field),val)
        except:
##            print 'error on item',item,val
##            print metadata.app_key_as_sortable(item.meta,self.field)
##            print self.op(val,metadata.app_key_as_sortable(item.meta,self.field))
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
            return self.op(metadata.app_key_as_sortable(item.meta,self.field),val)
        except:
            print 'int cmp fail',item,val
            print metadata.app_key_as_sortable(item.meta,self.field)
            print self.op(metadata.app_key_as_sortable(item.meta,self.field),val)
            return False

date_re=re.compile(r'(\d{4})(?:[\-\/](\d{1,2}))?(?:[\-\/](\d{1,2}))?(?:[;, -](\d{1,2}))?(?:[:-](\d{1,2}))?(?:[:-](\d{1,2}))?')

class DateCompare: ##todo: this compares only the date part of the datetime, also need a datetime compare class
    def __init__(self,field,op=eq,mdate=False):
        self.field=field
        self.op=op
#        self.__call__=self.call1
        if mdate:
            self.__call__=self.call2
        else:
            self.__call__=self.call1
    def call1(self,l,r,item):
        try:
            fulldatetime=metadata.app_key_as_sortable(item.meta,self.field)
            dateonly=datetime.datetime(fulldatetime.year,fulldatetime.month,fulldatetime.day)
            return self.op(dateonly,r)
        except:
            return False
    def call2(self,l,r,item):
        #text=r.strip()
        try:
            fulldatetime=datetime.datetime.fromtimestamp(item.mtime)
            dateonly=datetime.datetime(fulldatetime.year,fulldatetime.month,fulldatetime.day)
            return self.op(dateonly,r)
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


def str2datetime(val,item=None):
    match=date_re.match(val) ##todo: should only need to do this once per search not for every item
    if not match:
        return False
    date_list=[]
    for g in match.groups():
        if g:
            date_list.append(int(g))
        else:
            break
    date_list+=[1]*max(0,3-len(date_list))
    return datetime.datetime(*date_list)


literal_converter={
(str,datetime.datetime):str2datetime
}

converter={
(str,bool):str2bool,
(str,datetime.datetime):str2datetime
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
('mdate=',(DateCompare('DateMod',eq,True),None,datetime.datetime)),
('mdate>=',(DateCompare('DateMod',ge,True),None,datetime.datetime)),
('mdate<=',(DateCompare('DateMod',le,True),None,datetime.datetime)),
('mdate>',(DateCompare('DateMod',gt,True),None,datetime.datetime)),
('mdate<',(DateCompare('DateMod',lt,True),None,datetime.datetime)),
('date=',(DateCompare('DateTaken'),None,datetime.datetime)),
('date>=',(DateCompare('DateTaken',ge),None,datetime.datetime)),
('date<=',(DateCompare('DateTaken',le),None,datetime.datetime)),
('date>',(DateCompare('DateTaken',gt),None,datetime.datetime)),
('date<',(DateCompare('DateTaken',lt),None,datetime.datetime)),
('selected',(selected_filter,None,None)),
('changed',(changed_filter,None,None)),
('tagged',(tagged_filter,None,None))
]


class Index():
    def __init__(self,key_cb=get_mtime,items=[],collection=None):
        self.items=[]
        for item in items:
            self.add(key_cb(item),item)
        self.key_cb=key_cb
        self.sort_key_text=''
        for text,cb in sort_keys.iteritems():
            if cb==key_cb:
                self.sort_key_text=text
        self.filter_tree=None
        self.filter_text=''
        self.reverse=False
        self.collection=collection
    def copy(self):
        dup=Index(self.key_cb)
        dup.sort_key_text=self.sort_key_text
        dup.filter_tree=self.filter_tree
        dup.filter_text=self.filter_text
        dup.collection=collection
        dup.items[:]=self.items[:]
        return dup
    def set_filter(self,expr):
        self.filter_tree=sp.parse_expr(TOKENS[:],expr,literal_converter)
    def clear_filter(self,expr):
        self.filter_tree=None
    def add(self,key,item,apply_filter=True):
        if apply_filter and self.filter_tree:
            if not sp.call_tree(bool,self.filter_tree,converter,item):
                return False
        bisect.insort(self.items,[key,item])
        return True
    def remove(self,key,item):
        ind=bisect.bisect_left(self.items,[key,item])
        i=list.__getitem__(self.items,ind)
        if key==i[0]:
            if item==i[1]:
                list.pop(self.items,ind)
                return
            raise KeyError
    def add_item(self,item,apply_filter=True):
        if self.add(self.key_cb(item),item,apply_filter):
            pluginmanager.mgr.callback_collection('t_collection_item_added_to_view',self.collection,self,item)
    def find_item(self,item):
        i=bisect.bisect_left(self.items,[self.key_cb(item),item])
        if i>=len(self) or i<0:
            return -1
        if self.items[i][1]==item:
            return i if not self.reverse else len(self.items)-1-i
        return -1
    def del_ind(self,ind):
        ##todo: check ind is in the required range
        if self.reverse:
            i=len(self.items)-1-ind
            pluginmanager.mgr.callback_collection('t_collection_item_removed_from_view',self.collection,self,self.items[i])
            del self.items[i]
        else:
            pluginmanager.mgr.callback_collection('t_collection_item_removed_from_view',self.collection,self,self.items[ind])
            del self.items[ind]
    def del_item(self,item):
        ind=self.find_item(item)
        if ind>=0:
            self.del_ind(ind)
            return True
        return False
    def __call__(self,index):
        if index>=len(self):
            return
        if self.reverse:
            return self.items[len(self.items)-1-index][1]
        else:
            return self.items[index][1]
    def __len__(self):
        return len(self.items)
    def get_items(self,first,last):
        if self.reverse:
            return [i[1] for i in self.items[len(self.items)-last:len(self.items)-first]]
        else:
            return [i[1] for i in self.items[first:last]]
    def get_selected_items(self):
        return [i[1] for i in self.items if i[1].selected]
    def empty(self):
        del self.items[:]
