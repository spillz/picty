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


def load_image(item,interrupt_fn):
    try:
        imfile=open(item.filename,'rb')
        p = ImageFile.Parser()
        while not interrupt_fn():
            s = imfile.read(100000)
            if not s:
                break
            p.feed(s)
        image = p.close()
        try:
            orient=item.meta['Exif.Image.Orientation']
        except:
            orient=1

        if interrupt_fn():
            return False
        if orient>1:
            for method in settings.transposemethods[orient]:
                image=image.transpose(method)
    except:
        try:
            image=Image.open(item.filename)
        except:
            image=None
    item.image=image
    try:
        item.imagergba='A' in item.image.getbands()
    except:
        item.imagergba=False
    if item.image:
        return True
    return False


def size_image(item,size,antialias):
    ##todo: put this on a background thread (at least if antialias is true)
    image=item.image
    if not image:
        return False
    (w,h)=size
    (iw,ih)=item.image.size
    if (w*h*iw*ih)==0:
        return False
    if 1.0*(w*ih)/(h*iw)>1.0:
        w=h*iw/ih
    else:
        h=w*ih/iw
    try:
        if antialias:
            qimage=image.resize((w,h),Image.ANTIALIAS).tostring()
        else:
            qimage=image.resize((w,h)).tostring()
    except:
        qimage=None
    item.qview=qimage
    item.qview_size=(w,h)
    if qimage:
        return True
    return False


def load_metadata(item):
    try:
        item.meta = pyexiv2.Image(item.filename)
        item.meta.readMetadata()
    except:
        print 'Error reading metadata for',item.filename
        item.meta=None

def has_thumb(item):
    print 'checking for thumb'
    if not settings.maemo:
        print 'not maemo'
        uri = gnomevfs.get_uri_from_local_path(item.filename)
        print thumb_factory.lookup(uri,item.mtime)
        if thumb_factory.lookup(uri,item.mtime):
            print 'thumb found'
            return True
        if thumb_factory_large.lookup(uri,item.mtime):
            return True
    return False

def make_thumb(item):
    '''this assumes jpg'''
    try:
        image = Image.open(item.filename)
        image.thumbnail((128,128),Image.ANTIALIAS)
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
        item.thumbsize=thumbsize
        item.thumb=thumb
        item.thumbrgba=thumbrgba
    return True


def load_thumb(item):
    try:
        if settings.maemo:
            image = Image.open(item.filename)
            image.thumbnail((128,128))
        else:
            uri = gnomevfs.get_uri_from_local_path(item.filename)
            thumburi=thumb_factory.lookup(uri,item.mtime)
            if thumburi:
                image = Image.open(thumburi)
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
