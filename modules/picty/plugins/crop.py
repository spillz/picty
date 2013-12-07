'''

    picty - Image Crop Plugin
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

#TODO: Impose the aspect ratio constraint (and add defaults to the drop down)
#TODO: Rounding or some other problem prevents setting the crop handle to the bottom right of the image

import gtk
from PIL import Image
import json
import os.path

from picty import imagemanip
from picty import settings
from picty import pluginbase
from picty.uitools import widget_builder as wb

#get/set properties for crop_dimensions variable - used to automatically updat the text entry controls whenever they change
def get_crop_dimensions(self):
    return self._crop_dimensions

def set_crop_dimensions(self,cropd):
    self._crop_dimensions = cropd
    if self.crop_bar:
        xloc = self.crop_bar['cx'].get_active()
        if xloc == 0:
            x=cropd[0]
            w=cropd[2]-cropd[0]
        elif xloc == 1:
            x=(cropd[0]+cropd[2])/2
            w=cropd[2]-cropd[0]
        elif xloc == 2:
            x=cropd[2]
            w=cropd[2]-cropd[0]

        self.crop_bar['x'].handler_block_by_func(self.entry_changed)
        self.crop_bar['x'].set_text(str(x))
        self.crop_bar['x'].handler_unblock_by_func(self.entry_changed)
        self.crop_bar['w'].entry.handler_block_by_func(self.entry_changed)
        self.crop_bar['w'].entry.set_text(str(w))
        self.crop_bar['w'].entry.handler_unblock_by_func(self.entry_changed)

        yloc = self.crop_bar['cy'].get_active()
        if yloc == 0:
            y=cropd[1]
            h=cropd[3]-cropd[1]
        elif yloc == 1:
            y=(cropd[1]+cropd[3])/2
            h=cropd[3]-cropd[1]
        elif yloc == 2:
            y=cropd[3]
            h=cropd[3]-cropd[1]

        self.crop_bar['y'].handler_block_by_func(self.entry_changed)
        self.crop_bar['y'].set_text(str(y))
        self.crop_bar['y'].handler_unblock_by_func(self.entry_changed)
        self.crop_bar['h'].entry.handler_block_by_func(self.entry_changed)
        self.crop_bar['h'].entry.set_text(str(h))
        self.crop_bar['h'].entry.handler_unblock_by_func(self.entry_changed)

default_constraints = [
    (-1,-1,'none'),
    (1,1,'aspect'),
    (3,2,'aspect'),
    (2,3,'aspect'),
    (4,3,'aspect'),
    (3,4,'aspect'),
    (6,4,'aspect'),
    (4,6,'aspect'),
    (7,5,'aspect'),
    (5,7,'aspect'),
    (10,8,'aspect'),
    (8,10,'aspect'),
    (16,9,'aspect'),
    (9,16,'aspect'),
    (16,10,'aspect'),
    (10,16,'aspect'),
    ]

class CropPlugin(pluginbase.Plugin):
    name='Crop'
    display_name='Image Crop'
    api_version='0.1.0'
    version='0.1.0'
    crop_dimensions = property(get_crop_dimensions, set_crop_dimensions)
    crop_bar = None
    def __init__(self):
        self.crop_mode=False
        self.crop_anchor=(0,0)
        self._crop_dimensions=(0,0,0,0)
        self.move_mode=False
        self.hover_zone=0
        self.dragging=False
        self.active_constraint=None
        self.constraints=default_constraints
        settings_file = os.path.join(settings.settings_dir,'crop_plugin_settings.json')

    def plugin_init(self,mainframe,app_init):
        self.viewer=mainframe.iv
        self.load_prefs()
        #todo: need to add a widget to handle editing of constraints
        self.constraint_model = gtk.ListStore(int,int,str)
        #todo: save default as json file

        self.crop_bar = wb.PaddedHBox([
            ('cx',wb.ComboBox(['Lft','Mid','Rgt']),False),
            ('x',wb.Entry(),False),
            ('cy',wb.ComboBox(['Top','Mid','Btm']),False),
            ('y',wb.Entry(),False),
            ('w',wb.LabeledEntry(' W:'),False),
            ('h',wb.LabeledEntry(' H:'),False),
            ('constraints',wb.ComboBox(self.constraints,self.constraint_model),True),
            ('edit_constraints',wb.Button('...'),False),
            ('ok',wb.Button('_Apply'),False),
            ('cancel',wb.Button('_Cancel'),False),
        ])
        cb=self.crop_bar
        for k in ['x','y']:
            cb[k].set_width_chars(4)
            cb[k].connect('changed',self.entry_changed,k)
            cb['c'+k].set_active(0)
            cb['c'+k].connect('changed',self.crop_entry_axis)
        for k in ['w','h']:
            cb[k].entry.set_width_chars(4)
            cb[k].entry.connect('changed',self.entry_changed,k)

        cell = gtk.CellRendererText()
        cb['constraints'].pack_start(cell, True)
        cb['constraints'].set_cell_data_func(cell, self.constraint_as_text)
        cb['constraints'].set_active(0)

        cb.show_all()
        cb['constraints'].connect("changed",self.crop_aspect)
        cb['ok'].connect("clicked",self.crop_do_callback)
        cb['cancel'].connect("clicked",self.crop_cancel_callback)

        imagemanip.transformer.register_transform('crop',self.do_crop_transform)

    def plugin_shutdown(self,app_shutdown=False):
        #deregister the button in the viewer
        if self.crop_mode:
            self.reset(app_shutdown)
        self.save_prefs()
        imagemanip.transformer.deregister_transform('crop')

    def save_prefs(self):
        data = {'constraints':self.constraints,'version':self.version}
        settings.save_addon_prefs('crop_plugin_settings',data)

    def load_prefs(self):
        data = settings.load_addon_prefs('crop_plugin_settings')
        if data:
            self.constraints = data['constraints']

    def entry_changed(self, entry, dim):
        value = entry.get_text()
        if value =='':
            return
        l = list(self._crop_dimensions)
        try:
            value = int(value)
            if dim=='x':
                xloc=self.crop_bar['cx'].get_active()
                if xloc==0:
                    l[0] = value
                elif xloc==1:
                    w = l[2] - l[0]
                    l[0] = value - w/2
                    l[2] = value + w/2 + w%2
                elif xloc==2:
                    l[2] = value
            elif dim=='y':
                yloc=self.crop_bar['cy'].get_active()
                if yloc==0:
                    l[1] = value
                elif yloc==1:
                    h = l[3] - l[1]
                    l[0] = value - h/2
                    l[1] = value - h/2 + h%2
                elif yloc==2:
                    l[2] = value
            elif dim=='w':
                l[2] = l[0] + value
                a=self.active_constraint
                if a:
                    yvalue=value*a[1]/a[0]
                    print 'new height needed',yvalue
                    l[3] = l[1] + yvalue
                    self.crop_dimensions = tuple(l)
            elif dim=='h':
                l[3] = l[1] + value
                a=self.active_constraint
                if a:
                    xvalue=value*a[0]/a[1]
                    l[2] = l[0] + xvalue
                    self.crop_dimensions = tuple(l)
            self._crop_dimensions = tuple(l)
            self.viewer.redraw_view()
        except:
            self.crop_dimensions = self._crop_dimensions

    def constraint_as_text(self, celllayout, cell, model, iter):
        x,y,t = model[iter]
        d=''
        s=''
        if t == 'aspect':
            d=':'
        elif t == 'pixels':
            d='x'
            s='px'
        if x<0 and y<0:
            value = 'None'
        else:
            value = '%i%s%i%s'%(x,d,y,s)
        cell.set_property("text",value)

    def do_crop_transform(self,item,params):
        item.image=item.image.crop(params['pixel_rect'])

    def viewer_register_shortcut(self,shortcut_toolbar):
        '''
        called by the framework to register shortcut on mouse over commands
        append a tuple containing the shortcut commands
        '''
        shortcut_toolbar.register_tool_for_plugin(self,'Crop',self.crop_button_callback,shortcut_toolbar.cb_showing_tranforms,['picty-image-crop'],'Interactively crop this image',40)

    def crop_button_callback(self,cmd):
        '''
        the user has entered crop mode
        hand the plugin exclusive control of the viewer
        '''
        item=self.viewer.item
        if not self.viewer.plugin_request_control(self):
            return
        self.crop_mode=True
        self.viewer.image_box.pack_start(self.crop_bar,False)
        self.viewer.image_box.reorder_child(self.crop_bar,0)
        self.item=item
        self.press_handle=self.viewer.imarea.connect_after("button-press-event",self.button_press)
        self.release_handle=self.viewer.imarea.connect_after("button-release-event",self.button_release)
        self.motion_handle=self.viewer.imarea.connect_after("motion-notify-event",self.mouse_motion_signal)

    def crop_do_callback(self,widget):
        self.viewer.il.add_transform('crop',{'pixel_rect':self.crop_dimensions})
        #self.viewer.il.transform_image() ##todo: this should get called after all but the last call in reset
        self.reset()
#        self.viewer.resize_and_refresh_view(zoom='fit')

    def crop_cancel_callback(self,widget):
        self.reset(True)

    def reset(self,shutdown=False):
        self.hover_zone=0
        self.crop_anchor=(0,0)
        self.crop_dimensions=(0,0,0,0)
        self.crop_mode=False
        self.move_mode=False
        self.item=None
        self.viewer.image_box.remove(self.crop_bar)
        self.viewer.imarea.disconnect(self.press_handle)
        self.viewer.imarea.disconnect(self.release_handle)
        self.viewer.imarea.disconnect(self.motion_handle)
        self.viewer.plugin_release(self)
        if not shutdown:
            self.viewer.resize_and_refresh_view(zoom='fit')

    def viewer_release(self,force=False):
        self.reset()
        return True

    def crop_aspect(self,widget):
        #slider has been shifted, crop the image accordingly (on the background thread?)
        if not self.crop_mode:
            return
        self.active_constraint=self.constraint_model[self.crop_bar["constraints"].get_active_iter()]
        if self.active_constraint[0]<0 and self.active_constraint[1]<0:
            self.active_constraint=None
        X = (self._crop_dimensions[0],self._crop_dimensions[2])
        Y = (self._crop_dimensions[1],self._crop_dimensions[3])
        X,Y = self.aspect_constrained(X,Y)
        self.crop_dimensions = (X[0],Y[0],X[1],Y[1])
        self.viewer.resize_and_refresh_view()

    def aspect_constrained(self,X,Y):
        '''
        given a rectangle X = (left,right),Y = (top,bottom), return a resized rect that matches the aspect ratio
        '''
        c = self.active_constraint
        if c:
            w = X[1] - X[0]
            h = Y[1] - Y[0]
            x = X[0]
            y = Y[0]
            s = 1 if w*h>0 else -1
            if c[1]*w > c[0]*h:
                w = s*c[0]*h/c[1]
            else:
                h = s*c[1]*w/c[0]
            X = (x,x+w)
            Y = (y,y+h)
        return X,Y

    def crop_entry_axis(self,widget):
        #slider has been shifted, crop the image accordingly (on the background thread?)
        if not self.crop_mode:
            return
        self.crop_dimensions=self._crop_dimensions
        self.viewer.resize_and_refresh_view()

    def viewer_to_image(self,x,y):
        X,Y = self.viewer.screen_xy_to_image(x,y)
        return min(max(0,X),self.viewer.item.image.size[0]),min(max(0,Y),self.viewer.item.image.size[1])

    def button_press(self,widget,event):
        if not self.crop_mode:
            return
        if event.button==1:
            self.dragging=True
            x,y=self.viewer_to_image(event.x,event.y)
            x0,y0,x1,y1=self.crop_dimensions
            print 'button press',x,y
            print 'cd',self.crop_dimensions
            if self.hover_zone==5:
                self.move_mode=True
                x=x1
                y=y1
                self.crop_anchor=(x0,y0)
            elif self.hover_zone==1:
                self.crop_anchor=(x1,y1)
            elif self.hover_zone==2:
                self.crop_anchor=(x0,y1)
            elif self.hover_zone==3:
                self.crop_anchor=(x1,y0)
            elif self.hover_zone==4:
                self.crop_anchor=(x0,y0)
            else:
                self.crop_anchor=(x,y)
            X=(self.crop_anchor[0],x)
            Y=(self.crop_anchor[1],y)
            self.crop_dimensions=(min(X),min(Y),max(X),max(Y))
            self.hover_zone=0
            self.viewer.redraw_view()

    def button_release(self,widget,event):
        if not self.crop_mode:
            return
        if event.button==1 and self.dragging:
            self.dragging=False
            x,y=self.viewer_to_image(event.x,event.y)
            if not self.move_mode:
                X=(self.crop_anchor[0],x)
                Y=(self.crop_anchor[1],y)
                X,Y = self.aspect_constrained(X,Y)
                self.crop_dimensions=(min(X),min(Y),max(X),max(Y))
            else:
                x0,y0,x1,y1=self.crop_dimensions
                X=(x0+x1)/2
                Y=(y0+y1)/2
                iw,ih=self.item.image.size
                dx=max(-x0,min(x-X,iw-x1))
                dy=max(-y0,min(y-Y,ih-y1))
                self.crop_dimensions=(x0+dx,y0+dy,x1+dx,y1+dy)
            self.move_mode=False
            self.viewer.redraw_view()

    def mouse_motion_signal(self,obj,event):
        '''callback when mouse moves in the viewer area (updates image overlay as necessary)'''
        if not self.crop_mode:
            return
        if self.dragging:
            x,y=self.viewer_to_image(event.x,event.y)
            if not self.move_mode:
                X=(self.crop_anchor[0],x)
                Y=(self.crop_anchor[1],y)
                X,Y = self.aspect_constrained(X,Y)
                self.crop_dimensions=(min(X),min(Y),max(X),max(Y))
            else:
                x0,y0,x1,y1=self.crop_dimensions
                X=(x0+x1)/2
                Y=(y0+y1)/2
                iw,ih=self.item.image.size
                dx=max(-x0,min(x-X,iw-x1))
                dy=max(-y0,min(y-Y,ih-y1))
                self.crop_dimensions=(x0+dx,y0+dy,x1+dx,y1+dy)
            self.viewer.redraw_view()
        else:
            mx,my=self.viewer.screen_xy_to_scaled_image(event.x,event.y)
            old_zone=self.hover_zone
            x0,y0,x1,y1=self.crop_dimensions
            x0,y0 = self.viewer.image_xy_to_scaled_image(x0,y0)
            x1,y1 = self.viewer.image_xy_to_scaled_image(x1,y1)
            radx=max(min(15,(x1-x0)/3),1)
            rady=max(min(15,(y1-y0)/3),1)
            hover_zone_pts=(
            (1,x0,y0),
            (2,x1,y0),
            (3,x0,y1),
            (4,x1,y1),
            (5,(x0+x1)/2,(y0+y1)/2)
            )
            for z,x,y in hover_zone_pts:
                self.hover_zone=z*(1.0*abs(mx-x)/radx+1.0*abs(my-y)/rady<=1)
                if self.hover_zone:
                    break
            if old_zone!=self.hover_zone:
                self.viewer.redraw_view()

    def viewer_relinquish_control(self):
        #user has cancelled the view of the current item, plugin must cancel open operations
        pass

    def viewer_render_end(self,drawable,gc,item):
        if not self.crop_mode:
            return
        if self.crop_dimensions==(0,0,0,0):
            return
        W,H=self.viewer.imarea.window.get_size()
        x,y,w,h=self.crop_dimensions
        x,y=self.viewer.image_xy_to_screen(x,y)
        w,h=self.viewer.image_xy_to_screen(w,h)
        w-=x
        h-=y
        #block out the background in red
        fill_gc=drawable.new_gc()
        fill_gc.set_function(gtk.gdk.OR)
        colormap=drawable.get_colormap()
        red= colormap.alloc('red')
        fill_gc.set_foreground(red)
        fill_gc.set_background(red)
        drawable.draw_rectangle(fill_gc,True,0,0,W,y)
        drawable.draw_rectangle(fill_gc,True,0,y,x,y+h)
        drawable.draw_rectangle(fill_gc,True,x+w,y,W,y+h)
        drawable.draw_rectangle(fill_gc,True,0,y+h,W,H)

        #draw drag handles
        hlen=min(17,(w-1)/3)
        vlen=min(17,(h-1)/3)
        thickness=3 #max(2,int((hlen+vlen)/6))
        colormap=drawable.get_colormap()
        grey= colormap.alloc('grey')
        white= colormap.alloc('white')
        handle_gc=drawable.new_gc()
        hhandle_gc=drawable.new_gc()
        handle_gc.set_foreground(grey)
        handle_gc.set_background(grey)
        handle_gc.set_line_attributes(thickness,gtk.gdk.LINE_SOLID,gtk.gdk.CAP_ROUND,gtk.gdk.JOIN_BEVEL)
        hhandle_gc.set_foreground(white)
        hhandle_gc.set_background(white)
        hhandle_gc.set_line_attributes(thickness,gtk.gdk.LINE_SOLID,gtk.gdk.CAP_ROUND,gtk.gdk.JOIN_BEVEL)
        x=int(x)-1
        y=int(y)-1
        #top left
        if self.hover_zone==1:
            drawable.draw_line(hhandle_gc,x,y,x+hlen,y)
            drawable.draw_line(hhandle_gc,x,y,x,y+vlen)
        else:
            drawable.draw_line(handle_gc,x,y,x+hlen,y)
            drawable.draw_line(handle_gc,x,y,x,y+vlen)

        #top right
        if self.hover_zone==2:
            drawable.draw_line(hhandle_gc,x+w,y,x+w-hlen,y)
            drawable.draw_line(hhandle_gc,x+w,y,x+w,y+vlen)
        else:
            drawable.draw_line(handle_gc,x+w,y,x+w-hlen,y)
            drawable.draw_line(handle_gc,x+w,y,x+w,y+vlen)

        #bottom left
        if self.hover_zone==3:
            drawable.draw_line(hhandle_gc,x,y+h,x+hlen,y+h)
            drawable.draw_line(hhandle_gc,x,y+h,x,y+h-vlen)
        else:
            drawable.draw_line(handle_gc,x,y+h,x+hlen,y+h)
            drawable.draw_line(handle_gc,x,y+h,x,y+h-vlen)

        #bottom right
        if self.hover_zone==4:
            drawable.draw_line(hhandle_gc,x+w,y+h,x+w-hlen,y+h)
            drawable.draw_line(hhandle_gc,x+w,y+h,x+w,y+h-vlen)
        else:
            drawable.draw_line(handle_gc,x+w,y+h,x+w-hlen,y+h)
            drawable.draw_line(handle_gc,x+w,y+h,x+w,y+h-vlen)

        #center
        if self.hover_zone==5:
            drawable.draw_line(hhandle_gc,x+w/2-hlen/2,y+h/2,x+w/2+hlen/2,y+h/2) ##todo: an alternative would be too render a highlight over the whole image
            drawable.draw_line(hhandle_gc,x+w/2,y+h/2-vlen/2,x+w/2,y+h/2+vlen/2)
        else:
            drawable.draw_line(handle_gc,x+w/2-hlen/2,y+h/2,x+w/2+hlen/2,y+h/2) ##todo: an alternative would be too render a highlight over the whole image
            drawable.draw_line(handle_gc,x+w/2,y+h/2-vlen/2,x+w/2,y+h/2+vlen/2)
