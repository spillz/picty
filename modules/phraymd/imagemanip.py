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

rotate_right_tx={1:6,2:5,3:8,4:7,5:4,6:3,7:2,8:1}

rotate_left_tx={1:8,2:7,3:6,4:5,5:2,6:1,7:4,8:3}


thumb_factory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_NORMAL)
thumb_factory_large = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_LARGE)

import time

##global ram cache for images and thumbs
memimages=[]
memthumbs=[]


def load_metadata(item,collection=None,filename=None,get_thumbnail=False):
    if collection:
        if item.meta:
            meta=item.meta.copy()
        else:
            meta=item.meta
        result=metadata.load_metadata(item,filename,get_thumbnail)
        if result:
            if get_thumbnail:
                item.thumb=orient_pixbuf(item.thumb,item.meta)
                item.thumbsize=(item.thumb.get_width(),item.thumb.get_height())
            if item.meta!=meta:
                pluginmanager.mgr.callback_collection('t_collection_item_metadata_changed',collection,item,meta)
        return result
    else:
        return metadata.load_metadata(item,filename)

def rotate_left(item,collection=None):
    'rotates image anti-clockwise'
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
    'rotates image clockwise'
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
    if metadata.save_metadata(item):
        update_thumb_date(item)
        return True
    return False


def save_metadata_key(item,key,value):
    if metadata.save_metadata_key(item,key,value):
        update_thumb_date(item)
        return True
    return False



def scale_pixbuf(pixbuf,size):
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
    try:
        orient=meta['Orientation']
    except:
        orient=1
    if orient>1:
        for method in transposemethods[orient]:
            pixbuf=pixbuf.transpose(method)
    return pixbuf


def small_pixbuf(pixbuf):
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
    memimages.append(item)
    if len(memimages)>settings.max_memimages:
        olditem=memimages.pop(0)
        if olditem!=item:
            olditem.image=None
            olditem.qview_size=(0,0)
            olditem.qview=None


def cache_thumb(item):
    memthumbs.append(item)
    if len(memthumbs)>settings.max_memthumbs:
        olditem=memthumbs.pop(0)
        olditem.thumbsize=(0,0)
        olditem.thumb=None


def get_jpeg_or_png_image_file(item,size,strip_metadata):
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
            image=orient_pixbuf(image,item.meta)
        image.save(filename,quality=95)
        if not strip_metadata:
            metadata.copy_metadata(item,filename)
    return filename


def load_image(item,interrupt_fn,draft_mode=False):
    try:
        ##todo: load by mimetype (after porting to gio)
#        non-parsed version
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
        item.image=orient_pixbuf(image,item.meta)
    try:
        item.imagergba='A' in item.image.getbands()
    except:
        item.imagergba=False
    if item.image:
        cache_image(item)
        return True
    return False


def image_to_pixbuf(im):
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



def size_image(item,size,antialias=False,zoom='fit'):
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
    if item.thumburi and os.path.exists(item.thumburi):
        return True
    if not settings.maemo:
        uri = io.get_uri(item.filename)
        item.thumburi=thumb_factory.lookup(uri,item.mtime)
        if item.thumburi:
            return True
        if thumb_factory_large.lookup(uri,item.mtime):
            return True
    return False

def delete_thumb(item):
    if item.thumb:
        item.thumb=None
        item.thumbsize=None
    if item.thumburi:
        os.remove(item.thumburi)
        thumburi=thumb_factory.lookup(uri,item.mtime)
        os.remove(thumburi)
        item.thumburi=None


def update_thumb_date(item,interrupt_fn=None,remove_old=True):
    item.mtime=io.get_mtime(item.filename)
    if item.thumburi:
        if not item.thumb:
            load_thumb(item)
        uri = io.get_uri(item.filename)
        thumb_factory.save_thumbnail(item.thumb,uri,item.mtime)
        if remove_old:
            io.remove_file(item.thumburi)
        item.thumburi=thumb_factory.lookup(uri,item.mtime)
        return True
    return make_thumb(item,interrupt_fn)



def rotate_thumb(item,right=True,interrupt_fn=None):
    if thumb_factory.has_valid_failed_thumbnail(item.filename,item.mtime):
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
            thumb_factory.save_thumbnail(thumb_pb,uri,item.mtime)
            item.thumburi=thumb_factory.lookup(uri,item.mtime)
            if item.thumb:
                item.thumbsize=(width,height)
                item.thumb=thumb_pb
                cache_thumb(item)
            return True
        except:
            return False
    return False



def make_thumb(item,interrupt_fn=None,force=False):
    if thumb_factory.has_valid_failed_thumbnail(item.filename,item.mtime):
        if not force:
            item.cannot_thumb=True
            return
        print 'forcing thumbnail creation'
        uri = io.get_uri(item.filename)
        thumb_uri=thumb_factory.lookup(uri,item.mtime)
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
            image=orient_pixbuf(image,item.meta)
        thumbsize=image.size
        thumb_pb=image_to_pixbuf(image)
        if thumb_pb==None:
            raise TypeError
    except:
        print 'creating FAILED thumbnail',item
        item.thumbsize=(0,0)
        item.thumb=None
        item.cannot_thumb=True ##TODO: check if this is used anywhere -- try to remove
        thumb_factory.create_failed_thumbnail(item.filename,item.mtime)
        return False
    width=thumb_pb.get_width()
    height=thumb_pb.get_height()
    uri = io.get_uri(item.filename)
    thumb_factory.save_thumbnail(thumb_pb,uri,item.mtime)
    item.thumburi=thumb_factory.lookup(uri,item.mtime)
    item.cannot_thumb=False
    item.thumbsize=(width,height)
    item.thumb=thumb_pb
    cache_thumb(item)
    return True


def load_thumb_from_preview_icon(item):
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
        item.thumbsize=(item.thumb.get_width(),item.thumb.get_height())
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
                item.thumburi=thumb_factory.lookup(uri,item.mtime)
            if item.thumburi:
                image=gtk.gdk.pixbuf_new_from_file(item.thumburi)
                s=(image.get_width(),image.get_height())
                #image.thumbnail((128,128))
            else:
                thumburi=thumb_factory_large.lookup(uri,item.mtime)
                if thumburi:
                    #print 'using large thumb'
                    image = Image.open(thumburi)
                    image.thumbnail((128,128))
                    image=gtk.gdk.pixbuf_new_from_data(image.tostring(), gtk.gdk.COLORSPACE_RGB, False, 8, image.size[0], image.size[1], 3*image.size[0])
                    #print 'full loading',fullpath
                    image=None
                    item.thumburi=thumburi
    except:
        image=None
    if image!=None:
        item.thumbsize=(image.get_width(),image.get_height())
        item.thumb=image
        cache_thumb(item)
        return True
    else:
        item.thumburi=None
        item.thumb=None
        return False
#        item.thumbrgba='A' in image.getbands()
