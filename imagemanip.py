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

thumb_factory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_NORMAL)
thumb_factory_large = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_LARGE)

import time

memimages=[]
memthumbs=[]

def rotate_left(item):
    'rotates image anti-clockwise'
    try:
        orient=item.meta['Exif.Image.Orientation']
    except:
        orient=1
    item.meta['Exif.Image.Orientation']=settings.rotate_left_tx[orient]
    item.image=None
    item.qview=None
    item.thumb=None
    make_thumb(item)


def rotate_right(item):
    'rotates image clockwise'
    try:
        orient=item.meta['Exif.Image.Orientation']
    except:
        orient=1
    item.meta['Exif.Image.Orientation']=settings.rotate_right_tx[orient]
    item.image=None
    item.qview=None
    item.thumb=None
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
        image=None
        return False
    image.draft(image.mode,(1600,1600))
    if not interrupt_fn():
        print 'interrupted'
        return False
    try:
        orient=item.meta['Exif.Image.Orientation']
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
#        orient=item.meta['Exif.Image.Orientation']
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
    print w,h,iw,ih
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
    try:
        rawmeta = pyexiv2.Image(item.filename)
        rawmeta.readMetadata()
        item.meta=dict()
        for x in exif.tags:
            try:
                item.meta[x[0]]=rawmeta[x[0]]
            except:
                pass
    except:
        print 'Error reading metadata for',item.filename
        item.meta=None


def save_metadata(item):
    try:
        rawmeta = pyexiv2.Image(item.filename)
        rawmeta.readMetadata()
        for x in exif.writetags:
            try:
                rawmeta[x[0]]=item.meta[x[0]]
            except:
                pass
        rawmeta.writeMetadata()
    except:
        print 'Error writing metadata for',item.filename


def save_metadata_key(item,key,value):
    try:
        rawmeta = pyexiv2.Image(item.filename)
        rawmeta.readMetadata()
        rawmeta[key]=value
        rawmeta.writeMetadata()
    except:
        print 'Error writing metadata for',item.filename


def has_thumb(item):
    if item.thumburi:
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
    ##todo: could also try extracting the thumb from the image
    ## would not need to make the thumb in that case
    print 'making thumb',item
    try:
        image=Image.open(item.filename)
        #image.thumbnail((512,512))
        image.thumbnail((128,128),Image.ANTIALIAS)
    except:
        print 'creating FAILED thumbnail'
        item.thumbsize=(0,0)
        item.thumb=None
        item.cannot_thumb=True
        thumb_factory.create_failed_thumbnail(item.filename,item.mtime)
        return False
    try:
        orient=item.meta['Exif.Image.Orientation']
    except:
        orient=1
    if orient>1:
        for method in settings.transposemethods[orient]:
            image=image.transpose(method)
    thumbsize=image.size
    thumb=image.tostring()
    thumbrgba='A' in image.getbands()
    try:
        orient=item.meta['Exif.Image.Orientation']
    except:
        orient=1
    if orient>1:
        for method in settings.transposemethods[orient]:
            image=image.transpose(method)
    width=thumbsize[0]
    height=thumbsize[1]
#    if height<128 and width<128:
#        return False
    try:
        thumb_pb=gtk.gdk.pixbuf_new_from_data(data=thumb, colorspace=gtk.gdk.COLORSPACE_RGB, has_alpha=thumbrgba, bits_per_sample=8, width=width, height=height, rowstride=width*(3+thumbrgba)) #last arg is rowstride
    except:
        print 'error creating thumbnail',item.filename
        return False
    uri=gnomevfs.get_uri_from_local_path(item.filename)
    thumb_factory.save_thumbnail(thumb_pb,uri,item.mtime)
    if item.thumb:
        item.thumburi=thumb_factory.lookup(uri,item.mtime)
        item.thumbsize=thumbsize
        item.thumb=thumb
        item.thumbrgba=thumbrgba
        cache_thumb(item)
    return True


def load_thumb(item):
    ##todo: could also try extracting the thumb from the image
    ## would not need to make the thumb in that case
    try:
        if settings.maemo:
            image = Image.open(item.filename)
            image.thumbnail((128,128))
        else:
            uri = gnomevfs.get_uri_from_local_path(item.filename)
            if not item.thumburi:
                item.thumburi=thumb_factory.lookup(uri,item.mtime)
            if item.thumburi:
                image = Image.open(item.thumburi)
                s=image.size
                #image.thumbnail((128,128))
            else:
                thumburi=thumb_factory_large.lookup(uri,item.mtime)
                if thumburi:
                    #print 'using large thumb'
                    image = Image.open(thumburi)
                    image.thumbnail((128,128))
                else:
                    #print 'full loading',fullpath
                    image=None
    except:
        image=None
    thumb=None
    if image:
        try:
            thumb=image.tostring()
        except:
            pass
    if thumb:
        item.thumbsize=image.size
        item.thumb=thumb
        item.thumbrgba='A' in image.getbands()
