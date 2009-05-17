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


## provides gui elements for working with tags
## 1. tree interface for choosing tags to "paint" onto  images
## 2. tag selector dialog
## 3. tag auto-completer
## tag collection object (keeps track of available tags and counts)

class TagModel(gtk.TreeStore):
    def __init__(self,*args):
        gtk.TreeStore.__init__(self,*args)
    def row_draggable(self, path):
        print 'tag model'
        return self[path][0]!=''
#    def drag_data_delete(self, path):
#        return False
#    def drag_data_get(self, path, selection_data):
#        return False

class TagFrame(gtk.VBox):
    def __init__(self,worker,browser,user_tag_info):
        gtk.VBox.__init__(self)
        self.user_tags={}
        self.worker=worker
        self.browser=browser
        self.model=gtk.TreeStore(str,gtk.gdk.Pixbuf,str,'gboolean',str)
        self.tv=gtk.TreeView(self.model)
#        self.tv.set_reorderable(True)
        self.tv.set_headers_visible(False)
        self.tv.connect("row-activated",self.tag_activate)
        tvc_bitmap=gtk.TreeViewColumn(None,gtk.CellRendererPixbuf(),pixbuf=1)
        tvc_text=gtk.TreeViewColumn(None,gtk.CellRendererText(),text=2)
        toggle=gtk.CellRendererToggle()
        toggle.set_property("activatable",True)
        toggle.connect("toggled",self.toggle_signal)
        tvc_check=gtk.TreeViewColumn(None,toggle,active=3)
        ##gtk.CellRendererText
        self.tv.append_column(tvc_check)
        self.tv.append_column(tvc_bitmap)
        self.tv.append_column(tvc_text)
        self.tv.enable_model_drag_dest([('tag-tree-row', gtk.TARGET_SAME_WIDGET, 0),
                                    ('image-filename', gtk.TARGET_SAME_APP, 1)],
                                    gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE)
        self.tv.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
                  [('tag-tree-row', gtk.TARGET_SAME_WIDGET, 0)],
                  gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE)
        self.tv.connect("drag-data-received",self.drag_receive_signal)
        self.tv.connect("drag-data-get",self.drag_get_signal)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.add_with_viewport(self.tv)
        scrolled_window.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        self.pack_start(scrolled_window)

        button_box = gtk.HButtonBox()
        tag_mode_button= gtk.ToggleButton('Tag _Mode')
        tag_mode_button.connect("toggled",self.tag_model_toggle_signal)
        tag_mode_button.set_tooltip_text('When  this button is depressed, clicking on images in the browser adds the checked tags above, CTRL+click removes the tags')
        button_box.pack_start(tag_mode_button)
        button_box.show_all()
        self.pack_start(button_box,False)


        self.model.append(None,('',None,'Favorites',False,''))
        self.model.append(None,('',None,'Other',False,''))
        print 'TESTING',self.model.row_draggable((0,))
        self.set_user_tags(user_tag_info)

    def tag_model_toggle_signal(self, button):
        if button.get_active():
            self.browser.mode=self.browser.MODE_TAG
        else:
            self.browser.mode=self.browser.MODE_NORMAL
        self.browser.imarea.grab_focus()

    def iter_all_children(self,iter_node):
        '''iterate all rows from iter_node and their children'''
        while iter_node:
            yield self.model[iter_node]
            for r in self.iter_all_children(self.model.iter_children(iter_node)):
                yield r
            iter_node=self.model.iter_next(iter_node)

    def iter_all(self):
        '''iterate over entire tree'''
        for x in self.iter_all_children(self.model.get_iter_root()):
            yield x

    def get_checked_tags(self):
        return [it[0] for it in self.iter_all() if it[0]!='' and it[3]]

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
                    row=list(self.model[it])
                    print 'drop row',drop_row
                    if self.model[drop_row][0]=='':
                        new_it=self.model.append(drop_iter,row)
                    else:
                        new_it=self.model.insert_before(None,drop_iter,row)
                    new_path=self.model.get_path(new_it)
                    self.model.remove(it)
                    if self.model.get_path(it)[0]==0:
                        del self.user_tags[row[0]]
                    if new_path[0]==0:
                        self.user_tags[row[0]]=gtk.TreeRowReference(self.model,new_path)
            elif selection_data.type=='image-filename':
                pass

    def drag_get_signal(self, widget, drag_context, selection_data, info, timestamp):
        treeselection = self.tv.get_selection()
        model, paths = treeselection.get_selected_rows()
        strings=[]
        for p in paths:
            if self.model[p][0]!='':
                strings.append(self.model.get_string_from_iter(self.model.get_iter(p)))
        if len(strings)==0:
            return False
        selection_data.set('tag-tree-row', 8, '-'.join(strings))
        print 'get',selection_data,'value',paths

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
        self.model.insert(None,0,('',None,'Favorites',False,''))
        print 'setting up tag frame',usertaginfo
        for row in usertaginfo:
            print 'row',row
            path=row[0]
            parent=self.model.get_iter(path[0:len(path)-1])
            self.model.append(parent,[row[1],None,row[2],False,row[3]])
            self.user_tags[row[1]]=gtk.TreeRowReference(self.model,path)
        self.load_user_bitmaps(usertaginfo)

    def get_user_tags_rec(self,usertaginfo, iter):
        '''from a given node iter, recursively appends rows to usertaginfo'''
        while iter:
            row=list(self.model[iter])
            row.pop(1)
            row.pop(2)
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
                if row[4]!='':
                    try:
                        row[2]=gtk.gdk.pixbuf_new_from_file(row[4])
                    except:
                        pass

    def set_and_save_user_bitmap(self,tree_path,pixbuf):
        self.model[tree_path][2]=pixbuf
        png_path=os.path.join(os.environ['HOME'],'.phraymd/tag_png')
        if not os.path.exists(png_path):
            os.makedirs(png_path)
        if not os.path.isdir(png_path):
            return False
        fullname=os.path.join(png_path,self.model[tree_path][2])
        self.model[tree_path][4]=fullname
        pixbuf.save(fullname,'png')

    def tag_activate(self,treeview, path, view_column):
        if self.model[path][0]:
            self.browser.filter_entry.set_text('view:tag="%s"'%self.model[path][0])
            self.browser.filter_entry.activate()

    def toggle_signal(self,cellrenderertoggle, path):
        self.model[path][3]=not self.model[path][3]

    def refresh(self,tag_cloud):
        path=self.model.get_iter((1,))
        self.model.remove(path)
        self.model.append(None,('',None,'Other',False,''))
        for k in self.user_tags:
            path=self.user_tags[k].get_path()
            if path:
                self.model[path][2]=k+' (0)'
        for k in tag_cloud.tags:
            if k in self.user_tags:
                path=self.user_tags[k].get_path()
                if path:
                    self.model[path][2]=k+' (%i)'%(tag_cloud.tags[k])
            else:
                path=self.model.get_iter((1,))
                self.model.append(path,(k,None,k+' (%i)'%(tag_cloud.tags[k],),False,''))
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
