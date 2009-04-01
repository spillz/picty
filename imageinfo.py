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
    def key(self):
        return 1
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
        if 'thumburi' not in self.__dict__:
            self.thumburi=None
        self.qview=None
        self.qview_size=None
        self.image=None
        self.selected=False


class Collection(list):
    def __init__(self,items):
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
            return self.pop(i)
        return None
    def __call__(self,ind):
        return self[ind]
    def __getstate__(self):
        odict = self.__dict__.copy() # copy the dict since we change it
        return odict
    def __setstate__(self,dict):
        self.__dict__.update(dict)   # update attributes


def sort_mtime(item):
    return item.mtime


def sort_ctime(item):
    try:
        date=item.meta["Exif.Photo.DateTimeOriginal"]
        if type(date)==str:
            date=datetime.strptime(date)
        return date
    except:
        return datetime.datetime(1900,1,1)

def sort_fname(item):
    return os.path.split(item.filename)[1].lower()

def sort_folder(item):
    return item.filename

def try_rational(value):
#    print 'key value',value,type(value)
    if value:
        try:
            return 1.0*int(value[0])/int(value[1])
        except:
            try:
                val=str(value).split('/')
                if val[0] and val[1]:
                    return 1.0*int(val[0])/int(val[1])
                return float(val[0])
            except:
                try:
                    return float(value)
                except:
                    return -1
    else:
        return -1

def sort_speed(item):
    try:
        return try_rational(item.meta['Exif.Photo.ExposureTime'])
    except:
        return None

def sort_aperture(item):
    try:
        return try_rational(item.meta['Exif.Photo.FNumber'])
    except:
        return None

def sort_focal(item):
    try:
        return try_rational(item.meta['Exif.Photo.FocalLength'])
    except:
        return None

def sort_orient(item):
    try:
        orient=int(item.meta['Exif.Image.Orientation'])
    except:
        orient=1
    return orient

def sort_keyword(item):
    try:
        return item.meta['Xmp.dc.subject']
    except:
        return None


sort_keys={
        'Date Taken':sort_ctime,
        'Date Last Modified':sort_mtime,
        'File Name':sort_fname,
        'Orientation':sort_orient,
        'Folder':sort_folder,
        'Shutter Speed':sort_speed,
        'Aperture':sort_aperture,
#        'ISO Speed':sort_iso,
        'Focal Length':sort_focal
        }


def mtime_filter(item,criteria):
    val=sort_mtime(item)
    if criteria[0]<=val<=criteria[1]:
        return True
    return False

def ctime_filter(item,criteria):
    val=sort_ctime(item)
    if criteria[0]<=val<=criteria[1]:
        return True
    return False

def keyword_filter(item,criteria):
    val=sort_keyword(item)
    if criteria[0]=='in':
        if val and criteria[1] in val.lower():
            return True

class Index(list):
    def __init__(self,key_cb=sort_mtime,items=[]):
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
        print 'finding',i,self.key_cb(item),item
        if i>=len(self) or i<0:
            return -1
        print 'found',i,self[i],item,item<self[i][1],item>self[i][1]
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
