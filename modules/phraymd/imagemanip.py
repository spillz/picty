'''

    phraymd
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

import gnome.ui
import gtk

import StringIO
import Image
import ImageFile
import metadata
import datetime
import bisect
import os.path
import os

import settings
import imageinfo
import io
import pluginmanager

##todo: move to imagemanip to eliminate the Image dependency
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


thumb_factory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_NORMAL)
thumb_factory_large = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_LARGE)

import time

##global ram cache for images and thumbs
memimages=[]
memthumbs=[]

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


def load_metadata(item,collection=None,filename=None,get_thumbnail=False):
    if item.meta:
        meta=item.meta.copy()
    else:
        meta=item.meta
    result=metadata.load_metadata(item,filename,get_thumbnail)
    if result:
        if isinstance(item.meta,dict):
            item.meta=imageinfo.PickledDict(item.meta)
        if item.thumb and get_thumbnail:
            item.thumb=orient_pixbuf(item.thumb,item.meta)
        if collection!=None and item.meta!=meta:
            pluginmanager.mgr.callback_collection('t_collection_item_metadata_changed',collection,item,meta)
    return result

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
    rotate_thumb(item,False)


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
    rotate_thumb(item,True) ##TODO: If this fails, should revert orientation



def save_metadata(item):
    '''
    save the writable key values in item.meta to the image (translating phraymd native keys to IPTC/XMP/Exif standard keys as necessary)
    '''
    if metadata.save_metadata(item):
        item.mtime=io.get_mtime(item.filename) ##todo: this and the next line should be a method of the image class
        update_thumb_date(item)
        return True
    return False


def save_metadata_key(item,key,value):
    '''
    sets the metadata key to value and saves the change in the image
    '''
    if metadata.save_metadata_key(item,key,value):
        item.mtime=io.get_mtime(item.filename)
        update_thumb_date(item)
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


def get_jpeg_or_png_image_file(item,size,strip_metadata):
    '''
    writes a temporary copy of the image to disk
    '''
    import tempfile
    filename=item.filename
    try:
        image=Image.open(item.filename)
    except:
        try:
            cmd=settings.dcraw_cmd%(item.filename,)
            imdata=os.popen(cmd).read()
            if not imdata or len(imdata)<100:
                cmd=settings.dcraw_backup_cmd%(item.filename,)
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
            if item.filename==filename:
                h,filename=tempfile.mkstemp('.jpg')
    if image.format not in ['JPEG','PNG']:
        if item.filename==filename:
            h,filename=tempfile.mkstemp('.jpg')
    if strip_metadata:
        if item.filename==filename:
            h,filename=tempfile.mkstemp('.jpg')
    if filename!=item.filename:
        if strip_metadata:
            image=orient_image(image,item.meta)
        image.save(filename,quality=95)
        if not strip_metadata:
            metadata.copy_metadata(item,filename)
    return filename ##todo: potentially insecure because the reference to the file handle gets dropped


def load_image(item,interrupt_fn,draft_mode=False):
    '''
    load a PIL image and store it in item.image
    '''
    try:
        ##todo: load by mimetype (after porting to gio)
#        non-parsed version
        if io.get_mime_type(item.filename)=='image/x-adobe-dng': ##for extraction with dcraw
            raise TypeError
        image=Image.open(item.filename) ## retain this call even in the parsed version to avoid lengthy delays on raw images (since this call trips the exception)
        print 'opened image',item.filename,image
#        parsed version
        if not draft_mode and image.format=='JPEG':
            #parser doesn't seem to work correctly on anything but JPEGs
            f=open(item.filename,'rb')
            imdata=f.read(10000)
            p = ImageFile.Parser()
            while imdata and len(imdata)>0:
                p.feed(imdata)
                if not interrupt_fn():
                    return False
                imdata=f.read(10000)
            f.close()
            image = p.close()
            print 'parsed image with PIL'
    except:
        try:
            cmd=settings.dcraw_cmd%(item.filename,)
            imdata=os.popen(cmd).read()
            if not imdata or len(imdata)<100:
                cmd=settings.dcraw_backup_cmd%(item.filename,)
                imdata=os.popen(cmd).read()
                if not interrupt_fn():
                    return False
            p = ImageFile.Parser()
            p.feed(imdata)
            image = p.close()
            print 'parsed image with DCRAW'
        except:
            item.image=False
            return False
    if draft_mode:
        image.draft(image.mode,(1024,1024)) ##todo: pull size from screen resolution
    if interrupt_fn():
        item.image=orient_image(image,item.meta)
    try:
        item.imagergba='A' in item.image.getbands()
    except:
        item.imagergba=False
    if item.image:
        cache_image(item)
        return True
    return False


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
        w=zoom*iw ##todo: or is it divide??
        h=zoom*ih

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


def has_thumb(item):
    '''
    returns true if the item has a thumbnail image in the cache
    '''
    if item.thumburi and os.path.exists(item.thumburi):
        return True
    if not settings.maemo:
        uri = io.get_uri(item.filename)
        item.thumburi=thumb_factory.lookup(uri,int(item.mtime))
        if item.thumburi:
            return True
        if thumb_factory_large.lookup(uri,int(item.mtime)):
            return True
    return False

def delete_thumb(item):
    '''
    remove the thumb from the item and delete the associated thumbnail image file in the cache
    '''
    if item.thumb:
        item.thumb=None
    if item.thumburi:
        os.remove(item.thumburi)
        thumburi=thumb_factory.lookup(uri,int(item.mtime))
        os.remove(thumburi)
        item.thumburi=None


def update_thumb_date(item,interrupt_fn=None,remove_old=True):
    '''
    sets the internal date of the cached thumbnail image to that of the image file
    if the thumbnail name the thumbnail name will be updated
    if no thumbnail is present it will be create
    interrupt_fn - callback that returns False if job should be interrupted
    remove_old - if the item name has changed, removes the old thumbnail
    affects mtime, thumb, thumburi members of item
    '''
    item.mtime=io.get_mtime(item.filename)
    if item.thumburi:
        oldthumburi=item.thumburi
        if not item.thumb:
            load_thumb(item)
        uri = io.get_uri(item.filename)
        thumb_factory.save_thumbnail(item.thumb,uri,int(item.mtime))
        item.thumburi=thumb_factory.lookup(uri,int(item.mtime))
        if remove_old and oldthumburi!=item.thumburi:
            io.remove_file(oldthumburi)
        return True
    return make_thumb(item,interrupt_fn)



def rotate_thumb(item,right=True,interrupt_fn=None):
    '''
    rotates thumbnail of item 90 degrees right (clockwise) or left (anti-clockwise)
    right - rotate right if True else left
    interrupt_fn - callback that returns False if job should be interrupted
    '''
    if thumb_factory.has_valid_failed_thumbnail(item.filename,int(item.mtime)):
        return False
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
            width=thumb_pb.get_width()
            height=thumb_pb.get_height()
            uri = io.get_uri(item.filename)
            thumb_factory.save_thumbnail(thumb_pb,uri,int(item.mtime))
            item.thumburi=thumb_factory.lookup(uri,int(item.mtime))
            if item.thumb:
                item.thumb=thumb_pb
                cache_thumb(item)
            return True
        except:
            return False
    return False



def make_thumb(item,interrupt_fn=None,force=False):
    '''
    create a thumbnail from the original image using either PIL or dcraw
    interrupt_fn = callback that returns False if routine should cancel (not implemented)
    force = True if thumbnail should be recreated even if already present
    affects thumb, thumburi members of item
    '''
    if thumb_factory.has_valid_failed_thumbnail(item.filename,int(item.mtime)):
        if not force:
            item.thumb=False
            return
        print 'forcing thumbnail creation'
        uri = io.get_uri(item.filename)
        thumb_uri=thumb_factory.lookup(uri,int(item.mtime))
        if thumb_uri:
            print 'removing failed thumb',thumb_uri
            os.remove(thumb_uri)
    ##todo: could also try extracting the thumb from the image (essential for raw files)
    ## would not need to make the thumb in that case
    print 'MAKING THUMB FOR',item.filename
    t=time.time()
    try:
        uri = io.get_uri(item.filename)
        mimetype=io.get_mime_type(item.filename)
        thumb_pb=None
#        thumb_pb=thumb_factory.generate_thumbnail(uri,mimetype)
        if mimetype.lower().startswith('video'):
            cmd=settings.video_thumbnailer%(item.filename,)
            imdata=os.popen(cmd).read()
            image=Image.open(StringIO.StringIO(imdata))
#                p = ImageFile.Parser()
#                p.feed(imdata)
#                image = p.close()
            image.thumbnail((128,128),Image.ANTIALIAS) ##TODO: this is INSANELY slow -- find out why
        else:
            try:
                image=Image.open(item.filename)
                image.thumbnail((128,128),Image.ANTIALIAS)
            except:
                cmd=settings.dcraw_cmd%(item.filename,)
                imdata=os.popen(cmd).read()
                if not imdata or len(imdata)<100:
                    cmd=settings.dcraw_backup_cmd%(item.filename,)
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
        thumbsize=image.size
        thumb_pb=image_to_pixbuf(image)
        if thumb_pb==None:
            raise TypeError
    except:
        print 'creating FAILED thumbnail',item
        item.thumb=False
        thumb_factory.create_failed_thumbnail(item.filename,int(item.mtime))
        return False
    width=thumb_pb.get_width()
    height=thumb_pb.get_height()
    uri = io.get_uri(item.filename)
    thumb_factory.save_thumbnail(thumb_pb,uri,int(item.mtime))
    item.thumburi=thumb_factory.lookup(uri,int(item.mtime))
    item.thumb=thumb_pb
    cache_thumb(item)
    return True


def load_thumb_from_preview_icon(item):
    '''
    try to load a thumbnail embbeded in a picture using gio provided method g_preview_icon_data
    affects thumb member of item
    '''
    try:
        print 'loading thumb from preview icon',item.filename
        data,dtype=io.get_preview_icon_data(item.filename)
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
        print 'Error loading thumb from preview icon',item.filename
        print tb_text
        item.thumb=None
        return False

def load_thumb(item):
    '''
    load thumbnail from a cache location (currently using the thumbnailing methods provieded in gnome.ui)
    affects thumbnail, thumburi members of item
    '''
    ##todo: could also try extracting the thumb from the image
    ## would not need to make the thumb in that case
    image=None
    try:
        if settings.maemo:
            image = Image.open(item.filename)
            image.thumbnail((128,128))
        else:
            uri = io.get_uri(item.filename)
            if not item.thumburi:
                item.thumburi=thumb_factory.lookup(uri,int(item.mtime))
            if item.thumburi:
                image=gtk.gdk.pixbuf_new_from_file(item.thumburi)
                s=(image.get_width(),image.get_height())
                #image.thumbnail((128,128))
            else:
                thumburi=thumb_factory_large.lookup(uri,int(item.mtime))
                if thumburi:
                    try:
                        image = Image.open(thumburi)
                        image.thumbnail((128,128))
                        image=image_to_pixbuf(image) #todo: not sure this works (maybe because thumbnail doesn't finalize data?)
                    except:
                        image=gtk.gdk.pixbuf_new_from_file(item.thumburi)
                        image=image.scale_simple(128,128, gtk.gdk.INTERP_BILINEAR) #todo: doesn't this distort non-square images?
#                    item.thumburi=thumburi
    except:
        image=None
    if image!=None:
        item.thumb=image
        cache_thumb(item)
        return True
    else:
        item.thumburi=None
        item.thumb=None
        return False
#        item.thumbrgba='A' in image.getbands()
