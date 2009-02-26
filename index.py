import bisect

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
