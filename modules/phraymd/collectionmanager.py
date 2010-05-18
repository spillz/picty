'''

    phraymd
    Copyright (C) 2010  Damien Moore

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

import gtk
import gobject
import settings
import os.path

import collections
import io

COLUMN_ID=0
COLUMN_NAME=1
COLUMN_FONT_WGT=2
COLUMN_FONT_COLOR_SET=3
COLUMN_FONT_COLOR=4
COLUMN_PIXBUF=5
COLUMN_OPEN=6

def COLUMN_cols(coll,index):
    return [coll.type,coll.path,coll.collection,coll.icon_list,coll.pixbuf][index]

def get_icon(icon_id_list):
    t=gtk.icon_theme_get_default()
    ii=t.choose_icon(icon_id_list,gtk.ICON_SIZE_MENU,0)
    return None if not ii else ii.load_icon()


class CollectionSet(gobject.GObject):
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
     manages models that can display the collection model
    '''
    def __init__(self):
        self.collections={}
        self.types=['LOCALSTORE','DEVICE','DIRECTORY']
        self.models=[]
        self.dir_image=self.get_icon([gtk.STOCK_DIRECTORY])

    def add_model(self,model_type='SELECTOR'):   ##todo: remove model
        m=CollectionModel(self,model_type)
        self.models.append(m)
        return m
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
#                if c.is_open:
                    yield c
    def __getitem__(self,name):
        '''
        if name is an id returns the collection
        if name is an iter returns the collection descriptive data as a row from a tree model (list)
        '''
        if not name:
            return
        if isinstance(name,gtk.TreeIter):
            name=self.get_user_data(name)
        if name in self.collections:
            return self.collections[name]
        return None
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
    def __delitem__(self,name,delete_cache_file=True):
        coll=self.collections[name]
        if coll.type=='DEVICE' and coll.is_open:
            self.collection_closed(name)
        self.collection_removed(coll.id)
        del self.collections[name]
        if coll.type=='LOCALSTORE' and delete_cache_file:
            col_dir=os.path.join(settings.collections_dir,coll.name)
            try:
                if os.path.isdir(col_dir):
                    os.rmdir(col_dir)
                elif os.path.isfile(col_dir):
                    io.remove_file(col_dir)
            except IOError:
                print 'Error removing collection data files in',col_dir
                import sys,traceback
                tb_text=traceback.format_exc(sys.exc_info()[2])
                print tb_text
        if coll.type=='DEVICE' and self.count('DEVICE')==0:
            for m in self.models:
                m.all_mounts_removed()
    def clear(self):
        for id in self.collections:
            del self[id]
    def get_icon(self, icon_id_list):
        t=gtk.icon_theme_get_default()
        ii=t.choose_icon(icon_id_list,gtk.ICON_SIZE_MENU,0)
        try:
            pb=gtk.gdk.pixbuf_new_from_file(ii.get_filename()) if ii.get_filename() else None
        except:
            pb=None
        return pb
    def count(self,type=None):
        return sum([1 for id in self.iter_id(type)])
    def add_mount(self,path,name,icon_names):
        if not os.path.exists(path):
            return
        c=collections.Collection2()
        c.type='DEVICE'
        c.image_dirs=[path] ##todo: if device collection data is stored persistently, what to do if path changes?
        c.name=name
        c.id=path
        c.pixbuf=self.get_icon(icon_names)
        c.add_view()
        c.verify_after_walk=False
        if path.startswith(os.path.join(os.environ['HOME'],'.gvfs')):
            c.load_embedded_thumbs=False
            c.load_metadata=False
            c.load_preview_icons=True
            c.store_thumbnails=False ##todo: this needs to be implemented
        else:
            c.load_embedded_thumbs=True
            c.load_metadata=True
            c.load_preview_icons=False
            c.store_thumbnails=False
        if self.count('DEVICE')==0:
            for m in self.models:
                m.first_mount_added()
        self.collections[c.id]=c
        self.collection_added(c.id)
        return c
    def add_localstore(self,col_name,prefs=None):
        '''
        add a localstore collection to the collection set
        - col_name is the name of the collection (and is also used to set the filename of the collection cache file)
        - prefs is a dictionary containing the preferences for the colleciton, if None they will be loaded from the collection cache file
        '''
        c=collections.Collection2()
        col_path=os.path.join(settings.collections_dir,col_name)
        c.name=col_name
        c.id=col_path
        c.type='LOCALSTORE'
        c.pixbuf=self.get_icon([gtk.STOCK_HARDDISK]) ##todo: let user choose an icon
        c.add_view()
        if prefs!=None:
            c.set_prefs(prefs)
        else:
            c.load_prefs()
        self.collections[col_path]=c
        self.collection_added(c.id)
        return c
    def add_directory(self,path,prefs=None):
        c=collections.Collection2()
        c.name=os.path.split(path)[1]
        c.id=path
        c.type='DIRECTORY'
        c.image_dirs=[path]
        c.verify_after_walk=False
        c.pixbuf=self.get_icon([gtk.STOCK_DIRECTORY])
        c.recursive=prefs['recursive']
        c.load_embedded_thumbs=prefs['load_embedded_thumbs']
        c.load_metadata=prefs['load_metadata']
        if not c.load_metadata and c.load_embedded_thumbs:
            c.load_preview_icons=True
        c.store_thumbnails=prefs['store_thumbnails'] ##todo: this needs to be implemented

        c.add_view()
        self.collections[path]=c
        self.collection_added(c.id)
        return c
    def change_prefs(self,coll,new_prefs):
        if coll.is_open:
            return False #can't change open collections (too much potential for errors)
        old_prefs=coll.get_prefs()
        if new_prefs==old_prefs:
            return False #nothing has changed
        if new_prefs['name']!=coll.name:
            print 'renaming collection'
            new_path=os.path.join(settings.collections_dir,new_prefs['name'])
            old_path=os.path.join(settings.collections_dir,coll.name)
            if os.path.exists(new_path):
                print 'Error: collection with this name already exists'
                return False
            os.rename(old_path,new_path)
            self.collection_removed(coll.id)
            del self.collections[coll.id]
            coll.id=new_path
            coll.name=new_prefs['name']
            self.collections[coll.id]=coll
            self.collection_added(coll.id)
        del new_prefs['name']
        del old_prefs['name']
        if new_prefs!=old_prefs:
            new_prefs['name']=coll.name
            coll.set_prefs(new_prefs)
            coll.save_prefs()
        return True

    def remove(self,id):
        coll=self[id]
        del self[id]
        return coll
    def collection_added(self,id):
        for m in self.models:
            m.coll_added(id)
    def collection_changed(self,id):
        for m in self.models:
            m.coll_changed(id)
    def collection_removed(self,id):
        for m in self.models:
            m.coll_removed(id)
    def collection_opened(self,id):
        for m in self.models:
            m.coll_opening(id)
        self[id].is_open=True
        for m in self.models:
            m.coll_opened(id)
    def collection_closed(self,id):
        if id not in self.collections:
            return
        for m in self.models:
            m.coll_closing(id)
        c=self[id]
        c.is_open=False
        for m in self.models:
            m.coll_closed(id)
        if c.type=='DIRECTORY':
            self.remove(id)
    def init_localstores(self):
        for col_file in settings.get_collection_files():
            self.add_localstore(col_file)
    def init_mounts(self,mount_info):
        for name,icon_names,path in mount_info:
            self.add_mount(path,name,icon_names)


class CollectionModel(gtk.GenericTreeModel):
    '''
    derives from gtk.GenericTreeModel allowing user interaction as a gtk.ComboBox or gtk.TreeView
    methods needed for implementing gtk.TreeModel (see pygtk tutorial)
    '''
    def __init__(self,coll_set,model_type):
        gtk.GenericTreeModel.__init__(self)
        self.coll_set=coll_set
        self.model_type=model_type
        if model_type=='OPEN_SELECTOR':
            self.view_iter=self.view_iter_open_selector
        if model_type=='UNOPEN_SELECTOR':
            self.view_iter=self.view_iter_unopen_selector
        if model_type=='SELECTOR':
            self.view_iter=self.view_iter_selector
        if model_type=='ACTIVATOR':
            self.view_iter=self.view_iter_activator
        if model_type=='MENU':
            self.view_iter=self.view_iter_menu
        if model_type=='LOCALSTORE_SELECTOR':
            self.view_iter=self.view_iter_localstore_selector
        for r in self.view_iter():
            self.row_inserted(*self.pi_from_id(r))
    def coll_added(self,id):
        if self.model_type=='LOCALSTORE_SELECTOR' and self.coll_set[id].type!='LOCALSTORE':
            return
        if self.model_type!='OPEN_SELECTOR':
            self.row_inserted(*self.pi_from_id(id))
    def coll_removed(self,id):
        if self.model_type=='LOCALSTORE_SELECTOR' and self.coll_set[id].type!='LOCALSTORE':
            return
        if self.model_type!='OPEN_SELECTOR':
            self.row_deleted(self.pi_from_id(id)[0])
    def coll_opening(self,id):
        if self.model_type=='UNOPEN_SELECTOR':
            self.row_deleted(self.pi_from_id(id)[0])
    def coll_opened(self,id):
        if self.model_type=='LOCALSTORE_SELECTOR' and self.coll_set[id].type!='LOCALSTORE':
            return
        if self.model_type=='OPEN_SELECTOR':
            self.row_inserted(*self.pi_from_id(id))
        elif self.model_type in ('SELECTOR','MENU','ACTIVATOR'):
            self.row_changed(*self.pi_from_id(id))
    def coll_closing(self,id):
        if self.model_type=='LOCALSTORE_SELECTOR' and self.coll_set[id].type!='LOCALSTORE':
            return
        if self.model_type=='OPEN_SELECTOR':
            self.row_deleted(self.pi_from_id(id)[0])
        elif self.model_type in ('SELECTOR','MENU','ACTIVATOR'):
            self.row_changed(*self.pi_from_id(id))
    def coll_closed(self,id):
        if self.model_type=='UNOPEN_SELECTOR':
            self.row_inserted(*self.pi_from_id(id))
    def first_mount_added(self):
        if self.model_type not in ('SELECTOR','MENU'):
            self.row_deleted(self.pi_from_id('#no-devices')[0])
    def all_mounts_removed(self):
        if self.model_type in ('SELECTOR','MENU'):
            self.row_inserted(*self.pi_from_id('#no-devices'))
    def on_get_flags(self):
        return gtk.TREE_MODEL_LIST_ONLY
    def on_get_n_columns(self):
        return COLUMN_OPEN+1
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
        label_dict={
            '#add-localstore':('New Collection...',None),
            '#no-devices':('No Devices Connected',None),
            '#add-dir':('Open a Local Directory...',self.coll_set.dir_image),

        }
        if id.startswith('*'):
            return [id,'',800,False,'black',None,False]
        if id.startswith('#'):
            return [id,label_dict[id][0],400,False,'black',label_dict[id][1],False] ##todo: replace id[1:] with a dictionary lookup to a meaningful description
        ci=self.coll_set.collections[id]
        if ci.is_open:
            return [id,ci.name,800,False,'brown',ci.pixbuf,True]
        else:
            return [id,ci.name,400,False,'brown',ci.pixbuf,False]
    def view_iter_menu(self):
        '''
        this iterator defines the rows of the collection model
        and adds items for separators, collections and menu options
        '''
        tcount=0
        options=['#add-localstore',None,'#add-dir']
        for t in self.coll_set.types:
            if tcount>0:
                yield '*%i'%(tcount,)
            i=0
            for id in self.coll_set.iter_id(t):
                yield id
                i+=1
            if t=='DEVICE' and i==0:
                yield '#no-devices'
            if options[tcount]!=None:
                yield options[tcount]
            tcount+=1
    def view_iter_selector(self):
        '''
        returns an iterator over all collections
        and adds separators between collection types but no menu options
        '''
        tcount=0
        i=0
        for t in self.coll_set.types:
            if i>0:
                yield '*%i'%(tcount,)
            i=0
            for id in self.coll_set.iter_id(t):
                yield id
                i+=1
            if t=='DEVICE' and i==0:
                yield '#no-devices'
            tcount+=1
    def view_iter_activator(self):
        '''
        returns an iterator over all collections
        plus an additional option to browser a directory
        '''
        for t in self.coll_set.types:
            for id in self.coll_set.iter_id(t):
                yield id
        yield '#add-dir'
    def view_iter_open_selector(self):
        '''
        returns an iterator over the open collections
        and adds separators between collection types
        '''
        tcount=0
        i=0
        for t in self.coll_set.types:
            if i>0:
                yield '*%i'%(tcount,)
            i=0
            for id in self.coll_set.iter_id(t):
                if self.coll_set[id].is_open:
                    yield id
                    i+=1
            tcount+=1
    def view_iter_unopen_selector(self):
        '''
        returns an iterator over the closed collections
        and adds separators between collection types
        '''
        for t in self.coll_set.types:
            for id in self.coll_set.iter_id(t):
                if not self.coll_set[id].is_open:
                    yield id
    def pi_from_id(self,name): #return tuple of path and iter associated with the unique identifier
        iter=self.create_tree_iter(name)
        return self.get_path(iter),iter

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
#        'collection-toggled':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(str,)), #user toggles the collection button
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
        cpb.set_property("width",20) ##todo: don't hardcode the width
        self.combo.pack_start(cpb,False)
        self.combo.add_attribute(cpb, 'pixbuf', COLUMN_PIXBUF)
        cpt=gtk.CellRendererText()
        self.combo.pack_start(cpt,False)
        self.combo.add_attribute(cpt, 'text', COLUMN_NAME)
        self.combo.add_attribute(cpt, 'weight', COLUMN_FONT_WGT)
        self.combo.add_attribute(cpt, 'foreground-set', COLUMN_FONT_COLOR_SET)
        self.combo.add_attribute(cpt, 'foreground', COLUMN_FONT_COLOR)

#        cpto=gtk.CellRendererToggle()
#        self.combo.pack_start(cpto,False)
#        self.combo.add_attribute(cpto, 'active', COLUMN_OPEN)

        self.combo.show()
        self.pack_start(self.combo)
        self.combo.connect("changed",self.changed)
    def changed(self,combo):
        iter=combo.get_active_iter()
        if iter==None:
            self.emit('collection-changed','')
            return
        id=self.model[iter][COLUMN_ID]
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
        if self.model[iter][COLUMN_ID].startswith('*'):
            return True
        return False
    def get_choice(self):
        iter=self.combo.get_active_iter()
        if iter!=None:
            return self.model[iter][COLUMN_ID]
    def set_active(self,id):
        if id:
            self.combo.set_active_iter(self.model.create_tree_iter(id))
        else:
            self.combo.set_active(-1)
    def get_active(self):
        return self.get_choice()
    def get_active_coll(self):
        coll_id=self.get_choice()
        if not coll_id:
            return
        return self.model.coll_set[coll_id]

gobject.type_register(CollectionCombo)


class UnopenedCollectionList(gtk.TreeView):
    def __init__(self,model):
        gtk.TreeView.__init__(self,model)
        self.set_headers_visible(False)
        self.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_NONE)
        cpb=gtk.CellRendererPixbuf()
        cpb.set_property("width",20) ##todo: don't hardcode the width
        tvc=gtk.TreeViewColumn(None,cpb,pixbuf=COLUMN_PIXBUF)
        self.append_column(tvc)
        cpt=gtk.CellRendererText()
        tvc=gtk.TreeViewColumn(None,cpt,text=COLUMN_NAME,weight=COLUMN_FONT_WGT,foreground_set=COLUMN_FONT_COLOR_SET,foreground=COLUMN_FONT_COLOR)
        self.append_column(tvc)



class CollectionStartPage(gtk.VBox):
    __gsignals__={
        'collection-open':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(str,)), #user selects a collection to open
        'collection-new':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,tuple()), #user wants to create a new collection
        'collection-context-menu':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(str,)), #user has right clicked on a collection in the list
        'folder-open':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,tuple()), #user wants to browse a local directory as a collection
        }
    def __init__(self,coll_set):
        gtk.VBox.__init__(self)

        h=gtk.Label()
        h.set_markup("<b>What would you like to do?</b>")

        b1=gtk.VBox()
        l=gtk.Label("Open an existing collection, directory or device")
        b1.pack_start(l,False)
        open_button=gtk.Button("_Open")
        open_button.connect("clicked",self.open_collection)
        self.coll_list=UnopenedCollectionList(coll_set.add_model('ACTIVATOR'))
        self.coll_list.connect("row-activated",self.open_collection_by_activation)
        self.coll_list.connect("cursor-changed",self.open_possible,open_button)
        self.coll_list.add_events(gtk.gdk.BUTTON_MOTION_MASK)
        self.coll_list.connect("button-release-event",self.context_menu)
        sel=self.coll_list.get_selection()
        model,iter=sel.get_selected()
        if not iter:
            open_button.set_sensitive(False)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.add(self.coll_list)
        scrolled_window.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        b1.pack_start(scrolled_window,True)
#        hb=gtk.HButtonBox()
#        hb.pack_start(open_button,True,False)
#        b1.pack_start(hb,False,False)

        b2=gtk.VBox()
        l=gtk.Label("Create a new collection")
        b2.pack_start(l)
        hb=gtk.HButtonBox()
        new_store_button=gtk.Button("_New Collection...")
        new_store_button.connect("clicked",self.new_store)
        hb.pack_start(new_store_button,True,False)
        b2.pack_start(hb,False,False)

#        b3=gtk.VBox()
#        l=gtk.Label("Browse images in a local directory")
#        b3.pack_start(l)
#        hb=gtk.HButtonBox()
#        new_dir_button=gtk.Button("_Browse Folder...")
#        new_dir_button.connect("clicked",self.new_dir)
#        hb.pack_start(new_dir_button,True,False)
#        b3.pack_start(hb,False,False)

        self.set_spacing(30)
        self.pack_start(h,False)
        self.pack_start(b1)
        self.pack_start(b2,False)
#        self.pack_start(b3,False)
        self.show_all()

    def context_menu(self,widget,event):
        if event.button==3:
            (row_path,tvc,tvc_x,tvc_y)=self.coll_list.get_path_at_pos(event.x, event.y)
            if row_path:
                id=self.coll_list.get_model()[row_path][COLUMN_ID]
                self.emit('collection-context-menu',id)

    def open_collection_by_activation(self, treeview, path, view_column):
        model=self.coll_list.get_model()
        id=model[path][COLUMN_ID]
        if id=='#add-dir':
            self.emit("folder-open")
        else:
            self.emit("collection-open",id)

    def open_possible(self,treeview,open_button):
        sel=self.coll_list.get_selection()
        model,iter=sel.get_selected()
        if not iter:
            open_button.set_sensitive(False)
        else:
            open_button.set_sensitive(True)

    def open_collection(self,button):
        sel=self.coll_list.get_selection()
        if not sel:
            return
        model,iter=sel.get_selected()
        id=model[iter][COLUMN_ID]
        if id=='#add-dir':
            self.emit("folder-open")
        else:
            self.emit("collection-open",id)

    def new_store(self,button):
        self.emit("collection-new")

    def new_dir(self,button):
        self.emit("folder-open")

gobject.type_register(CollectionStartPage)


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

