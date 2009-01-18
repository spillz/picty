#!/usr/bin/python2.5

import gobject
import gtk
import Image
import threading
import os
import time
import gnome.ui
import gnomevfs

gtk.gdk.threads_init()

class ImageCacheItem(gobject.GObject):
    def __init__(self,filename,thumb=None,qviewjpeg=None):
        self.filename=filename
        self.mtime=None
        self.thumbsize=(0,0)
        self.thumb=thumb
        self.qviewjpeg=qviewjpeg
        self.cannot_thumb=False

#gobject.signal_new("cache-image-added", gtk.Widget, gobject.SIGNAL_ACTION, gobject.TYPE_BOOLEAN, (gtk.Widget, ImageCacheItem))

class ThumbManager:
    def __init__(self):
        '''
        thumb manager creates thumbnails asynchronously
        takes requests from and notifies viewers
        '''
        self.thumb_factory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_NORMAL)
        self.thumb_factory_l = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_LARGE)
        self.thread=threading.Thread(target=self._make_thumb)
        self.thumbqueue=[]
        self.viewers=[]
        self.memthumbs=[]
        self.max_memthumbs=1000
        self.vlock=threading.Lock()


        '''
        uri = gnomevfs.get_uri_from_local_path(path)
        mime = gnomevfs.get_mime_type(uri)

        thumbFactory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_LARGE)
        if thumbFactory.can_thumbnail(uri ,mime, 0):
            thumbnail = thumbFactory.generate_thumbnail(uri, mime)
            if thumbnail != None:
                thumbFactory.save_thumbnail(thumbnail, uri, 0)
        '''

    def request_thumbs(self,viewer,items):
        self.vlock.acquire()
        #print items
        for item in items:
            #print item.filename
            if not (viewer,item) in self.thumbqueue:
                if not item.thumb:
                    self.thumbqueue.append((viewer,item))
        if len(self.thumbqueue)>0 and not self.thread.isAlive():
            self.thread=threading.Thread(target=self._make_thumb)
            self.thread.start()
        self.vlock.release()

    def request_thumb(self,viewer,item):
        self.vlock.acquire()
        if not (viewer,item) in self.thumbqueue:
            self.thumbqueue.append((viewer,item))
        else:
            self.vlock.release()
            return
        if not self.thread.isAlive():
            self.thread=threading.Thread(target=self._make_thumb)
            self.thread.start()
        self.vlock.release()

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

    def _make_thumb(self):
        self.vlock.acquire()
        viewer,item=self.thumbqueue.pop()
        fullpath=item.filename
        uri=gnomevfs.get_uri_from_local_path(item.filename)
        mtime=item.mtime
        self.vlock.release()
        while 1:
            try:
                thumburi=self.thumb_factory.lookup(uri,mtime)
                if thumburi:
                    image = Image.open(thumburi)
                    #image.thumbnail((128,128))
                else:
                    thumburi=self.thumb_factory_large.lookup(uri,mtime)
                    if thumburi:
                        print 'using large thumb'
                        image = Image.open(thumburi)
                        image.thumbnail((128,128))
                    else:
                        image=None
                        #image = Image.open(fullpath)
                        #image.thumbnail((128,128))
            except:
                image=None
            self.vlock.acquire()
            if image:
                item.thumbsize=image.size
                item.thumb=image.tostring()
                self.memthumbs.append(item)
                self._check_thumb_limit()
            else:
                item.thumbsize=(0,0)
                item.thumb=None
                item.cannot_thumb=True
            gobject.idle_add(viewer.Thumb_cb,item)
            if len(self.thumbqueue)>0:
                viewer,item=self.thumbqueue.pop()
                fullpath=item.filename
                self.vlock.release()
            else:
                self.vlock.release()
                return

class ImageCache:
    def __init__(self):
        self.items=[]
        self.imagedir='/media/sharedrive/Documents/Pictures'
        self.imagetypes=['jpg','jpeg','png']
        self.thread=threading.Thread(target=self.data_loader)
        self.viewers=[]
        self.vlock=threading.Lock()
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
        os.path.walk(self.imagedir,self.walk_cb,0)
    def walk_cb(self,arg,dirname,names):
        #print dirname
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
            self.items.append(item)
            ## notify viewer(s)
            try:
#                image = Image.open(fullpath)
#                image.thumbnail((128,128))
#                item.thumbsize=image.size
#                item.thumb=image.tostring()
                ## notify viewer(s)
                item.mtime=mtime
                self.vlock.acquire()
                for v in self.viewers:
                    gobject.idle_add(v.AddImage,item)
                self.vlock.release()
            except:
                print 'failed reading',item.filename
            #time.sleep(0.1)


class ImageBrowser(gtk.HBox):
    '''
    a widget designed to rapidly display a collection of objects
    from an image cache
    '''
    def __init__(self,imcache,thumbmgr):
        gtk.HBox.__init__(self)
        self.Config()
        self.tm=thumbmgr

        self.offsety=0
        self.offsetx=0
        self.ic=imcache
        self.imagelist = self.ic.register_viewer(self)

        self.imarea=gtk.DrawingArea()
        self.Resize(600,400)
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
        self.pack_start(self.imarea)
        self.pack_start(self.vscroll,False)
        #self.connect('cache-image-added',self.AddImage)
        self.imarea.connect("realize",self.Render)
        self.imarea.connect("configure_event",self.Configure)
        self.imarea.connect("expose_event",self.Expose)
        self.scrolladj.connect("value-changed",self.ScrollSignal)
        self.imarea.add_events(gtk.gdk.SCROLL_MASK)
        self.imarea.connect("scroll-event",self.ScrollSignalPane)
        self.imarea.show()
        self.vscroll.show()
        #self.Resize(600,300)

    def Thumb_cb(self,item):
        ##TODO: Check if image is still on screen
        if item.thumb:
            self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def AddImage(self,item):
        self.imagelist.append(item)
        self.Configure(None,None)
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def ScrollSignalPane(self,obj,event):
        if event.direction==gtk.gdk.SCROLL_UP:
            self.ScrollUp(max(1,self.thumbheight+self.pad)/5)
        if event.direction==gtk.gdk.SCROLL_DOWN:
            self.ScrollDown(max(1,self.thumbheight+self.pad)/5)

    def ScrollSignal(self,obj):
        self.offsety=self.scrolladj.get_value()
        self.imarea.window.invalidate_rect((0,0,self.width,self.height),True)

    def UpdateScrollbar(self):
        self.scrolladj.set_all(value=self.offsety, lower=0,
                upper=len(self.imagelist)/self.horizimgcount*(self.thumbheight+self.pad),
                step_increment=max(1,self.thumbheight+self.pad)/5,
                page_increment=self.height, page_size=self.height)

    def Config(self):
        self.width=600
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

    def Expose(self,event,arg):
        self.Render(event)

    def Render(self,event):
        drawable = self.imarea.window
        gc = drawable.new_gc()
        ##TODO: USE draw_drawable to shift screen for small moves in the display (scrolling)
        #drawable.clear()
        display_space=True
        imgind=int(self.offsety)/(self.thumbheight+self.pad)*self.horizimgcount
        x=0
        y=imgind*(self.thumbheight+self.pad)/self.horizimgcount-int(self.offsety)
        drawable.clear()
        i=imgind
        thumbsneeded=[]
        while i<len(self.imagelist):
            if self.imagelist[i].thumb:
                (thumbwidth,thumbheight)=self.imagelist[i].thumbsize
                drawable.draw_rgb_image(gc,x,y,thumbwidth,thumbheight,
                                   gtk.gdk.RGB_DITHER_NONE,
                                   self.imagelist[i].thumb, -1, 0, 0)
            else:
                thumbsneeded.append(self.imagelist[i])
#                thumbsneeded.insert(0,self.imagelist[i])
            i+=1
            x+=self.thumbwidth+self.pad
            if x+self.thumbwidth>=self.width:
                y+=self.thumbheight+self.pad
                if y>=self.height+self.pad:
                    break
                else:
                    x=0
        for j in range(100):
            if imgind-1-j>=0:
                thumbsneeded.append(self.imagelist[imgind-1-j])
#                thumbsneeded.insert(0,self.imagelist[imgind-1-j])
            if i+j<len(self.imagelist):
                thumbsneeded.append(self.imagelist[i+j])
#                thumbsneeded.insert(0,self.imagelist[i+j])
        self.tm.request_thumbs(self,thumbsneeded)

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
        self.drawing_area = ImageBrowser(self.imcache,ThumbManager())

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
