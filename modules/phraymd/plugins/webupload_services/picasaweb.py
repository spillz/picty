import os
import os.path
import threading

import gtk
import gobject

from phraymd import imagemanip
from serviceui import *


##Picasa web uploads use the gdata api
import gdata.photos.service
import gdata.media
import gdata.geo

MODEL_COL_PICASA_TITLE=MODEL_COL_SERVICE+0
MODEL_COL_PICASA_DESCRIPTION=MODEL_COL_SERVICE+1
MODEL_COL_PICASA_TAGS=MODEL_COL_SERVICE+2

class PicasaService(UploadServiceBase):
    name='Picasa Web Albums'
    def __init__(self,service_ui_owner):
        UploadServiceBase.__init__(self,service_ui_owner)
        def box_add(box,widget,label_text,signal,signal_cb):
            hbox=gtk.HBox()
            if label_text:
                label=gtk.Label(label_text)
                hbox.pack_start(label,False)
            hbox.pack_start(widget,True)
            self.service_ui.pref_change_handlers.append((widget,widget.connect(signal,signal_cb)))
            box.pack_start(hbox,False)
            return widget
        box=self.service_ui.service_pref_box
        self.title_entry=box_add(box,gtk.Entry(),"Title","changed",self.title_changed)
        self.description_entry=box_add(box,gtk.Entry(),"Description","changed",self.description_changed)
        self.tags_entry=box_add(box,gtk.Entry(),"Tags","changed",self.tags_changed)

    def get_default_cols(self,item):
        def catch(cb,item):
            try:
                return cb(item)
            except:
                return ''
        title=metadata.app_key_to_string('Title',catch(lambda item: item.meta['Title'],item))
        description=metadata.app_key_to_string('ImageDescription',catch(lambda item: item.meta['ImageDescription'],item))
        tags=metadata.app_key_to_string('Keywords',catch(lambda item: item.meta['Keywords'],item))
        return (title,description,tags,False)

    def title_changed(self,widget):
        selected_rows=self.service_ui.get_selected()
        for r in selected_rows:
            r[MODEL_COL_PICASA_TITLE]=widget.get_text()

    def description_changed(self,widget):
        selected_rows=self.service_ui.get_selected()
        for r in selected_rows:
            r[MODEL_COL_PICASA_DESCRIPTION]=widget.get_text()

    def tags_changed(self,widget):
        print 'tags changed',widget.get_text()
        selected_rows=self.service_ui.get_selected()
        for r in selected_rows:
            r[MODEL_COL_PICASA_TAGS]=widget.get_text()

#    def private_changed(self,widget):
#        if widget.get_inconsistent():
#            widget.set_inconsistent(False)
#        selected_rows=self.service_ui.get_selected()
#        for r in selected_rows:
#            r[MODEL_COL_PICASA_PRIVATE]=widget.get_active()

    def login_dialog(self):
        self.password_data=password_entry_dialog(self,title='Enter Your Picasa Credentials',data_list=[('Username (E-mail)','',True),('Password','',False)])

    def get_pref_types(self):
        '''return a tuple of gobject type constants defining additional per image upload preferences (e.g. whether image is public or private)'''
        return (str,str,str,gobject.TYPE_BOOLEAN)

    def update_prefs(self,selected_rows):
        '''the user has just changed the selection in the upload_queue, update preference widgets accordingly'''
        val=self.service_ui.all_same(selected_rows,MODEL_COL_PICASA_TITLE)
        if val!=None:
            self.title_entry.set_text(val)
        else:
            self.title_entry.set_text("")
        val=self.service_ui.all_same(selected_rows,MODEL_COL_PICASA_DESCRIPTION)
        if val!=None:
            self.description_entry.set_text(val)
        else:
            self.description_entry.set_text("")
        val=self.service_ui.all_same(selected_rows,MODEL_COL_PICASA_TAGS)
        if val!=None:
            self.tags_entry.set_text(val)
        else:
            self.tags_entry.set_text("")
#        val=self.service_ui.all_same(selected_rows,MODEL_COL_PICASA_PRIVATE)
#        if val!=None:
#            self.private_check.set_active(val)
#        else:
#            self.private_check.set_inconsistent(True)

    def t_login(self):
        if self.password_data==None:
            self.t_notify_login(False,'Not Connected')
            return
        self.gd_c=gdata.photos.service.PhotosService()
        self.gd_c.email=self.password_data[0]
        self.gd_c.password=self.password_data[1]
        self.gd_c.source='phraymd-'+settings.version
        try:
            result=self.gd_c.ProgrammaticLogin()
            print 'Picasa login returned',result
            self.t_notify_login(True,'Logged in as %s'%(self.password_data[0],))
        except:
            import traceback, sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print 'Error on login',tb_text
            self.t_notify_login(False,'Login as %s unsuccessful'%(self.password_data[0],))

    def t_disconnect(self):
        del self.gd_c
        self.password_data=None
        self.t_notify_disconnect()

    def t_upload_photo(self,item,album=None,preferences=None):
        try:
            if album[0]=='':
                album_url = '/data/feed/api/user/%s/albumid/%s' % (self.gd_c.email, 'default')
            else:
                album_url = '/data/feed/api/user/%s/albumid/%s' % (self.gd_c.email, album[1].gphoto_id.text) ##
            self.t_notify_upload_progress(item,50)

            filename=imagemanip.get_jpeg_or_png_image_file(item,preferences[MODEL_COL_SIZE],preferences[MODEL_COL_STRIP])

            if not filename:
                return self.t_notify_photo_uploaded(item,False,'Invalid Image Type')

            photo = gdata.photos.PhotoEntry()
            #photo.summary = 'uploaded with phraymd'

            import atom
            photo.title=atom.Title()
            if preferences[MODEL_COL_PICASA_TITLE]:
                title=preferences[MODEL_COL_PICASA_TITLE]
            else:
                title=os.path.split(item.filename)[1]
            photo.title.text = title
            photo.media = gdata.media.Group()
            keywords=metadata.tag_bind(metadata.tag_split(preferences[MODEL_COL_PICASA_TAGS]),',')
            if keywords:
                photo.media.keywords = gdata.media.Keywords(text=keywords)
            description=preferences[MODEL_COL_PICASA_DESCRIPTION]
            if description:
                photo.media.description = gdata.media.Description(text=description)
            #photo.media.credit = gdata.media.Credit(text=preferences[MODEL_COL_PICASA_AUTHOR])
            photo=self.gd_c.InsertPhoto(album_url, photo, filename, io.get_mime_type(filename))
            if filename!=item.filename:
                os.remove(filename)

            self.t_notify_photo_uploaded(item,True,'Successful upload')
        except:
            import traceback, sys
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print 'Error on upload',tb_text
            self.t_notify_photo_uploaded(item,False,'Upload Failed')

    def t_get_albums(self):
        albums=self.gd_c.GetUserFeed()
        alist=[(a.title.text,a) for a in albums.entry]
        self.t_notify_albums(alist,'')
