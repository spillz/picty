'''

    picty - Image Enhance Plugin
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

##TODO: need a better icon (STOCK_COLOR_PICKER no good)
##TODO: there should probably only be one color enhance operation per image -- currently can stack up many)

import gtk
import Image
import ImageEnhance

from picty import imagemanip
from picty import settings
from picty import pluginbase


class EnhancePicker(gtk.HBox):
    def __init__(self,label_text,default,lo,hi,lo_increment,hi_increment,adj_cb):
        gtk.HBox.__init__(self)
        self.label=gtk.Label(label_text)
        self.adjustment=gtk.Adjustment(default,lo,hi,lo_increment,hi_increment,hi_increment)
        self.adjustment.connect("value-changed",adj_cb)
        self.slider=gtk.HScale(self.adjustment)
        self.slider.set_draw_value(False)
        self.angle_entry=gtk.SpinButton(self.adjustment,default,2)
        self.pack_start(self.label,False)
        self.pack_start(self.slider,expand=True)
        self.pack_start(self.angle_entry,False)
    def get_value(self):
        return self.adjustment.get_value()
    def set_value(self,value):
        return self.adjustment.set_value(value)

class EnhancePlugin(pluginbase.Plugin):
    name='Enhance'
    display_name='Image Enhance'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        self.enhance_mode=False
    def plugin_init(self,mainframe,app_init):
        #register a button in the viewer to enter enhance mode
        self.viewer=mainframe.iv

        self.unenhanced_screen_image=None
        self.cur_size=None
        self.cur_zoom=None



        self.ok_button=gtk.Button("_Apply")
        self.ok_button.connect("clicked",self.enhance_do_callback)
        self.cancel_button=gtk.Button("_Cancel")
        self.cancel_button.connect("clicked",self.enhance_cancel_callback)

        self.enhance_bar=gtk.VBox()

        self.picker_brightness = EnhancePicker("Brightness:",1.0,0.0,5.0,0.01,0.1,self.enhance_adjust)
        self.picker_color = EnhancePicker("Color:",1.0,0.0,5.0,0.01,0.1,self.enhance_adjust)
        self.picker_contrast = EnhancePicker("Contrast:",1.0,0.0,5.0,0.01,0.1,self.enhance_adjust)
        self.picker_sharpen = EnhancePicker("Sharpen:",1.0,0.0,5.0,0.01,0.1,self.enhance_adjust)

        self.enhance_bar.pack_start(self.picker_brightness)
        self.enhance_bar.pack_start(self.picker_color)
        self.enhance_bar.pack_start(self.picker_contrast)
        self.enhance_bar.pack_start(self.picker_sharpen)

        ok_box=gtk.HBox()
        ok_box.pack_start(self.cancel_button,False)
        ok_box.pack_start(self.ok_button,False)
        self.enhance_bar.pack_start(ok_box)
        self.enhance_bar.show_all()
        imagemanip.transformer.register_transform('enhance',self.do_enhance_transform)
        self.histo=None

    def plugin_shutdown(self,app_shutdown=False):
        #deregister the button in the viewer
        if self.enhance_mode:
            self.reset(app_shutdown)
        imagemanip.transformer.deregister_transform('enhance')

    def do_enhance_transform(self,item,params):
        image=item.image
        enhancer_sharpen = ImageEnhance.Sharpness(image)
        image = enhancer_sharpen.enhance(params['sharpness'])
        enhancer_color = ImageEnhance.Color(image)
        image = enhancer_color.enhance(params['color'])
        enhancer_contrast = ImageEnhance.Contrast(image)
        image = enhancer_contrast.enhance(params['contrast'])
        enhancer_brightness = ImageEnhance.Brightness(image)
        item.image = enhancer_brightness.enhance(params['brightness'])

    def viewer_register_shortcut(self,shortcut_toolbar):
        '''
        called by the framework to register shortcut on mouse over commands
        append a tuple containing the shortcut commands
        '''
        shortcut_toolbar.register_tool_for_plugin(self,'Enhance',self.enhance_button_callback,shortcut_toolbar.cb_showing_tranforms,[gtk.STOCK_COLOR_PICKER],'Enhance this image',43)

    def enhance_button_callback(self,cmd):
        '''
        the user has entered enhance mode
        set the viewer to a blocking mode to hand the plugin exclusive control of the viewer
        '''
        item=self.viewer.item
        if not self.viewer.plugin_request_control(self):
            return
        self.enhance_mode=True
        self.viewer.image_box.pack_start(self.enhance_bar,False)
        self.viewer.image_box.reorder_child(self.enhance_bar,0)
        self.item=item

    def enhance_do_callback(self,widget):
        self.viewer.il.add_transform('enhance',{
                'brightness':self.picker_brightness.get_value(),
                'color':self.picker_color.get_value(),
                'contrast':self.picker_contrast.get_value(),
                'sharpness':self.picker_sharpen.get_value(),
                'method':'PIL'
                })
        #self.viewer.il.transform_image()
        self.reset()

    def enhance_cancel_callback(self,widget):
        if self.enhance_mode:
            self.reset()

    def reset(self,shutdown=False):
        self.enhance_mode=False
        self.item=None
        self.histo=None
        self.unenhanced_screen_image=None
        self.viewer.image_box.remove(self.enhance_bar)
        self.viewer.plugin_release(self)
        self.picker_brightness.set_value(1.0)
        self.picker_color.set_value(1.0)
        self.picker_contrast.set_value(1.0)
        self.picker_sharpen.set_value(1.0)
        if not shutdown:
            self.viewer.resize_and_refresh_view()

    def enhance_adjust(self,adjustment):
        if not self.enhance_mode:
            return
        self.viewer.resize_and_refresh_view(force=True)

    def viewer_release(self,force=False):
        self.reset(True)
        return True

    def t_viewer_sizing(self,size,zoom,item):
        if not self.enhance_mode:
            return
        if size!=self.cur_size or not self.unenhanced_screen_image:
            self.unenhanced_screen_image=item.image.copy()
            self.unenhanced_screen_image.thumbnail(size)
        image=self.unenhanced_screen_image
        enhancer_sharpen = ImageEnhance.Sharpness(image)
        image = enhancer_sharpen.enhance(self.picker_sharpen.get_value())
        enhancer_color = ImageEnhance.Color(image)
        image = enhancer_color.enhance(self.picker_color.get_value())
        enhancer_contrast = ImageEnhance.Contrast(image)
        image = enhancer_contrast.enhance(self.picker_contrast.get_value())
        enhancer_brightness = ImageEnhance.Brightness(image)
        image = enhancer_brightness.enhance(self.picker_brightness.get_value())

        self.histo = image.histogram()
        item.qview=imagemanip.image_to_pixbuf(image)
        self.cur_size=size
        self.cur_zoom=zoom
        return True

    def viewer_render_end(self,drawable,gc,item):
        if not self.enhance_mode:
            return
        item=self.item
        iw,ih = drawable.get_size()
        if 'qview' in item.__dict__ and self.histo is not None:
            hg = imagemanip.graphical_histogram(self.histo,(iw-205,ih-133),(200,128),drawable)



