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

import gtk
import gobject
import settings
import os.path

import baseobjects
from fstools import io

try:
    from collectiontypes import localstorebin
except:
    pass
try:
    from collectiontypes import localdir
except:
    pass
try:
    from collectiontypes import flickr
except:
    pass
try:
    from collectiontypes import facebook
except:
    pass

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

def filter_selector(model, iter):
    id = model.get_value(iter, COLUMN_ID)
    return not id.startswith('~')

def filter_open_selector(model,iter):
    id = model.get_value(iter, COLUMN_ID)
    open = model.get_value(iter, COLUMN_OPEN)
    return not id.startswith('~') and open

def filter_unopen_selector(model,iter):
    id = model.get_value(iter, COLUMN_ID)
    open = model.get_value(iter, COLUMN_OPEN)
    return not id.startswith('~') and not open

def filter_activator(model,iter):
    return True

filter_funcs={
'OPEN_SELECTOR':filter_open_selector,        #shows only the open collections
'UNOPEN_SELECTOR':filter_unopen_selector, #shows only the unopened collections
'SELECTOR':filter_selector,      #shows both open and unopen collections
'ACTIVATOR':filter_activator            #shows both open and unopen collections, separators and availability of devices
}

class CollectionSet(gobject.GObject):
    '''
    Defines a set of image collections, managed with a dictionary like syntax
    The program uses this class to create and remove collections
    Add new collections with the new_collection(id,prefs)
     id is a uniquely identifying name (string)
     prefs is a dictionary with the following members
       type is a string corresponding id uniquely identifying a collection class, 'COLLECTION', 'DIRECTORY', 'DEVICE', 'WEBSERVICE'
       path/uri is the directory location of the images or a path to a collection file
       collection is a collection or none if the colleciton is not open
       display_name is the name shown to the user (usually == key value??)
       icon_str is the string identifying the icon
    also:
     manages models that can display the collection model
    '''
    def __init__(self,style=None):
        self.collections={}
        self.types=[c for c in baseobjects.registered_collection_classes]
        self.style = style
        if style:
            self.default_dir_image=self.get_icon(gtk.STOCK_DIRECTORY)
            #self.default_col_image=self.get_icon([gtk.STOCK_DIRECTORY])
            self.default_col_image=self.get_icon('picty-5')
        self.model=CollectionModel(self)

    def add_model(self,filter_type=None):
        m=self.model.filter_new()
        m.set_visible_func(filter_funcs[filter_type]) ##todo: define filter_funcs
        m.coll_set=self
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

    def __delitem__(self,name,delete_cache_file=True):
        coll=self.collections[name]
        if delete_cache_file:
            coll.delete_store()
        self.collection_removed(coll.id)
        del self.collections[name]
        if coll.type=='DEVICE' and self.count('DEVICE')==0: ##todo: is there anyway to not hardcode this here? (delegate to the class)
            self.model.all_mounts_removed()

    def clear(self):
        for id in self.collections:
            del self[id]

    def get_icon(self, icon_or_list):
        pb = None
        if isinstance(icon_or_list,str):
            icon = self.style.lookup_icon_set(icon_or_list)
            if icon!=None:
                pb = icon.render_icon(self.style, gtk.TEXT_DIR_NONE, gtk.STATE_NORMAL, gtk.ICON_SIZE_MENU, None, None)
        else: ##should be a tuple/list
            t=gtk.icon_theme_get_default()
            ii=t.choose_icon(icon_or_list,gtk.ICON_SIZE_MENU,0)
            try:
                pb=gtk.gdk.pixbuf_new_from_file(ii.get_filename()) if ii.get_filename() else None
            except:
                pass
        return pb

    def count(self,type=None):
        return sum([1 for id in self.iter_id(type)])

    def add_collection(self,collection):
        if collection.type=='DEVICE' and self.count('DEVICE')==0:
            self.model.first_mount_added()
        if collection.pixbuf is None:
            print 'SETTING ICON FROM DEFAULT',collection.pixbuf
            if collection.type=='LOCALDIR':
                collection.pixbuf = self.default_dir_image
            if collection.type!='DEVICE' and collection.type!='LOCALDIR':
                collection.pixbuf = self.default_col_image
        if isinstance(collection.pixbuf,str):
            print 'GETTING ICON FROM STRING',collection.pixbuf
            collection.pixbuf = self.get_icon(collection.pixbuf)
        self.collections[collection.id]=collection
        self.collection_added(collection.id)

    def new_collection(self,prefs):
        print 'CREATING NEW COLLECTION',prefs
        c=baseobjects.registered_collection_classes[prefs['type']](prefs)
        if not c.create_store():
            return False
        v=c.add_view()
        self.add_collection(c)
        return c

    def change_prefs(self,coll,new_prefs):
        if coll.is_open:
            return False #can't change open collections (too much potential for errors)
        old_prefs=coll.get_prefs()
        if new_prefs==old_prefs:
            return False #nothing has changed
        if 'name' in new_prefs and new_prefs['name']!=coll.name:
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
        self.model.coll_added(id)

    def collection_changed(self,id):
        self.model.coll_changed(id)

    def collection_removed(self,id):
        self.model.coll_removed(id)

    def collection_opened(self,id):
        self[id].is_open=True
        self.model.coll_opened(id)

    def collection_closed(self,id):
        if id not in self.collections:
            return
        c=self[id]
        c.is_open=False
        self.model.coll_closed(id)
        if not c.persistent and not c.type=='DEVICE': ##TODO: Second part is redundant because Devices are set to be persistent
            self.remove(id)

    def collection_online(self,id):
        pass

    def collection_offline(self,id):
        pass

    def init_localstores(self):
        for f in settings.get_collection_files():
            col_dir=os.path.join(settings.collections_dir,f)
            c=baseobjects.init_collection(col_dir)
            if c!=None:
#                c.add_view()
                self.add_collection(c)

    def add_mount(self,path,name,icon_names):
        if not os.path.exists(path):
            return
        if id in self.collections:
            return
        Dev=baseobjects.registered_collection_classes['DEVICE']
        impath = path
        subdirs = os.listdir(path)
        for testdir in ['DCIM', 'Pictures', 'Photos']:
            if testdir in subdirs:
                impath = os.path.join(path,'DCIM')
                if not os.path.isdir(impath):
                    impath = path
                else:
                    break
        prefs={
            'name':name,
            'id':path,
            'image_dirs':[impath],
            'pixbuf':self.get_icon(icon_names),
            }
        c=Dev(prefs)
        c.add_view()
        if 'mtp:host=' in path or path.startswith(os.path.join(settings.home_dir,'.gvfs')): #todo: probably a better way to identify mass storage from non-mass storage devices
            ##gphoto2 device (MTP)
            c.load_embedded_thumbs=False
            c.load_meta=False
            c.load_preview_icons=True
            c.store_thumbnails=False
        else:
            ##non-gphoto2 device (Mass Storage)
            c.load_embedded_thumbs=True
            c.load_meta=True
            c.load_preview_icons=False
            c.store_thumbnails=False
        self.add_collection(c)
        return c

    def add_directory(self,path,prefs):
        ###TODO: REMOVE THIS, CALLER SHOULD FILL OUT PREFERENCES AND USE new_collection
        if not os.path.exists(path):
            return
        Dir=baseobjects.registered_collection_classes['LOCALDIR']
        prefs['id']=path
        name=os.path.split(path)[1]
        if name=='':
            name='Folder'
        prefs['name']=name
        c=Dir(prefs)
        c.pixbuf=self.get_icon(gtk.STOCK_DIRECTORY)
        c.add_view()
        self.add_collection(c)
        return c

    def init_mounts(self,mount_info):
        for name,icon_names,path in mount_info:
            self.add_mount(path,name,icon_names)


class CollectionModel(gtk.ListStore):
    def __init__(self,coll_set):
        gtk.ListStore.__init__(self,str,str,int,bool,str,gtk.gdk.Pixbuf,bool)
        self.coll_set = coll_set
        self.append(self.as_row('~1no-devices'))
        self.append(self.as_row('~3add-dir'))
    def coll_added(self,id):
        self.insert(self.get_pos(id),self.as_row(id))
    def coll_removed(self,id):
        self.remove(self.get_iter(self.get_pos(id)))
    def coll_opened(self,id):
        self[self.get_pos(id)] = self.as_row(id)
    def coll_closed(self,id):
        self[self.get_pos(id)] = self.as_row(id)
    def first_mount_added(self):
        self.remove(self.get_iter(self.get_pos('~1no-devices')))
    def all_mounts_removed(self):
        self.insert(self.get_pos('~1no-devices'),self.as_row(id))
    def get_pos(self,id):
        t = '~' if id.startswith('~') else self.coll_set[id].type
        for i in range(len(self)): #ORDERED COLLECTIONS, DIRECTORIES, DEVICES
            id1 = self[i][0]
            t1 = '~' if id1.startswith('~') else self.coll_set[self[i][0]].type
            if id == id1:
                return i
            if t < t1:
                return i
            if id.lower() < id1.lower():
                return i
        return len(self)
    def as_row(self,id):
        label_dict={
            '~1no-devices':('No Devices Connected',None),
            '~2add-localstore':('New Collection...',None),
            '~3add-dir':('Open a Local Directory...',self.coll_set.default_dir_image),
        }
        if id.startswith('*'):
            return [id,'',800,False,'black',None,False]
        if id.startswith('~'):
            return [id,label_dict[id][0],400,False,'black',label_dict[id][1],False] ##todo: replace id[1:] with a dictionary lookup to a meaningful description
        ci=self.coll_set.collections[id]
        if ci.is_open:
            return [id,ci.name,800,False,'brown',ci.pixbuf,True]
        else:
            return [id,ci.name,400,False,'brown',ci.pixbuf,False]



##Combo entries should look something like this
##TODO: Implement separators and improve sorting

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
    def __init__(self,model,coll_set):
        gtk.VBox.__init__(self)
        self.model=model
        self.coll_set=coll_set

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
        if id=='~3add-dir':
            self.emit('add-dir')
        elif id=='~2add-localstore':
            self.emit('add-localstore')
        elif id.startswith('~'):
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
            self.combo.set_active(-1)
        it=self.model.get_iter_first()
        while it is not None:
            if self.model[it][COLUMN_ID]==id:
                self.combo.set_active_iter(it)
                return
            it=self.model.iter_next(it)
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
        self.pack_start(b2,False)
        self.pack_start(b1)
#        self.pack_start(b3,False)
        self.show_all()

    def context_menu(self,widget,event):
        if event.button==3:
            (row_path,tvc,tvc_x,tvc_y)=self.coll_list.get_path_at_pos(int(event.x), int(event.y))
            if row_path:
                id=self.coll_list.get_model()[row_path][COLUMN_ID]
                self.emit('collection-context-menu',id)

    def open_collection_by_activation(self, treeview, path, view_column):
        model=self.coll_list.get_model()
        id=model[path][COLUMN_ID]
        if id=='~3add-dir':
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
        if id=='~3add-dir':
            self.emit("folder-open")
        else:
            self.emit("collection-open",id)

    def new_store(self,button):
        self.emit("collection-new")

    def new_dir(self,button):
        self.emit("folder-open")

gobject.type_register(CollectionStartPage)

