import bisect
import threading
import datetime

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


class Index(list):
    def __init__(self,key_cb=sort_mtime,items=[]):
        list.__init__(self)
        for item in items:
            self.add(key_cb(item),item)
        self.key_cb=key_cb
        self.reverse=False
    def add(self,key,item):
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
