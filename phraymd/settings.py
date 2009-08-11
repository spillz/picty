##phraymd global settings
import os
import cPickle
import Image
import gtk

maemo=False

version='0.3.0' #version is saved to settings and configuration files

plugins_disabled=[]

if maemo:
    max_memthumbs=100
    max_memimages=1
    precache_count=50
else:
    max_memthumbs=1000
    max_memimages=3
    precache_count=500 ##not currently used

#custom launchers understand the following variable substituions:
#$FULLPATH,$DIR,$FULLNAME,$NAME,$EXT
custom_launchers={
'image/jpeg':[('GIMP','gimp "$FULLPATH"'),],
'image/png':[('GIMP','gimp "$FULLPATH"'),],
'image/x-pentax-pef':[('UFRaw','ufraw "$FULLPATH"'),],
'default':[('Nautilus','nautilus "$DIR"'),],
}

edit_command_line='gimp'
dcraw_cmd='/usr/bin/dcraw -e -c "%s"'
dcraw_backup_cmd='/usr/bin/dcraw -T -h -w -c "%s"'

imagetypes=['jpg','jpeg','png']

def get_user_dir(env_var,alt_path):
    try:
        path=os.path.join(os.environ[env_var],'phraymd')
    except KeyError:
        path=os.path.join(os.environ['HOME'],alt_path)
    if not os.path.exists(path):
        os.makedirs(path)
    return path

settings_dir=get_user_dir('XDG_CONFIG_HOME','.config/phraymd')
data_dir=get_user_dir('XDG_DATA_HOME','.local/share/phraymd')
cache_dir=get_user_dir('XDG_CACHE_HOME','.cache/') ##todo: not using cache yet. parts of the collection are definitely cache

conf_file=os.path.join(settings_dir,'app-settings')
collection_file=os.path.join(data_dir,'collection') ##todo: support multiple collections
image_dirs=[] ##todo: yuck! - store collection directories in the collection class (they are at least saved in the collection file now)
store_thumbs=True

legacy_conf_file=os.path.join(os.environ['HOME'],'.phraymd-settings')
legacy_collection_file=os.path.join(os.environ['HOME'],'.phraymd-collection')

def save():
    global version, image_dirs, store_thumbs, precache_count, custom_launchers, user_tag_info, places
    try:
        f=open(conf_file,'wb')
    except:
        return False
    try:
        cPickle.dump(version,f,-1)
        cPickle.dump(store_thumbs,f,-1)
        cPickle.dump(precache_count,f,-1)
        cPickle.dump(custom_launchers,f,-1)
    finally:
        f.close()

def load():
    global version, image_dirs, store_thumbs, precache_count, custom_launchers, user_tag_info, places
    try:
        f=open(conf_file,'rb')
    except:
        try:
            print 'loading legacy config file'
            f=open(legacy_conf_file,'rb')
        except:
            return False
    try:
        file_version=cPickle.load(f)
        print 'loaded settings file with version',file_version
        if file_version<'0.3.0':
            image_dirs=cPickle.load(f)
        store_thumbs=cPickle.load(f)
        precache_count=cPickle.load(f)
        if file_version>='0.3.0':
            custom_launchers=cPickle.load(f)
            for c in custom_launchers:
                custom_launchers[c]=list(custom_launchers[c])
        else:
            if file_version>='0.2.3':
                user_tag_info=cPickle.load(f)
                custom_launchers=cPickle.load(f)
                for c in custom_launchers:
                    custom_launchers[c]=list(custom_launchers[c])
            if file_version>='0.2.4':
                places=cPickle.load(f)
    except:
        pass
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

def write_empty_collection():
    try:
        f=open(collection_file,'wb')
    except:
        print 'failed to open collection for write'
        return False
    cPickle.dump(version,f,-1)
    cPickle.dump(image_dirs,f,-1)
    import imageinfo
    collection=imageinfo.Collection([])
    cPickle.dump(collection,f,-1)
    f.close()
    return True


def init():
    global image_dirs
    load()
    if not os.path.exists(collection_file) and not os.path.exists(legacy_collection_file):
        user_add_dir()
        if len(image_dirs)==0:
            import sys
            print 'no image directory selected... quitting'
            sys.exit()
        if not write_empty_collection():
            import sys
            print 'error creating collection file... quitting'
            sys.exit()
    save()
    print 'Starting image browser on',image_dirs
