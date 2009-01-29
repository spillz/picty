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

maemo=False

import gobject
import gtk
import Image
import ImageFile
import threading
import os
import time
import exif
import datetime

try:
    import gnome.ui
    import gnomevfs
    import pyexiv2
except:
    maemo=True

##ORIENTATION INTEPRETATIONS FOR Exif.Image.Orienation
'''
  1        2       3      4         5            6           7          8

888888  888888      88  88      8888888888  88                  88  8888888888
88          88      88  88      88  88      88  88          88  88      88  88
8888      8888    8888  8888    88          8888888888  8888888888          88
88          88      88  88
88          88  888888  888888
'''

global_transposemethods=(None,tuple(),(Image.FLIP_LEFT_RIGHT,),(Image.ROTATE_180,),
            (Image.ROTATE_180,Image.FLIP_LEFT_RIGHT),(Image.ROTATE_90,Image.FLIP_LEFT_RIGHT),
            (Image.ROTATE_270,),(Image.ROTATE_270,Image.FLIP_LEFT_RIGHT),
            (Image.ROTATE_90,))
#global_transposemethods=(None,tuple(),(Image.FLIP_LEFT_RIGHT,),(Image.ROTATE_180,),
#            (Image.ROTATE_180,Image.FLIP_LEFT_RIGHT),(Image.ROTATE_90,Image.FLIP_LEFT_RIGHT),
#            (Image.ROTATE_90,),(Image.ROTATE_270,Image.FLIP_LEFT_RIGHT),
#            (Image.ROTATE_270,))

gobject.threads_init()
#gtk.gdk.threads_init()

global_image_dir=os.environ['HOME']
global_image_dir='/media/sharedrive/Documents/Pictures'
if maemo:
    global_precache_count=100
else:
    global_precache_count=4000
print 'Starting image browser on',global_image_dir

class ImageCacheItem(gobject.GObject):
    def __init__(self,filename,thumb=None):
        self.filename=filename
        self.mtime=None
        self.thumbsize=(0,0)
        self.thumb=thumb
        self.thumbrgba=False
        self.qview=None
        self.qview_size=None
        self.image=None
        self.cannot_thumb=False

class ThumbManager:
    def __init__(self,viewer):
        '''
        thumb manager creates thumbnails asynchronously
        takes requests from and notifies viewers
        '''
        if not maemo:
            self.thumb_factory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_NORMAL)
            self.thumb_factory_large = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_LARGE)
        self.thread=threading.Thread(target=self._make_thumb)
        self.queue_onscreen=[]
        self.queue_fore=[]
        self.queue_back=[]
        self.viewers=[]
        self.memthumbs=[]
        if maemo:
            self.max_memthumbs=1000
        else:
            self.max_memthumbs=8000

        self.vlock=threading.Lock()
        self.viewer=viewer
        self.event=threading.Event()
        self.exit=False
        self.thread.start()

        '''
        uri = gnomevfs.get_uri_from_local_path(path)
        mime = gnomevfs.get_mime_type(uri)

        thumbFactory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_LARGE)
        if thumbFactory.can_thumbnail(uri ,mime, 0):
            thumbnail = thumbFactory.generate_thumbnail(uri, mime)
            if thumbnail != None:
                thumbFactory.save_thumbnail(thumbnail, uri, 0)
        '''

    def request_thumbs(self,onscreen_items,fore_items,back_items):
        self.vlock.acquire()
        self.queue_onscreen=onscreen_items
        self.queue_fore=fore_items
        self.queue_back=back_items
        self.event.set()
        self.vlock.release()

#    def request_thumbs(self,items):
#        self.vlock.acquire()
#        if len(items)>0:
#            self.thumbqueue=items
#            self.event.set()
#        else:
#            print 'request 0 thumbs'
#        self.vlock.release()
#
#    def request_thumb(self,viewer,item):
#        self.vlock.acquire()
#        try:
#            self.thumbqueue.remove(item)
#        except:
#            None
#        self.thumbqueue.append(item)
#        self.vlock.release()
#        self.event.set()
#
#    def cancel_thumb(self,viewer,item):
#        try:
#            del self.thumbqueue[self.thumbqueue.find((viewer,item))]
#        except:
#            print 'thumb_cancel fail',(viewer,item)

    def _check_thumb_limit(self):
        if len(self.memthumbs)>self.max_memthumbs:
            olditem=self.memthumbs.pop(0)
            olditem.thumbsize=(0,0)
            olditem.thumb=None
    def quit(self):
        self.vlock.acquire()
        self.queue_onscreen=[]
        self.queue_fore=[]
        self.queue_back=[]
        self.exit=True
        self.vlock.release()
        self.event.set()
        while self.thread.isAlive():
            time.sleep(0.1)

    def _store_thumbnail(self,item):
        '''this assumes jpg'''
        print 'storing thumbnail',item.filename,item.mtime
        width=item.thumbsize[0]
        height=item.thumbsize[1]
        if height<128 and width<128:
            return
        try:
            thumb_pb=gtk.gdk.pixbuf_new_from_data(data=item.thumb, colorspace=gtk.gdk.COLORSPACE_RGB, has_alpha=item.thumbrgba, bits_per_sample=8, width=width, height=height, rowstride=width*(3+item.thumbrgba)) #last arg is rowstride
        except:
            return
        uri=gnomevfs.get_uri_from_local_path(item.filename)
        self.thumb_factory.save_thumbnail(thumb_pb,uri,item.mtime)

    def _store_failed_thumbnail(self,item):
        self.thumb_factory.create_failed_thumbnail(item.filename,item.mtime)

    def _make_thumb(self):
        while 1:
            self.vlock.acquire()
            if len(self.queue_onscreen)==0 and len(self.queue_fore)==0 and len(self.queue_back)==0:
#                print 'waiting'
                self.event.clear()
                self.vlock.release()
                self.event.wait()
                self.vlock.acquire()
            if self.exit:
                self.vlock.release()
                return
            item=None
            while True:
                try:
                    #print len(self.queue_onscreen),',',
                    item=self.queue_onscreen.pop(0)
                except:
                    if len(self.queue_fore)>len(self.queue_back):
                        try:
                            item=self.queue_fore.pop(0)
                        except:
                            break
                    else:
                        try:
                            item=self.queue_back.pop()
                        except:
                            break
                if item.thumb==None:
                    break
            if item!=None and item.thumb!=None:
                self.vlock.release()
                continue

            fullpath=item.filename
            #print 'loading',fullpath
            if not maemo:
                uri=gnomevfs.get_uri_from_local_path(item.filename)
            mtime=item.mtime
            self.vlock.release()
            storethumb=False
            try:
                if maemo:
                    image = Image.open(fullpath)
                    image.thumbnail((128,128))
                else:
                    thumburi=self.thumb_factory.lookup(uri,mtime)
                    if thumburi:
                        image = Image.open(thumburi)
                        s=image.size
                        #image.thumbnail((128,128))
                    else:
                        thumburi=self.thumb_factory_large.lookup(uri,mtime)
                        if thumburi:
                            #print 'using large thumb'
                            image = Image.open(thumburi)
                            image.thumbnail((128,128))
                        else:
                            #print 'full loading',fullpath
                            #image=None
                            image = Image.open(fullpath)
                            image.thumbnail((128,128))
                            try:
                                image_meta = pyexiv2.Image(item.filename)
                                image_meta.readMetadata()
                            except:
                                print 'Error reading metadata for',item.filename
                            try:
                                orient=image_meta['Exif.Image.Orientation']
                            except:
                                orient=1

                            if orient>1:
                                for method in global_transposemethods[orient]:
                                    image=image.transpose(method)
                            storethumb=True
            except:
                #print 'thumb error'
                image=None
            if image:
                try:
                    thumb=image.tostring()
                except:
                    None
            self.vlock.acquire()
            if self.exit:
                self.vlock.release()
                return
            if image:
                item.thumbsize=image.size
                item.thumb=thumb
                item.thumbrgba='A' in image.getbands()
                if storethumb:
                    self._store_thumbnail(item)
                self.memthumbs.append(item)
                self._check_thumb_limit()
            else:
                item.thumbsize=(0,0)
                item.thumb=None
                item.cannot_thumb=True
                self._store_failed_thumbnail(item)
            gobject.idle_add(self.viewer.Thumb_cb,item)
            self.vlock.release()

class ImageCache:
    def __init__(self):
        self.items=[]
        self.notify_items=[]
        self.imagedir=global_image_dir
        self.imagetypes=['jpg','jpeg','png']
        self.thread=threading.Thread(target=self.data_loader)
        self.viewers=[]
        self.vlock=threading.Lock()
        self.exit=False
        self.thread.start()
    def register_viewer(self,viewer):
        self.vlock.acquire()
        self.viewers.append(viewer)
        items=self.items[:]
        self.vlock.release()
        return items
    def release_viewer(self,viewer):
        self.vlock.acquire()
        try:
            del self.viewers[self.viewers.index(viewer)]
        except:
            print 'viewer not registered',viewer
        self.vlock.release()
    def data_loader(self):
        self.last_update_time=time.time()
        try:
            os.path.walk(self.imagedir,self.walk_cb,0)
        except StopIteration:
            return
        self.vlock.acquire()
        for v in self.viewers:
            gobject.idle_add(v.AddImages,self.notify_items)
        self.notify_items=[]
        self.vlock.release()
    def quit(self):
        self.exit=True
        while self.thread.isAlive():
            time.sleep(0.1)
    def walk_cb(self,arg,dirname,names):
        #print dirname
        if self.exit:
            raise StopIteration
        i=0
        while i<len(names):
            if names[i].startswith('.'):
                names.pop(i)
            else:
                i+=1

        for p in names: #may need some try, except blocks
            r=p.rfind('.')
            if r<=0:
                continue
            if not p[r+1:].lower() in self.imagetypes:
                continue
            fullpath=os.path.join(dirname, p)
            mtime=os.path.getmtime(fullpath)
            st=os.stat(fullpath)
            if os.path.isdir(fullpath):
                continue
            item=ImageCacheItem(fullpath)
            item.mtime=mtime
            self.vlock.acquire()
            self.notify_items.append(item)
                ## notify viewer(s)
            if time.time()>self.last_update_time+1.0 or len(self.notify_items)>100:
                self.last_update_time=time.time()
                for v in self.viewers:
                    gobject.idle_add(v.AddImages,self.notify_items)
                self.items=self.items+self.notify_items
                self.notify_items=[]
            self.vlock.release()

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
                image_meta=None
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
                    #import pyexiv2
                    try:
                        image_meta = pyexiv2.Image(item.filename)
                        image_meta.readMetadata()
                    except:
                        print 'Error reading metadata for',item.filename
                    try:
                        orient=image_meta['Exif.Image.Orientation']
                    except:
                        orient=1

                    if orient>1:
                        for method in global_transposemethods[orient]:
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
                item.image_meta=image_meta
                self.memimages.append(item)
                self._check_image_limit()
                gobject.idle_add(self.viewer.ImageLoaded,item)
                self.vlock.release()
                if not image:
                    self.vlock.acquire()
                    continue
                #notify
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
                #self.vlock.release()
                try:
                    qimage=image.resize((w,h)).tostring()
                except:
                    qimage=None

                #self.vlock.acquire()
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
        #import datetime
        d=datetime.datetime.fromtimestamp(item.mtime)
        self.meta_table.data_items['UnixLastModified'][1].set_text(d.isoformat(' '))
        for k,v in exif.tags:
            try:
                value=item.image_meta[k]
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
        if self.item.image_meta:
            rows+=len(exif.tags)
        stable=gtk.ScrolledWindow()
        stable.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        table = gtk.Table(rows=rows, columns=2, homogeneous=False)
        self.AddMetaRow(table,'Full Path',self.item.filename,0)
        self.AddMetaRow(table,'Last Modified',d.isoformat(' '),1)
        r=2
        for k,v in exif.tags:
            try:
                self.AddMetaRow(table,v,str(self.item.image_meta[k]),r)
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
    def __init__(self,imcache):
        gtk.HBox.__init__(self)
        self.Config()
        self.tm=ThumbManager(self)
        self.neededitem=None
        self.iv=ImageViewer(self.ButtonPress_iv)
        self.is_fullscreen=False
        self.is_iv_fullscreen=False

        self.offsety=0
        self.offsetx=0
        self.ind_view_first=0
        self.ind_view_last=1
        self.ind_viewed=-1

        self.ic=imcache
        self.imagelist = self.ic.register_viewer(self)

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
        #self.Resize(600,300)

    def KeyPress(self,obj,event):
        print 'key press',event.keyval
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
        if (maemo and event.keyval==65475) or event.keyval==65480: #f6 on maemo or f11
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
        self.ic.quit()
        self.tm.quit()
        return False

    def Thumb_cb(self,item):
        ##TODO: Check if image is still on screen
#        if item.thumb:
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def AddImages(self,items):
        for item in items:
            self.imagelist.append(item)
        self.UpdateDimensions()
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def AddImage(self,item):
        self.imagelist.append(item)
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
        if maemo:
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
        fore_items=self.imagelist[self.ind_view_last:self.ind_view_last+global_precache_count/2]
        back_items=self.imagelist[self.ind_view_first-global_precache_count/2:self.ind_view_first]
        self.tm.request_thumbs(onscreen_items,fore_items,back_items)
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

class HelloWorld:

    # This is a callback function. The data arguments are ignored
    # in this example. More on callbacks below.
    def on_down(self, widget, data=None):
        self.drawing_area.ScrollDown()

    def on_up(self, widget, data=None):
        self.drawing_area.ScrollUp()

    def delete_event(self, widget, event, data=None):
        # If you return FALSE in the "delete_event" signal handler,
        # GTK will emit the "destroy" signal. Returning TRUE means
        # you don't want the window to be destroyed.
        # This is useful for popping up 'are you sure you want to quit?'
        # type dialogs.

        # Change FALSE to TRUE and the main window will not be destroyed
        # with a "delete_event".
        return False

    def destroy(self, widget, data=None):
        print "destroy signal occurred"
        gtk.main_quit()

    def __init__(self):
        # create a new window
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        self.window.set_size_request(800, 600)

        # When the window is given the "delete_event" signal (this is given
        # by the window manager, usually by the "close" option, or on the
        # titlebar), we ask it to call the delete_event () function
        # as defined above. The data passed to the callback
        # function is NULL and is ignored in the callback function.
        self.window.connect("delete_event", self.delete_event)

        # Here we connect the "destroy" event to a signal handler.
        # This event occurs when we call gtk_widget_destroy() on the window,
        # or if we return FALSE in the "delete_event" callback.
        self.window.connect("destroy", self.destroy)

        # Sets the border width of the window.
        #self.window.set_border_width(10)

        # Creates a new button with the label "Hello World".
        self.buttonup = gtk.Button("up")
        self.buttondown = gtk.Button("down")

        # When the button receives the "clicked" signal, it will call the
        # function hello() passing it None as its argument.  The hello()
        # function is defined above.
        self.buttonup.connect("clicked", self.on_up, None)
        self.buttondown.connect("clicked", self.on_down, None)

        # This will cause the window to be destroyed by calling
        # gtk_widget_destroy(window) when "clicked".  Again, the destroy
        # signal could come from here, or the window manager.
        #self.button.connect_object("clicked", gtk.Widget.destroy, self.window)

        # This packs the button into the window (a GTK container).

        # The final step is to display this newly created widget.

        self.imcache=ImageCache()
        self.drawing_area = ImageBrowser(self.imcache)

        self.window.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.window.connect("key-press-event",self.drawing_area.KeyPress)

        # and the window
        hb=gtk.HBox()
        vb=gtk.VBox()
        hb.pack_start(self.buttonup)
        hb.pack_start(self.buttondown)
        #vb.pack_start(hb,False)
        vb.pack_start(self.drawing_area)
        self.window.add(vb)
        self.window.show()
        vb.show()
        hb.show()
        self.drawing_area.show()
        self.buttonup.show()
        self.buttondown.show()

    def main(self):
        # All PyGTK applications must have a gtk.main(). Control ends here
        # and waits for an event to occur (like a key press or mouse event).
        gtk.main()

# If the program is run directly or passed as an argument to the python
# interpreter then create a HelloWorld instance and show it
if __name__ == "__main__":
    hello = HelloWorld()
    hello.main()
