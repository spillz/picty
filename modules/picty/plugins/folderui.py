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

import threading
import cPickle
import copy

import os.path
import gobject
import gtk

from picty import pluginbase
from picty import baseobjects
from picty import imagemanip
from picty import backend
from picty import settings
from picty.uitools import dialogs

class FolderTreeRebuildJob(backend.WorkerJob):
    def __init__(self,worker,collection,browser,folderframe):
        backend.WorkerJob.__init__(self,'FOLDERCLOUDREBUILD')
        self.folderframe=folderframe

    def __call__(self):
        if not self.folderframe:
            return True
#        while self.pos<len(collection):
        self.folderframe.folder_cloud.empty()
        for item in self.collection:
            self.folderframe.folder_cloud.add(item)
        self.folderframe.folder_cloud_view.empty()
        for item in self.view:
            self.folderframe.folder_cloud_view.add(item)
        if self.folderframe:
            gobject.idle_add(self.folderframe.start_refresh_timer)
        return True


class FolderTree():
    '''
    python representation of the folder tree of the images in a view or collection in the `folders` attribute
    example folder structure
    /home/user/Pictures
    +a/b.jpg
    +b/c.jpg
    +b/d/e.jpg
    will have `folders` attribute
    [{'a':[{},1],'b':[{'c':[{},1]},2]},3]
    '''
    def __init__(self):
        self.folders=[dict(),0]
    def __repr__(self):
        return self.folders.__repr__()
    def copy(self):
        c=FolderTree()
        c.folders=copy.deepcopy(self.folders)
        return c
    def empty(self):
        self.folders=dict()
    def folder_add(self,path):
        print 'adding',path
        path_folders = path.split('/')
        base = self.folders
        base[1]+=1
        for f in path_folders:
            if f in base[0]:
                base[0][f][1]+=1
            else:
                base[0][f]=[dict(),1]
            base = base[0][f]
    def folder_remove(self,path):
        path_folders = path.split('/')
        base = self.folders
        base[1]-=1
        for f in path_folders:
            if f in base[0]:
                if base[0][f][1]>1:
                    base[0][f][1]-=1
                else:
                    del base[0][f]
                    return
            else:
                print 'warning: removing item',item,'with keyword',k,'not in folder cloud'
                return
            base = base[0][f]
    def add(self,item):
        if item.meta==None:
            return False
        try:
            self.folder_add(os.path.split(item.uid)[0])
        except:
            return False
        return True
    def remove(self,item):
        try:
            if item.meta==None:
                return False
            self.folder_remove(os.path.split(item.uid)[0])
        except:
            return False
        return True
    def update(self,item,old_meta):
        try:
            self.folder_remove(os.path.split(item.uid)[0])
        except:
            pass
        try:
            self.folder_add(os.path.split(item.uid)[0])
        except:
            pass
    def revert(self,item):
        try:
            self.folder_remove(os.path.split(item.uid)[0])
        except:
            pass
        try:
            self.folder_add(os.path.split(item.uid)[0])
        except:
            pass


##    M_TYPE=0 #type of row: 0=Favorite, 1=Other, 2=Category, 3=Folder
##    M_KEY=1 #name of the folder or category
##    M_PIXBUF=2 #pixbuf image displayed next to folder
##    M_DISP=3 #display text
##    M_CHECK=4 #state of check box
##    M_PIXPATH=5 #path to pixbuf


class FolderSidebarPlugin(pluginbase.Plugin):
    name='FolderSidebar'
    display_name='Folder Sidebar'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        print 'INITIALIZED FOLDER SIDEBAR PLUGIN'
    def plugin_init(self,mainframe,app_init):
        self.mainframe=mainframe
        self.worker=mainframe.tm
        self.block_refresh={}
        data=settings.load_addon_prefs('folder_plugins_settings')
        if data:
            pass
        self.folderframe=FolderFrame(self.mainframe,{})
        self.folderframe.show_all()
        self.mainframe.sidebar.append_page(self.folderframe,gtk.Label("Folders"))
#        self.mainframe.connect("folder-row-dropped",self.folder_dropped_in_browser)
        self.mainframe.connect("view-rebuild-complete",self.view_rebuild_complete)
    def plugin_shutdown(self,app_shutdown=False):
        data={
            'version':self.version,
        }
        settings.save_addon_prefs('folder_plugin_settings',data)
    def t_collection_item_added(self,collection,item):
        '''item was added to the collection'''
        if not collection.local_filesystem:
            return
        self.folderframe.folder_cloud[collection].add(item)
        self.thread_refresh()
    def t_collection_item_removed(self,collection,item):
        '''item was removed from the collection'''
        if not collection.local_filesystem:
            return
        self.folderframe.folder_cloud[collection].remove(item)
        self.thread_refresh()
    def t_collection_item_metadata_changed(self,collection,item,meta_before):
        '''item metadata has changed'''
        if collection!=None:
            if not collection.local_filesystem:
                return
            self.folderframe.folder_cloud[collection].update(item,meta_before)
            i=collection.get_active_view().find_item(item)
            if i>=0:
                self.folderframe.folder_cloud_view[collection.get_active_view()].update(item,meta_before)
            self.thread_refresh()
    def t_collection_item_added_to_view(self,collection,view,item):
        '''item in collection was added to view'''
        if not collection.local_filesystem:
            return
        self.folderframe.folder_cloud_view[view].add(item)
        self.thread_refresh()
    def t_collection_item_removed_from_view(self,collection,view,item):
        '''item in collection was removed from view'''
        if not collection.local_filesystem:
            return
        self.folderframe.folder_cloud_view[view].remove(item)
        self.thread_refresh()
    def t_collection_modify_start_hint(self,collection):
        if not collection.local_filesystem:
            return
        self.block_refresh[collection]=True
    def t_collection_modify_complete_hint(self,collection):
        if not collection.local_filesystem:
            return
        del self.block_refresh[collection]
        self.thread_refresh()
    def thread_refresh(self):
        if self.worker.active_collection not in (self.block_refresh):
            gobject.idle_add(self.folderframe.start_refresh_timer)
    def folder_dropped_in_browser(self,mainframe,browser,item,folder_widget,path):
        return #nothing really to do here? Should remove drag to browser
#        print 'folder Plugin: dropped',folder_widget,path
#        folders=self.folderframe.get_folders(path)
#        if not item.selected:
#            imagemanip.toggle_folders(item,folders)
#        else:
#            self.worker.keyword_edit(folders,True)
    def t_collection_loaded(self,collection):
        '''collection has loaded into main frame'''
        if not collection.local_filesystem:
            return
        self.folderframe.folder_cloud[collection]=FolderTree()
        view=collection.get_active_view()
        if view:
            self.folderframe.folder_cloud_view[view]=FolderTree()
        for item in collection:
            self.folderframe.folder_cloud[collection].add(item)
        self.thread_refresh()
    def t_collection_closed(self,collection):
        if not collection.local_filesystem:
            return
        del self.folderframe.folder_cloud[collection]
        try:
            del self.folderframe.folder_cloud_view[collection.get_active_view()]
        except KeyError:
            pass
        self.thread_refresh()
    def collection_activated(self,collection):
        self.folderframe.refresh()
    def t_view_emptied(self,collection,view):
        '''the view has been flushed'''
        self.folderframe.folder_cloud_view[view]=FolderTree()
        self.folderframe.refresh()
    def t_view_updated(self,collection,view):
        '''the view has been updated'''
        self.folderframe.folder_cloud_view[view]=FolderTree()
        for item in view:
            self.folderframe.folder_cloud_view[view].add(item)
        self.folderframe.refresh()
    def view_rebuild_complete(self,mainframe,browser):
        self.folderframe.refresh()
    def load_user_folders(self,filename):
        pass
    def save_user_folders(self,filename):
        pass


#class FolderModel(gtk.TreeStore):
#    def __init__(self,*args):
#        gtk.TreeStore.__init__(self,*args)
#    def row_draggable(self, path):
#        print 'folder model'
#        return self[path][0]!=''
#    def drag_data_delete(self, path):
#        return False
#    def drag_data_get(self, path, selection_data):
#        return False

class FolderFrame(gtk.VBox):
    '''
    provides a tree view for seeing the folder structure of the collection
    and offers double click, and right click menu options to filter the collection to those folders
    TODO: Add support for drag and drop to move files
    '''
    ##column indices of the treestore
    M_TYPE=0 #type of row: 0=Favorite, 1=Other, 2=Category, 3=Folder
    M_KEY=1 #name of the folder or category
    M_PIXBUF=2 #pixbuf image displayed next to folder
    M_DISP=3 #display text
    M_CHECK=4 #state of check box
    M_PIXPATH=5 #path to pixbuf
    def __init__(self,mainframe,user_folder_info):
        gtk.VBox.__init__(self)
        self.set_spacing(5)
        self.folder_cloud={} ##these are updated on the worker thread, be careful about accessing on the main thread (should use locks)
        self.folder_cloud_view={}
        self.mainframe=mainframe
        self.worker=mainframe.tm
        label=gtk.Label()
        label.set_markup("<b>Folders</b>")
        label.set_alignment(0.05,0)
        #self.pack_start(label,False)
        self.model=gtk.TreeStore(int,str,gtk.gdk.Pixbuf,str,'gboolean',str)
##        self.sort_model=gtk.TreeModelSort(self.model)
##        self.sort_model.set_sort_column_id(1, gtk.SORT_ASCENDING)
        self.tv=gtk.TreeView(self.model)
#        self.tv.set_reorderable(True)
        self.tv.set_headers_visible(False)
        self.tv.connect("row-activated",self.folder_activate_subfolder)
#        tvc_bitmap=gtk.TreeViewColumn(None,gtk.CellRendererPixbuf(),pixbuf=self.M_PIXBUF,markup=self.M_DISP)
#        tvc_text=gtk.TreeViewColumn(None,gtk.CellRendererText(),markup=self.M_DISP)
        tvc=gtk.TreeViewColumn()
        txt=gtk.CellRendererText()
        pb=gtk.CellRendererPixbuf()
        tvc.pack_start(pb,False)
        tvc.pack_start(txt,True)
        tvc.add_attribute(pb,'pixbuf',self.M_PIXBUF)
        tvc.add_attribute(txt,'markup',self.M_DISP)
#        toggle=gtk.CellRendererToggle()
#        toggle.set_property("activatable",True)
#        toggle.connect("toggled",self.toggle_signal)
#        tvc_check=gtk.TreeViewColumn(None,toggle,active=self.M_CHECK)
#        ##gtk.CellRendererText
##        self.tv.append_column(tvc_check)
##        self.tv.append_column(tvc_bitmap)
##        self.tv.append_column(tvc_text)
        self.tv.append_column(tvc)

#        self.tv.enable_model_drag_dest([('folder-tree-row', gtk.TARGET_SAME_WIDGET, 0),
#                                    ('image-filename', gtk.TARGET_SAME_APP, 1)],
#                                    gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE)
#        self.tv.connect("drag-data-received",self.drag_receive_signal)
#        self.tv.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
#                  [('folder-tree-row', gtk.TARGET_SAME_APP, 0)],
#                  gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
#        self.tv.connect("drag-data-get",self.drag_get_signal)

        self.tv.add_events(gtk.gdk.BUTTON_MOTION_MASK)
        self.tv.connect("button-release-event",self.context_menu)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.add(self.tv)
        scrolled_window.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        self.pack_start(scrolled_window)

#        button_box = gtk.HButtonBox()
##        button_box.pack_start(folder_sel_button)
##        folder_mode_button= gtk.ToggleButton('Folder Mode')
##        folder_mode_button.connect("toggled",self.folder_mode_toggle_signal)
##        folder_mode_button.set_tooltip_text('When this button is depressed, clicking on images in the browser adds the checked folders above, CTRL+click removes the folders')
##        button_box.pack_start(folder_mode_button)
#        button_box.show_all()
#        self.pack_start(button_box,False)
        self.timer=None
        self.collection=None

    def start_refresh_timer(self):
        if self.timer!=None:
            self.timer.cancel()
        self.timer=threading.Timer(1,self.refresh)
        self.timer.start()

    def context_menu(self,widget,event):
        if event.button==3:
            (row_path,tvc,tvc_x,tvc_y)=self.tv.get_path_at_pos(int(event.x), int(event.y))
            row_iter=self.model.get_iter(row_path)
            menu=gtk.Menu()
            def menu_add(menu,text,callback):
                item=gtk.MenuItem(text)
                item.connect("activate",callback,row_iter)
                menu.append(item)
                item.show()

            menu_add(menu,"Show images in this folder and sub folders",self.folder_activate_subfolders)
            menu_add(menu,"Show images in this folder",self.folder_activate)
            menu_add(menu,"Restrict view to images in this folder",self.folder_activate_view)
            menu.popup(parent_menu_shell=None, parent_menu_item=None, func=None, button=1, activate_time=0, data=0)

    def iter_all_children(self,iter_node):
        '''iterate all rows from iter_node and their children'''
        while iter_node:
            yield self.model[iter_node]
            for r in self.iter_all_children(self.model.iter_children(iter_node)):
                yield r
            iter_node=self.model.iter_next(iter_node)

    def iter_row_children(self,iter_node):
        '''generator for current row and all children'''
        yield self.model[iter_node]
        for x in self.iter_all_children(self.model.iter_children(iter_node)):
            yield x

    def iter_children(self,iter):
        iter=self.model.iter_children(iter)
        while iter:
            yield iter #self.model[iter]
            iter=self.model.iter_next(iter)

    def iter_all(self):
        '''iterate over entire tree'''
        for x in self.iter_all_children(self.model.get_iter_root()):
            yield x

    def move_row_and_children(self,iter_node,dest_iter,rownum=None):
        def copy(iter_node,dest_iter,rownum=None):
            row=list(self.model[iter_node])
            if rownum!=None:
                dest_iter=self.model.insert(dest_iter,rownum,row)
            else:
#                it=self.model.iter_children(dest_iter)
#                it=None
                n=self.model.iter_n_children(dest_iter)
                for i in range(n):
                    it=self.model.iter_nth_child(dest_iter,i)
                    if self.model[it][self.M_DISP].lower()>row[self.M_DISP].lower():
                        dest_iter=self.model.insert(dest_iter,i,row)
                        n=-1
                        break
                if n>=0:
                    dest_iter=self.model.append(dest_iter,row)
            row=self.model[dest_iter]
            if row[self.M_TYPE]==3:
                self.user_folders[row[self.M_KEY]]=gtk.TreeRowReference(self.model,self.model.get_path(dest_iter))
            iter_node=self.model.iter_children(iter_node)
            while iter_node:
                copy(iter_node,dest_iter)
                iter_node=self.model.iter_next(iter_node)
        iter=dest_iter
        while iter: ##abort if user is trying to drag a row to one of its children
            if self.model.get_path(iter)==self.model.get_path(iter_node):
                return
            iter=self.model.iter_parent(iter)
        copy(iter_node,dest_iter,rownum)
        self.model.remove(iter_node)


#    def get_checked_folders(self):
#        return [it[self.M_KEY] for it in self.iter_all() if it[self.M_TYPE]==3 and it[self.M_CHECK]]

#    def get_folders(self,path):
#        iter=self.model.get_iter(path)
#        return [it[self.M_KEY] for it in self.iter_row_children(iter) if it[self.M_TYPE]==3]

#    def drag_receive_signal(self, widget, drag_context, x, y, selection_data, info, timestamp):
#        '''something was dropped on a tree row'''
#        drop_info = self.tv.get_dest_row_at_pos(x, y)
#        if drop_info:
#            drop_row,pos=drop_info
#            drop_iter=self.model.get_iter(drop_row)
#            data=selection_data.data
#            if selection_data.type=='folder-tree-row':
#                paths=data.split('-')
#                iters=[]
#                for path in paths:
#                    iters.append(self.model.get_iter(path))
#                for it in iters:
#                    path=list(self.model.get_path(drop_iter))
#                    rownum=path.pop()
#                    if self.model[it]<2:
#                        continue
#                    ##gtk.TREE_VIEW_DROP_BEFORE, gtk.TREE_VIEW_DROP_AFTER, gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or gtk.TREE_VIEW_DROP_INTO_OR_AFTER
#                    if self.model[drop_iter][self.M_TYPE]==3:
#                        if pos in [gtk.TREE_VIEW_DROP_AFTER,gtk.TREE_VIEW_DROP_INTO_OR_AFTER]:
#                            rownum+=1
#                        drop_iter=self.model.iter_parent(drop_iter)
#                        self.move_row_and_children(it,drop_iter,rownum)
#                    else:
#                        if pos in [gtk.TREE_VIEW_DROP_INTO_OR_BEFORE,gtk.TREE_VIEW_DROP_INTO_OR_AFTER]:
#                            self.move_row_and_children(it,drop_iter)
#                        else:
#                            if pos==gtk.TREE_VIEW_DROP_AFTER:
#                                pos+=1
#                            self.move_row_and_children(it,drop_iter,pos)
#            elif selection_data.type=='image-filename':
#                model_path=list(self.model.get_path(drop_iter))
#                if len(model_path)<=1 or model_path[0]==1:
#                    return
#                path=data
#                from picty import baseobjects
#                item=baseobjects.Item(path)
#                ind=self.worker.active_collection.find(item)
#                if ind<0:
#                    return False
#                thumb_pb=self.worker.active_collection(ind).thumb
#                if thumb_pb:
#                    width,height=gtk.icon_size_lookup(gtk.ICON_SIZE_MENU)
#                    width=width*3/2
#                    height=height*3/2
#                    tw=thumb_pb.get_width()
#                    th=thumb_pb.get_height()
#                    if width/height>tw/th:
#                        height=width*th/tw
#                    else:
#                        width=height*tw/th
#                    thumb_pb=thumb_pb.scale_simple(width*3/2,height*3/2,gtk.gdk.INTERP_BILINEAR)
#                    self.set_and_save_user_bitmap(drop_iter,thumb_pb)
#                ## get the thumbnail and set the drop_iter row pixbuf and pixpath accordingly
#                pass
#
#    def drag_get_signal(self, widget, drag_context, selection_data, info, timestamp):
#        treeselection = self.tv.get_selection()
#        model, paths = treeselection.get_selected_rows()
#        strings=[]
#        for p in paths:
#            if self.model[p][self.M_TYPE] not in (0,1):
#                strings.append(self.model.get_string_from_iter(self.model.get_iter(p)))
#        if len(strings)==0:
#            return False
#        selection_data.set('folder-tree-row', 8, '-'.join(strings))

    def folder_activate_view(self, widget, iter):
        path = list(path)
        folder = []
        while len(path)>1:
            folder.insert(0,self.model[tuple(path)][self.M_KEY])
            path.pop(-1)
        text='folder="%s" '%'/'.join(path)
        self.mainframe.filter_entry.set_text('lastview&'+text.strip())
        self.mainframe.filter_entry.activate()

    def folder_activate(self,treeview, path, view_column):
        path = list(path)
        folder = []
        while len(path)>1:
            folder.insert(0,self.model[tuple(path)][self.M_KEY])
            path.pop(-1)
        text='folder="%s" '%'/'.join(folder)
        self.mainframe.filter_entry.set_text(text.strip())
        self.mainframe.filter_entry.activate()

    def folder_activate_subfolder(self,treeview, path, view_column):
        path = list(path)
        folder = []
        while len(path)>1:
            folder.insert(0,self.model[tuple(path)][self.M_KEY])
            path.pop(-1)
        text='folder~"%s" '%'/'.join(folder)
        self.mainframe.filter_entry.set_text(text.strip())
        self.mainframe.filter_entry.activate()

    def refresh(self):
        collection=self.worker.active_collection
        if collection==None:
            view=None
        else:
            view=collection.get_active_view()
        try:
            folder_cloud=self.folder_cloud[collection].copy() ##todo: should be using a lock here
        except KeyError:
            folder_cloud=FolderTree()
        try:
            folder_cloud_view=self.folder_cloud_view[view].copy()
        except KeyError:
            folder_cloud_view=FolderTree()
        if self.collection != collection:
            self.model.clear()
            self.collection=collection
            if collection is not None:
                self.model.append(None,(1,'other',None,'<b>%s</b>'%(collection.image_dirs[0]),False,None))
        if collection is None or not collection.local_filesystem:
            return

        root_folder_list=sorted([(t.lower(),t,folder_cloud.folders[0][t]) for t in folder_cloud.folders[0]])
        root_folder_list=[t[1:] for t in root_folder_list]
        def add_folder(parent_iter,folder_list_object):
            '''
            recursively add folder object to tree
            '''
            for folder_name,data in folder_list_object:
                it = self.model.append(parent_iter,(3,folder_name,None,folder_name+' (%i)'%(data[1]),False,None))
                folder_list = sorted([(t.lower(),t,data[0][t]) for t in data[0]])
                folder_list = [t[1:] for t in folder_list]
                add_folder(it,folder_list)
        def update_folder(parent_iter,folder_list_object):
            '''
            recursively add folder object to tree
            '''
            names = [f[0] for f in folder_list_object]
            for ch in self.iter_children(parent_iter):
                print ch
                ind  = names.index(self.model[ch][1])
                if ind<0:
                    self.model.remove(ch)
                else:
                    del folder_list_object[ind]
                    del names[ind]
            for folder_name,data in folder_list_object:
                it = self.model.append(parent_iter,(3,folder_name,None,folder_name+' (%i)'%(data[1]),False,None))
                folder_list = sorted([(t.lower(),t,data[0][t]) for t in data[0]])
                folder_list = [t[1:] for t in folder_list]
                add_folder(it,folder_list)
        it = self.model.get_iter((0,))
        update_folder(it,root_folder_list)
        self.tv.expand_row((0,),False)

