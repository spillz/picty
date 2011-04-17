import pluginmanager
import viewsupport
import os.path
import cPickle
import settings

registered_collection_classes={}
registered_view_classes={}
registered_item_classes={}


def register_collection(type_id,class0):
    registered_collection_classes[type_id]=class0
def register_view(type_id,class0):
    registered_view_classes[type_id]=class0
def register_item(type_id,class0):
    registered_item_classes[type_id]=class0

def init_collection(col_dir):
    try:
        if os.path.isfile(col_dir):
            return None
        f=open(os.path.join(col_dir,'prefs'),'rb')
        version=cPickle.load(f)
        prefs={'type':'LOCALSTORE','name':os.path.split(col_dir)[1],'id':col_dir}
        if version<'0.3.0':
            prefs['image_dirs']=settings.legacy_image_dirs
        elif version<'0.4.0':
            prefs['image_dirs']=cPickle.load(f)
        elif version>='0.4.1':
            prefs=cPickle.load(f)
        try:
            c=registered_collection_classes[prefs['type']](prefs)
        except KeyError:
            c=registered_collection_classes['LOCALSTORE'](prefs)
        c.add_view()
        return c
    except:
        import traceback,sys
        tb_text=traceback.format_exc(sys.exc_info()[2])
        print "Error Creating Collection"
        print tb_text
        return None


def create_empty_collection(name,prefs,overwrite_if_exists=False):
    col_dir=os.path.join(settings.collections_dir,name)
    pref_file=os.path.join(os.path.join(settings.collections_dir,name),'prefs')
    data_file=os.path.join(os.path.join(settings.collections_dir,name),'data')
    if not overwrite_if_exists:
        if os.path.exists(col_dir):
            return False
    try:
        if not os.path.exists(col_dir):
            os.makedirs(col_dir)
        f=open(pref_file,'wb')
        cPickle.dump(settings.version,f,-1)
#        d={}
#        for p in col_prefs: ##todo: col_prefs should be a member of the relevant collection class
#            if p in prefs:
#                d[p]=prefs[p]
        cPickle.dump(prefs,f,-1)
        f.close()
        f=open(data_file,'wb')
        cPickle.dump(settings.version,f,-1)
        cPickle.dump([],f,-1) #empty list of items
        f.close()
    except:
        print 'Error writing empty collection to ',col_dir
        import traceback,sys
        tb_text=traceback.format_exc(sys.exc_info()[2])
        print tb_text
        return False
    return True


class CollectionBase:
    pref_items=['type','type_descr','name','pixbuf','id'] ##the list of variables that will be saved
    persistent=False
    type=None
    user_creatable=False
    pref_widget=None
    add_widget=None
    def __init__(self,prefs=None):
        self.is_open=False
        self.numselected=0
        self.views=[]
        self.active_view=None

        self.name=''
        self.pixbuf=None
        self.id=''
        if prefs:
            self.set_prefs(prefs)

    def set_prefs(self,prefs):
        for p in self.pref_items:
            if p in prefs:
                self.__dict__[p]=prefs[p]

    def get_prefs(self):
        prefs={}
        for p in self.pref_items:
            prefs[p]=self.__dict__[p]
        return prefs

    def pref_file(self):
        return os.path.join(os.path.join(settings.collections_dir,self.name),'prefs')

    def data_file(self):
        return os.path.join(os.path.join(settings.collections_dir,self.name),'data')

    def delete_store(self):
        os.remove


    def add_view(self,sort_criteria=viewsupport.get_mtime):
        if self.view_class==None:
            return None
        view=self.view_class(sort_criteria,[],self)
        self.views.append(view)
        if not self.active_view:
            self.active_view=view
        return view

    def remove_view(self,view):
        ind=self.view.find(view)
        if ind>=0:
            del self.views[ind]
            return view
        return False

    def set_active_view(self,view):
        if view in self.views:
            self.active_view=view

    def get_active_view(self):
        return self.active_view

    ##required overrides (must be overridden to implement a collection)
    def pref_gui_box(self):
        pass
    def add(self,item,add_to_view=True):
        '''
        provider should send 't_collection_item_added' to plugins
        '''
        pass
    def item_metadata_update(self,item):
        '''
        notification from item that its metadata has been changed
        '''
#        '''
#        provider should send 't_collection_item_updated' to plugins --NOT SURE IF NECESSARY
#        '''
        pass
    def find(self,item):
        pass
    def delete(self,item,delete_from_view=True):
        '''
        provider should send 't_collection_item_removed' to plugins
        '''
        pass
    def __call__(self,ind):
        pass
    def __getitem__(self,ind):
        pass
    def get_all_items(self): #was get_items
        pass
    def open(self):
        return True
    def close(self):
        return True
    def empty(self,empty_views=True):
        pass
    def __len__(self):
        pass
    def load_thumbnail(self,item):
        pass
    def make_thumbnail(self,item,pixbuf):
        pass
    def get_pixbuf(self,item,size_bound=None):
        pass
    def set_pixbuf(self,item):
        pass
    def get_file_data(self,item):
        pass
    def set_file_data(self,item):
        pass


class ViewBase: ##base class for the filter view of a collection and (for now) reference implementation
    def __init__(self,key_cb=viewsupport.get_mtime,items=[],collection=None):
        self.key_cb=key_cb
        self.sort_key_text=''
        for text,cb in viewsupport.sort_keys.iteritems():
            if cb==key_cb:
                self.sort_key_text=text
        self.filter_tree=None
        self.filter_text=''
        self.reverse=False
        self.collection=collection
    def __call__(self,ind):
        pass
    def __getitem__(self,ind):
        pass
    def set_filter(self,expr):
        self.filter_tree=sp.parse_expr(viewsupport.TOKENS[:],expr,viewsupport.literal_converter)
    def clear_filter(self,expr):
        self.filter_tree=None
    def add_item(self,item,apply_filter=True):
        '''
        add item to the view
        provider should send 't_collection_item_added_to_view' notification to plugins
        '''
    def find_item(self,item):
        '''
        return the index position whose for a given item in the collection
        '''
    def del_item(self,item):
        '''
        delete the item from the view
        provider should send a 't_collection_item_removed_from_view' notification to plugins
        '''
    def del_ind(self,ind):
        ##todo: check ind is in the required range
        '''
        delete the item at position ind from the collection
        provider should send a 't_collection_item_removed_from_view' notification to plugins
        '''
    def __getitem__(self,index):
        pass
    def __call__(self,index):
        pass
    def __len__(self):
        pass
    def get_items(self,first,last):
        pass
    def get_selected_items(self):
        pass
    def empty(self):
        '''
        removes all items from the view
        provider should send a 't_view_emptied' notification to plugins
        '''
        pass


class Item(str):
    '''An item is a class describing an image file, including filename, pixbuf representations and related metadata'''
    ##an item is not a baseclass. thus, all collections share a common item type
    def __init__(self,uid):  ##LEGACY CONSTRUCTOR TAKES mtime
        str.__init__(uid)
        self.uid=uid
        self.mtime=None ##todo: move this to the meta dictionary
        self.thumb=None
        self.thumburi=None
        self.qview=None
        self.image=None
        self.meta_changed=False
        self.meta=None ##a copy of self.meta will be stored as self.meta_backup if self.meta_changed is True
        self.selected=False
        self.relevance=0
        ##TODO: should an item have a collection member?

    def load_thumbnail(self):
        pass
    def make_thumbnail(self,pixbuf):
        pass
    def get_pixbuf(self,size_bound):
        '''
        returns a pixbuf no larger than the dimensions in size_bound
        return none if no fullsize image available
        '''
        pass
    def key(self):
        return 1
    def meta_revert(self,collection=None):
        if self.meta_changed:
            self.meta=self.meta_backup
            del self.meta_backup
        self.meta_changed=False
        if collection:
            collection.item_metadata_update(self)
    def mark_meta_saved(self,collection=None):
        if self.meta_changed:
            del self.meta_backup
        self.meta_changed=False
        if collection:
            collection.item_metadata_update(self)
    def set_meta_key(self,key,value,collection=None):
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
        if self.meta==self.meta_backup:
            del self.meta_backup
            self.meta_changed=False
        if collection:
            pluginmanager.mgr.callback_collection('t_collection_item_metadata_changed',collection,self,old)
            collection.item_metadata_update(self)
        return self.meta_changed
    def set_meta(self,meta,collection=None):
        if not self.meta_changed:
            self.meta_backup=self.meta.copy()
            self.meta_changed=True
        old=self.meta
        self.meta=meta
        if self.meta==self.meta_backup:
            del self.meta_backup
            self.meta_changed=False
        if collection:
            pluginmanager.mgr.callback_collection('t_collection_item_metadata_changed',collection,self,old)
            collection.item_metadata_update(self)
        return self.meta_changed
    def __getstate__(self):
        odict = self.__dict__.copy() # copy the dict since we change it
        if odict['thumb']:
            odict['thumb']=None
        del odict['qview']
        del odict['image']
        del odict['selected']
        del odict['relevance']
        return odict
    def __setstate__(self,dict):
        self.__dict__.update(dict)   # update attributes
        self.thumb=None
        self.qview=None
        self.image=None
        self.selected=False
        self.relevance=0
