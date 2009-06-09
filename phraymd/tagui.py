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

import gtk
import imageinfo

###TODOs: Moving rows should move children


## provides gui elements for working with tags
## 1. tree interface for choosing tags to "paint" onto  images
## 2. tag selector dialog
## 3. tag auto-completer
## tag collection object (keeps track of available tags and counts)

#class TagModel(gtk.TreeStore):
#    def __init__(self,*args):
#        gtk.TreeStore.__init__(self,*args)
#    def row_draggable(self, path):
#        print 'tag model'
#        return self[path][0]!=''
#    def drag_data_delete(self, path):
#        return False
#    def drag_data_get(self, path, selection_data):
#        return False

class TagFrame(gtk.VBox):
    ##column indices of the treestore
    M_TYPE=0 #type of row: 0=Favorite, 1=Other, 2=Category, 3=Tag
    M_KEY=1 #name of the tag or category
    M_PIXBUF=2 #pixbuf image displayed next to tag
    M_DISP=3 #display text
    M_CHECK=4 #state of check box
    M_PIXPATH=5 #path to pixbuf
    def __init__(self,worker,browser,user_tag_info):
        gtk.VBox.__init__(self)
        self.user_tags={}
        self.worker=worker
        self.browser=browser
        self.model=gtk.TreeStore(int,str,gtk.gdk.Pixbuf,str,'gboolean',str)
        self.tv=gtk.TreeView(self.model)
#        self.tv.set_reorderable(True)
        self.tv.set_headers_visible(False)
        self.tv.connect("row-activated",self.tag_activate)
        tvc_bitmap=gtk.TreeViewColumn(None,gtk.CellRendererPixbuf(),pixbuf=self.M_PIXBUF)
        tvc_text=gtk.TreeViewColumn(None,gtk.CellRendererText(),markup=self.M_DISP)
        toggle=gtk.CellRendererToggle()
        toggle.set_property("activatable",True)
        toggle.connect("toggled",self.toggle_signal)
        tvc_check=gtk.TreeViewColumn(None,toggle,active=self.M_CHECK)
        ##gtk.CellRendererText
        self.tv.append_column(tvc_check)
        self.tv.append_column(tvc_bitmap)
        self.tv.append_column(tvc_text)
        self.tv.enable_model_drag_dest([('tag-tree-row', gtk.TARGET_SAME_WIDGET, 0),
                                    ('image-filename', gtk.TARGET_SAME_APP, 1)],
                                    gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE)
        self.tv.connect("drag-data-received",self.drag_receive_signal)
        self.tv.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
                  [('tag-tree-row', gtk.TARGET_SAME_APP, 0)],
                  gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        self.tv.connect("drag-data-get",self.drag_get_signal)
        self.tv.add_events(gtk.gdk.BUTTON_MOTION_MASK)
        self.tv.connect("button-release-event",self.context_menu)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.add_with_viewport(self.tv)
        scrolled_window.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        self.pack_start(scrolled_window)

        button_box = gtk.HButtonBox()
        tag_sel_button= gtk.Button('_Tag Selected')
        tag_sel_button.connect("clicked",self.tag_selected_signal)
        tag_sel_button.set_tooltip_text('Applies checked tags above to the selected images in the view')
        button_box.pack_start(tag_sel_button)
        tag_mode_button= gtk.ToggleButton('Tag _Mode')
        tag_mode_button.connect("toggled",self.tag_mode_toggle_signal)
        tag_mode_button.set_tooltip_text('When this button is depressed, clicking on images in the browser adds the checked tags above, CTRL+click removes the tags')
        button_box.pack_start(tag_mode_button)
        button_box.show_all()
        self.pack_start(button_box,False)

        self.model.append(None,(0,'favorites',None,'<b>Favorites</b>',False,''))
        self.model.append(None,(1,'other',None,'<b>Other</b>',False,''))
        self.set_user_tags(user_tag_info)

    def context_menu(self,widget,event):
        if event.button==3:
            (row_path,tvc,tvc_x,tvc_y)=self.tv.get_path_at_pos(event.x, event.y)
            row_iter=self.model.get_iter(row_path)
            menu=gtk.Menu()
            def menu_add(menu,text,callback):
                item=gtk.MenuItem(text)
                item.connect("activate",callback,row_iter)
                menu.append(item)
                item.show()
            if row_path[0]==0:
                if self.model[row_path][self.M_TYPE] in (0,2):
                    menu_add(menu,"New _Category",self.add_category)
                    menu_add(menu,"New _Tag",self.add_tag)
                if len(row_path)>1:
                    if self.model[row_path][self.M_TYPE]==3:
                        menu_add(menu,"_Delete Tag",self.remove_tag)
                        menu_add(menu,"Re_name Tag",self.rename_tag)
                        menu_add(menu,"_Apply to Selected Images",self.apply_tag_to_browser_selection)
                        menu_add(menu,"Re_move from Selected Images",self.remove_tag_from_browser_selection)
                    if self.model[row_path][self.M_TYPE]==2:
                        menu_add(menu,"_Delete Category",self.remove_category)
                        menu_add(menu,"Re_name Category",self.rename_category)
                menu_add(menu,"Remove _Image",self.remove_bitmap)
                menu.popup(parent_menu_shell=None, parent_menu_item=None, func=None, button=1, activate_time=0, data=0)

    def remove_bitmap(self,widget,iter):
        self.delete_user_bitmap(iter)

    def add_tag(self,widget,parent):
        k=self.browser.entry_dialog('Add a Tag','Name:')
        if not k:
            return
        try:
            new_iter=self.model.append(parent,(3,k,None,k+' (%i)'%(0,),False,''))
            new_path=self.model.get_path(new_iter)
            self.user_tags[k]=gtk.TreeRowReference(self.model,new_path)
        except:
            pass

    def remove_tag(self,widget,iter):
        try:
            k=self.model[iter][self.M_KEY]
            self.model.remove(iter)
            del self.user_tags[k]
        except:
            pass

    def rename_tag(self,widget,parent):
        old_key=self.model[iter][self.M_KEY]
        k=self.browser.entry_dialog('Rename Tag','New Name:',old_key)
        if not k or k==old_key:
            return
        try:
            self.model[iter][self.M_KEY]=k
            self.model[iter][self.M_DISP]=k
            self.user_tags[k]=self.user_tags[old_key]
            del self.user_tags[old_key]
        except:
            pass

    def add_category(self,widget,parent):
        k=self.browser.entry_dialog('Add a Category','Name:')
        if not k:
            return
        try:
            self.model.append(parent,(2,k,None,'<b>%s</b>'%(k,),False,''))
        except:
            pass

    def remove_category(self,widget,iter):
        try:
            self.model.remove(iter)
        except:
            pass

    def rename_category(self,widget,iter):
        old_key=self.model[iter][self.M_KEY]
        k=self.browser.entry_dialog('Rename Category','New Name:',old_key)
        if not k or k==old_key:
            return
        try:
            self.model[iter][self.M_KEY]=k
            self.model[iter][self.M_DISP]='<b>%s</b>'%(k,)
        except:
            pass

    def apply_tag_to_browser_selection(self,widget,iter):
        row=self.model[iter]
        if row[self.M_TYPE]!=3:
            return
        keyword_string='"%s"'%(row[self.M_KEY],)
        if keyword_string:
            self.worker.keyword_edit(keyword_string)

    def remove_tag_from_browser_selection(self,widget,iter):
        row=self.model[iter]
        if row[self.M_TYPE]!=3:
            return
        keyword_string='"%s"'%(row[self.M_KEY],)
        if keyword_string:
            self.worker.keyword_edit(keyword_string,True)

    def tag_mode_toggle_signal(self, button):
        if button.get_active():
            self.browser.mode=self.browser.MODE_TAG
        else:
            self.browser.mode=self.browser.MODE_NORMAL
        self.browser.imarea.grab_focus()

    def tag_selected_signal(self, button):
        tags=self.get_checked_tags()
        keyword_string=''
        for t in tags:
            keyword_string+='"%s" '%(t,)
        if keyword_string:
            self.worker.keyword_edit(keyword_string)

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
            print iter
            yield self.model[iter]
            iter=self.model.iter_next(iter)

    def iter_all(self):
        '''iterate over entire tree'''
        for x in self.iter_all_children(self.model.get_iter_root()):
            yield x

##    def iter_all_children(self,iter_node):
##        '''generator for current row and all children'''
##        iter_node=self.model.iter_children(iter_node)
##        while iter_node:
##            for iter_node in self.iter_all_children(self.model.iter_children(iter_node)):
##                yield iter_node
##            iter_node=self.model.iter_next(iter_node)

    def move_row_and_children(self,iter_node,dest_iter,rownum=None):
        def copy(iter_node,dest_iter,rownum=None):
            row=list(self.model[iter_node])
            if rownum!=None:
                print 'inserting',row,rownum
                dest_iter=self.model.insert(dest_iter,rownum,row)
            else:
                print 'appending',row,rownum
                dest_iter=self.model.append(dest_iter,row)
            row=self.model[dest_iter]
            print 'dest',dest_iter
            if row[self.M_TYPE]==3:
                self.user_tags[row[self.M_KEY]]=gtk.TreeRowReference(self.model,self.model.get_path(dest_iter))
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

    def get_checked_tags(self):
        return [it[self.M_KEY] for it in self.iter_all() if it[self.M_TYPE]==3 and it[self.M_CHECK]]

    def get_tags(self,path):
        iter=self.model.get_iter(path)
        return [it[self.M_KEY] for it in self.iter_row_children(iter) if it[self.M_TYPE]==3]

    def drag_receive_signal(self, widget, drag_context, x, y, selection_data, info, timestamp):
        '''something was dropped on a tree row'''
        drop_info = self.tv.get_dest_row_at_pos(x, y)
        if drop_info:
            drop_row,pos=drop_info
            drop_iter=self.model.get_iter(drop_row)
            data=selection_data.data
            if selection_data.type=='tag-tree-row':
                paths=data.split('-')
                iters=[]
                for path in paths:
                    iters.append(self.model.get_iter(path))
                for it in iters:
                    path=list(self.model.get_path(drop_iter))
                    rownum=path.pop()
                    if self.model[it]<2:
                        continue
                    ##gtk.TREE_VIEW_DROP_BEFORE, gtk.TREE_VIEW_DROP_AFTER, gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or gtk.TREE_VIEW_DROP_INTO_OR_AFTER
                    if self.model[drop_iter][self.M_TYPE]==3:
                        if pos in [gtk.TREE_VIEW_DROP_AFTER,gtk.TREE_VIEW_DROP_INTO_OR_AFTER]:
                            rownum+=1
                        drop_iter=self.model.iter_parent(drop_iter)
                        print drop_iter,path,rownum
                        self.move_row_and_children(it,drop_iter,rownum)
                    else:
                        if pos in [gtk.TREE_VIEW_DROP_INTO_OR_BEFORE,gtk.TREE_VIEW_DROP_INTO_OR_AFTER]:
                            self.move_row_and_children(it,drop_iter)
                        else:
                            if pos==gtk.TREE_VIEW_DROP_AFTER:
                                pos+=1
                            self.move_row_and_children(it,drop_iter,pos)
            elif selection_data.type=='image-filename':
                path=data
                import imageinfo
                item=imageinfo.Item(path,0)
                ind=self.worker.collection.find(item)
                if ind<0:
                    return False
                thumb_pb=self.worker.collection(ind).thumb
                if thumb_pb:
                    width,height=gtk.icon_size_lookup(gtk.ICON_SIZE_MENU)
                    width=width*3/2
                    height=height*3/2
                    tw=thumb_pb.get_width()
                    th=thumb_pb.get_height()
                    if width/height>tw/th:
                        width=height*tw/th
                    else:
                        height=width*th/tw
                    thumb_pb=thumb_pb.scale_simple(width*1.5,height*1.5,gtk.gdk.INTERP_BILINEAR)
                    self.set_and_save_user_bitmap(drop_iter,thumb_pb)
                ## get the thumbnail and set the drop_iter row pixbuf and pixpath accordingly
                pass

    def drag_get_signal(self, widget, drag_context, selection_data, info, timestamp):
        treeselection = self.tv.get_selection()
        model, paths = treeselection.get_selected_rows()
        strings=[]
        for p in paths:
            print 'drag get',p,self.model[p][self.M_TYPE]
            if self.model[p][self.M_TYPE] not in (0,1):
                strings.append(self.model.get_string_from_iter(self.model.get_iter(p)))
        if len(strings)==0:
            return False
        selection_data.set('tag-tree-row', 8, '-'.join(strings))

    def set_user_tags(self,usertaginfo):
        '''
        sets the user defined tags
        usertaginfo is a list with each element a sublist containing:
            [tree_path,tag_name,display_text,icon_path]
            NB: model contains [tag_name,pixbuf,display_text,check_state,icon_path]
        '''
        self.user_tags={}
        path=self.model.get_iter((0,))
        self.model.remove(path)
        self.model.insert(None,0,(0,'favorites',None,'<b>Favorites</b>',False,''))
##        try:
        for row in usertaginfo:
            path=row[0]
            parent=self.model.get_iter(path[0:len(path)-1])
            self.model.append(parent,[row[1],row[2],None,row[3],False,row[4]])
            self.user_tags[row[2]]=gtk.TreeRowReference(self.model,path)
        self.load_user_bitmaps(usertaginfo)
##        except:
##            self.user_tags={}
##            path=self.model.get_iter((0,))
##            self.model.remove(path)
##            self.model.insert(None,0,(0,'',None,'Favorites',False,''))

    def get_user_tags_rec(self,usertaginfo, iter):
        '''from a given node iter, recursively appends rows to usertaginfo'''
        while iter:
            row=list(self.model[iter])
            row.pop(self.M_CHECK) ##todo: reverse order of pop is critical here
            row.pop(self.M_PIXBUF)
            usertaginfo.append([self.model.get_path(iter)]+row)
            self.get_user_tags_rec(usertaginfo, self.model.iter_children(iter))
            iter=self.model.iter_next(iter)

    def get_user_tags(self):
        iter=self.model.get_iter((0,))
        usertaginfo=[]
        self.get_user_tags_rec(usertaginfo,self.model.iter_children(iter))
        return usertaginfo

##    def user_bitmaps_to_buffer(self,usertaginfo):
##        ##todo: what if bitmaps haven't finished loading?
##        data=''
##        def cb(buf):
##            data+=buf
##        for row in usertaginfo:
##            if row[2]!=None:
##                row[2].save_to_callback(cb,"png")
##                row[2]=data

    def load_user_bitmaps(self,usertaginfo):
        for t in self.user_tags:
            if t:
                row=self.model[self.user_tags[t].get_path()]
                if row[self.M_PIXPATH]!='':
                    try:
                        row[self.M_PIXBUF]=gtk.gdk.pixbuf_new_from_file(row[self.M_PIXPATH])
                    except:
                        pass

    def delete_user_bitmap(self,tree_path):
        import os
        import os.path
        self.model[tree_path][self.M_PIXBUF]=None
        png_path=os.path.join(os.environ['HOME'],'.phraymd/tag_png')
        fullname=os.path.join(png_path,self.model[tree_path][self.M_KEY])
        try:
            os.remove(fullname)
        except:
            pass

    def set_and_save_user_bitmap(self,tree_path,pixbuf):
        import os.path
        if not self.model[tree_path][self.M_KEY]:
            return False
        self.model[tree_path][self.M_PIXBUF]=pixbuf
        png_path=os.path.join(os.environ['HOME'],'.phraymd/tag_png')
        if not os.path.exists(png_path):
            os.makedirs(png_path)
        if not os.path.isdir(png_path):
            return False
        fullname=os.path.join(png_path,self.model[tree_path][self.M_KEY])
        self.model[tree_path][self.M_PIXPATH]=fullname
        try:
            pixbuf.save(fullname,'png')
        except:
            ##todo: log an error or warn user
            pass

    def tag_activate(self,treeview, path, view_column):
        text=''
        for row in self.iter_row_children(self.model.get_iter(path)):
            if row[self.M_TYPE]==3:
                text+='tag="%s" '%row[self.M_KEY]
        if text:
            self.browser.filter_entry.set_text('view:'+text.strip())
            self.browser.filter_entry.activate()

    def check_row(self,path,state):
        self.model[path][self.M_CHECK]=state
        iter=self.model.get_iter(path)
        for row in self.iter_row_children(iter):
            row[self.M_CHECK]=state
        iter=self.model.iter_parent(iter)
        while iter:
            self.model[iter][self.M_CHECK]=reduce(bool.__and__,[r[self.M_CHECK] for r in self.iter_children(iter)],True)
            iter=self.model.iter_parent(iter)

    def toggle_signal(self,toggle_widget, path):
        state = not toggle_widget.get_active()
        self.check_row(path,state)

    def refresh(self,tag_cloud):
        path=self.model.get_iter((1,))
        self.model.remove(path)
        self.model.append(None,(1,'other',None,'<b>Other</b>',False,''))
        for k in self.user_tags:
            path=self.user_tags[k].get_path()
            row=self.model[path]
            if row[self.M_TYPE]==3:
                try:
                    row[self.M_DISP]=k+' (0)'
                except:
                    print 'ERROR'
                    print row
                    print k
                    print self.user_tags
        for k in tag_cloud.tags:
            if k in self.user_tags:
                path=self.user_tags[k].get_path()
                if path:
                    self.model[path][self.M_DISP]=k+' (%i)'%(tag_cloud.tags[k])
            else:
                path=self.model.get_iter((1,))
                self.model.append(path,(3,k,None,k+' (%i)'%(tag_cloud.tags[k],),False,''))
        self.tv.expand_row((0,),False)
        self.tv.expand_row((1,),False)

if __name__=='__main__':
    window = gtk.Window()
    tree = TagFrame()
    vertical_box = gtk.VBox(False, 6)
    button_box = gtk.HButtonBox()
    insert = gtk.Button('Tag Images')
    description = gtk.Button('Untag Images')

    vertical_box.pack_start(tree)
    vertical_box.pack_start(button_box, False, False)
    button_box.pack_start(insert)
    button_box.pack_start(description)
    window.add(vertical_box)

#    insert.connect('clicked', insert_item)
#    description.connect('clicked', show_description)
    window.connect('destroy', lambda window: gtk.main_quit())

    window.resize(400, 500)
    window.show_all()

    gtk.main()
