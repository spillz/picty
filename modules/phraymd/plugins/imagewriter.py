'''

    phraymd - Image Writer Plugin
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

import os.path

import gtk
import Image

from phraymd import imagemanip
from phraymd import settings
from phraymd import pluginbase
from phraymd import metadatadialogs
from phraymd import metadata

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
            self.viewer.refresh_view()
    def viewer_register_shortcut(self,shortcut_commands):
        '''
        called by the framework to register shortcut on mouse over commands
        append a tuple containing the shortcut commands
        '''
        shortcut_commands.register_tool_for_plugin(self,'Image Writer',self.writer_button_callback,shortcut_commands.default_active_callback,'phraymd-image-write','Write a copy of the image including any edits',priority=30)
    def writer_button_callback(self,cmd,item):
        #the user has entered rotate mode
        #need to somehow set the viewer to a blocking mode to hand the plugin exclusive control of the viewer
        if not self.viewer.plugin_request_control(self):
            return
        self.writer_mode=True
        self.filename_entry.set_text(item.filename)
        self.viewer.image_box.pack_start(self.write_bar,False)
        self.viewer.image_box.reorder_child(self.write_bar,0)
        self.item=item
    def write_do_callback(self,widget):
        filename=self.filename_entry.get_text()
        path,name=os.path.split(filename)
        if not name:
            return
        if not path:
            filename=os.path.join(os.path.split(item.filename)[0],name)
        if os.path.exists(filename):
            if metadatadialogs.prompt_dialog("File Exists","Do you want to overwrite\n"+filename+"?",("_Cancel","_Overwrite"),1)==0:
                return
        try:
            self.item.image.save(filename)
        except:
            metadatadialogs.prompt_dialog("Save Failed","Could not save image\n"+filename,("_OK",),1)
            return
        if not metadata.copy_metadata(self.item,filename):
            metadatadialogs.prompt_dialog("Save Failed","Warning: Could not write metadata to image image\n"+filename,("_OK",),1)
        self.reset()
    def write_cancel_callback(self,widget):
        self.reset(True)
    def viewer_release(self,force=False):
        self.reset(True)
        return True
