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

import gnomevfs
import gnome.ui
import gtk
import Image
import ImageFile
import exif
import pyexiv2
import datetime
import bisect
import settings
import imageinfo
import os.path
import os

thumb_factory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_NORMAL)
thumb_factory_large = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_LARGE)

import time

memimages=[]
memthumbs=[]

def rotate_left(item):
    'rotates image anti-clockwise'
    try:
        orient=item.meta['Orientation']
    except:
        orient=1
    if orient<1 or orient>8:
        print 'warning: invalid orientation',orient,'for image',item,'-- hardcoding to 1'
        orient=1
    item.set_meta_key('Orientation',settings.rotate_left_tx[orient])
    item.image=None
    item.qview=None
    item.thumb=None
    item.thumburi=None
    print 'rotate left',item,'from',orient,'to',settings.rotate_left_tx[orient]
    make_thumb(item)


def rotate_right(item):
    'rotates image clockwise'
    try:
        orient=item.meta['Orientation']
    except:
        orient=1
    if orient<1 or orient>8:
        print 'warning: invalid orientation',orient,'for image',item,'-- hardcoding to 1'
        orient=1
    item.set_meta_key('Orientation',settings.rotate_right_tx[orient])
    item.image=None
    item.qview=None
    item.thumb=None
    item.thumburi=None
    make_thumb(item)

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


def load_image(item,interrupt_fn):
    try:
        image=Image.open(item.filename)
    except:
        try:
            cmd=settings.dcraw_cmd%(item.filename,)
            imdata=os.popen(cmd).read()
            p = ImageFile.Parser()
            p.feed(imdata)
            image = p.close()
        except:
            image=None
            return False
    image.draft(image.mode,(1600,1600))
    if not interrupt_fn():
        print 'interrupted'
        return False
    try:
        orient=item.meta['Orientation']
    except:
        orient=1
    if orient>1:
        for method in settings.transposemethods[orient]:
            image=image.transpose(method)
            if not interrupt_fn():
                print 'interrupted'
                return False
    item.image=image
    try:
        item.imagergba='A' in item.image.getbands()
    except:
        item.imagergba=False
    if item.image:
        cache_image(item)
        return True
    return False


def size_image(item,size,antialias=False):
#    import time
#    t=time.time()
#    image=Image.open(item.filename)
#    print 'open time',time.time()-t
#    image=item.image
    image=item.image
    if not image:
        return False
#    try:
#        orient=item.meta['Orientation']
#    except:
#        orient=1
#    if orient<=4:
#        (w,h)=size
#    else:
#        (h,w)=size
    (w,h)=size
    (iw,ih)=image.size
    if (w*h*iw*ih)==0:
        return False
    if 1.0*(w*ih)/(h*iw)>1.0:
        w=h*iw/ih
    else:
        h=w*ih/iw
    if (w*h*iw*ih)==0:
        return False
#    t=time.time()
#    image.draft(image.mode,(w,h))
#    print 'draft time',time.time()-t
    t=time.time()
    try:
        if antialias:
            qimage=image.resize((w,h),Image.ANTIALIAS) ##Image.BILINEAR
        else:
            qimage=image.resize((w,h),Image.BILINEAR) ##Image.BILINEAR
#            qimage=image.resize((w,h))
    except:
        qimage=None
    print 'resize time',time.time()-t
#    t=time.time()
#    if orient>1:
#        for method in settings.transposemethods[orient]:
#            qimage=qimage.transpose(method)
##            if not interrupt_fn():
##                print 'interrupted'
##                return False
#    print 'rotate time',time.time()-t
    if qimage:
        item.qview=qimage.tostring()
        item.qview_size=qimage.size
        return True
    return False


def load_metadata(item):
    if item.meta==False:
        return
    try:
        rawmeta = pyexiv2.Image(item.filename)
        rawmeta.readMetadata()
        item.meta=dict()
        exif.get_exiv2_meta(item.meta,rawmeta)
    except:
        print 'Error reading metadata for',item.filename
        item.meta=False
    item.mark_meta_saved()
    return True


def save_metadata(item):
    if item.meta==False:
        return False
    try:
        rawmeta = pyexiv2.Image(item.filename)
        rawmeta.readMetadata()
        exif.set_exiv2_meta(item.meta,rawmeta)
        rawmeta.writeMetadata()
    except:
        print 'Error writing metadata for',item.filename
        return False
    item.mark_meta_saved()
    return True


def save_metadata_key(item,key,value):
    try:
        rawmeta = pyexiv2.Image(item.filename)
        rawmeta.readMetadata()
        rawmeta[key]=value
        rawmeta.writeMetadata()
    except:
        print 'Error writing metadata for',item.filename


def has_thumb(item):
    if item.thumburi and os.path.exists(item.thumburi):
        return True
    if not settings.maemo:
        uri = gnomevfs.get_uri_from_local_path(item.filename)
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


def make_thumb(item,interrupt_fn=None):
    '''this assumes jpg'''
    if thumb_factory.has_valid_failed_thumbnail(item.filename,item.mtime):
        return
    ##todo: could also try extracting the thumb from the image (essential for raw files)
    ## would not need to make the thumb in that case
    t=time.time()
    try:
        uri=gnomevfs.get_uri_from_local_path(item.filename)
        mimetype=gnomevfs.get_mime_type(uri)
        thumb_pb=None
#        thumb_pb=thumb_factory.generate_thumbnail(uri,mimetype)
        if not thumb_pb:
            try:
                image=Image.open(item.filename)
                image.thumbnail((128,128),Image.ANTIALIAS)
            except:
                print 'first pass fail took',time.time()-t,'seconds'
                cmd=settings.dcraw_cmd%(item.filename,)
                print 'trying to thumb',item,cmd
                imdata=os.popen(cmd).read()
                print 'read took',time.time()-t,'seconds'
                print 'opened cmd',len(imdata)
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
                print 'parse took',time.time()-t,'seconds'
                image.thumbnail((128,128),Image.ANTIALIAS) ##TODO: this is INSANELY slow -- find out why
                print 'thumb took',time.time()-t,'seconds'
            try:
                orient=item.meta['Orientation']
            except:
                orient=1
            if orient>1:
                for method in settings.transposemethods[orient]:
                    image=image.transpose(method)
            thumbsize=image.size
            thumb=image.tostring()
            thumbrgba='A' in image.getbands()
            try:
                orient=item.meta['Orientation']
            except:
                orient=1
            width=thumbsize[0]
            height=thumbsize[1]
            if orient>1:
                for method in settings.transposemethods[orient]:
                    image=image.transpose(method)
            thumb_pb=gtk.gdk.pixbuf_new_from_data(data=thumb, colorspace=gtk.gdk.COLORSPACE_RGB, has_alpha=thumbrgba, bits_per_sample=8, width=width, height=height, rowstride=width*(3+thumbrgba)) #last arg is rowstride
    except:
        print 'creating FAILED thumbnail',item
        item.thumbsize=(0,0)
        item.thumb=None
        item.cannot_thumb=True ##TODO: check if this is used anywhere -- try to remove
        thumb_factory.create_failed_thumbnail(item.filename,item.mtime)
        return False
    width=thumb_pb.get_width()
    height=thumb_pb.get_height()
#    if height<128 and width<128:
#        return False
    uri=gnomevfs.get_uri_from_local_path(item.filename)
    thumb_factory.save_thumbnail(thumb_pb,uri,item.mtime)
    item.thumburi=thumb_factory.lookup(uri,item.mtime)
    if item.thumb:
        item.thumbsize=(width,height)
        item.thumb=thumb_pb
#        item.thumbrgba=thumbrgba ##todo: remove thumbrgba
        cache_thumb(item)
    return True


def load_thumb(item):
    ##todo: could also try extracting the thumb from the image
    ## would not need to make the thumb in that case
    image=None
    try:
        if settings.maemo:
            image = Image.open(item.filename)
            image.thumbnail((128,128))
        else:
            uri = gnomevfs.get_uri_from_local_path(item.filename)
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
    except:
        image=None
    thumb=None
    if image:
        try:
            thumb=image
        except:
            pass
    if thumb!=None:
        item.thumbsize=(thumb.get_width(),thumb.get_height())
        item.thumb=thumb
        return True
#        item.thumbrgba='A' in image.getbands()
