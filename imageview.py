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

maemo=True

import gobject
import gtk
import Image
import threading
import os
import time
if not maemo:
    import gnome.ui
    import gnomevfs

gobject.threads_init()
#gtk.gdk.threads_init()

global_image_dir=os.environ['HOME']
global_image_dir='/media/sharedrive/Documents/Pictures'
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
        self.thumbqueue=[]
        self.viewers=[]
        self.memthumbs=[]
        self.max_memthumbs=10000
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

    def request_thumbs(self,items):
        self.vlock.acquire()
        if len(items)>0:
            self.thumbqueue=items
            self.event.set()
        else:
            print 'request 0 thumbs'
        self.vlock.release()

    def request_thumb(self,viewer,item):
        self.vlock.acquire()
        try:
            self.thumbqueue.remove(item)
        except:
            None
        self.thumbqueue.append(item)
        self.vlock.release()
        self.event.set()

    def cancel_thumb(self,viewer,item):
        try:
            del self.thumbqueue[self.thumbqueue.find((viewer,item))]
        except:
            print 'thumb_cancel fail',(viewer,item)

    def _check_thumb_limit(self):
        if len(self.memthumbs)>self.max_memthumbs:
            olditem=self.memthumbs.pop(0)
            olditem.thumbsize=(0,0)
            olditem.thumb=None
    def quit(self):
        self.vlock.acquire()
        self.thumbqueue=[]
        self.exit=True
        self.vlock.release()
        self.event.set()
        while self.thread.isAlive():
            time.sleep(0.1)

    def _make_thumb(self):
        print 'thumb thread entry'
        while 1:
            self.vlock.acquire()
            if len(self.thumbqueue)==0:
#                print 'waiting'
                self.event.clear()
                self.vlock.release()
                self.event.wait()
                self.vlock.acquire()
            if self.exit:
                return
            item=self.thumbqueue.pop(0)
            fullpath=item.filename
            #print 'loading',fullpath
            if not maemo:
                uri=gnomevfs.get_uri_from_local_path(item.filename)
            mtime=item.mtime
            self.vlock.release()
            try:
                if maemo:
                    image = Image.open(fullpath)
                    image.thumbnail((128,128))
                else:
                    thumburi=self.thumb_factory.lookup(uri,mtime)
                    if thumburi:
                        image = Image.open(thumburi)
                        s=image.size
                        if s[0]<2 and s[1]<2:
                            print fullpath,s
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
            except:
                #print 'thumb error'
                image=None
            self.vlock.acquire()
            if image:
                item.thumbsize=image.size
                item.thumb=image.tostring()
                item.thumbrgba='A' in image.getbands()
                self.memthumbs.append(item)
                self._check_thumb_limit()
            else:
                item.thumbsize=(0,0)
                item.thumb=None
                item.cannot_thumb=True
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
            self.items.append(item)
            self.notify_items.append(item)
                ## notify viewer(s)
            if time.time()>self.last_update_time+1.0:
                self.last_update_time=time.time()
                self.vlock.acquire()
                for v in self.viewers:
                    gobject.idle_add(v.AddImages,self.notify_items)
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
    def set_item(self,item,sizing=None):
        self.vlock.acquire()
        self.item=item
        self.sizing=sizing
        self.vlock.release()
        self.event.set()
    def _check_image_limit(self):
        if len(self.memimages)>self.max_memimages:
            olditem=self.memimages.pop(0)
            if olditem!=self.item:
                olditem.image=None
                olditem.qview_size=(0,0)
                olditem.qview=None
    def _background_task(self):
        while 1:
            self.vlock.acquire()
            if self.sizing or self.item and not self.item.image:
                self.event.set()
            else:
                print 'event clear'
                self.event.clear()
            self.vlock.release()
            self.event.wait()
            self.vlock.acquire()
            item=self.item
            self.vlock.release()
            print 'load viewer wait over'
            if self.exit:
                return
            if not item:
                continue
            if not item.image:
                print 'loading viewer image'
                try:
                    image=Image.open(item.filename)
                except:
                    image=None
                self.vlock.acquire()
                item.image=image
                self.vlock.release()
                if not image:
                    continue
                #notify
            if self.sizing:
                self.vlock.acquire()
                (w,h)=self.sizing
                (iw,ih)=item.image.size
                if (w*h*iw*ih)==0:
                    continue
                if w/h>iw/ih:
                    w=h*iw/ih
                else:
                    h=w*ih/iw
                self.vlock.release()
                print 'sizing viewer image',(w,h)
                qimage=image.resize((w,h)).tostring()

                self.vlock.acquire()
                item.qview=qimage
                item.qview_size=(w,h)
                item.imagergba='A' in item.image.getbands()
                self.memimages.append(item)
                self._check_image_limit()
                gobject.idle_add(self.viewer.ImageSized,item)
                self.sizing=None
                self.vlock.release()



class ImageViewer(gtk.HBox):
    def __init__(self):
        gtk.HBox.__init__(self)
        self.il=ImageLoader(self)
        self.imarea=gtk.DrawingArea()
        self.imarea.connect("realize",self.Render)
        self.imarea.connect("configure_event",self.Configure)
        self.imarea.connect("expose_event",self.Expose)
        self.connect("destroy", self.destroy)
        self.imarea.set_size_request(400, 400)
        self.pack_start(self.imarea)
        self.width=400
        self.height=400
        self.imarea.show()
        self.item=None


    def destroy(self,event):
        self.il.quit()

    def ImageSized(self,item):
        print 'sized msg',item.filename
        if item==self.item:
            self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def SetItem(self,item):
        self.item=item
        self.il.set_item(item,(self.width,self.height))
        #self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def Configure(self,event,arg):
        rect=self.imarea.get_allocation()
        self.width=rect.width
        self.height=rect.height
        self.il.update_image_size(self.width,self.height)
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def Expose(self,event,arg):
        self.Render(event)

    def Render(self,event):
        print 'render'
        drawable = self.imarea.window
        gc = drawable.new_gc()
        drawable.clear()
        if self.item.qview:
            (iw,ih)=self.item.qview_size
            x=(self.width-iw)/2
            y=(self.height-ih)/2
            print 'qview',x,y,iw,ih
            if x>=0 and y>=0:
                drawable.draw_rgb_image(gc,x,y,iw,ih,
                   gtk.gdk.RGB_DITHER_NONE,
                   self.item.qview, -1, 0, 0)

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
        self.iv=ImageViewer()

        self.offsety=0
        self.offsetx=0
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
        self.connect("destroy", self.destroy)
        self.imarea.connect("realize",self.Render)
        self.imarea.connect("configure_event",self.Configure)
        self.imarea.connect("expose_event",self.Expose)
        self.scrolladj.connect("value-changed",self.ScrollSignal)
        self.imarea.add_events(gtk.gdk.SCROLL_MASK)
        self.imarea.connect("scroll-event",self.ScrollSignalPane)
        self.imarea.add_events(gtk.gdk.BUTTON_MOTION_MASK)
        self.imarea.connect("button-press-event",self.ButtonPress)

        self.imarea.show()
        self.vscroll.show()
        #self.Resize(600,300)

    def ButtonPress(self,obj,event):
        ind=(int(self.offsety)+int(event.y))/(self.thumbheight+self.pad)*self.horizimgcount
        ind+=min(self.horizimgcount,int(event.x)/(self.thumbwidth+self.pad))
        ind=max(0,min(len(self.imagelist),ind))
        print 'clicked',ind
        self.iv.SetItem(self.imagelist[ind])
        self.iv.show()

    def destroy(self,event):
        self.tm.quit()
        self.ic.quit()

    def Thumb_cb(self,item):
        ##TODO: Check if image is still on screen
#        if item.thumb:
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def AddImages(self,items):
        for item in items:
            self.imagelist.append(item)
        self.Configure(None,None)

    def AddImage(self,item):
        self.imagelist.append(item)
        self.Configure(None,None)
        #self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def ScrollSignalPane(self,obj,event):
        if event.direction==gtk.gdk.SCROLL_UP:
            self.ScrollUp(max(1,self.thumbheight+self.pad)/5)
        if event.direction==gtk.gdk.SCROLL_DOWN:
            self.ScrollDown(max(1,self.thumbheight+self.pad)/5)

    def ScrollSignal(self,obj):
        self.offsety=self.scrolladj.get_value()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def UpdateScrollbar(self):
        self.scrolladj.set_all(value=self.offsety, lower=0,
                upper=len(self.imagelist)/self.horizimgcount*(self.thumbheight+self.pad),
                step_increment=max(1,self.thumbheight+self.pad)/5,
                page_increment=self.height, page_size=self.height)

    def Config(self):
        self.width=160
        self.height=400
        self.thumbwidth=128
        self.thumbheight=128
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

    def Configure(self,event,arg):
        rect=self.imarea.get_allocation()
        self.width=rect.width
        self.height=rect.height
        self.horizimgcount=max(self.width/(self.thumbwidth+self.pad),1)
        self.maxoffsety=len(self.imagelist)*(self.thumbheight+self.pad)/self.horizimgcount
        self.UpdateScrollbar()
        self.UpdateThumbReqs()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def Expose(self,event,arg):
        self.Render(event)

    def UpdateThumbReqs(self):
        ## DATA NEEDED
        self.ind_view_first = int(self.offsety)/(self.thumbheight+self.pad)*self.horizimgcount
        self.ind_view_last = min(len(self.imagelist),self.ind_view_first+self.horizimgcount*(2+self.height/(self.thumbheight+self.pad)))
        thumb_reqs=[]
        for i in range(self.ind_view_first,self.ind_view_last):
            item=self.imagelist[i]
            if not item.thumb and not item.cannot_thumb:
                thumb_reqs.append(item)
        for i in range(min(self.imagelist,100)):
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

    def Render(self,event):
        self.ind_view_first = int(self.offsety)/(self.thumbheight+self.pad)*self.horizimgcount
        self.ind_view_last = min(len(self.imagelist),self.ind_view_first+self.horizimgcount*(2+self.height/(self.thumbheight+self.pad)))
        drawable = self.imarea.window
        gc = drawable.new_gc()
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
            if self.imagelist[i].thumb:
                (thumbwidth,thumbheight)=self.imagelist[i].thumbsize
                if self.imagelist[i].thumbrgba:
                    try:
                        drawable.draw_rgb_32_image(gc,x,y,thumbwidth,thumbheight,
                                   gtk.gdk.RGB_DITHER_NONE,
                                   self.imagelist[i].thumb, -1, 0, 0)
                    except:
                        None
                        #print 'thumberror',self.imagelist[i].filename,self.imagelist[i].thumbsize
                else:
                    try:
                        drawable.draw_rgb_image(gc,x,y,thumbwidth,thumbheight,
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
            if x+self.thumbwidth>=self.width:
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
