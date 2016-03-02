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
from PIL import Image
import tempfile

from picty import imagemanip
from picty import settings
from picty import pluginbase
from picty.uitools import dialogs, widget_builder as wb
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
                ext = io.get_ext(self.dest_path)
                if ext:
                    ext = '.'+ext
                h,dpath = tempfile.mkstemp(ext)
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

class ImageExportJob(backend.WorkerJob):
    def __init__(self, worker, collection, browser, plugin, items, dest_path, max_size):
        backend.WorkerJob.__init__(self,'IMAGEEXPORT',950,worker,collection,browser)
        self.plugin=plugin
        self.items=items
        self.dest_path=dest_path
        self.i = 0
        self.max_size = max_size

    def __call__(self):
        while self.i < len(self.items):
            size=None
            item = self.items[i]
            if self.max_size:
                size=(self.max_size,self.max_size)
            path = imagemanip.get_jpeg_or_png_image_file(item,self.collection,size,False,True) #keep metadata, apply image edits
            if path is None:
                continue
            dest_path = os.path.join(self.dest_path,os.path.split(path)[1])
            if os.path.exists(dest_path):
                #rename it
                pass
            if path != self.collection.get_path(item):
                io.move_file(path, dest_path)
            else:
                io.copy_file(path, dest_path)
            ##TODO: SEND AN UPDATE MESSAGE
            if not self.ishighestpriority():
                return False

        ##FIXME: NEED TO CHECK END OF LOOP LOGIC
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

    def browser_popup_menu(self,context_menu,item,selection):
        '''
        add menu items to the browser right click context menu
        `context_menu` is an instance of context_menu.ContextMenu, which has a simple interface for adding menu items
        `item` is the selected item
        `selection` is True if a multiple items have been selected, otherwise False
        '''
        if selection:
            context_menu.add("Export as...",self.export_selected_dlg, args = (item, selection))

    def export_selected_dlg(self, menuitem, item, selection):
        button_list = ("_Cancel",0, "_Export",1)
        title = "Export Selected Images"
        dialog = gtk.Dialog(title,None,gtk.DIALOG_MODAL,button_list)
        default_path = ''
        label = None
        browse_prompt = 'Select the destination folder'
        vb = wb.PaddedVBox()
        with vb:
            with wb.LabeledWidgets(pack_args = 'lw'):
                wb.Pack(dialogs.PathnameEntry(default_path,label,browse_prompt), 'destination', 'Destination Folder:')
                wb.Entry('1024', pack_args = ('max_side', 'Maximum Length (pixels)'))
        vb.show_all()
        dialog.vbox.pack_start(vb)
        dialog.set_default_response(1)
        dialog.set_response_sensitive(1,False)
        vb['lw']['destination'].path_entry.connect('changed', lambda *args: dialog.set_response_sensitive(1,os.path.exists(vb['lw']['destination'].get_path())))
        result = dialog.run()
        fd = vb['lw'].get_form_data()
        dialog.destroy()
        if result == 1:
            self.run_as_job(self.export_task, self.export_complete, 900, True, fd['destination'], int(fd['max_side']))

    def export_task(self, job, item, complete_cb, destination, max_size):
        size=None
        if not item.selected:
            return
        if max_size:
            size=(max_size,max_size)
        path = imagemanip.get_jpeg_or_png_image_file(item,self.collection,size,False,True) #keep metadata, apply image edits
        if path is None:
            return
        dest_path = os.path.join(destination,os.path.split(path)[1])
        if os.path.exists(dest_path):
            #rename it
            pass
        if path != self.collection.get_path(item):
            io.move_file(path, dest_path)
        else:
            io.copy_file(path, dest_path)

    def export_complete(self, *args):
        print args
        pass
