'''

    picty - Image Rotation Plugin
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

import gtk
from PIL import Image

from picty import imagemanip
from picty import settings
from picty import pluginbase

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

        self.angle_adjustment=gtk.Adjustment(0,-180,180,0.01,0.1,0.1)
        self.angle_adjustment.connect("value-changed",self.rotate_adjust)
        self.slider=gtk.HScale(self.angle_adjustment)
        self.slider.set_draw_value(False)
        self.angle_entry=gtk.SpinButton(self.angle_adjustment,0.0,2)
        self.ok_button=gtk.Button("_Apply")
        self.ok_button.connect("clicked",self.rotate_do_callback)
        self.cancel_button=gtk.Button("_Cancel")
        self.cancel_button.connect("clicked",self.rotate_cancel_callback)

        self.rotate_bar=gtk.HBox()
        self.rotate_bar.pack_start(self.slider)
        self.rotate_bar.pack_start(self.angle_entry,False)
        self.rotate_bar.pack_start(self.cancel_button,False)
        self.rotate_bar.pack_start(self.ok_button,False)
        self.rotate_bar.show_all()
        imagemanip.transformer.register_transform('rotate',self.do_rotate_transform)

    def plugin_shutdown(self,app_shutdown=False):
        #deregister the button in the viewer
        if self.rotate_mode:
            self.reset(app_shutdown)
        imagemanip.transformer.deregister_transform('rotate')

    def do_rotate_transform(self,item,params):
        item.image=item.image.rotate(params['angle'],Image.BILINEAR,True)

    def viewer_register_shortcut(self,shortcut_toolbar):
        '''
        called by the framework to register shortcut on mouse over commands
        append a tuple containing the shortcut commands
        '''
        shortcut_toolbar.register_tool_for_plugin(self,'Rotate',self.rotate_button_callback,shortcut_toolbar.cb_showing_tranforms,['picty-image-rotate'],'Rotate or straighten this image',43)

    def rotate_button_callback(self,cmd):
        '''
        the user has entered rotate mode
        set the viewer to a blocking mode to hand the plugin exclusive control of the viewer
        '''
        item=self.viewer.item
        if not self.viewer.plugin_request_control(self):
            return
        self.rotate_mode=True
        self.viewer.image_box.pack_start(self.rotate_bar,False)
        self.viewer.image_box.reorder_child(self.rotate_bar,0)
        self.item=item

    def rotate_do_callback(self,widget):
        self.viewer.il.add_transform('rotate',{'angle':-self.angle_adjustment.get_value()})
        #self.viewer.il.transform_image()
        self.reset()

    def rotate_cancel_callback(self,widget):
        if self.rotate_mode:
            self.reset()

    def reset(self,shutdown=False):
        self.rotate_mode=False
        self.item=None
        self.unrotated_screen_image=None
        self.viewer.image_box.remove(self.rotate_bar)
        self.viewer.plugin_release(self)
        self.angle_adjustment.set_value(0)
        if not shutdown:
            self.viewer.resize_and_refresh_view()

    def rotate_adjust(self,adjustment):
        if not self.rotate_mode:
            return
        self.viewer.resize_and_refresh_view(force=True)

    def viewer_release(self,force=False):
        self.reset(True)
        return True

    def t_viewer_sizing(self,size,zoom,item):
        if not self.rotate_mode:
            return
        if size!=self.cur_size or not self.unrotated_screen_image or self.viewer.zoom_level!='fit':
            self.unrotated_screen_image=item.image.copy()
            self.unrotated_screen_image.thumbnail(size)
        image=self.unrotated_screen_image.rotate(-self.angle_adjustment.get_value(),Image.NEAREST,expand=True)
        image.thumbnail(size)
        item.qview=imagemanip.image_to_pixbuf(image)
        self.cur_size=size
        self.cur_zoom=zoom
        return True

    def viewer_render_end(self,drawable,gc,item):
        if not self.rotate_mode:
            return
        W,H=self.viewer.imarea.window.get_size()

        #draw drag handles
        colormap=drawable.get_colormap()
        white= colormap.alloc_color('white')
        handle_gc=drawable.new_gc()
        handle_gc.set_function(gtk.gdk.XOR)
        handle_gc.set_foreground(white)
        handle_gc.set_background(white)

        grid_size=min(max(40,W/12),W)
        len_grid_x=int(W/grid_size)
        len_grid_y=int(H/grid_size)

        for i in range(len_grid_x):
            drawable.draw_line(handle_gc,i*grid_size+grid_size/2,0,i*grid_size+grid_size/2,H)

        for i in range(len_grid_y):
            drawable.draw_line(handle_gc,0,i*grid_size+grid_size/2,W,i*grid_size+grid_size/2)



