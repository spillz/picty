'''

    picty
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

import StringIO
import Image
import ImageFile
import metadata
import datetime
import bisect
import os.path
import os
import threading

import settings
import baseobjects
import io
import pluginmanager

import uuid
muuid = lambda x:str(uuid.uuid5(uuid.NAMESPACE_URL,x))

##TODO: Windows workaround for lack of thumbnail factory (note that collection.cache must always be none to avoid errors)
try:
    import gnome.ui
    thumb_factory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_NORMAL)
    thumb_factory_large = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_LARGE)
except:
    thumb_factory = None
    thumb_factory_large = None

##ORIENTATION INTEPRETATIONS FOR Exif.Image.Orienation
'''
  1        2       3      4         5            6           7          8

888888  888888      88  88      8888888888  88                  88  8888888888
88          88      88  88      88  88      88  88          88  88      88  88
8888      8888    8888  8888    88          8888888888  8888888888          88
88          88      88  88
88          88  888888  888888
'''

transposemethods=(None,tuple(),(Image.FLIP_LEFT_RIGHT,),(Image.ROTATE_180,),
            (Image.ROTATE_180,Image.FLIP_LEFT_RIGHT),(Image.ROTATE_90,Image.FLIP_LEFT_RIGHT),
            (Image.ROTATE_270,),(Image.ROTATE_270,Image.FLIP_LEFT_RIGHT),
            (Image.ROTATE_90,))

transposemethods_pb=(None,
            (None,gtk.gdk.PIXBUF_ROTATE_NONE),
            (True,gtk.gdk.PIXBUF_ROTATE_NONE),
            (None,gtk.gdk.PIXBUF_ROTATE_UPSIDEDOWN),
            (True,gtk.gdk.PIXBUF_ROTATE_UPSIDEDOWN),
            (False,gtk.gdk.PIXBUF_ROTATE_COUNTERCLOCKWISE),
            (None,gtk.gdk.PIXBUF_ROTATE_CLOCKWISE),
            (False,gtk.gdk.PIXBUF_ROTATE_CLOCKWISE),
            (None,gtk.gdk.PIXBUF_ROTATE_COUNTERCLOCKWISE))

rotate_right_tx={1:6,2:5,3:8,4:7,5:4,6:3,7:2,8:1}

rotate_left_tx={1:8,2:7,3:6,4:5,5:2,6:1,7:4,8:3}


import time

##global ram cache for images and thumbs
memimages=[]
memthumbs=[]


def rotate_left(item,collection=None):
    '''
    rotates image anti-clockwise by setting the Orientation metadata key (rotate thumbnail accordingly and reset full size images)
    '''
    try:
        orient=item.meta['Orientation']
    except:
        orient=1
    if orient<1 or orient>8:
        print 'warning: invalid orientation',orient,'for image',item,'-- hardcoding to 1'
        orient=1
    item.set_meta_key('Orientation',rotate_left_tx[orient],collection)
    item.image=None
    item.qview=None
    if collection==None:
        rotate_thumb(item,False)
    else:
        collection.rotate_thumbnail(item,False)


def rotate_right(item,collection=None):
    '''
    rotates image clockwise by setting the Orientation metadata key (rotate thumbnail accordingly and reset full size images)
    '''
    try:
        orient=item.meta['Orientation']
    except:
        orient=1
    if orient<1 or orient>8:
        print 'warning: invalid orientation',orient,'for image',item,'-- hardcoding to 1'
        orient=1
    item.set_meta_key('Orientation',rotate_right_tx[orient],collection)
    item.image=None
    item.qview=None
    if collection==None:
        rotate_thumb(item,True)
    else:
        collection.rotate_thumbnail(item,True)


def toggle_tags(item,tags,collection=None):
    try:
        tags_lower=[t.lower() for t in tags]
        meta=item.meta.copy()
        try:
            tags_kw=meta['Keywords']
        except:
            tags_kw=[]
        tags_kw_lower=[t.lower() for t in tags_kw]
        new_tags=list(tags_kw)
        all_present=reduce(bool.__and__,[t in tags_kw_lower for t in tags_lower],True)
        if all_present:
            print 'removing tags',new_tags,tags_kw_lower,tags_lower
            j=0
            while j<len(new_tags):
                if tags_kw_lower[j] in tags_lower:
                    new_tags.pop(j)
                    tags_kw_lower.pop(j)
                else:
                    j+=1
        else:
            for j in range(len(tags)):
                if tags_lower[j] not in tags_kw_lower:
                    new_tags.append(tags[j])
        if len(new_tags)==0:
            try:
                del meta['Keywords']
            except:
                pass
        else:
            meta['Keywords']=new_tags
        item.set_meta(meta,collection)
    except:
        pass

def add_tags(item,tags):
    try:
        tags_lower=[t.lower() for t in tags]
        meta=item.meta.copy()
        try:
            tags_kw=meta['Keywords']
        except:
            tags_kw=[]
        tags_kw_lower=[t.lower() for t in tags_kw]
        new_tags=list(tags_kw)
        for j in range(len(tags)):
            if tags_lower[j] not in tags_kw_lower:
                new_tags.append(tags[j])
        if len(new_tags)==0:
            try:
                del meta['Keywords']
            except:
                pass
        else:
            meta['Keywords']=new_tags
        item.set_meta(meta)
    except:
        pass

def remove_tags(item,tags):
    try:
        tags_lower=[t.lower() for t in tags]
        meta=item.meta.copy()
        tags_kw=list(meta['Keywords'])
        tags_kw_lower=[t.lower() for t in tags_kw]
        new_tags=[]
        for j in range(len(tags_kw)):
            if tags_kw_lower[j] not in tags_lower:
                new_tags.append(tags_kw[j])
        if len(new_tags)==0:
            del meta['Keywords']
        else:
            meta['Keywords']=new_tags
        item.set_meta(meta)
    except:
        pass

def set_tags(item,tags):
    try:
        meta=item.meta.copy()
        meta['Keywords']=tags
        item.set_meta(meta)
    except:
        pass

def get_coords(item):
    '''retrieve a pair of latitude longitude coordinates in degrees from item'''
    try:
        return item.meta['LatLon']
    except:
        return None

def set_coords(item,lat,lon):
    '''set the latitude and longitude in degrees to the item's exif metadata'''
    item.set_meta_key('LatLon',(lat,lon))

def item_in_region(item,lat0,lon0,lat1,lon1):
    '''returns true if the item's geolocation is contained in the rectangular region (lat0,lon0),(lat1,lon1)'''
    c=get_coords(item)
    if c and lat1<=c[0]<=lat0 and lon0<=c[1]<=lon1:
            return True
    return False



def load_metadata(item,collection=None,filename=None,get_thumbnail=False,missing_only=False,check_for_sidecar=False,notify_plugins=True):
    if item.meta is not None:
        meta=item.meta.copy()
    else:
        meta=None
    if filename is None:
        if collection is not None:
            filename=collection.get_path(item)
    print 'loading metadata for item',item
    if check_for_sidecar and 'sidecar' not in item.__dict__:
        p=os.path.splitext(collection.get_path(item))[0]+'.xmp'
        if os.path.exists(p):
            item.sidecar=collection.get_relpath(p)
        else:
            p=collection.get_path(item)+'.xmp'
            if os.path.exists(p):
                item.sidecar=collection.get_relpath(p)
    if check_for_sidecar and 'sidecar' in item.__dict__:
        if os.path.exists(collection.get_path(item.sidecar)):
            result=metadata.load_sidecar(item,collection.get_path(item.sidecar),missing_only)
            if get_thumbnail:
                metadata.load_thumbnail(item,collection.get_path(item))
        else:
            del item.sidecar
            result=metadata.load_metadata(item,filename,get_thumbnail,missing_only)
    else:
        result=metadata.load_metadata(item,filename,get_thumbnail,missing_only)
    if result:
##PICKLED DICT
#        if isinstance(item.meta,dict):
#            item.meta=imageinfo.PickledDict(item.meta)
        if item.thumb and get_thumbnail:
            item.thumb=orient_pixbuf(item.thumb,item.meta)
        if collection is not None and notify_plugins and item.meta!=meta:
            pluginmanager.mgr.callback_collection('t_collection_item_metadata_changed',collection,item,meta)
    return result


def save_metadata(item,collection,cache=None,sidecar_on_failure=True):
    '''
    save the writable key values in item.meta to the image (translating picty native keys to IPTC/XMP/Exif standard keys as necessary)
    '''
    fname=collection.get_path(item)
    if 'sidecar' in item.__dict__:
        if os.path.exists(collection.get_path(item.sidecar)):
            result = metadata.save_sidecar(item,collection.get_path(item.sidecar))
        else:
            del item.sidecar
            result = metadata.save_metadata(item,fname)
    else:
        result = metadata.save_metadata(item,fname)
    if result:
        item.mtime=io.get_mtime(fname) ##todo: this and the next line should be a method of the image class
        update_thumb_date(item,collection,cache)
        return True
    else:
        if sidecar_on_failure and 'sidecar' not in item.__dict__:
            item.sidecar=item.uid + '.xmp'
            metadata.create_sidecar(item,collection.get_path(item),collection.get_path(item.sidecar))
            return metadata.save_sidecar(item,collection.get_path(item.sidecar))
    return False


def save_metadata_key(item,collection,key,value,cache=None):
    '''
    sets the metadata key to value and saves the change in the image
    '''
    fname=collection.get_path(item)
    if metadata.save_metadata_key(fname,key,value):
        item.mtime=io.get_mtime(fname)
        update_thumb_date(item,collection,cache)
        return True
    return False



def scale_pixbuf(pixbuf,size): #todo: rename this scale_and_square_pixbuf
    '''
    returns a copy of the pixbuf scaled down to the integer size, and makes the image square, cropping as necessary
    '''
    tw=pixbuf.get_width()
    th=pixbuf.get_height()
    dest=pixbuf.copy()
    dest_x=0
    dest_y=0
    if tw>th:
        h=size
        w=tw*size/th
        dest_x=(w-h)/2
    else:
        w=size
        h=th*size/tw
        dest_y=(h-w)/2
    pb=pixbuf.scale_simple(w,h, gtk.gdk.INTERP_BILINEAR)
    pb_square=pb.subpixbuf(dest_x,dest_y,size,size)
    return pb_square

def orient_pixbuf(pixbuf,meta):
    '''
    returns a rotated copy of the pixbuf based on the value of the 'Orientation' metadata key in meta
    '''
    try:
        orient=meta['Orientation']
    except:
        orient=1
    if orient>1:
        method=transposemethods_pb[orient]
        if method[0]!=None:
            pixbuf=pixbuf.flip(method[0])
        pixbuf=pixbuf.rotate_simple(method[1])
    return pixbuf


def small_pixbuf(pixbuf):
    '''
    create a scaled down version of a gdk pixbuf (same proportions, twice standard menu icon size)
    '''
    width,height=gtk.icon_size_lookup(gtk.ICON_SIZE_MENU)
    width=width*2
    height=height*2
    tw=pixbuf.get_width()
    th=pixbuf.get_height()
    if width/height>tw/th:
        width=height*tw/th
    else:
        height=width*th/tw
    return pixbuf.scale_simple(width,height,gtk.gdk.INTERP_BILINEAR)



def cache_image(item):
    '''
    append the item to the list of items with images kept in memory. drops first added thumbs once the max queue length is exceeded (settings.max_memimages)
    '''
    memimages.append(item)
    if len(memimages)>settings.max_memimages:
        olditem=memimages.pop(0)
        if olditem!=item:
            olditem.image=None
            olditem.qview=None


def cache_thumb(item):
    '''
    append the item to the list of items with thumbs kept in memory. drops first added thumbs once the max queue length is exceeded (settings.max_memthumbs)
    '''
    memthumbs.append(item)
    if len(memthumbs)>settings.max_memthumbs:
        olditem=memthumbs.pop(0)
        olditem.thumb=None


def get_jpeg_or_png_image_file(item,collection,size,strip_metadata,filename=''):
    '''
    writes a temporary copy of the image to disk
    '''
    import tempfile
    itemfile=None
    if not filename:
        itemfile=collection.get_path(item)
        filename=itemfile
    src_filename=filename
    try:
        image=Image.open(filename)
    except:
        try:
            cmd=settings.dcraw_cmd%(filename,)
            imdata=os.popen(cmd).read()
            if not imdata or len(imdata)<100:
                cmd=settings.dcraw_backup_cmd%(filename,)
                imdata=os.popen(cmd).read()
                if not interrupt_fn():
                    return False
            p = ImageFile.Parser()
            p.feed(imdata)
            image = p.close()
            h,filename=tempfile.mkstemp('.jpg')
        except:
            return None
    if size:
        size=tuple(int(dim) for dim in size.split('x'))
        if len(size)>0 and size[0]>0 and size[1]>0:
            image.thumbnail(size,Image.ANTIALIAS)
            if itemfile==filename:
                h,filename=tempfile.mkstemp('.jpg')
    if image.format not in ['JPEG','PNG']:
        if itemfile==filename:
            h,filename=tempfile.mkstemp('.jpg')
    if strip_metadata:
        if itemfile==filename:
            h,filename=tempfile.mkstemp('.jpg')
    if filename!=src_filename:
        if strip_metadata:
            image=orient_image(image,item.meta)
        image.save(filename,quality=95)
        if not strip_metadata:
            metadata.copy_metadata(item.meta,src_filename,filename)
    return filename ##todo: potentially insecure because the reference to the file handle gets dropped


def orient_image(image,meta):
    '''
    returns a rotated copy of the PIL image based on the value of the 'Orientation' metadata key in meta
    '''
    try:
        orient=meta['Orientation']
    except:
        orient=1
    if orient>1:
        for method in transposemethods[orient]:
            image=image.transpose(method)
    return image

class ImageTransformer:
    '''
    Helper class for applying a sequence of transformations to an image
    '''
    def __init__(self):
        self.transform_handlers = {}
        self.tlock=threading.Lock() #transform lock -- main thread should acquire lock before call register_ or deregister_transform

    def register_transform(self,name,callback):
        '''
        register a transform with name and a callback
        '''
        self.tlock.acquire()
        self.transform_handlers[name] = callback
        self.tlock.release()

    def deregister_transform(self,name):
        '''
        remove a registered transform by name
        '''
        self.tlock.acquire()
        try:
            del self.transform_handlers[name]
            self.tlock.release()
            return True
        except:
            self.tlock.release()
            return False

    def apply_transforms(self,item,interrupt_cb):
        '''
        perform image transform operatiosn specified in the metadata on the
        PIL image member of item (i.e. item.image)
        transform_handlers is a dictionary containing name callbacks to perform the operations
        interrupt_cb is a function that returns True if processing should be aborted
        TODO: On long running operations it would be good to provide the user with progress feedback
        '''
        if item.meta==None or 'ImageTransforms' not in item.meta:
            return True
        transforms = item.meta['ImageTransforms']
        if len(transforms)>0 and 'original_image' not in item.__dict__:
            item.original_image = item.image.copy()
        self.tlock.acquire()
        for instruction,params in transforms:
            try:
                self.transform_handlers[instruction](item,params) #todo: should pass the interrupt_cb as well
            except:
                import sys
                import traceback
                print 'Error Applying Transform to Image',item,instruction,params
                tb_text=traceback.format_exc(sys.exc_info()[2])
                print tb_text
            if not interrupt_cb():
                self.tlock.release()
                return False
        self.tlock.release()
        return True

    def get_transforms(self,item):
        try:
            return item.meta['ImageTransforms']
        except:
            return []

    def get_transform(self,item,index):
        return item.meta['ImageTransforms'][index]

    def get_n_transforms(self,item):
        return len(get_transforms(item))

    def add_transform(self,item,name,params,collection=None):
        self.tlock.acquire()
        transforms = self.get_transforms(item)[:]
        transforms.append([name,params])
        item.set_meta_key('ImageTransforms',transforms,collection)
        self.tlock.release()
        return True

    def replace_transform(self,item,index,name,params,collection=None):
        self.tlock.acquire()
        transforms = self.get_transforms(item)[:][index] = [name,params]
        item.set_meta_key('ImageTransforms',transforms,collection)
        self.tlock.release()
        return True

    def remove_transform(self,item,index,collection=None):
        self.tlock.acquire()
        try:
            transforms = item.get_transforms(item)[:]
            del transforms['ImageTransforms'][index]
            item.set_meta_key('ImageTransforms',transforms,collection)
        except:
            self.tlock.release()
            return False
        self.tlock.release()
        return True

transformer = ImageTransformer()


def load_image(item,collection,interrupt_fn,draft_mode=False,apply_transforms=True):
    '''
    load a PIL image and store it in item.image
    if transform_handlers are specified and the image has tranforms they will be applied
    '''
    itemfile=collection.get_path(item)
    mimetype=io.get_mime_type(itemfile)
    oriented=False
    try:
        ##todo: load by mimetype (after porting to gio)
#        non-parsed version
        if 'original_image' in item.__dict__:
            image=item.original_image.copy()
        else:
            if not mimetype.startswith('image'):
                print 'No image available for item',item,'with mimetype',mimetype
                item.image=False
                return False
            print 'Loading Image:',item,mimetype
            if io.get_mime_type(itemfile) in settings.raw_image_types: ##for extraction with dcraw
                raise TypeError
            image=Image.open(itemfile) ## retain this call even in the parsed version to avoid lengthy delays on raw images (since this call trips the exception)
    #        parsed version
            if not draft_mode and image.format=='JPEG':
                #parser doesn't seem to work correctly on anything but JPEGs
                f=open(itemfile,'rb')
                imdata=f.read(10000)
                p = ImageFile.Parser()
                while imdata and len(imdata)>0:
                    p.feed(imdata)
                    if not interrupt_fn():
                        return False
                    imdata=f.read(10000)
                f.close()
                image = p.close()
                print 'Parsed image with PIL'
            else:
                raise TypeError
    except:
        try:
            if mimetype in gdk_mime_types:
                image_pb=gtk.gdk.pixbuf_new_from_file(itemfile)
                image_pb=orient_pixbuf(image_pb,item.meta)
                oriented=True
                width,height = image_pb.get_width(),image_pb.get_height()
                image=Image.fromstring("RGB",(width,height),image_pb.get_pixels() ) ##TODO: What about RGBA and grey scale images?
                print 'Parsed image with GDK'
            else:
                if mimetype in settings.raw_image_types:
                    cmd=settings.raw_image_types[mimetype][0]%(itemfile,)
                else:
                    cmd=settings.dcraw_cmd%(itemfile,)
                imdata=os.popen(cmd).read()
                if not imdata or len(imdata)<100:
                    cmd=settings.dcraw_backup_cmd%(itemfile,)
                    oriented=True
                    imdata=os.popen(cmd).read()
                    if not interrupt_fn():
                        return False
                p = ImageFile.Parser()
                p.feed(imdata)
                image = p.close()
                print 'Parsed image with DCRAW'
        except:
            import sys
            import traceback
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print 'Error Loading Image',item,mimetype
            print tb_text
            item.image=False
            return False
    print item.meta
    if draft_mode:
        image.draft(image.mode,(1024,1024)) ##todo: pull size from screen resolution
    if not interrupt_fn():
        return
    if oriented:
        item.image=orient_image(image,{})
    else:
        item.image=orient_image(image,item.meta)
    try:
        item.imagergba='A' in item.image.getbands()
    except:
        item.imagergba=False
    if item.image:
        if apply_transforms!=None:
            transformer.apply_transforms(item,interrupt_fn)
        cache_image(item)
        return True
    return False


def free_image(item):
    if 'image' in item:
        del item.image
    if 'original_image' in item:
        del item.original_image
    if 'qview' in item:
        del item.qview


def image_to_pixbuf(im):
    '''
    convert a PIL image to a gdk pixbuf
    '''
    bands=im.getbands()
    rgba = True if 'A' in bands else False
    pixbuf=None
    w,h=im.size
    if 'R' in bands and 'G' in bands and 'B' in bands:
        pixbuf=gtk.gdk.pixbuf_new_from_data(im.tostring(), gtk.gdk.COLORSPACE_RGB, rgba, 8, w, h, w*(3+rgba))
    if 'P' in bands:
        fmt="gif"
        file1 = StringIO.StringIO()
        im.save(file1, fmt)
        contents = file1.getvalue()
        file1.close()
        loader = gtk.gdk.PixbufLoader(fmt)
        loader.write(contents, len(contents))
        pixbuf = loader.get_pixbuf()
        loader.close()
    return pixbuf


def size_image(item,size,antialias=False,zoom='fit'): ##todo: rename as size image to view (maybe abstract the common features)
    '''
    resize the fullsize PIL Image item.image and return the result in item.qview
    '''
    image=item.image
    if not image:
        return False
    if zoom=='fit':
        (w,h)=size
        (iw,ih)=image.size
        if w<iw or h<ih:
            if (w*h*iw*ih)==0:
                return False
            if 1.0*(w*ih)/(h*iw)>1.0:
                w=h*iw/ih
            else:
                h=w*ih/iw
            if (w*h*iw*ih)==0:
                return False
        else:
            image.load()
            item.qview=image_to_pixbuf(image)
            return True
    else:
        (iw,ih)=image.size
        w=int(zoom*iw) ##todo: or is it divide??
        h=int(zoom*ih)

    t=time.time()
    try:
        if antialias:
            print 'antialiasing'
            qimage=image.resize((w,h),Image.ANTIALIAS) ##Image.BILINEAR
        else:
            qimage=image.resize((w,h),Image.BILINEAR) ##Image.BILINEAR
    except:
        qimage=None
    print 'resize time',time.time()-t
    if qimage:
        item.qview=image_to_pixbuf(qimage)
    return False


def has_thumb(item,collection,cache=None):
    '''
    returns true if the item has a thumbnail image in the cache
    '''
    fname=collection.get_path(item)
    if item.thumburi and os.path.exists(item.thumburi):
        return True
    if cache==None:
        uri = io.get_uri(fname)
        item.thumburi=thumb_factory.lookup(uri,int(item.mtime))
        if item.thumburi:
            return True
        if thumb_factory_large.lookup(uri,int(item.mtime)):
            return True
    else:
        thumburi=os.path.join(cache,muuid(item.uid+str(int(item.mtime))))+'.png'
        if os.path.exists(thumburi):
            item.thumburi = thumburi
            return True
    return False

def delete_thumb(item):
    '''
    remove the thumb from the item and delete the associated thumbnail image file in the cache
    '''
    if item.thumb:
        item.thumb=None
    if item.thumburi:
        io.remove_file(item.thumburi) ##TODO: What if item is in gnome cache? (This will probably work, but maybe not the best way to remove items from cache?) commented code below doesn't look right (deleting twice?)
##        thumburi=thumb_factory.lookup(uri,int(item.mtime))
##        os.remove(thumburi)
        item.thumburi=None


def update_thumb_date(item,collection,cache=None,interrupt_fn=None,remove_old=True):
    '''
    sets the internal date of the cached thumbnail image to that of the image file
    if the thumbnail name the thumbnail name will be updated
    if no thumbnail is present it will be created
    interrupt_fn - callback that returns False if job should be interrupted
    remove_old - if the item name has changed, removes the old thumbnail
    affects mtime, thumb, thumburi members of item
    '''
    itemfile=collection.get_path(item)
    item.mtime=io.get_mtime(itemfile)
    if item.thumburi:
        oldthumburi=item.thumburi
        if not item.thumb:
            load_thumb(item,collection)
        uri = io.get_uri(itemfile)
        if cache==None:
            thumb_factory.save_thumbnail(item.thumb,uri,int(item.mtime))
            item.thumburi=thumb_factory.lookup(uri,int(item.mtime))
        else:
            if not os.path.exists(cache):
                os.makedirs(cache)
            item.thumburi=os.path.join(cache,muuid(item.uid+str(int(item.mtime))))+'.png'
            item.thumb.save(item.thumburi,"png")
        if remove_old and oldthumburi!=item.thumburi:
            io.remove_file(oldthumburi)
        return True
    return make_thumb(item,collection,interrupt_fn,cache=cache)



def rotate_thumb(item,right=True,interrupt_fn=None):
    '''
    rotates thumbnail of item 90 degrees right (clockwise) or left (anti-clockwise)
    right - rotate right if True else left
    interrupt_fn - callback that returns False if job should be interrupted
    '''
    if item.thumburi:
        try:
            image=Image.open(item.thumburi)
            if right:
                image=image.transpose(Image.ROTATE_270)
            else:
                image=image.transpose(Image.ROTATE_90)
            thumbsize=image.size
            thumbrgba='A' in image.getbands()
            width=thumbsize[0]
            height=thumbsize[1]
            thumb_pb=gtk.gdk.pixbuf_new_from_data(data=image.tostring(), colorspace=gtk.gdk.COLORSPACE_RGB, has_alpha=thumbrgba, bits_per_sample=8, width=width, height=height, rowstride=width*(3+thumbrgba)) #last arg is rowstride
            return thumb_pb
        except:
            return False
    return False

gdk_mime_types=set([m for n in gtk.gdk.pixbuf_get_formats() for m in n['mime_types']])

def make_thumb(item,collection,interrupt_fn=None,force=False,cache=None):
    '''
    create a thumbnail from the original image using either PIL or dcraw
    interrupt_fn = callback that returns False if routine should cancel (not implemented)
    force = True if thumbnail should be recreated even if already present
    affects thumb, thumburi members of item
    '''
    itemfile=collection.get_path(item)
    thumb_pb=None
    if cache==None and thumb_factory.has_valid_failed_thumbnail(itemfile,int(item.mtime)):
        if not force:
            item.thumb=False
            return False
        print 'Forcing thumbnail creation'
        uri = io.get_uri(itemfile)
        thumb_uri=thumb_factory.lookup(uri,int(item.mtime))
        if thumb_uri:
            os.remove(thumb_uri)
    if not force and item.thumb==False:
        return False
    delete_thumb(item)
    ##todo: could also try extracting the thumb from the image (essential for raw files)
    ## would not need to make the thumb in that case
    print 'Creating thumbnail for',item.uid,itemfile
    t=time.time()
    try:
        uri = io.get_uri(itemfile)
        mimetype=io.get_mime_type(itemfile)
        thumb_pb=None
        if mimetype.lower().startswith('video'):
            cmd=settings.video_thumbnailer%(itemfile,)
            imdata=os.popen(cmd).read()
            image=Image.open(StringIO.StringIO(imdata))
            image.thumbnail((128,128),Image.ANTIALIAS) ##TODO: this is INSANELY slow -- find out why
        else:
            try:
                mime=io.get_mime_type(itemfile)
                if mime in gdk_mime_types:
                    thumb_pb=gtk.gdk.pixbuf_new_from_file_at_size(itemfile,128,128)
                    thumb_pb=orient_pixbuf(thumb_pb,item.meta)
                    image=None
                    print 'Opened with GDK'
                else:
                    image=Image.open(itemfile)
                    image.thumbnail((128,128),Image.ANTIALIAS)
                    print 'Opened with PIL'
            except:
                cmd=settings.dcraw_cmd%(itemfile,)
                imdata=os.popen(cmd).read()
                if not imdata or len(imdata)<100:
                    cmd=settings.dcraw_backup_cmd%(itemfile,)
                    imdata=os.popen(cmd).read()
#                pipe = subprocess.Popen(cmd, shell=True,
#                        stdout=PIPE) ##, close_fds=True
#                print pipe
#                pipe=pipe.stdout
#                print 'pipe opened'
#                imdata=pipe.read()
#                print 'pipe read'
                p = ImageFile.Parser()
                p.feed(imdata)
                image = p.close()
                image.thumbnail((128,128),Image.ANTIALIAS) ##TODO: this is INSANELY slow -- find out why
                image=orient_image(image,item.meta)
                print 'Opened with DCRAW'
        if image is not None:
            thumb_pb=image_to_pixbuf(image)
        if thumb_pb is None:
            raise TypeError
    except:
        item.thumb=False
        item.thumburi=None
        if cache==None:
            thumb_factory.create_failed_thumbnail(itemfile,int(item.mtime))
        print 'Error creating thumbnail for',item
        import sys
        import traceback
        tb_text=traceback.format_exc(sys.exc_info()[2])
        print tb_text
        return False
    width=thumb_pb.get_width()
    height=thumb_pb.get_height()
    uri = io.get_uri(itemfile)
    #save the new thumbnail
    try:
        if cache==None:
            thumb_factory.save_thumbnail(thumb_pb,uri,int(item.mtime))
            item.thumburi=thumb_factory.lookup(uri,int(item.mtime))
        else:
            if not os.path.exists(cache):
                os.makedirs(cache)
            item.thumburi=os.path.join(cache,muuid(item.uid+str(int(item.mtime))))+'.png'
            thumb_pb.save(item.thumburi,"png")
    except:
        print 'Error writing thumbnnail for',item
        import sys
        import traceback
        tb_text=traceback.format_exc(sys.exc_info()[2])
        print tb_text
        item.thumb=False
        item.thumburi=None
        if cache==None:
            thumb_factory.create_failed_thumbnail(itemfile,int(item.mtime))
        return False
    item.thumb=thumb_pb
    cache_thumb(item)
    return True


def load_thumb_from_preview_icon(item,collection):
    '''
    try to load a thumbnail embbeded in a picture using gio provided method g_preview_icon_data
    affects thumb member of item
    '''
    try:
        itemfile=collection.get_path(item)
        print 'loading thumb from preview icon',item.uid
        data,dtype=io.get_preview_icon_data(itemfile)
        loader = gtk.gdk.PixbufLoader()
        loader.write(data.read())
        pb = loader.get_pixbuf()
        loader.close()
        w=pb.get_width()
        h=pb.get_height()
        a=max(128,w,h) ##todo: remove hardcoded sizes
        item.thumb=pb.scale_simple(128*w/a,128*h/a,gtk.gdk.INTERP_BILINEAR)
        return True
    except:
        import sys
        import traceback
        tb_text=traceback.format_exc(sys.exc_info()[2])
        print 'Error loading thumb from preview icon',item.uid
        print tb_text
        item.thumb=None
        return False

def load_embedded_thumb(item,collection):
    if metadata.load_thumbnail(item,collection.get_path(item)):
        item.thumb=orient_pixbuf(item.thumb,item.meta)
        return True
    return False

def load_thumb(item,collection,cache=None):
    '''
    load thumbnail from a cache location (optionally using the
    thumbnailing methods provieded in gnome.ui if cache is None)
    affects thumbnail, thumburi members of item
    '''
    ##todo: rename load_thumb_from_cache
    ##note that loading thumbs embedded in image files is handled in load_thumb_from_preview_icon and load_metadata
    if item.thumb==False:
        return False
    image=None
    try:
        if item.thumburi:
            image=gtk.gdk.pixbuf_new_from_file(item.thumburi)
            s=(image.get_width(),image.get_height())
            if s[0]>128 or s[1]>128:
                m=max(s)
                w=s[0]*128/m
                h=s[1]*128/m
                image=image.scale_simple(w,h,gtk.gdk.INTERP_BILINEAR) #todo: doesn't this distort non-square images?
        else:
            if cache!=None:
                thumburi=os.path.join(cache,muuid(item.uid+str(int(item.mtime))))+'.png'
                if os.path.exists(thumburi):
                    item.thumburi=thumburi
            elif collection.local_filesystem:
                itemfile=collection.get_path(item)
                uri = io.get_uri(itemfile)
                item.thumburi=thumb_factory.lookup(uri,int(item.mtime))
                if not item.thumburi:
                    thumburi=thumb_factory_large.lookup(uri,int(item.mtime))
            if thumburi:
                image = Image.open(thumburi)
                image.thumbnail((128,128))
                image=image_to_pixbuf(image) #todo: not sure this works (maybe because thumbnail doesn't finalize data?)
            elif item.thumburi:
                image=gtk.gdk.pixbuf_new_from_file(item.thumburi)
                image=image.scale_simple(128,128, gtk.gdk.INTERP_BILINEAR) #todo: doesn't this distort non-square images?
    except:
        image=None
    if image is not None:
        item.thumb=image
        cache_thumb(item)
        return True
    else:
        return False
