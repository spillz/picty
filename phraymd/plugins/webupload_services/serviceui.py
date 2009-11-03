import os
import os.path
import threading

import gtk
import gobject

from phraymd import settings
from phraymd import pluginbase
from phraymd import imageinfo
from phraymd import imagemanip
from phraymd import io
from phraymd import collections
from phraymd import exif



MODEL_COL_PIXBUF=0
MODEL_COL_NAME=1
MODEL_COL_PROGRESS=2
MODEL_COL_STATE=3
MODEL_COL_ITEM=4
MODEL_COL_SIZE=5
MODEL_COL_STRIP=6
MODEL_COL_ALBUM=7
MODEL_COL_SERVICE=8  ##service gets columns 8 and higher of the model to assing service specific preferences (e.g. private/public images)


'''
How the plugin should work

Select service (picasa, flickr, facebook etc)
Login => Enter username and password (or pull from gnomekeyring)
Select Album from List of Existing or Create New One (or don't choose any album)
Option to use tags or not, strip metadata, resize images to a fixed size
Queue Photos
Hit Start => Images upload on a background thread
Queue can be edited during upload
Option to stop upload at any time
'''

def password_entry_dialog(self,title='Enter password',data_list=[('Username','',True),('Password','',False)]):
    dialog = gtk.Dialog(title,None,gtk.DIALOG_MODAL,
                     (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
    def add_entry(dialog,prompt,default,visible):
        prompt_label=gtk.Label()
        prompt_label.set_label(prompt)
        entry=gtk.Entry()
        entry.set_text(default)
        entry.set_visibility(visible)
        entry.set_property("activates-default",True)
        hbox=gtk.HBox()
        hbox.pack_start(prompt_label,False)
        hbox.pack_start(entry)
        dialog.vbox.pack_start(hbox)
        return entry
    entries=[add_entry(dialog,*d) for d in data_list]
    dialog.vbox.show_all()
    dialog.set_default_response(gtk.RESPONSE_ACCEPT)
    response=dialog.run()
    if response==gtk.RESPONSE_ACCEPT:
        ret_val=[entry.get_text() for entry in entries]
    else:
        ret_val=None
    dialog.destroy()
    return ret_val


class UploadServiceBase(object):
    name='BaseClass'
    def __init__(self,service_ui_owner):
        self.service_ui=service_ui_owner
        self.lock=threading.Lock()
        self.event=threading.Event()
        self.thread=threading.Thread(target=self._worker)
        self.request=None
        self.stop=False ##read only in thread -- check this in t_upload_photo to see if user wants to stop upload
        self.quit=False ##read only in thread -- program wants to shutdown check if this True in any of the t_* overrides and return immediately
        self.user_data=None
        self.thread.start()
    def set_request(self,request,data=tuple()):
        self.lock.acquire()
        self.request=request
        self.user_data=data
        if request:
            self.event.set()
        else:
            self.event.clear()
        self.lock.release()
    def stop(self):
        self.stop=True
    def clear_request(self):
        self.set_request(None,None)
    def shutdown(self):
        self.quit=True
        self.event.set()
    ## services should override the following methods
    def login_dialog():
        '''before t_login is called, you can prompt user on the main thread for username, password etc
        alternatively, use this to retrieve authentication info from a password store (e.g. gnome keyring)
        '''
        pass
    def get_pref_types(self):
        '''return a tuple of gobject type constants defining additional per image upload preferences (e.g. whether image is public or private)'''
        return tuple()
    def get_default_cols(self,item):
        return tuple()
    def update_prefs(self,selected_rows):
        '''the user has just changed the selection in the upload_queue, update preference widgets accordingly'''
        pass
    def t_login(self):
        '''service should connect to the users account using credentials from login_dialog'''
        pass
    def t_disconnect(self):
        '''user wants to logout, clear out the local credentials'''
        pass
    def t_upload_photo(self,item,album=None,preferences=None):
        '''upload item asynchronously. ideally provide frequent progress updates and watch out for stop signal'''
        pass
    def t_get_albums(self):
        '''retrieve the list of albums and call t_notify_albums when succesful'''
        pass
    ##do not override the following methods -- services should call to provide standard notifications to the ui
    def t_notify_login(self,success,message):
        gobject.idle_add(self.service_ui.cb_login,success,message)
    def t_notify_disconnect(self):
        gobject.idle_add(self.service_ui.cb_disconnect)
    def t_notify_albums(self,albums,message=None):
        gobject.idle_add(self.service_ui.cb_albums,albums,message)
    def t_notify_upload_progress(self,item,percent):
        gobject.idle_add(self.service_ui.cb_progress,item,percent)
    def t_notify_photo_uploaded(self,item,success,message):
        gobject.idle_add(self.service_ui.cb_uploaded,item,success,message)
    def _worker(self):
        while 1:
            if self.quit:
                return
            self.lock.acquire()
            if self.request:
                self.event.set()
            else:
                self.event.clear()
            self.lock.release()
            self.event.wait()
            self.lock.acquire()
            request=self.request
            user_data=self.user_data
            self.request=None
            self.user_data=None
            self.lock.release()
            ##todo: set lock here (main thread caller should check for lock)
            if self.quit:
                return
            if request=='login':
                self.t_login(*user_data)
            elif request=='upload':
                self.t_upload_photo(*user_data)
            elif request=='albums':
                self.t_get_albums(*user_data)
            elif request=='disconnect':
                self.t_disconnect(*user_data)


class UploadQueue(gtk.HBox):
    def __init__(self,worker,service_col_types,default_service_cols_cb):
        gtk.HBox.__init__(self)
        self.worker=worker
        self.default_service_cols_cb=default_service_cols_cb
        self.active_row=None
        self.active_item=None
        self.model=gtk.ListStore(gtk.gdk.Pixbuf,str,gobject.TYPE_DOUBLE,gobject.TYPE_INT,gobject.TYPE_PYOBJECT,str,gobject.TYPE_BOOLEAN,str,*service_col_types)
        self.upload_collection=collections.SimpleCollection()
        self.tv=gtk.TreeView(self.model)
        self.tv.set_reorderable(True)
        self.tv.set_headers_visible(False)
        self.tv.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        ##self.tv.connect("row-activated",self.tag_activate)
        tvc_bitmap=gtk.TreeViewColumn(None,gtk.CellRendererPixbuf(),pixbuf=MODEL_COL_PIXBUF)
        tvc_text=gtk.TreeViewColumn(None,gtk.CellRendererText(),markup=MODEL_COL_NAME)
        prog=gtk.CellRendererProgress()
        tvc_progress=gtk.TreeViewColumn(None,prog,value=MODEL_COL_PROGRESS)
        ##gtk.CellRendererText
        self.tv.append_column(tvc_bitmap)
        self.tv.append_column(tvc_text)
        self.tv.append_column(tvc_progress)

        target_list=self.tv.drag_dest_get_target_list()
        target_list=gtk.target_list_add_uri_targets(target_list,0)
        self.tv.enable_model_drag_dest(target_list,
                                    gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY)
#        self.tv.drag_dest_set(gtk.DEST_DEFAULT_ALL,
#                target_list,
#                gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        self.tv.connect("drag-data-received",self.drag_receive_signal)
        self.tv.add_events(gtk.gdk.BUTTON_MOTION_MASK)
        self.tv.connect("button-release-event",self.context_menu)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.add(self.tv)
        scrolled_window.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        self.pack_start(scrolled_window)

    def drag_receive_signal(self, widget, drag_context, x, y, selection_data, info, timestamp):
        drop_info = self.tv.get_dest_row_at_pos(x, y)
        if drop_info:
            drop_row,pos=drop_info
            drop_iter=self.model.get_iter(drop_row)
        else:
            drop_row=None
            drop_iter=None
            pos=None
        iter=None
        data=selection_data.data
        uris=selection_data.get_uris()
        if uris: ##todo: all of this should be done on the worker thread, with a notification to add items to the list when done
            for uri in uris:
                path=io.get_path_from_uri(uri)
                from phraymd import imageinfo
                item=imageinfo.Item(path,0)
                ind=self.upload_collection.find(item) #don't include items already in the list
                if ind>=0:
                    continue
                ind=self.worker.collection.find(item)
                if ind<0:
                    continue
                item=self.worker.collection(ind)
                if not item.thumb:
                    image_manip.load_thumb(item)
                thumb_pb=item.thumb
                if thumb_pb:
                    width,height=gtk.icon_size_lookup(gtk.ICON_SIZE_MENU)
                    width=width*3/2
                    height=height*3/2
                    tw=thumb_pb.get_width()
                    th=thumb_pb.get_height()
                    if width/height>tw/th:
                        height=width*th/tw
                    else:
                        width=height*tw/th
                    thumb_pb=thumb_pb.scale_simple(width*1.5,height*1.5,gtk.gdk.INTERP_BILINEAR)
                self.upload_collection.add(item)
                row=(thumb_pb,os.path.split(item.filename)[1],0.0,0,item,'',False,'')+self.default_service_cols_cb(item)
                if iter:
                    iter=self.model.insert_after(iter,row)
                elif not drop_row:
                    iter=self.model.append(row)
                    ref_first=gtk.TreeRowReference(self.model,self.model.get_path(iter))
                elif pos == gtk.TREE_VIEW_DROP_BEFORE:
                    iter=self.model.insert_before(drop_iter,row)
                    ref_first=gtk.TreeRowReference(self.model,self.model.get_path(iter))
                else:
                    iter=self.model.insert_after(drop_iter,row)
                    ref_first=gtk.TreeRowReference(self.model,self.model.get_path(iter))
            first_path=ref_first.get_path()
            last_path=self.model.get_path(iter)
            self.tv.get_selection().unselect_all()
            self.tv.get_selection().select_range(first_path,last_path)

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
            menu_add(menu,"_Remove From Queue",self.remove_selected_rows)
            if len(menu.get_children())>0:
                menu.popup(parent_menu_shell=None, parent_menu_item=None, func=None, button=1, activate_time=0, data=0)

    def remove_row(self,iter):
        item=self.model[iter][MODEL_COL_ITEM]
        if item==self.active_item:
            return False
        self.upload_collection.delete(item) #don't include items already in the list
        self.model.remove(iter)
        return True


    def remove_selected_rows(self,widget,event):
        store,row_list=self.tv.get_selection().get_selected_rows()
        refs=[gtk.TreeRowReference(store,r) for r in row_list]
        for r in refs:
            self.remove_row(store.get_iter(r.get_path()))

    def next_item(self):
        if self.active_row and self.active_row[MODEL_COL_STATE]==0:
            return self.active_row
        for row in self.model:
            if row[MODEL_COL_STATE]==0:
                self.active_row=row
                self.active_item=row[MODEL_COL_ITEM]
                return row
        self.active_row=None
        self.active_item=None
        return None

    def set_active_state(self,state,progress):
        if self.active_row:
            self.active_row[MODEL_COL_STATE]=state
            self.active_row[MODEL_COL_PROGRESS]=progress
            return True
        return False


class ServiceUI(gtk.VBox):
    '''
    Each web service uploader has a unique instance of the common user interface described by the ServiceUI
    The interface features generic image specific settings (title, tags, resize preferences etc), and
    an upload queue.
    The ServiceUI is responsible for instantiating a class derived from ServiceBase
    The ServiceBase derived class handles the site-specific implementation details and additional service
    specific options
    '''
    def __init__(self,mainframe,service_data):
        '''
        Instantiates a user interface frame for uploading to a particular web service
        mainframe - the main application frame
        service_class - the class derived from ServiceBase implementing the service specific details.
        '''
        gtk.VBox.__init__(self)
        def vbox_group(widgets):
            box=gtk.VBox()
            for w in widgets:
                box.pack_start(*w)
            return box
        def hbox_group(widgets):
            box=gtk.HBox()
            for w in widgets:
                box.pack_start(*w)
            return box

        self.service_pref_box=gtk.VBox() ##the service should add service specific image preferences to this box
        self.mainframe=mainframe
        self.pref_change_handlers=[]
        smod=__import__('phraymd.plugins.webupload_services.'+service_data[2],fromlist=[service_data[3]])
        self.service=getattr(smod,service_data[3])(self) ##todo: handle import errors in the plugin

        self.login_status=gtk.Label("Not connected") ##display "connected as <username>" once logged in
        self.login_button=gtk.Button("Login ...") ##display "change login" if connected already
        self.login_button.connect("clicked",self.cb_login_button)


        self.album_label=gtk.Label("Album")
        self.album_model=gtk.ListStore(str,gobject.TYPE_PYOBJECT)
        self.album_combo_entry=gtk.ComboBoxEntry(self.album_model,0)
        #self.album_combo_entry=gtk.ComboBox(self.album_model)

        self.use_tags_check=gtk.CheckButton("Upload tags")
        self.resize_label=gtk.Label("Resize to (max width x max height)")
        self.resize_entry=gtk.Entry()
        self.strip_metadata_check=gtk.CheckButton("Strip metadata")

        self.upload_queue=UploadQueue(mainframe.tm,self.service.get_pref_types(),self.get_default_service_cols)
        self.service_box=gtk.VBox()

        self.start_stop_button=gtk.Button("Start _Upload")
        self.start_stop_button.connect("clicked",self.cb_start_stop_button)
        self.empty_button=gtk.Button("_Empty Queue")
        self.empty_button.connect("clicked",self.cb_empty_button)
        self.clean_up_button=gtk.Button("_Clean Up")
        self.clean_up_button.connect("clicked",self.cb_clean_up_button)
        self.select_all_button=gtk.Button("Select _All")
        self.select_all_button.connect("clicked",self.cb_select_all_button)
        self.select_none_button=gtk.Button("Select _None")
        self.select_none_button.connect("clicked",self.cb_select_none_button)

        self.login_box=hbox_group([(self.login_status,False),(self.login_button,True,False)])
        self.pack_start(self.login_box,False)
        self.pack_start(self.upload_queue,True)
        self.pack_start(hbox_group([(self.start_stop_button,False),(self.empty_button,False),(self.clean_up_button,False),(self.select_all_button,False),(self.select_none_button,False)]),False)
        self.pref_box=vbox_group(
            (
            (hbox_group([(self.album_label,False),(self.album_combo_entry,True)]),False),
            (hbox_group([(self.resize_label,False),(self.resize_entry,False)]),False),
            (self.strip_metadata_check,False),
            (self.service_pref_box,False)
            )
            )
        self.pack_start(self.pref_box,False)

        self.upload_queue.tv.get_selection().connect("changed",self.selection_changed)
        self.pref_change_handlers.append((self.resize_entry,self.resize_entry.connect("changed",self.resize_entry_changed)))
        self.pref_change_handlers.append((self.strip_metadata_check,self.strip_metadata_check.connect("toggled",self.strip_metadata_check_toggled)))
        self.pref_change_handlers.append((self.album_combo_entry,self.album_combo_entry.child.connect("changed",self.album_combo_entry_changed)))

        self.pref_box.set_sensitive(False)

#        self.settings_box.set_sensitive(False)
#        self.service_box.set_sensitive(False)
        self.logged_in=False
        self.started=False
        self.start_stop_button.set_sensitive(False)

        self.show_all()

    def all_same(self,selected_rows,index):
        if len(selected_rows)==0:
            return None
        value=selected_rows[0][index]
        for r in selected_rows[1:]:
            if r[index]!=value:
                return None
        return value

    def selection_changed(self,selection):
        store,row_list=selection.get_selected_rows()
        selected_rows=[store[r] for r in row_list]
        if len(selected_rows)==0:
            self.pref_box.set_sensitive(False)
        else:
            self.pref_box.set_sensitive(True)
        self.update_prefs(selected_rows)

    def update_prefs(self,selected_rows):
        for o,h in self.pref_change_handlers:
            o.handler_block(h)
        val=self.all_same(selected_rows,MODEL_COL_ALBUM)
        if val!=None:
            self.album_combo_entry.child.set_text(val)
        else:
            self.album_combo_entry.set_text("")
        val=self.all_same(selected_rows,MODEL_COL_SIZE)
        if val!=None:
            self.resize_entry.set_text(val)
        else:
            self.resize_entry.set_text("")
        val=self.all_same(selected_rows,MODEL_COL_STRIP)
        if val!=None:
            self.strip_metadata_check.set_active(val)
            self.strip_metadata_check.set_inconsistent(False)
        else:
            self.strip_metadata_check.set_inconsistent(True)
        self.service.update_prefs(selected_rows)
        for o,h in self.pref_change_handlers:
            o.handler_unblock(h)

    def get_default_service_cols(self,item):
        return self.service.get_default_cols(item)

    def get_selected(self):
        store,row_list=self.upload_queue.tv.get_selection().get_selected_rows()
        return [store[r] for r in row_list]

    def album_combo_entry_changed(self,widget):
        selected_rows=self.get_selected()
        for r in selected_rows:
            r[MODEL_COL_ALBUM]=widget.get_text()

    def resize_entry_changed(self,widget):
        selected_rows=self.get_selected()
        for r in selected_rows:
            r[MODEL_COL_SIZE]=widget.get_text()

    def strip_metadata_check_toggled(self,widget):
        if widget.get_inconsistent():
            widget.set_inconsistent(False)
        selected_rows=self.get_selected()
        for r in selected_rows:
            r[MODEL_COL_STRIP]=widget.get_active()

    def cb_login_button(self,widget):
        if not self.logged_in:
            widget.set_sensitive(False)
            self.service.login_dialog()
            self.service.set_request('login')
        else:
            widget.set_sensitive(False)
            self.service.set_request('disconnect')

    def cb_empty_button(self,widget):
        model=self.upload_queue.model
        iter=model.get_iter_first()
        while iter:
            if self.upload_queue.active_row!=model[iter]:
                if not self.upload_queue.remove_row(iter):
                    return
            else:
                iter=model.iter_next(iter)

    def cb_clean_up_button(self,widget):
        model=self.upload_queue.model
        iter=model.get_iter_first()
        while iter:
            if model[iter][MODEL_COL_PROGRESS]>=100:
                if not self.upload_queue.remove_row(iter):
                    return
            else:
                iter=model.iter_next(iter)

    def cb_select_all_button(self,widget):
        sel=self.upload_queue.tv.get_selection()
        sel.select_all()

    def cb_select_none_button(self,widget):
        sel=self.upload_queue.tv.get_selection()
        sel.unselect_all()


    def cb_start_stop_button(self,widget):
        if not self.started:
            row=self.upload_queue.next_item()
            if row:
                prefs=list(row)
                iter=self.album_combo_entry.get_active_iter()
                if iter:
                    path=self.album_model.get_path(iter)
                    album=list(self.album_model[path])
                else:
                    album=['',None]
                self.started=True
                self.login_button.set_sensitive(False)
                widget.set_label("Stop _Upload")
                self.service.set_request('upload',(self.upload_queue.active_item,album,prefs))
        else:
            self.login_button.set_sensitive(False)
            widget.set_sensitive(False)
            widget.set_label("Stopping")
            self.service.set_request('stop')

    def cb_login(self,success,message):
        self.logged_in=True
        self.login_status.set_text(message)
        print 'login',success,message
        if success:
            self.login_button.set_sensitive(True)
            self.login_button.set_label("Disconnect")
            self.start_stop_button.set_sensitive(True)
            self.service.set_request('albums')
        else:
            ##todo: disable widgets
            self.login_button.set_label("Login...")
            self.start_stop_button.set_sensitive(False)
            self.service.set_request('disconnect')

    def cb_disconnect(self):
        self.album_model.clear()
        self.logged_in=False
        self.login_status.set_text('Not connected')
        self.login_button.set_sensitive(True)
        self.login_button.set_label("Login...")
        self.start_stop_button.set_sensitive(False)

    def cb_albums(self,albums,message):
        self.album_model.clear()
        for a in albums:
            self.album_model.append(a)

    def cb_progress(self,item,percent):
        if self.upload_queue.active_item!=item:
            return
        self.upload_queue.set_active_state(2,percent)

    def cb_uploaded(self,item,success,message):
        if self.upload_queue.active_item!=item:
            print 'invalid item',item,self.upload_queue.active_item
            return
        if success:
            self.upload_queue.set_active_state(1,100)
            if self.start_stop_button.get_property("sensitive"):
                row=self.upload_queue.next_item()
                if row!=None:
                    prefs=list(row)
                    iter=self.album_combo_entry.get_active_iter()
                    if iter:
                        path=self.album_model.get_path(iter)
                        album=list(self.album_model[path])
                    else:
                        album=['',None]
                    self.service.set_request('upload',(self.upload_queue.active_item,album,prefs))
                    return
        else:
            self.upload_queue.set_active_state(-1,0)
        self.start_stop_button.set_sensitive(True)
        self.login_button.set_sensitive(True)
        self.start_stop_button.set_label("Start _Upload")
        self.started=False

