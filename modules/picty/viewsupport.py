'''

    picty
    Copyright (C) 2013  Damien Moore

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
this module defines helper functions for:
    1. generating human readable image metadata for display in the view
    2. sorting and filtering the view
'''


##standard imports
import bisect
import datetime
import os.path
import re

##picty imports
import pluginmanager
import simple_parser as sp
import metadata
import settings


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
    return os.path.split(item.uid)[1].lower()

def get_folder(item):
    return item.uid

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

def none_filter(l,r,item=None):
    return True

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
    return item.is_meta_changed()

def tagged_filter(l,r,item):
    if item.meta==None:
        return False
    if 'Keywords' not in item.meta:
        return False
    if not item.meta['Keywords']:
        return False
    if len(item.meta['Keywords'])>0:
        return True
    return item.meta['Keywords']

def geotagged_filter(l,r,item):
    if item.meta==None:
        return False
    if 'LatLon' not in item.meta:
        return False
    if not item.meta['LatLon']:
        return False
    return item.meta['LatLon']

def keyword_filter(item,test):
    if not test:
        return True
    test=test.lower()
    relevance=0
    item_string=''
    item_string+=item.uid.lower()
    if item.meta!=None:
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

class DateTime(list):
    def __init__(self,list_object):
        list.__init__(self,list_object)
        dtlen=len(list_object)
        dtlist=list_object[:]
        dtlist+=[1]*max(0,7-dtlen)
        self.datetime=datetime.datetime(*dtlist)

class DateCompare:
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
            cmplen=len(r)
            fulldatetime=metadata.app_key_as_sortable(item.meta,self.field)
            trimdtlist=[fulldatetime.year,fulldatetime.month,fulldatetime.day,fulldatetime.hour,fulldatetime.minute,fulldatetime.second,fulldatetime.microsecond]
            if cmplen<len(trimdtlist):
                trimdtlist[cmplen:]=[1]*(len(trimdtlist)-cmplen)
            trimdtlist+=[1]*max(0,7-len(trimdtlist))
            trimdt=datetime.datetime(*trimdtlist)
            return self.op(trimdt,r.datetime)
        except:
            return False
    def call2(self,l,r,item):
        #text=r.strip()
        try:
            cmplen=len(r)
            fulldatetime=datetime.datetime.fromtimestamp(item.mtime)
            trimdtlist=[fulldatetime.year,fulldatetime.month,fulldatetime.day,fulldatetime.hour,fulldatetime.minute,fulldatetime.second,fulldatetime.microsecond]
            if cmplen<len(trimdtlist):
                trimdtlist[cmplen:]=[1]*(len(trimdtlist)-cmplen)
            trimdtlist+=[1]*max(0,7-len(trimdtlist))
            trimdt=datetime.datetime(*trimdtlist)
            return self.op(trimdt,r.datetime)
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

def str2datetime_list(val,item=None):
    match=date_re.match(val) ##todo: should only need to do this once per search not for every item
    if not match:
        return False
    date_list=[]
    for g in match.groups():
        if g:
            date_list.append(int(g))
        else:
            break
    return DateTime(date_list)


literal_converter={
(str,DateTime):str2datetime_list
}

converter={
(str,bool):str2bool,
(str,DateTime):str2datetime_list
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
('mdate=',(DateCompare('DateMod',eq,True),None,DateTime)),
('mdate>=',(DateCompare('DateMod',ge,True),None,DateTime)),
('mdate<=',(DateCompare('DateMod',le,True),None,DateTime)),
('mdate>',(DateCompare('DateMod',gt,True),None,DateTime)),
('mdate<',(DateCompare('DateMod',lt,True),None,DateTime)),
('date=',(DateCompare('DateTaken'),None,DateTime)),
('date>=',(DateCompare('DateTaken',ge),None,DateTime)),
('date<=',(DateCompare('DateTaken',le),None,DateTime)),
('date>',(DateCompare('DateTaken',gt),None,DateTime)),
('date<',(DateCompare('DateTaken',lt),None,DateTime)),
('selected',(selected_filter,None,None)),
('changed',(changed_filter,None,None)),
('geotagged',(geotagged_filter,None,None)),
('tagged',(tagged_filter,None,None)),
]

