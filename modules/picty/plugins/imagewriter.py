'''

    picty - Image Writer Plugin
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

import os.path

import gtk
import gobject
import Image
import tempfile

from picty import imagemanip
from picty import settings
from picty import pluginbase
from picty.uitools import dialogs
from picty import metadata
from picty import backend
from picty.fstools import io

class ImageWriteJob(backend.WorkerJob):
    def __init__(self,worker,collection,browser,plugin,item,src_path,dest_path):
        backend.WorkerJob.__init__(self,'IMAGEWRITE',950,worker,collection,browser)
        self.plugin=plugin
        self.item=item
        self.src_path=src_path
        self.dest_path=dest_path

    def __call__(self):
        try:
            if io.equal(self.dest_path,self.src_path):
                h,dpath=tempfile.mkstemp('.jpg')
            else:
                dpath = self.dest_path
            self.item.image.save(dpath)
        except:
            gobject.idle_add(self.plugin.image_write_failed)
            return True
        if not metadata.copy_metadata(self.item.meta,self.src_path,dpath):
            gobject.idle_add(self.plugin.image_write_meta_failed)
            return True
        if dpath!=self.dest_path:
            try:
                io.remove_file(self.dest_path)
                io.move_file(dpath,self.dest_path)
            except IOError:
                gobject.idle_add(self.plugin.image_write_meta_failed)
        gobject.idle_add(self.plugin.image_write_done)
        return True


class ImageWriterPlugin(pluginbase.Plugin):
    name='ImageWriter'
    display_name='Image Writer'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        self.writer_mode=False
    def plugin_init(self,mainframe,app_init):
        #register a button in the viewer to enter rotate mode
        self.viewer=mainframe.iv
        self.worker=mainframe.tm

        self.unrotated_screen_image=None
        self.cur_size=None
        self.cur_zoom=None

#        self.angle_adjust.connect("value-changed",self.rotate_adjust)
        self.filename_entry=gtk.Entry()
        self.browse_button=gtk.Button("_Browse...")
        self.ok_button=gtk.Button("_Save")
        self.cancel_button=gtk.Button("_Cancel")
        self.ok_button.connect("clicked",self.write_do_callback)
        self.cancel_button.connect("clicked",self.write_cancel_callback)

        self.write_bar=gtk.HBox()
        self.write_bar.pack_start(self.filename_entry)
        self.write_bar.pack_start(self.browse_button,False)
        self.write_bar.pack_start(self.cancel_button,False)
        self.write_bar.pack_start(self.ok_button,False)
        self.write_bar.show_all()
    def plugin_shutdown(self,app_shutdown=False):
        #deregister the button in the viewer
        if self.writer_mode:
            self.reset(app_shutdown)
    def reset(self,shutdown=False):
        self.writer_mode=False
        self.item=None
        self.viewer.image_box.remove(self.write_bar)
        self.viewer.plugin_release(self)
        if not shutdown:
            self.viewer.resize_and_refresh_view()
    def viewer_register_shortcut(self,shortcut_toolbar):
        '''
        called by the framework to register shortcut on mouse over commands
        append a tuple containing the shortcut commands
        '''
        shortcut_toolbar.register_tool_for_plugin(self,'Image Writer',self.writer_button_callback,shortcut_toolbar.cb_has_image,['picty-image-write'],'Write a copy of the image (original or edited, whichever is showing)',priority=30)
    def writer_button_callback(self,cmd):
        '''
        the user has entered rotate mode
        need to somehow set the viewer to a blocking mode to hand the plugin exclusive control of the viewer
        '''
        item=self.viewer.item
        if not self.viewer.plugin_request_control(self):
            return
        self.writer_mode=True
        self.filename_entry.set_text(self.viewer.collection.get_path(item))
        self.viewer.image_box.pack_start(self.write_bar,False)
        self.viewer.image_box.reorder_child(self.write_bar,0)
        self.item=item
    def write_do_callback(self,widget):
        dest_path=self.filename_entry.get_text()
        path,name=os.path.split(dest_path)
        src_path=self.viewer.collection.get_path(self.item)
        if not name:
            return
        if not path:
            path=self.viewer.collection.get_path(self.item)
            dest_path=os.path.join(os.path.split(path)[0],name)
        if os.path.exists(dest_path):
            if dialogs.prompt_dialog("File Exists","Do you want to overwrite\n"+dest_path+"?",("_Cancel","_Overwrite"),1)==0:
                return
        self.worker.queue_job_instance(ImageWriteJob(self.worker,self.viewer.collection,None,self,self.item,src_path,dest_path))
    def image_write_failed(self):
        dialogs.prompt_dialog("Save Failed","Could not save image\n"+dest_path,("_OK",),1)
    def image_write_meta_failed(self):
        dialogs.prompt_dialog("Metadata could not be written","Warning: Could not write metadata to image image\n"+dest_path,("_OK",),1)
    def image_write_done(self):
        self.reset()
    def write_cancel_callback(self,widget):
        self.reset(True)
    def viewer_release(self,force=False):
        self.reset(True)
        return True
