import gtk
import gobject
import settings
import os.path


TYPE=0
PATH=1
COLLECTION=2
DISPLAY_NAME=3
ICON_LIST=4
PIXBUF=5

COMBO_ID=0
COMBO_NAME=1
COMBO_FONT_WGT=2
COMBO_PIXBUF=3
COMBO_OPEN=4

class CollectionData:
    def __init__(self,type,path,collection,name,icon_list):
        self.type=type
        self.path=path
        self.collection=collection
        self.name=name
        self.icon_list=icon_list
        self.pixbuf=self.get_icon(icon_list)
    def __getitem__(self,index):
        return [self.type,self.path,self.collection,self.icon_list,self.pixbuf][index]
    def get_icon(self, icon_id_list):
        t=gtk.icon_theme_get_default()
        ii=t.choose_icon(icon_id_list,gtk.ICON_SIZE_MENU,0)
        return None if not ii else ii.load_icon()


class CollectionSet(gtk.GenericTreeModel):
    '''
    Defines sets of image collections, managed with a dictionary like syntax
    c[key]=value
    where
     key is a uniquely identifying name (string)
     value is [type, path/uri, collection, display_name, icon_data]
     type is caller defined, but for example 'COLLECTION', 'DIRECTORY', 'DEVICE', 'WEBSERVICE'
     path/uri is the directory location of the images or a path to a collection file
     colleciton is a collection or none if the colleciton is not open
     display_name is the name shown to the user (usually == key value??)
     icon_str is the string identifying the icon
    also implements various iterators for retrieving collection info
    Derives from gtk.GenericTreeModel allowing user interaction as a gtk.ComboBox or gtk.TreeView
    '''
    def __init__(self):
        gtk.GenericTreeModel.__init__(self)
        self.collections={}
        self.types=['LOCALSTORE','DEVICE','DIRECTORY']
    def __iter__(self):
        '''
        iterator yielding all open collections
        '''
        for c in self.collections:
            yield c
    def iter_id(self,ctype=None):
        '''
        iterator yielding the unique id of all open collections
        '''
        for c in self.collections:
            if not ctype or self.collections[c][TYPE]==ctype:
                yield c
    def iter_coll(self,ctype=None):
        '''
        iterates over the open collections yielding the collection matching ctype
        '''
        for c in self.collections:
            if not ctype or self.collections[c][TYPE]==ctype:
                if self.collections[c][COLLECTION]:
                    yield self.collections[c][COLLECTION]
    def iter_info(self,ctype=None):
        '''
        iterates over the collections yielding the colleciton information list matching ctype
        '''
        for c in self.collections:
            if not ctype or self.collections[c][TYPE]==ctype:
                if self.collections[c][COLLECTION]:
                    yield self.collections[c]
    def __getitem__(self,name):
        '''
        if passed a string name, returns the CollectionData entry
        if passed an iter, returns the model row as a list
        '''
        if isinstance(name,gtk.TreeIter):
            name=self.get_user_data(name)
            return self.as_row(name)
        return self.collections[name]
    def pi_from_name(self,name):
        iter=self.create_tree_iter(name)
        return self.get_path(iter),iter
    def __setitem__(self,name,value):
        if isinstance(name,gtk.TreeIter):
            name=self.get_user_data(name)
        if not isinstance(value,CollectionData):
             raise ValueError("CollectionSet Error: invalid value "+str(value))
        added=True if name not in self.collections else False
        self.collections[name]=value
        if added:
            self.row_inserted(*self.pi_from_name(name))
        else:
            self.row_changed(*self.pi_from_name(name))
    def __del__(self,name):
        del self.collections[name]
        path=self._get_path(name)
        self.row_deleted(*self.pi_from_name(name))
    def clear(self):
        for name in self.collections:
            del self[name]
    def get_icon(self, icon_id_list):
        t=gtk.icon_theme_get_default()
        ii=t.choose_icon(icon_id_list,gtk.ICON_SIZE_MENU,0)
        return None if not ii else ii.load_icon()
    def add_mount(self,path,collection,name,icon_names):
        coll=self[path][COLLECTION]
        self[path]=CollectionData('DEVICE',path,collection,name,icon_names,self.get_icon(icon_names))
    def remove_mount(self,path):
        coll=self[path][COLLECTION]
        del self[path]
        return coll
    def init_localstores(self):
        for col_file in settings.get_collection_files():
            col_path=os.path.join(settings.collections_dir,col_file)
            self[col_path]=CollectionData('LOCALSTORE',col_path,None,col_file,[gtk.STOCK_HARDDISK])
    def init_mounts(self,mount_info):
        for name,icon_names,path in mount_info:
##            collection=self.worker.collections_find_by_path(path)
            self[path]=CollectionData('DEVICE',path,None,name,icon_names)

##    def init_view(self):
##        #display_name, font_wgt, Pixbuf, coll_type, path/uri, collection
##        self.model.clear()
##        if self.init_type('COLLECTION')>0:
##            self.append_separator()
##        if self.init_type('DEVICE')>0:
##            self.append_separator()
##        self.init_type('DIRECTORY')

    '''
    implementing gtk.TreeModel (see pygtk tutorial)
    '''
    def on_get_flags(self):
        return gtk.TREE_MODEL_LIST_ONLY
    def on_get_n_columns(self):
        return ICON_LIST+2
    def on_get_column_type(self, index):
        return [str,str,int,gtk.gdk.Pixbuf,bool][index]
    def view_iter(self):
        '''
        this iterator defines the rows of the collection model
        '''
        tcount=0
        options=['#new-coll',None,'#add-dir']
        for t in self.types:
            if tcount>0:
                yield '*%i'%(tcount,)
                if options[tcount]:
                    yield options[tcount]
            for id in self.iter_id(t):
                yield id
            tcount+=1
    def on_get_iter(self, path):
        i=0
        for id in self.view_iter():
            if i==path[0]:
                return id
            i+=1
        return None
#    def _get_path(self, name):
#        i=0
#        for id in self.view_iter():
#            if name==id:
#                return (i,)
#            i+=1
#        return None
    def on_get_path(self, rowref):
        i=0
        for id in self.view_iter():
            if id==rowref:
                return i
            i+=1
        return None
    def as_row(self,id):
#        print 'as_row called',rowref
#        id=self.get_user_data(rowref)
        if id.startswith('*'):
            return [id,'',800,None,False]
        if id.startswith('#'):
            return [id,id[1:],400,None,False] ##todo: replace id[1:] with a dictionary lookup to a meaningful description
        ci=self.collections[id]
        if ci[COLLECTION]:
            return [id,ci.name,800,ci.pixbuf,True]
        else:
            return [id,ci.name,400,ci.pixbuf,False]
    def on_get_value(self, rowref, column):
        return self.as_row(rowref)[column]
    def on_iter_next(self, rowref):
        i=0
        for id in self.view_iter():
            if id==rowref:
                return i+1
            i+=1
    def on_iter_children(self, parent):
        return None
    def on_iter_has_child(self, rowref):
        return False
    def on_iter_n_children(self, rowref):
        if rowref==None:
            return sum([1 for r in self.view_iter()])
        return 0
    def on_iter_nth_child(self, parent, n):
        if parent:
            return None
        return self.on_get_iter((n,))
    def on_iter_parent(self, child):
        return None



##Combo entries

##[] COLLECTIONS X
##[Manage collections...]
##---------------------
##[] DEVICES X
##[Manage devices...]
##---------------------
##[] DIRECTORIES X
##[Open Directory...]

##[] == icon
## name text is highlighted for open collections
## X == close button


class CollectionCombo(gtk.VBox):
    __gsignals__={
        'collection-changed':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(str,)), #user selects a collection
        'collection-toggled':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(str,)), #user toggles the collection button
        'add-dir':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,tuple()), #user choooses the "browse dir" button
        'add-localstore':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,tuple()), #user chooses the "new collection" button
        }
    def __init__(self,collection_set):
        gtk.VBox.__init__(self)
        self.model=collection_set

        self.combo=gtk.ComboBox(self.model)
        self.combo.set_row_separator_func(self.sep_cb)
        cpb=gtk.CellRendererPixbuf()
        self.combo.pack_start(cpb,False)
        self.combo.add_attribute(cpb, 'pixbuf', COMBO_PIXBUF)
        cpt=gtk.CellRendererText()
        self.combo.pack_start(cpt,False)
        self.combo.add_attribute(cpt, 'text', COMBO_NAME)
        self.combo.add_attribute(cpt, 'weight', COMBO_FONT_WGT)

        cpto=gtk.CellRendererToggle()
        self.combo.pack_start(cpto,False)
        self.combo.add_attribute(cpto, 'active', COMBO_OPEN)

        self.combo.show()
        self.pack_start(self.combo)
        self.combo.connect("changed",self.changed)
    def changed(self,combo):
        iter=combo.get_active_iter()
        id=self.model[iter][COMBO_ID]
        if id=='#add_dir':
            self.emit('add-dir')
        elif id=='#add-localstore':
            self.emit('add-localstore')
        elif not id.startswith('*'):
            self.emit('collection-changed',id)
    def sep_cb(self, model, iter):
        '''
        callback determining whether a row should appear as a separator in the combo
        '''
        if self.model[iter][COMBO_NAME].startswith('*'):
            return True
        return False
    def get_choice(self):
        iter=self.combo.get_active_iter()
        if iter!='':
            return self.model[iter][COMBO_ID]
    def set_active(self,id):
        if id:
            self.combo.set_active_iter(self.model.create_tree_iter(id))


gobject.type_register(CollectionCombo)



'''
class Manager:
    def __init__(self,worker):
        self.coll_set=collectionset.CollectionSet()
        self.coll_combo=CollectionCombo(self.coll_set)
        self.volume_monitor=io.VolumeMonitor()
        self.volume_monitor.connect("mount-added",self.mount_added)
        self.volume_monitor.connect("mount-removed",self.mount_removed)
        self.active_collection_id=None
        self.coll_combo.connect("changed",self.changed_collection)
    def collection_changed(self,model,iter):
        self.active_collection_id=iter
    def mount_added(self,name,icon_names,path):
        self.coll_set.add_mount(path,name,icon_names)
        self.coll_combo.init_view()
    def mount_removed(self,name,icon_names,path):
        collection=self.coll_set[path].collection
        self.coll_set.remove_mount(path)
        self.coll_combo.init_view()
    def add_dir(self,name,path):
        pass
    def remove_dir(self,name):
        pass
    def add_localstore(self,name,path,collection):
        pass
    def remove_localstore(self,name,path,collection):
        pass
'''

