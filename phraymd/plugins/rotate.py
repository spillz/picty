'''

    phraymd - Image Rotation Plugin
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
import Image

from phraymd import imagemanip
from phraymd import settings
from phraymd import pluginbase

class RotatePlugin(pluginbase.Plugin):
    name='Rotate'
    display_name='Image Rotation'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        self.rotate_mode=False
    def plugin_init(self,mainframe,app_init):
        #register a button in the viewer to enter rotate mode
        self.viewer=mainframe.iv

        self.unrotated_screen_image=None
        self.cur_size=None
        self.cur_zoom=None

        self.angle_adjust=gtk.Adjustment(0,-180,180,0.01,0.1,0.1)
        self.angle_adjust.connect("value-changed",self.rotate_adjust)
        self.slider=gtk.HScale(self.angle_adjust)
        self.slider.set_draw_value(False)
        self.angle_entry=gtk.SpinButton(self.angle_adjust,0.0,2)
        self.ok_button=gtk.Button("_Rotate")
        self.ok_button.connect("clicked",self.rotate_do_callback)
        self.cancel_button=gtk.Button("_Cancel")
        self.cancel_button.connect("clicked",self.rotate_cancel_callback)

        self.rotate_bar=gtk.HBox()
        self.rotate_bar.pack_start(self.slider)
        self.rotate_bar.pack_start(self.angle_entry,False)
        self.rotate_bar.pack_start(self.cancel_button,False)
        self.rotate_bar.pack_start(self.ok_button,False)
        self.rotate_bar.show_all()
    def plugin_shutdown(self,app_shutdown=False):
        #deregister the button in the viewer
        if self.rotate_mode:
            self.reset(app_shutdown)
    def viewer_register_shortcut(self,mainframe,shortcut_commands):
        '''
        called by the framework to register shortcut on mouse over commands
        append a tuple containing the shortcut commands
        '''
        def show_on_hover(item,hover):
            return True
        shortcut_commands.append(
            ('Rotate',self.rotate_button_callback,show_on_hover,False,mainframe.render_icon('phraymd-image-rotate', gtk.ICON_SIZE_LARGE_TOOLBAR),'Main')
            )
    def rotate_button_callback(self,viewer,item):
        #the user has entered rotate mode
        #need to somehow set the viewer to a blocking mode to hand the plugin exclusive control of the viewer
        if not self.viewer.plugin_request_control(self):
            return
        self.rotate_mode=True
        self.viewer.image_box.pack_start(self.rotate_bar,False)
        self.item=item
    def rotate_do_callback(self,widget):
        self.item.image=self.item.image.rotate(-self.angle_adjust.get_value(),Image.ANTIALIAS,True)
        self.reset()
    def rotate_cancel_callback(self,widget):
        if self.rotate_mode:
            self.reset()
    def reset(self,shutdown=False):
        self.rotate_mode=False
        self.item=None
        self.viewer.image_box.remove(self.rotate_bar)
        self.viewer.plugin_release(self)
        if not shutdown:
            self.viewer.refresh_view()
    def rotate_adjust(self,adjustment):
        if not self.rotate_mode:
            return
        self.viewer.refresh_view()
    def viewer_release(self,force=False):
        self.reset(True)
        return True
    def t_viewer_sizing(self,size,zoom,item):
        if not self.rotate_mode:
            return
        if size!=self.cur_size or not self.unrotated_screen_image:
            self.unrotated_screen_image=item.image.copy()
            self.unrotated_screen_image.thumbnail(size)
        if self.angle_adjust.get_value()!=0.0:
            print 'CALCULATING ROTATION ',self.angle_adjust.get_value()
            image=self.unrotated_screen_image.rotate(-self.angle_adjust.get_value(),Image.NEAREST,expand=True)
            image.thumbnail(size)
            item.qview=imagemanip.image_to_pixbuf(image)
        self.cur_size=size
        self.cur_zoom=zoom
        return True
