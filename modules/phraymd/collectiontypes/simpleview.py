from phraymd import baseobjects, viewsupport, pluginmanager, simple_parser as sp
import bisect
import cPickle

class SimpleView(baseobjects.ViewBase):
    def __init__(self,key_cb=viewsupport.get_mtime,items=[],collection=None):
        self.items=[]
        for item in items:
            self.add(key_cb(item),item)
        self.key_cb=key_cb
        self.sort_key_text=''
        for text,cb in collection.browser_sort_keys.iteritems():
            if cb==key_cb:
                self.sort_key_text=text
        self.filter_tree=None
        self.filter_text=''
        self.reverse=False
        self.collection=collection
        self.loaded=False
    def load(self,file_handle):
        '''
        reconstruct the view by loading it from the file_handle
        using pickle to load the keys and current filter
        '''
        items,self.filter_text,self.reverse = cPickle.load(file_handle)
        self.items = [[key, self.collection[self.collection.find(uid)] ] for (key,uid) in items]
        self.loaded=True
    def save(self,file_handle):
        '''
        save the list of keys and uids in the view to the file_handle
        '''
        items = [(key,item.uid) for (key,item) in self.items]
        view_data = (items,self.filter_text,self.reverse)
        cPickle.dump(view_data,file_handle,-1)
        print 'SAVED VIEW',self
    def copy(self):
        dup=SimpleView(self.key_cb,[],self.collection)
        dup.sort_key_text=self.sort_key_text
        dup.filter_tree=self.filter_tree
        dup.filter_text=self.filter_text
        dup.reverse=self.reverse
        dup.items[:]=self.items[:]
        return dup
    def set_filter(self,expr):
        self.filter_tree=sp.parse_expr(viewsupport.TOKENS[:],expr,viewsupport.literal_converter)
    def clear_filter(self,expr):
        self.filter_tree=None
    def add(self,key,item,apply_filter=True):
        if apply_filter and self.filter_tree:
            if not sp.call_tree(bool,self.filter_tree,viewsupport.converter,item):
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
            pluginmanager.mgr.callback_collection('t_collection_item_removed_from_view',self.collection,self,self.items[i][1])
            del self.items[i]
        else:
            pluginmanager.mgr.callback_collection('t_collection_item_removed_from_view',self.collection,self,self.items[ind][1])
            del self.items[ind]
    def del_item(self,item):
        ind=self.find_item(item)
        if ind>=0:
            self.del_ind(ind)
            return True
        return False
    def __call__(self,index):
        if index<0 or index>=len(self):
            return
        return self[index]
    def __getitem__(self,index):
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


baseobjects.register_view('SIMPLEVIEW',SimpleView)
