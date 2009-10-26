##phraymd global settings
import os
import cPickle
import Image
import gtk

maemo=False

version='0.3.2' #version is saved to data and configuration files

plugins_disabled=[]

if maemo:
    max_memthumbs=100
    max_memimages=1
    precache_count=50
else:
    max_memthumbs=1000
    max_memimages=3
    precache_count=500 ##not currently used

#custom launchers (tools) available from right click menu in browser
#tools understand the following variable substituions:
#$FULLPATH,$DIR,$FULLNAME,$NAME,$EXT
custom_launchers={
'image/jpeg':[('GIMP','gimp "$FULLPATH"'),],
'image/png':[('GIMP','gimp "$FULLPATH"'),],
'image/x-pentax-pef':[('UFRaw','ufraw "$FULLPATH"'),],
'default':[('Nautilus','nautilus "$DIR"'),],
}

layout={}  #the layout of the user interface

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

collections_dir=os.path.join(data_dir,'collections')
if not os.path.exists(collections_dir):
    os.makedirs(collections_dir)

active_collection=None
active_collection_file=''
default_collection_file=os.path.join(collections_dir,'collection') ##todo: support multiple collections
legacy_collection_file=os.path.join(os.environ['HOME'],'.phraymd-collection')
legacy_collection_file2=os.path.join(data_dir,'collection')
if not os.path.exists(default_collection_file):
    if os.path.exists(legacy_collection_file2):
        os.renames(legacy_collection_file2,default_collection_file)
    elif os.path.exists(legacy_collection_file):
        os.renames(legacy_collection_file,default_collection_file)

conf_file=os.path.join(settings_dir,'app-settings')
legacy_conf_file=os.path.join(os.environ['HOME'],'.phraymd-settings')

legacy_image_dirs=[]


def save():
    global version, precache_count, custom_launchers, user_tag_info, places, active_collection_file
    try:
        f=open(conf_file,'wb')
    except:
        return False
    try:
        cPickle.dump(version,f,-1)
        cPickle.dump(active_collection_file,f,-1)
        cPickle.dump(precache_count,f,-1)
        cPickle.dump(layout,f,-1)
        cPickle.dump(custom_launchers,f,-1)
        cPickle.dump(plugins_disabled,f,-1)
    finally:
        f.close()


def load():
    global version, precache_count, custom_launchers, user_tag_info, places, layout, active_collection_file, legacy_image_dirs, plugins_disabled
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
        if file_version>='0.3.2':
            active_collection_file=cPickle.load(f)
        if file_version<'0.3.0':
            legacy_image_dirs=cPickle.load(f)
        if file_version<='0.3.1':
            store_thumbs=cPickle.load(f)
        precache_count=cPickle.load(f)
        if file_version>='0.3.1':
            layout=cPickle.load(f)
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
        if file_version>='0.3.2':
            plugins_disabled=cPickle.load(f)
    except:
        pass
    finally:
        f.close()


def user_add_dir():
    image_dirs=[]
    fcd=gtk.FileChooserDialog(title='Choose Photo Directory', parent=None, action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
        buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK), backend=None)
    fcd.set_current_folder(os.environ['HOME'])
    response=fcd.run()
    if response == gtk.RESPONSE_OK:
        image_dirs.append(fcd.get_filename())
    fcd.destroy()
    return image_dirs


def init():
    global image_dirs, active_collection_file
    load()
    if not os.path.exists(active_collection_file):
        try:
            active_collection_file=os.path.join(collections_dir,get_collection_files()[0])
        except:
            pass
    if not os.path.exists(active_collection_file) and not os.path.exists(legacy_collection_file2) and not os.path.exists(legacy_collection_file):
        image_dirs=user_add_dir()
        if len(image_dirs)==0:
            import sys
            print 'no image directory selected... quitting'
            sys.exit()
        import imageinfo
        if not imageinfo.create_empty_file(os.path.join(collections_dir,'collection'),image_dirs):
            import sys
            print 'error creating collection file... quitting'
            sys.exit()
        active_collection_file=os.path.join(collections_dir,'collection')
    save()


def get_collection_files():
    return os.listdir(collections_dir)
