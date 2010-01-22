import gtk
import gobject
import settings
import os.path

import collections


COMBO_ID=0
COMBO_NAME=1
COMBO_FONT_WGT=2
COMBO_FONT_COLOR_SET=3
COMBO_FONT_COLOR=4
COMBO_PIXBUF=5
COMBO_OPEN=6

def combo_cols(coll,index):
    return [coll.type,coll.path,coll.collection,coll.icon_list,coll.pixbuf][index]

def get_icon(icon_id_list):
    t=gtk.icon_theme_get_default()
    ii=t.choose_icon(icon_id_list,gtk.ICON_SIZE_MENU,0)
    return None if not ii else ii.load_icon()


class CollectionSet(gtk.GenericTreeModel):
    '''
    Defines a set of image collections, managed with a dictionary like syntax
    The program should use this class to create and remove collections
    c[key]=value
    where
     key is a uniquely identifying name (string)
     value is [type, path/uri, collection, display_name, icon_data]
     type is caller defined, but for example 'COLLECTION', 'DIRECTORY', 'DEVICE', 'WEBSERVICE'
     path/uri is the directory location of the images or a path to a collection file
     colleciton is a collection or none if the colleciton is not open
     display_name is the name shown to the user (usually == key value??)
     icon_str is the string identifying the icon
    also:
     implements various iterators for retrieving collection info
     derives from gtk.GenericTreeModel allowing user interaction as a gtk.ComboBox or gtk.TreeView
    '''
    def __init__(self):
        gtk.GenericTreeModel.__init__(self)
        self.collections={}
        self.types=['LOCALSTORE','DEVICE','DIRECTORY']
        for r in self.view_iter():
            self.row_inserted(*self.pi_from_id(r))
    def __iter__(self):
        '''
        iterator yielding all open collections
        '''
        for id,c in self.collections.iteritems():
            if c.is_open:
                yield c
    def iter_id(self,ctype=None):
        '''
        iterator yielding the unique id of all collections
        '''
        for id,c in self.collections.iteritems():
            if not ctype or c.type==ctype:
                yield id
    def iter_coll(self,ctype=None):
        '''
        iterates over the open collections yielding the collection matching ctype
        '''
        for id,c in self.collections.iteritems():
            if not ctype or c.type==ctype:
                if c.is_open:
                    yield c
    def __getitem__(self,name):
        '''
        if name is an id returns the collection
        if name is an iter returns the collection descriptive data as a row from a tree model (list)
        '''
        if not name:
            return
        if isinstance(name,gtk.TreeIter):
            id=self.get_user_data(name)
            return self.as_row(id)
        return self.collections[name]
    def pi_from_id(self,name): #return tuple of path and iter associated with the unique identifier
        iter=self.create_tree_iter(name)
        return self.get_path(iter),iter
#    def __setitem__(self,name,value):
#        if isinstance(name,gtk.TreeIter):
#            id=self.get_user_data(name)
#        if isinstance(name,str):
#            id=name
#        if not isinstance(value,Collection):
#             raise ValueError("CollectionSet Error: invalid value "+str(value))
#        added=True if id not in self.collections else False
#        self.collections[id]=value
#        if added:
#            self.row_inserted(*self.pi_from_id(id))
#        else:
#            self.row_changed(*self.pi_from_id(id))
    def __delitem__(self,name):
        coll=self.collections[name]
        self.row_deleted(*self.pi_from_id(name)[0])
        del self.collections[name]
        path=self.on_get_path(name)
        if coll.type=='DEVICE':
            self.row_inserted(*self.pi_from_id('#no-devices'))
    def clear(self):
        for id in self.collections:
            del self[id]
    def get_icon(self, icon_id_list):
        t=gtk.icon_theme_get_default()
        ii=t.choose_icon(icon_id_list,gtk.ICON_SIZE_MENU,0)
        return None if not ii else ii.load_icon()
    def count(self,type=None):
        return sum([1 for id in self.iter_id(type)])
    def add_mount(self,path,name,icon_names):
        c=collections.Collection()
        c.type='DEVICE'
        c.image_dirs=[path] ##todo: if device collection data is stored persistently, what to do if path changes?
        c.name=name
        c.id=path
        c.pixbuf=self.get_icon(icon_names)
        c.add_view()
        if self.count('DEVICE')==0:
            self.row_deleted(*self.pi_from_id('#no-devices')[0])
        self.collections[c.id]=c
        self.row_inserted(*self.pi_from_id(c.id))
        return c
    def add_localstore(self,col_file):
        c=collections.Collection()
        col_path=os.path.join(settings.collections_dir,col_file)
        c.filename=col_path
        c.name=col_file
        c.id=col_path
        c.type='LOCALSTORE'
        c.add_view()
        self.collections[col_path]=c
        self.row_inserted(*self.pi_from_id(c.id))
        return c
    def add_directory(self,path,recursive=False):
        c=collections.Collection()
        c.filename=''
        c.name=os.path.split(path)[1]
        c.id=path
        c.type='DIRECTORY'
        c.image_dirs=[path]
        c.recursive=recursive
        c.add_view()
        self.collections[path]=c
        self.row_inserted(*self.pi_from_id(c.id))
        return c
    def remove(self,id):
        coll=self[id]
        del self[id]
        return coll
    def open_collection(self,id):
        pass
    def close_collection(self,id):
        pass
    def init_localstores(self):
        for col_file in settings.get_collection_files():
            self.add_localstore(col_file)
    def init_mounts(self,mount_info):
        for name,icon_names,path in mount_info:
            self.add_mount(path,name,icon_names)

    '''
    methods needed for implementing gtk.TreeModel (see pygtk tutorial)
    TODO: put this stuff in a separate class
    TODO: can then define multiple implementations of the class model for different widgets
    '''
    def on_get_flags(self):
        return gtk.TREE_MODEL_LIST_ONLY
    def on_get_n_columns(self):
        return COMBO_OPEN+1
    def on_get_column_type(self, index):
        return [str,str,int,bool,str,gtk.gdk.Pixbuf,bool][index]
    def on_get_iter(self, path):
        i=0
        for id in self.view_iter():
            if i==path[0]:
                return id
            i+=1
        return None
    def on_get_path(self, rowref):
        i=0
        for id in self.view_iter():
            if id==rowref:
                return (i,)
            i+=1
        return None
    def on_get_value(self, rowref, column):
        return self.as_row(rowref)[column]
    def on_iter_next(self, rowref):
        matched=False
        for id in self.view_iter():
            if matched:
                return id
            if id==rowref:
                matched=True
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
    '''
    helper methods for implementing the tree model methods
    '''
    def as_row(self,id):
#        print 'as_row called',rowref
#        id=self.get_user_data(rowref)
        label_dict={
            '#add-localstore':'New Collection...',
            '#no-devices':'No Devices Connected',
            '#add-dir':'Browse a Local Directory...',

        }
        if id.startswith('*'):
            return [id,'',800,False,'black',None,False]
        if id.startswith('#'):
            return [id,label_dict[id],400,False,'black',None,False] ##todo: replace id[1:] with a dictionary lookup to a meaningful description
        ci=self.collections[id]
        if ci.is_open:
            return [id,ci.name,800,False,'brown',ci.pixbuf,True]
        else:
            return [id,ci.name,400,False,'brown',ci.pixbuf,False]
    def view_iter(self):
        '''
        this iterator defines the rows of the collection model
        '''
        tcount=0
        options=['#add-localstore',None,'#add-dir']
        for t in self.types:
            if tcount>0:
                yield '*%i'%(tcount,)
            i=0
            for id in self.iter_id(t):
                yield id
                i+=1
            if t=='DEVICE' and i==0:
                yield '#no-devices'
            if options[tcount]!=None:
                yield options[tcount]
            tcount+=1



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
        self.combo.set_focus_on_click(False)
        cpb=gtk.CellRendererPixbuf()
        self.combo.pack_start(cpb,False)
        self.combo.add_attribute(cpb, 'pixbuf', COMBO_PIXBUF)
        cpt=gtk.CellRendererText()
        self.combo.pack_start(cpt,False)
        self.combo.add_attribute(cpt, 'text', COMBO_NAME)
        self.combo.add_attribute(cpt, 'weight', COMBO_FONT_WGT)
        self.combo.add_attribute(cpt, 'foreground-set', COMBO_FONT_COLOR_SET)
        self.combo.add_attribute(cpt, 'foreground', COMBO_FONT_COLOR)

#        cpto=gtk.CellRendererToggle()
#        self.combo.pack_start(cpto,False)
#        self.combo.add_attribute(cpto, 'active', COMBO_OPEN)

        self.combo.show()
        self.pack_start(self.combo)
        self.combo.connect("changed",self.changed)
    def changed(self,combo):
        iter=combo.get_active_iter()
        if iter==None:
            self.emit('collection-changed','')
            return
        id=self.model[iter][COMBO_ID]
        if id=='#add-dir':
            self.emit('add-dir')
        elif id=='#add-localstore':
            self.emit('add-localstore')
        elif id.startswith('#'):
            return
        elif not id.startswith('*'):
            self.emit('collection-changed',id)
    def sep_cb(self, model, iter):
        '''
        callback determining whether a row should appear as a separator in the combo
        '''
        if self.model[iter][COMBO_ID].startswith('*'):
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

