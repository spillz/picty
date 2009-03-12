##Image viewers global settings
import os
import cPickle
import Image
import gtk

maemo=False

version='0.2.0'

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

if maemo:
    precache_count=100
else:
    precache_count=4000

imagetypes=['jpg','jpeg','png']

image_dirs=[]
store_thumbs=True
conf_file=os.path.join(os.environ['HOME'],'.phomgr-settings')

def save():
    global version, image_dirs, store_thumbs, precache_count, conf_file
    try:
        f=open(conf_file,'wb')
    except:
        return False
    try:
        cPickle.dump(version,f,-1)
        cPickle.dump(image_dirs,f,-1)
        cPickle.dump(store_thumbs,f,-1)
        cPickle.dump(precache_count,f,-1)
    finally:
        f.close()

def load():
    global version, image_dirs, store_thumbs, precache_count
    try:
        f=open(conf_file,'rb')
    except:
        return False
    try:
        version=cPickle.load(f)
        image_dirs=cPickle.load(f)
        store_thumbs=cPickle.load(f)
        precache_count=cPickle.load(f)
        print 'load'
    finally:
        f.close()

def user_add_dir():
    global image_dirs
    fcd=gtk.FileChooserDialog(title='Choose Photo Directory', parent=None, action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
        buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK), backend=None)
    fcd.set_current_folder(os.environ['HOME'])
    response=fcd.run()
    if response == gtk.RESPONSE_OK:
        image_dirs.append(fcd.get_filename())
    print 'im dirs',image_dirs
    fcd.destroy()
    return image_dirs

def init():
    global image_dirs
    load()
    if len(image_dirs)==0:
        user_add_dir()
        if len(image_dirs)==0:
            import sys
            print 'no image directory selected... quitting'
            sys.exit()
    save()
    print 'Starting image browser on',image_dirs

