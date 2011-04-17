'''

    phraymd
    Copyright (C) 2009  Damien Moore

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

##standard imports
import bisect
import datetime
import os
import os.path
import re
import datetime
import cPickle

import gtk

##phraymd imports
import pluginmanager
import settings
import monitor2 as monitor
import viewsupport
import baseobjects
import simple_parser as sp
import dialogs

class LocalStorePrefWidget(gtk.VBox):
    def __init__(self,value_dict=None):
        gtk.VBox.__init__(self)
        box,self.name_entry=dialogs.box_add(self,[(gtk.Entry(),True,None)],'Collection Name: ')
        self.path_entry=dialogs.PathnameEntry('','Path to Images: ','Choose a Directory',directory=True)
        self.pack_start(self.path_entry,False)
        self.name_entry.connect("changed",self.name_changed)
        self.path_entry.path_entry.connect("changed",self.path_changed)

        self.a_frame=gtk.Expander("Advanced Options")
        self.a_box=gtk.VBox()
        self.a_frame.add(self.a_box)
        self.recursive_button=gtk.CheckButton('Recurse sub-directories')
        self.recursive_button.set_active(True)
        self.load_meta_check=gtk.CheckButton("Load Metadata")
        self.load_meta_check.set_active(True)
        self.use_internal_thumbnails_check=gtk.CheckButton("Use Embedded Thumbnails if Available")
        self.use_internal_thumbnails_check.set_active(False)
        self.store_thumbnails_check=gtk.CheckButton("Store Thumbnails in Cache") #todo: need to implement in backend
        self.store_thumbnails_check.set_active(True)
        self.a_box.pack_start(self.recursive_button,False)
        self.a_box.pack_start(self.load_meta_check,False)
        self.a_box.pack_start(self.use_internal_thumbnails_check,False)
        self.pack_start(self.a_frame,False)
        self.show_all()
        if value_dict:
            self.set_values(value_dict)

    def path_changed(self,entry):
        sensitive=len(self.name_entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename

    def name_changed(self,entry):
        sensitive=len(entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename

    def get_values(self):
        return {
                'name': self.name_entry.get_text().replace('/','').strip(),
                'image_dirs': [self.path_entry.get_path()],
                'recursive': self.recursive_button.get_active(),
                'load_metadata':self.load_meta_check.get_active(),
                'load_embedded_thumbs':self.use_internal_thumbnails_check.get_active(),
                'load_preview_icons':self.use_internal_thumbnails_check.get_active() and not self.load_meta_check.get_active(),
                'store_thumbnails':self.store_thumbnails_check.get_active(),
                }

    def set_values(self,val_dict):
        self.name_entry.set_text(val_dict['name'])
        if len(val_dict['image_dirs'])>0:
            self.path_entry.set_path(val_dict['image_dirs'][0])
        self.recursive_button.set_active(val_dict['recursive'])
        self.load_meta_check.set_active(val_dict['load_metadata'])
        self.use_internal_thumbnails_check.set_active(val_dict['load_embedded_thumbs'])


class NewLocalStoreWidget(gtk.VBox):
    def __init__(self,main_dialog,value_dict):
        gtk.VBox.__init__(self)
        self.main_dialog=main_dialog
        label=gtk.Label()
        label.set_markup("<b>Local Store Settings</b>")
        self.pack_start(label,False)
        box,self.name_entry=dialogs.box_add(self,[(gtk.Entry(),True,None)],'Collection Name: ')
        self.path_entry=dialogs.PathnameEntry('','Path to Images: ','Choose a Directory',directory=True)
        self.pack_start(self.path_entry,False)
        self.name_entry.connect("changed",self.name_changed)
        self.path_entry.path_entry.connect("changed",self.path_changed)

        self.a_frame=gtk.Expander("Advanced Options")
        self.a_box=gtk.VBox()
        self.a_frame.add(self.a_box)
        self.recursive_button=gtk.CheckButton('Recurse sub-directories')
        self.recursive_button.set_active(True)
        self.load_meta_check=gtk.CheckButton("Load Metadata")
        self.load_meta_check.set_active(True)
        self.use_internal_thumbnails_check=gtk.CheckButton("Use Embedded Thumbnails if Available")
        self.use_internal_thumbnails_check.set_active(False)
        self.store_thumbnails_check=gtk.CheckButton("Store Thumbnails in Cache") #todo: need to implement in backend
        self.store_thumbnails_check.set_active(True)
        self.monitor_images_check=gtk.CheckButton("Monitor Image Folders for Changes") #todo: need to implement in backend
        self.monitor_images_check.set_active(True)
        self.a_box.pack_start(self.recursive_button,False)
        self.a_box.pack_start(self.load_meta_check,False)
        self.a_box.pack_start(self.use_internal_thumbnails_check,False)
        self.a_box.pack_start(self.monitor_images_check,False)
        #self.a_box.pack_start(self.store_thumbnails_check,False) ##todo: switch this back on and implement in backend/imagemanip

        self.pack_start(self.a_frame,False)
        self.show_all()

#        self.main_dialog.create_button.set_sensitive(False)
        if value_dict:
            self.set_values(value_dict)

    def activate(self):
        sensitive=len(self.name_entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename
        self.main_dialog.create_button.set_sensitive(sensitive)

    def path_changed(self,entry):
        sensitive=len(self.name_entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename
        self.main_dialog.create_button.set_sensitive(sensitive)

    def name_changed(self,entry):
        sensitive=len(entry.get_text().strip())>0 and os.path.exists(self.path_entry.get_path()) ##todo: also check that name is a valid filename
        self.main_dialog.create_button.set_sensitive(sensitive)

#    def path_changed(self,entry):

    def get_values(self):
        return {
                'name': self.name_entry.get_text().strip(),
                'image_dirs': [self.path_entry.get_path()],
                'recursive': self.recursive_button.get_active(),
                'load_metadata':self.load_meta_check.get_active(),
                'load_embedded_thumbs':self.use_internal_thumbnails_check.get_active(),
                'load_preview_icons':self.use_internal_thumbnails_check.get_active() and not self.load_meta_check.get_active(),
                'monitor_image_dirs':self.monitor_images_check.get_active(),
                'store_thumbnails':self.store_thumbnails_check.get_active(),
                }

    def set_values(self,val_dict):
        self.name_entry.set_text(val_dict['name'])
        if len(val_dict['image_dirs'])>0:
            self.path_entry.set_path(val_dict['image_dirs'][0])
        self.recursive_button.set_active(val_dict['recursive'])
        self.load_meta_check.set_active(val_dict['load_metadata'])
        self.use_internal_thumbnails_check.set_active(val_dict['load_embedded_thumbs'])
        self.monitor_images_check.set_active(val_dict['monitor_image_dirs'])
        self.store_thumbnails_check.set_active(val_dict['store_thumbnails'])


def create_empty_localstore(name,prefs,overwrite_if_exists=False):
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
        d={}
        for p in Collection.col_prefs:
            if p in prefs:
                d[p]=prefs[p]
        cPickle.dump(d,f,-1)
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


class CollectionView(baseobjects.ViewBase):
    def __init__(self,key_cb=viewsupport.get_mtime,items=[],collection=None):
        self.items=[]
        for item in items:
            self.add(key_cb(item),item)
        self.key_cb=key_cb
        self.sort_key_text=''
        for text,cb in viewsupport.sort_keys.iteritems():
            if cb==key_cb:
                self.sort_key_text=text
        self.filter_tree=None
        self.filter_text=''
        self.reverse=False
        self.collection=collection
    def copy(self):
        dup=Index(self.key_cb)
        dup.sort_key_text=self.sort_key_text
        dup.filter_tree=self.filter_tree
        dup.filter_text=self.filter_text
        dup.collection=self.collection
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
            pluginmanager.mgr.callback_collection('t_collection_item_removed_from_view',self.collection,self,self.items[i])
            del self.items[i]
        else:
            pluginmanager.mgr.callback_collection('t_collection_item_removed_from_view',self.collection,self,self.items[ind])
            del self.items[ind]
    def del_item(self,item):
        ind=self.find_item(item)
        if ind>=0:
            self.del_ind(ind)
            return True
        return False
    def __call__(self,index):
        if index>=len(self):
            return
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



class Collection(baseobjects.CollectionBase):
    '''defines a sorted collection of Items with
    callbacks to plugins when the contents of the collection change'''
    ##todo: do more plugin callbacks here instead of the job classes?
    type='LOCALSTORE'
    type_descr='Local Store'
    pref_widget=LocalStorePrefWidget
    add_widget=NewLocalStoreWidget
    persistent=True
    user_creatable=True
    view_class=CollectionView
    col_prefs=('name','image_dirs','recursive','verify_after_walk','load_metadata','load_embedded_thumbs',
                'load_preview_icons','trash_location','thumbnail_cache','monitor_image_dirs')
    def __init__(self,prefs): #todo: store base path for the collection
        ##the following attributes are set at run-time by the owner
        baseobjects.CollectionBase.__init__(self,prefs)

#        ##the collection consists of an array of entries for images, which are cached in the collection file
        self.items=[] #the image/video items

        ##and has the following properties (which are stored in the collection file if it exists)
        self.image_dirs=[]
        self.recursive=True
        self.verify_after_walk=True
        self.load_metadata=True #image will be loaded into the collection and view without metadata
        self.load_embedded_thumbs=False #only relevant if load_metadata is true
        self.load_preview_icons=False #only relevant if load_metadata is false
        self.trash_location=None #none defaults to <collection dir>/.trash
        self.thumbnail_cache=None #use gnome/freedesktop or put in the image folder
        self.monitor_image_dirs=True

        ## the collection optionally has a filesystem monitor and views (i.e. subsets) of the collection of images
        self.monitor=None
        self.monitor_master_callback=None
        self.browser=None

        if prefs:
            self.set_prefs(prefs)

        self.id=self.name

    def create_store(self):
        return create_empty_localstore(self.name,self.get_prefs())

    def copy(self):
        dup=Collection2([])
        dup.items=self.items[:]
        dup.numselected=self.numselected
        dup.image_dirs=self.image_dirs[:]
        dup.verify_after_walk=self.verify_after_walk
        dup.load_metadata=self.load_metadata
        dup.load_embedded_thumbs=self.load_embedded_thumbs
        dup.load_preview_icons=self.load_preview_icons
        dup.monitor=None
        dup.views=[]
        for v in self.views:
            dup.views.append(v.copy())
        return dup

    def copy_from(self,dup):
        self.items[:]=dup.items[:]
        self.numselected=dup.numselected
        self.image_dirs=dup.image_dirs[:]
        self.verify_after_walk=dup.verify_after_walk
        self.load_metadata=dup.load_metadata
        self.load_embedded_thumbs=dup.load_embedded_thumbs
        self.load_preview_icons=dup.load_preview_icons
        del self.views[:]
        for v in dup.views:
            self.views.append(v.copy())
        return dup

    def simple_copy(self):
        return SimpleCollection(self,True)

    def add(self,item,add_to_view=True):
        '''
        add an item to the collection and notify plugin
        '''
        try:
            ind=bisect.bisect_left(self.items,item)
            if len(self.items)>ind>0 and self.items[ind]==item:
                raise LookupError
            self.items.insert(ind,item)
            self.numselected+=item.selected
            pluginmanager.mgr.callback_collection('t_collection_item_added',self,item)
            if add_to_view:
                for v in self.views:
                    v.add_item(item)
            return True
        except LookupError:
            print 'WARNING: tried to add',item,ind,'to collection',self.id,'but an item with this id was already present'
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print tb_text
            return False

    def find(self,item):
        '''
        find an item in the collection and return its index
        '''
        i=bisect.bisect_left(self,item)
        if i>=len(self.items) or i<0:
            return -1
        if self.items[i]==item:
            return i
        return -1

    def item_metadata_update(self,item):
        '''
        notification from item that its metadata has been changed
        '''
        pass
#        ind=find(item)
#        if ind>=0:
#            self.items[ind]=item

    def delete(self,item,delete_from_view=True):
        '''
        delete an item from the collection, returning the item to the caller if present
        notifies plugins if the item is remmoved
        '''
        i=self.find(item)
        if i>=0:
            item=self.items[i]
            self.numselected-=item.selected
            self.items.pop(i)
            pluginmanager.mgr.callback_collection('t_collection_item_removed',self,item)
            for v in self.views:
                v.del_item(item)
            return item
        return None

    def __call__(self,ind):
        return self.items[ind]

    def __getitem__(self,ind):
        return self.items[ind]

    def get_items(self):
        return self.items[:]

    def start_monitor(self,callback):
        if self.monitor_image_dirs:
            self.monitor_master_callback=callback
            self.monitor=monitor.Monitor(self.image_dirs,self.recursive,self.monitor_callback)

    def end_monitor(self):
        if self.monitor!=None and self.monitor_image_dirs:
            self.monitor.stop()
            self.monitor=None

    def monitor_callback(self,path,action,is_dir):
        self.monitor_master_callback(self,path,action,is_dir)

    def open(self):
        '''
        load the collection from a binary pickle file
        '''
        col_dir=os.path.join(settings.collections_dir,self.name)
        if self.is_open:
            return True
        try:
            if os.path.isfile(col_dir):
                return self.legacy_open(col_dir)
            f=open(self.data_file(),'rb')
            version=cPickle.load(f)
            print 'Loaded collection version',version
            if version>='0.5':
                self.items=cPickle.load(f)
            self.numselected=0
            return True
        except:
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print "Error Loading Collection",self.name
            print tb_text
            self.empty()
            return False

    def close(self):
        '''
        save the collection to a binary pickle file using the filename attribute of the collection
        '''
        if self.type!='FLICKR':
            return True
        print 'started close',self.name
        if not self.is_open:
            return True
        if self.type!='FLICKR':
            return False
        print 'starting close',self.name
        try:
            col_dir=os.path.join(settings.collections_dir,self.name)
            print 'closing',col_dir
            if os.path.isfile(col_dir):
                print 'removing',col_dir
                os.remove(col_dir)
            if not os.path.exists(col_dir):
                print 'make dir',col_dir
                os.makedirs(col_dir)
            #self.save_prefs()
            f=open(self.data_file(),'wb')
            cPickle.dump(settings.version,f,-1)
            cPickle.dump(self.items,f,-1)
            f.close()
            self.empty()
        except:
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print "Error Writing Collection",self.name
            print tb_text
            return False
        return True

    def empty(self,empty_views=True):
        del self.items[:]
        self.numselected=0
        if empty_views:
            for v in self.views:
                v.empty()

    def __len__(self):
        return len(self.items)

    def set_prefs(self,prefs):
        for p in self.col_prefs:
            if p in prefs:
                self.__dict__[p]=prefs[p]

    def get_prefs(self):
        prefs={}
        for p in self.col_prefs:
            prefs[p]=self.__dict__[p]
        return prefs

    def delete_cache_files(self):
        col_dir=os.path.join(settings.collections_dir,self.name)
        try:
            if os.path.isdir(col_dir):
                for root, dirs, files in os.walk(col_dir, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(col_dir)
            elif os.path.isfile(col_dir):
                io.remove_file(col_dir)
            return True
        except IOError:
            print 'Error removing collection data files in',col_dir
            import sys,traceback
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print tb_text
            return False

    def legacy_open(self,filename='',load_items=True):  ##todo: put all of the legacy cruft elsewhere
        '''
        load the collection from a binary pickle file identified by the pathname in the filename argument
        '''
        if self.is_open:
            return True
        print 'loading legacy collection',filename
        try:
            if not filename:
                return False
            f=open(filename,'rb')
            version=cPickle.load(f)
            if version<'0.3.0':
                self.image_dirs=settings.legacy_image_dirs
            elif version<='0.4.0':
                self.image_dirs=cPickle.load(f)
            elif version>='0.4.1':
                d=cPickle.load(f)
                self.set_prefs(d)
            if load_items:
                if version>='0.4.0':
                    self.items=cPickle.load(f)
                else:
                    f.close()
                    c=Collection([])
                    c.load(filename)
                    self.items[:]=c[:]
            self.numselected=0
            return True
        except:
            import traceback,sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print "Error Loading Collection",filename
            print tb_text
            self.empty()
            return False



baseobjects.register_collection('LOCALSTORE',Collection)
baseobjects.register_view('LOCALSTORE',CollectionView)
