import os
import os.path
import threading

import gtk
import gobject

from phraymd import imagemanip
from serviceui import *


##Flickr web uploads use the gdata api
import flickrapi

MODEL_COL_FLICKR_TITLE=MODEL_COL_SERVICE+0
MODEL_COL_FLICKR_DESCRIPTION=MODEL_COL_SERVICE+1
MODEL_COL_FLICKR_TAGS=MODEL_COL_SERVICE+2
MODEL_COL_FLICKR_PRIVACY=MODEL_COL_SERVICE+3

privacy_levels=[
'PUBLIC',
'FRIENDS AND FAMILY',
'FRIENDS',
'FAMILY',
'PRIVATE'
]

PRIVACY_PUBLIC=0
PRIVACY_FRIENDS_AND_FAMILY=1
PRIVACY_FRIENDS=2
PRIVACY_FAMILY=3
PRIVACY_PRIVATE=4


class FlickrService(UploadServiceBase):
    name='Flickr Web Albums'
    api_key = 'c0ec5403179a50fbbff9f3f65b664b29'
    api_secret = 'd5340e24789b7fd9'
    def __init__(self,service_ui_owner):
        UploadServiceBase.__init__(self,service_ui_owner)
        def box_add(box,widget,label_text,signal,signal_cb):
            hbox=gtk.HBox()
            if label_text:
                label=gtk.Label(label_text)
                hbox.pack_start(label,False)
            entry=gtk.Entry()
            hbox.pack_start(widget,True)
            self.service_ui.pref_change_handlers.append((widget,widget.connect(signal,signal_cb)))
            box.pack_start(hbox,False)
            return widget
        box=self.service_ui.service_pref_box
        self.title_entry=box_add(box,gtk.Entry(),"Title","changed",self.title_changed)
        self.description_entry=box_add(box,gtk.Entry(),"Description","changed",self.description_changed)
        self.tags_entry=box_add(box,gtk.Entry(),"Tags","changed",self.tags_changed)
        self.private_combo=box_add(box,gtk.combo_box_new_text(),"Privacy","changed",self.private_changed)
        for l in privacy_levels:
            self.private_combo.append_text(l)
        ##todo: login belongs elsewhere
        self.flickr_client = flickrapi.FlickrAPI(self.api_key, self.api_secret)
        try:
            (self.token, self.frob) = self.flickr_client.get_token_part_one('write',lambda perms,data:None)
            if self.token:
                print 'logged in'
                self.flickr_client.get_token_part_two((self.token, self.frob))
                login_resp=self.flickr_client.test_login()
                user=login_resp.find('user')
                self.username=user.find('username').text
                self.id=user.attrib['id']
                print 'login result',self.username,self.id
                self.t_notify_login(True,'Logged in as %s'%(self.username,))
        except flickrapi.FlickrError:
            pass

    def get_pref_types(self):
        '''return a tuple of gobject type constants defining additional per image upload preferences (e.g. whether image is public or private)'''
        return (str,str,str,gobject.TYPE_INT)

    def get_default_cols(self,item):
        '''set the default service specific preferences for each image that gets dragged to the upload queue'''
        def catch(cb,item):
            try:
                return cb(item)
            except:
                return ''
        title=exif.app_key_to_string('Title',catch(lambda item: item.meta['Title'],item))
        description=exif.app_key_to_string('ImageDescription',catch(lambda item: item.meta['ImageDescription'],item))
        tags=exif.app_key_to_string('Keywords',catch(lambda item: item.meta['Keywords'],item))
        private=0
        return (title,description,tags,private)

    def title_changed(self,widget):
        selected_rows=self.service_ui.get_selected()
        for r in selected_rows:
            r[MODEL_COL_FLICKR_TITLE]=widget.get_text()

    def description_changed(self,widget):
        selected_rows=self.service_ui.get_selected()
        for r in selected_rows:
            r[MODEL_COL_FLICKR_DESCRIPTION]=widget.get_text()

    def tags_changed(self,widget):
        selected_rows=self.service_ui.get_selected()
        for r in selected_rows:
            r[MODEL_COL_FLICKR_TAGS]=widget.get_text()

    def private_changed(self,widget):
        selected_rows=self.service_ui.get_selected()
        for r in selected_rows:
            r[MODEL_COL_FLICKR_PRIVACY]=widget.get_active()

    def update_prefs(self,selected_rows):
        '''the user has just changed the selection in the upload_queue, update preference widgets accordingly'''
        val=self.service_ui.all_same(selected_rows,MODEL_COL_FLICKR_TITLE)
        if val!=None:
            self.title_entry.set_text(val)
        else:
            self.title_entry.set_text("")
        val=self.service_ui.all_same(selected_rows,MODEL_COL_FLICKR_DESCRIPTION)
        if val!=None:
            self.description_entry.set_text(val)
        else:
            self.description_entry.set_text("")
        val=self.service_ui.all_same(selected_rows,MODEL_COL_FLICKR_TAGS)
        if val!=None:
            self.tags_entry.set_text(val)
        else:
            self.tags_entry.set_text("")
        val=self.service_ui.all_same(selected_rows,MODEL_COL_FLICKR_PRIVACY)
        if val!=None:
            self.private_combo.set_active(val)
        else:
            self.private_combo.set_active(-1)


    def login_dialog(self):
        self.flickr_client = flickrapi.FlickrAPI(self.api_key, self.api_secret)
        (self.token, self.frob) = self.flickr_client.get_token_part_one(perms='write')
        if not self.token:
            from phraymd import metadatadialogs
            result=metadatadialogs.prompt_dialog('Allow Flickr Access','phraymd has opened a Flickr application authentication page in your web browser. Please give phraymd access to your flickr account accepting the prompt in your web browser. Press "Done" when complete',buttons=('_Done',),default=0)

    def t_login(self):
        try:
            self.flickr_client.get_token_part_two((self.token, self.frob))
            login_resp=self.flickr_client.test_login()
            user=login_resp.find('user')
            self.username=user.find('username').text
            self.id=user.attrib['id']
            print 'login result',self.username,self.id
            self.t_notify_login(True,'Logged in as %s'%(self.username,))
        except flickrapi.FlickrError:
            self.t_notify_login(False,'Login failed')

    def t_disconnect(self):
        print 'disconnecting from flickr'
        del self.flickr_client
        self.token=None
        self.frob=None
        self.t_notify_disconnect()

    def t_upload_photo(self,item,album=None,preferences=None):
        try:

            filename=imagemanip.get_jpeg_or_png_image_file(item,preferences[MODEL_COL_SIZE],preferences[MODEL_COL_STRIP])

            if not filename:
                return self.t_notify_photo_uploaded(item,False,'Invalid Image Type')


            title=preferences[MODEL_COL_FLICKR_TITLE]
            if not title:
                title=os.path.split(item.filename)[1]
            tags=preferences[MODEL_COL_FLICKR_TAGS]
            description=preferences[MODEL_COL_FLICKR_DESCRIPTION]
            privacy=preferences[MODEL_COL_FLICKR_PRIVACY]
            public=True if privacy==PRIVACY_PUBLIC else False
            family=True if privacy in [PRIVACY_FRIENDS,PRIVACY_FRIENDS_AND_FAMILY] else False
            friends=True if privacy in [PRIVACY_FAMILY,PRIVACY_FRIENDS_AND_FAMILY] else False

            def progress_cb(progress,done):
                print 'progress notify',progress,done
                self.t_notify_upload_progress(item,progress)
            photo_id=self.flickr_client.upload(filename=filename,title=title,description=description,tags=tags,
                is_public=public,is_family=family,is_friend=friends,callback=progress_cb)
            photo_id=photo_id.find('photoid').text

            if album:
                photoset_id=album[1].attrib['id']
                self.flickr_client.photosets_addPhoto(photoset_id=photoset_id,photo_id=photo_id)

            if filename!=item.filename:
                os.remove(filename)

            self.t_notify_photo_uploaded(item,True,'Successful upload')
        except:
            import traceback, sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print 'Error on upload',tb_text
            self.t_notify_photo_uploaded(item,False,'Upload Failed')

    def t_get_albums(self):
        try:
            response=self.flickr_client.photosets_getList()
            photosets=response.find('photosets')
            sets=photosets.findall('photoset')
            alist=[(s.find('title').text,s) for s in sets]
            print alist
            self.t_notify_albums(alist,'')
        except flickrapi.FlickrError:
            self.t_notify_albums([],'')
