#!/usr/bin/python2.5

'''

    Light Weight Image Browser (temporary name)
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

import gobject
import gnomevfs
import gtk

gobject.threads_init()
gtk.gdk.threads_init()


import Image
import ImageFile
import threading
import os
import time
import exif
import datetime
import bisect

try:
    import gnome.ui
    import gnomevfs
    import pyexiv2
except:
    print 'missing modules... exiting!'
    import sys
    sys.exit()

import settings
import backend
settings.init() ##todo: make this call on first import inside the module


class ImageLoader:
    def __init__(self,viewer):
        self.thread=threading.Thread(target=self._background_task)
        self.item=None
        self.sizing=None
        self.memimages=[]
        self.max_memimages=2
        self.vlock=threading.Lock()
        self.viewer=viewer
        self.event=threading.Event()
        self.exit=False
        self.thread.start()

    def update_image_size(self,width,height):
        self.vlock.acquire()
        self.sizing=(width,height)
        self.vlock.release()
        self.event.set()

    def quit(self):
        self.vlock.acquire()
        self.exit=True
        self.vlock.release()
        self.event.set()
        while self.thread.isAlive():
            time.sleep(0.1)

    def set_item(self,item,sizing=None):
        self.vlock.acquire()
        self.item=item
        self.sizing=sizing
        self.vlock.release()
        self.event.set()

    def _check_image_limit(self):
        if len(self.memimages)>self.max_memimages:
            olditem=self.memimages.pop(0)
            if olditem.filename!=self.item.filename: ##TODO: Better comparison of items
                olditem.image=None
                olditem.qview_size=(0,0)
                olditem.qview=None

    def _background_task(self):
        self.vlock.acquire()
        while 1:
            if self.sizing or self.item and not self.item.image:
                self.event.set()
            else:
                self.event.clear()
            self.vlock.release()
            self.event.wait()
            self.vlock.acquire()
            item=self.item
            self.vlock.release()
            if self.exit:
                return
            if not item:
                self.vlock.acquire()
                continue
            if not item.image:
                try:
                    #import ImageFile
                    imfile=open(item.filename,'rb')
                    p = ImageFile.Parser()
                    while self.item.filename==item.filename:
                        s = imfile.read(100000)
                        if not s:
                            break
                        p.feed(s)
                    if self.item.filename!=item.filename:
                        self.vlock.acquire()
                        continue
                    image = p.close()
                    try:
                        orient=item.meta['Exif.Image.Orientation']
                    except:
                        orient=1

                    if orient>1:
                        for method in settings.transposemethods[orient]:
                            image=image.transpose(method)
                except:
                    try:
                        image=Image.open(item.filename)
                    except:
                        image=None
                self.vlock.acquire()
                item.image=image
                try:
                    item.imagergba='A' in item.image.getbands()
                except:
                    item.imagergba=False
                self.memimages.append(item)
                self._check_image_limit()
                gobject.idle_add(self.viewer.ImageLoaded,item)
                self.vlock.release()
                if not image:
                    self.vlock.acquire()
                    continue
            self.vlock.acquire()
            if self.sizing:
                image=item.image
                (w,h)=self.sizing
                (iw,ih)=item.image.size
                if (w*h*iw*ih)==0:
                    self.vlock.acquire()
                    continue
                if 1.0*(w*ih)/(h*iw)>1.0:
                    w=h*iw/ih
                else:
                    h=w*ih/iw
                try:
                    qimage=image.resize((w,h)).tostring()
                except:
                    qimage=None
                item.qview=qimage
                item.qview_size=(w,h)
                gobject.idle_add(self.viewer.ImageSized,item)
                self.sizing=None


class ImageViewer(gtk.VBox):
    def __init__(self,click_callback=None):
        gtk.VBox.__init__(self)
        self.il=ImageLoader(self)
        self.imarea=gtk.DrawingArea()
        self.meta_table=self.CreateMetaTable()
        self.pack_start(self.imarea)
        self.pack_start(self.meta_table)

        self.imarea.connect("realize",self.Render)
        self.imarea.connect("configure_event",self.Configure)
        self.imarea.connect("expose_event",self.Expose)
        self.connect("destroy", self.Destroy)
        self.imarea.add_events(gtk.gdk.SCROLL_MASK)
        self.imarea.add_events(gtk.gdk.BUTTON_MOTION_MASK)
        if not click_callback:
            self.imarea.connect("button-press-event",self.ButtonPress)
        else:
            self.imarea.connect("button-press-event",click_callback)

        self.imarea.set_size_request(64, 64)
        self.width=64
        self.height=64
        self.imarea.show()
        self.item=None
        self.ImageNormal()
        #self.set_position(self.get_allocation().height)

    def AddMetaRow(self,table,data_items,key,label,data,row):
        child1=gtk.Label(label)
        table.attach(child1, left_attach=0, right_attach=1, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)
        child2=gtk.Entry()
        child2.set_text(data)
        table.attach(child2, left_attach=1, right_attach=2, top_attach=row, bottom_attach=row+1,
               xoptions=gtk.EXPAND|gtk.FILL, yoptions=gtk.EXPAND|gtk.FILL, xpadding=0, ypadding=0)
        data_items[key]=(child1,child2)

    def CreateMetaTable(self):
        rows=2
        rows+=len(exif.tags)
        stable=gtk.ScrolledWindow()
        stable.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        table = gtk.Table(rows=rows, columns=2, homogeneous=False)
        stable.data_items=dict()
        self.AddMetaRow(table, stable.data_items,'FullPath','Full Path','',0)
        self.AddMetaRow(table, stable.data_items,'UnixLastModified','Last Modified','',1)
        r=2
        for k,v in exif.tags:
            try:
                self.AddMetaRow(table,stable.data_items,k,v,'',r)
            except:
                None
            r+=1
        table.show_all()
        stable.add_with_viewport(table)
        stable.set_focus_chain(tuple())
        return stable

    def UpdateMetaTable(self,item):
        self.meta_table.data_items['FullPath'][1].set_text(item.filename)
        d=datetime.datetime.fromtimestamp(item.mtime)
        self.meta_table.data_items['UnixLastModified'][1].set_text(d.isoformat(' '))
        for k,v in exif.tags:
            try:
                value=item.meta[k]
                try:
                    if len(value)==2:
                        value='%4.3f'%(1.0*value[0]/value[1])
                    else:
                        value=str(value)
                except:
                    value=str(value)
            except:
                value=''
            self.meta_table.data_items[k][1].set_text(value)

    def CreateMetadataFrame(self):
        rows=2
        #import datetime
        d=datetime.datetime.fromtimestamp(self.item.mtime)
        #import exif
        if self.item.meta:
            rows+=len(exif.tags)
        stable=gtk.ScrolledWindow()
        stable.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        table = gtk.Table(rows=rows, columns=2, homogeneous=False)
        self.AddMetaRow(table,'Full Path',self.item.filename,0)
        self.AddMetaRow(table,'Last Modified',d.isoformat(' '),1)
        r=2
        for k,v in exif.tags:
            try:
                self.AddMetaRow(table,v,str(self.item.meta[k]),r)
            except:
                None
            r+=1
        table.show_all()
        stable.add_with_viewport(table)
        return stable

    def ImageFullscreen(self):
        try:
            self.meta_table.hide()
        except:
            None
        self.fullscreen=True

    def ImageNormal(self):
        try:
            self.meta_table.show()
        except:
            None
        self.fullscreen=False

    def ButtonPress(self,obj,event):
        self.ImageNormal()
        self.hide()

    def Destroy(self,event):
        self.il.quit()
        return False

    def ImageSized(self,item):
        if item.filename==self.item.filename:
            self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)
        else:
            print 'sized wrong item'

    def ImageLoaded(self,item):
        if item.filename==self.item.filename:
            self.UpdateMetaTable(item)

    def SetItem(self,item):
        self.item=item
        self.il.set_item(item,(self.width,self.height))
        #self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def Configure(self,obj,event):
        self.width=event.width
        self.height=event.height
        self.il.update_image_size(self.width,self.height)
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def Expose(self,event,arg):
        self.Render(event)

    def Render(self,event):
        drawable = self.imarea.window
        gc = drawable.new_gc()
        colormap=drawable.get_colormap()
        black = colormap.alloc('black')
        drawable.set_background(black)
        drawable.clear()
        if self.item.qview:
            (iw,ih)=self.item.qview_size
            x=(self.width-iw)/2
            y=(self.height-ih)/2
            #if x>=0 and y>=0:
            if self.item.imagergba:
                try:
                    drawable.draw_rgb_32_image(gc,x,y,iw,ih,
                           gtk.gdk.RGB_DITHER_NONE,
                           self.item.qview, -1, 0, 0)
                except:
                    None
            else:
                try:
                    drawable.draw_rgb_image(gc,x,y,iw,ih,
                           gtk.gdk.RGB_DITHER_NONE,
                           self.item.qview, -1, 0, 0)
                except:
                    None

class ImageBrowser(gtk.HBox):
    '''
    a widget designed to rapidly display a collection of objects
    from an image cache
    '''
    def __init__(self):
        gtk.HBox.__init__(self)
        self.Config()
        self.tm=backend.Worker(self)
        self.imagelist=self.tm.collection
        self.neededitem=None
        self.iv=ImageViewer(self.ButtonPress_iv)
        self.is_fullscreen=False
        self.is_iv_fullscreen=False

        self.offsety=0
        self.offsetx=0
        self.ind_view_first=0
        self.ind_view_last=1
        self.ind_viewed=-1

        self.imarea=gtk.DrawingArea()
        self.Resize(160,400)
        self.scrolladj=gtk.Adjustment()
        self.vscroll=gtk.VScrollbar(self.scrolladj)
        #(w,h)=self.vscroll.get_size_request()
        #print 'Vscroll size',w,h
        #self.vscroll.set_size_request(50,h)

        ##st=self.vscroll.get_style()
        ##stw=2*self.vscroll.style_get_property('slider-width')
        ##print st,stw
        ##st.set_property('slider-width',stw)
        ##self.vscroll.set_style(st)

        #hbox=gtk.HBox()
        self.pack_start(self.iv)
        self.pack_start(self.imarea)
        self.pack_start(self.vscroll,False)
        #self.connect('cache-image-added',self.AddImage)
        self.connect("destroy", self.Destroy)
        self.imarea.connect("realize",self.Render)
        self.imarea.connect("configure_event",self.Configure)
        self.imarea.connect("expose_event",self.Expose)
        self.scrolladj.connect("value-changed",self.ScrollSignal)
        self.imarea.add_events(gtk.gdk.SCROLL_MASK)
        self.imarea.connect("scroll-event",self.ScrollSignalPane)
        self.imarea.add_events(gtk.gdk.BUTTON_MOTION_MASK)
        self.imarea.connect("button-press-event",self.ButtonPress)

        #self.set_flags(gtk.CAN_FOCUS)

#        self.vscroll.add_events(gtk.gdk.KEY_PRESS_MASK)
#        self.vscroll.set_flags(gtk.CAN_FOCUS)
#        self.vscroll.grab_focus()

        self.imarea.show()
        self.vscroll.show()
        self.tm.request_loadandmonitorcollection()
        #self.Resize(600,300)

    def KeyPress(self,obj,event):
        #print 'key press',event.keyval
        if event.keyval==65307: #escape
            self.iv.hide()
            self.iv.ImageNormal()
            self.imarea.show()
            self.vscroll.show()
        if event.keyval==65293: #enter
            if self.ind_viewed>=0:
                if self.is_iv_fullscreen:
                    self.ViewImage(self.ind_viewed)
                    self.iv.ImageNormal()
                    self.imarea.show()
                    self.vscroll.show()
                    self.is_iv_fullscreen=False
                else:
                    self.ViewImage(self.ind_viewed)
                    self.iv.ImageFullscreen()
                    self.imarea.hide()
                    self.vscroll.hide()
                    self.is_iv_fullscreen=True
        if (settings.maemo and event.keyval==65475) or event.keyval==65480: #f6 on settings.maemo or f11
            if self.is_fullscreen:
                self.window.unfullscreen()
                self.is_fullscreen=False
            else:
                self.window.fullscreen()
                self.is_fullscreen=True
        if event.keyval==65361: #left
            if self.ind_viewed>0:
                self.ViewImage(self.ind_viewed-1)
        if event.keyval==65363: #right
            if self.ind_viewed<len(self.imagelist)-1:
                self.ViewImage(self.ind_viewed+1)
        if event.keyval==65362: #up
            self.vscroll.set_value(self.vscroll.get_value()-self.scrolladj.step_increment)
        if event.keyval==65364: #dn
            self.vscroll.set_value(self.vscroll.get_value()+self.scrolladj.step_increment)
        if event.keyval==65365: #pgup
            self.vscroll.set_value(self.vscroll.get_value()-self.scrolladj.page_increment)
        if event.keyval==65366: #pgdn
            self.vscroll.set_value(self.vscroll.get_value()+self.scrolladj.page_increment)
        if event.keyval==65360: #home
            self.vscroll.set_value(self.scrolladj.lower)
        if event.keyval==65367: #end
            self.vscroll.set_value(self.scrolladj.upper)

        #if event.keyval

    def ViewImage(self,ind):
        self.ind_viewed=ind
        self.iv.SetItem(self.imagelist[ind])
        self.iv.show()
        self.offsety=max(0,ind*(self.thumbheight+self.pad)/self.horizimgcount)#-self.width/2)
        self.UpdateDimensions()
#        self.ind_view_first = ind#int(self.offsety)/(self.thumbheight+self.pad)*self.horizimgcount
#        self.ind_view_last = min(len(self.imagelist),self.ind_view_first+self.horizimgcount*(2+self.height/(self.thumbheight+self.pad)))
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)
        #self.UpdateScrollbar()
        #self.UpdateThumbReqs()

    def ButtonPress_iv(self,obj,event):
        if self.is_iv_fullscreen:
            self.ViewImage(self.ind_viewed)
            self.iv.ImageNormal()
            self.imarea.show()
            self.vscroll.show()
            self.is_iv_fullscreen=False
        else:
            self.ViewImage(self.ind_viewed)
            self.iv.ImageFullscreen()
            self.imarea.hide()
            self.vscroll.hide()
            self.is_iv_fullscreen=True

    def ButtonPress(self,obj,event):
        ind=(int(self.offsety)+int(event.y))/(self.thumbheight+self.pad)*self.horizimgcount
        ind+=min(self.horizimgcount,int(event.x)/(self.thumbwidth+self.pad))
        ind=max(0,min(len(self.imagelist)-1,ind))
        self.ViewImage(ind)

    def Destroy(self,event):
        self.tm.quit()
        return False

    def Thumb_cb(self,item):
        ##TODO: Check if image is still on screen
#        if item.thumb:
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def AddImages(self,items):
#        for item in items:
#            self.imagelist.add(item)
        self.UpdateDimensions()
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def AddImage(self,item):
#        self.imagelist.add(item)
        self.UpdateDimensions()
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def ScrollSignalPane(self,obj,event):
        if event.direction==gtk.gdk.SCROLL_UP:
            self.ScrollUp(max(1,self.thumbheight+self.pad)/5)
        if event.direction==gtk.gdk.SCROLL_DOWN:
            self.ScrollDown(max(1,self.thumbheight+self.pad)/5)

    def ScrollSignal(self,obj):
        self.offsety=self.scrolladj.get_value()
        self.UpdateFirstLastIndex()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def UpdateScrollbar(self):
        self.scrolladj.set_all(value=self.offsety, lower=0,
                upper=len(self.imagelist)*(self.thumbheight+self.pad)/self.horizimgcount,
                step_increment=max(1,self.thumbheight+self.pad)/5,
                page_increment=self.height, page_size=self.height)

    def Config(self):
        self.width=160
        self.height=400
        self.thumbwidth=128
        self.thumbheight=128
        if settings.maemo:
            self.pad=20
        else:
            self.pad=30

    def Resize(self,x,y):
        self.imarea.set_size_request(x, y)
        self.width=x
        self.height=y
        self.horizimgcount=(self.width/(self.thumbwidth+self.pad))
        self.maxoffsety=len(self.imagelist)*(self.thumbheight+self.pad)/self.horizimgcount

    def ScrollUp(self,step=10):
        self.vscroll.set_value(self.vscroll.get_value()-step)

    def ScrollDown(self,step=10):
        self.vscroll.set_value(self.vscroll.get_value()+step)

    def UpdateFirstLastIndex(self):
        self.ind_view_first = int(self.offsety)/(self.thumbheight+self.pad)*self.horizimgcount
        self.ind_view_last = min(len(self.imagelist),self.ind_view_first+self.horizimgcount*(2+self.height/(self.thumbheight+self.pad)))

    def UpdateDimensions(self):
        self.offsety=self.offsety*self.horizimgcount
        self.horizimgcount=max(self.width/(self.thumbwidth+self.pad),1)
        self.maxoffsety=len(self.imagelist)*(self.thumbheight+self.pad)/self.horizimgcount
        self.offsety=self.offsety/self.horizimgcount
        if self.ind_viewed>=0:
            self.ind_view_first=max(self.ind_viewed-self.height/2/(self.thumbwidth+self.pad)*self.horizimgcount,0)
            self.offsety=self.ind_view_first*(self.thumbheight+self.pad)/self.horizimgcount
        self.UpdateFirstLastIndex()
        self.offsety=self.ind_view_first*(self.thumbheight+self.pad)/self.horizimgcount

    def Configure(self,obj,event):
        self.width=event.width
        self.height=event.height
        self.UpdateDimensions()
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def Expose(self,event,arg):
        self.Render(event)

    def UpdateThumbReqs(self):
        ## DATA NEEDED
        #self.ind_view_first = int(self.offsety)/(self.thumbheight+self.pad)*self.horizimgcount
        #self.ind_view_last = min(len(self.imagelist),self.ind_view_first+self.horizimgcount*(2+self.height/(self.thumbheight+self.pad)))

        onscreen_items=self.imagelist[self.ind_view_first:self.ind_view_last]
        #fore_items=self.imagelist[self.ind_view_last:self.ind_view_last+settings.precache_count/2]
        #back_items=self.imagelist[self.ind_view_first-settings.precache_count/2:self.ind_view_first]
        self.tm.request_thumbnails(onscreen_items) ##todo: caching ,fore_items,back_items
##OLD VERSION
        '''
                thumb_reqs=[]
                for i in range(self.ind_view_first,self.ind_view_last):
                    item=self.imagelist[i]
                    if not item.thumb and not item.cannot_thumb:
                        thumb_reqs.append(item)
                for i in range(min(self.imagelist,50)):
                    if self.ind_view_first-i-1>=0:
                        item=self.imagelist[self.ind_view_first-i-1]
                        if not item.thumb and not item.cannot_thumb:
                            thumb_reqs.append(item)
                    if self.ind_view_last+i<len(self.imagelist):
                        item=self.imagelist[i+self.ind_view_last]
                        if not item.thumb and not item.cannot_thumb:
                            thumb_reqs.append(item)
                if len(thumb_reqs)>0:
                    self.tm.request_thumbs(thumb_reqs)
        '''

    def Render(self,event):
        #self.ind_view_first = int(self.offsety)/(self.thumbheight+self.pad)*self.horizimgcount
        #self.ind_view_last = min(len(self.imagelist),self.ind_view_first+self.horizimgcount*(2+self.height/(self.thumbheight+self.pad)))
        self.imagelist.lock.acquire()
        drawable = self.imarea.window
        gc = drawable.new_gc()
        colormap=drawable.get_colormap()
        grey = colormap.alloc('grey')
        gc_v = drawable.new_gc(foreground=grey,background=grey)
        colormap=drawable.get_colormap()
        black = colormap.alloc('black')
        drawable.set_background(black)

        #gc_viewed_item = drawable.new_gc()
        #gc_viewed_item.set_foreground(gtk.gdk.color_parse('red'))
        #gc_viewed_item.set_background(gtk.gdk.color_parse('red'))
        ##TODO: USE draw_drawable to shift screen for small moves in the display (scrolling)
        #drawable.clear()
        display_space=True
        imgind=self.ind_view_first
        x=0
        y=imgind*(self.thumbheight+self.pad)/self.horizimgcount-int(self.offsety)
        drawable.clear()
        i=imgind
        neededitem=None
        while i<self.ind_view_last:
            if self.ind_viewed==i:
                drawable.draw_rectangle(gc_v, True, x+self.pad/8, y+self.pad/8, self.thumbwidth+self.pad*3/4, self.thumbheight+self.pad*3/4)
#            drawable.draw_rectangle(gc, True, x+self.pad/4, y+self.pad/4, self.thumbwidth+self.pad/2, self.thumbheight+self.pad/2)
            if self.imagelist[i].thumb:
                (thumbwidth,thumbheight)=self.imagelist[i].thumbsize
                adjy=self.pad/2+(128-thumbheight)/2
                adjx=self.pad/2+(128-thumbwidth)/2
                if self.imagelist[i].thumbrgba:
                    try:
                        drawable.draw_rgb_32_image(gc,x+adjx,y+adjy,thumbwidth,thumbheight,
                                   gtk.gdk.RGB_DITHER_NONE,
                                   self.imagelist[i].thumb, -1, 0, 0)
                    except:
                        None
                        #print 'thumberror',self.imagelist[i].filename,self.imagelist[i].thumbsize
                else:
                    try:
                        drawable.draw_rgb_image(gc,x+adjx,y+adjy,thumbwidth,thumbheight,
                                   gtk.gdk.RGB_DITHER_NONE,
                                   self.imagelist[i].thumb, -1, 0, 0)
                    except:
                        None
                        #print 'thumberror',self.imagelist[i].filename,self.imagelist[i].thumbsize
            else:
                item=self.imagelist[i]
                #if not neededitem and not item.thumb and not  item.cannot_thumb:
                #    neededitem=self.imagelist[i]
#                thumbsneeded.insert(0,self.imagelist[i])
            i+=1
            x+=self.thumbwidth+self.pad
            if x+self.thumbwidth+self.pad>=self.width:
                y+=self.thumbheight+self.pad
                if y>=self.height+self.pad:
                    break
                else:
                    x=0
        self.imagelist.lock.release()

class MainWindow:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_size_request(800, 400)
        self.window.connect("delete_event", self.delete_event)
        self.window.connect("destroy", self.destroy)

#        self.imcache=ImageCache()
        self.drawing_area = ImageBrowser()

        self.window.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.window.connect("key-press-event",self.drawing_area.KeyPress)

        vb=gtk.VBox()
        vb.pack_start(self.drawing_area)
        self.window.add(vb)
        self.window.show()
        vb.show()
        self.drawing_area.show()

    def on_down(self, widget, data=None):
        self.drawing_area.ScrollDown()

    def on_up(self, widget, data=None):
        self.drawing_area.ScrollUp()

    def delete_event(self, widget, event, data=None):
        return False #allows the window to be destroyed

    def destroy(self, widget, data=None):
        print "destroy signal occurred"
        gtk.main_quit()

    def main(self):
        gtk.main()

if __name__ == "__main__":
    wnd = MainWindow()
    wnd.main()
