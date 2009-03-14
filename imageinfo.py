import bisect
import threading


class Item(list):
    def __init__(self,filename,mtime):
        list.__init__(self,[filename])
        self.filename=filename
        self.mtime=mtime
        self.thumbsize=(0,0)
        self.thumb=None
        self.meta=None
        self.thumbrgba=False
        self.qview=None
        self.qview_size=None
        self.image=None
        self.cannot_thumb=False
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
        return odict
    def __setstate__(self,dict):
        self.__dict__.update(dict)   # update attributes
        self.thumbsize=None
        self.thumb=None
        self.thumbrgba=False
        self.qview=None
        self.qview_size=None
        self.image=None

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
    def __getstate__(self):
        odict = self.__dict__.copy() # copy the dict since we change it
        return odict
    def __setstate__(self,dict):
        self.__dict__.update(dict)   # update attributes

def sort_mtime(item):
    return item

class Index(list):
    def __init__(self,items=[],key_cb=sort_mtime):
        list.__init__(self)
        for item in items:
            self.add(key_cb(item),item)
    def add(self,key,item):
        bisect.insort(self,(key,item))
    def remove(self,key,item):
        ind=bisect.bisect_left(self,(key,item))
        print ind
        i=list.__getitem__(self,ind)
        if key==i[0]:
            if item==i[1]:
                list.pop(self,ind)
                return
            raise KeyError

if __name__=='__main__':
    a=Index([5,4,1,2])
    print a
    a.add(3,3)
    print a
    a.remove(2,2)
    print a
