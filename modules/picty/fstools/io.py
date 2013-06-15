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

import os,os.path
import platform

def get_mtime(path):
    '''
    forces mtime to an integer for compatibility with gnome thumbnailer
    '''
    return int(os.path.getmtime(path)) ##todo: better to just cast to int in the few places a float would cause problems

def get_true_path(path):
    return path  ##todo: unfortunately, this runs too slowly to be used. there must be a simpler way to get the name as represented on the disk
    p=os.getcwd()
    if not os.path.exists(path):
        os.chdir(p)
        return None
    try:
        os.chdir(path)
        path=os.path.abspath('.')
        os.chdir(p)
        return path
    except OSError:
        base,name=os.path.split(path)
        try:
            os.chdir(base)
        except OSError:
            return None
        for n in os.listdir(base):
            if os.path.samefile(n,name):
                b=os.path.abspath('.')
                os.chdir(p)
                return os.path.join(b,n)
        return None

try:
    import gio
    import gobject
    print 'Using gio'

    def get_preview_icon_data(path):
        ifile=gio.File(path)
        info=ifile.query_info("preview::icon")
        icon=info.get_attribute_object("preview::icon")
        data,dtype=icon.load()
        return data,dtype

    def equal(path1,path2):
        return gio.File(path1).equal(gio.File(path2))

    class VolumeMonitor(gobject.GObject):
        __gsignals__={
            'mount-added':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_STRING,gobject.TYPE_PYOBJECT,gobject.TYPE_STRING)),
            'mount-removed':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_STRING,gobject.TYPE_PYOBJECT,gobject.TYPE_STRING)),
            }

        def __init__(self):
            gobject.GObject.__init__(self)
            self.vm=gio.volume_monitor_get()
            self.vm.connect("mount-added",self.mount_added)
            self.vm.connect("mount-removed",self.mount_removed)
        def mount_added(self,vm,m):
            print 'mount event',vm,m
            self.emit("mount-added",m.get_name(),m.get_icon().get_names(),m.get_root().get_path())
        def mount_removed(self,vm,m):
            print 'unmount event',vm,m
            self.emit("mount-removed",m.get_name(),m.get_icon().get_names(),m.get_root().get_path())
        def get_mount_path_from_device_name(self,unix_device_name):
            for m in self.vm.get_mounts():
                if m.get_volume().get_identifier('unix-device') == unix_device_name:
                    try:
                        return m.get_root().get_path()
                    except:
                        pass

        def get_mount_info(self):
            '''
            returns a list of tuples (name,icon_data,fuse path)
            '''
            mdict={}
            mounts=[]
            for m in self.vm.get_mounts():
                root=m.get_root()
                name=m.get_name()
                try:
                    icon_names=m.get_icon().get_names()
                except AttributeError:
                    icon_names=[]
                if root not in mdict:
                    vals=[name,icon_names,root.get_path()]
                    mdict[root]=vals
                    mounts.append(vals)
                else:
                    if len(icon_names)>len(mdict[root][1]):
                        mdict[root][1]=icon_names
                    if len(name)>len(mdict[root][0]):
                        mdict[root][0]=name
            return mounts
    gobject.type_register(VolumeMonitor)

    def get_uri(path):
        ifile=gio.File(path)
        return ifile.get_uri()

    def get_path_from_uri(uri):
        ifile=gio.File(uri)
        return ifile.get_path()

    if platform.system() == 'Windows':
        import _winreg
        def get_mime_type(path):
            ifile=gio.File(path)
            info=ifile.query_info(gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE)
            ext = info.get_content_type()
            reg = _winreg.ConnectRegistry(None,_winreg.HKEY_CLASSES_ROOT)
            subkey = _winreg.OpenKey(reg,"MIME\DataBase\Content Type")
            key_count, val_count, ldate = _winreg.QueryInfoKey(subkey)
            mimetype=''
            for k in range(key_count):
                mime = _winreg.EnumKey(subkey,k)
#                if not mime.lower().startswith('image'):
#                    continue
                mimekey = _winreg.OpenKey(subkey,mime)
                mimekey_count, mimeval_count, ldate = _winreg.QueryInfoKey(mimekey)
                for j in range(mimeval_count):
                    mstr, value, vtype = _winreg.EnumValue(mimekey,j)
                    if mstr == 'Extension' and value.lower() == ext.lower():
                        mimetype = mime
                        break
            if mimetype == 'image/pjpeg': #windows defines a pjpeg for progressive jpeg, but all modern jpeg libs can open pjpeg, so no need to distinguish for our purposes
                mimetype = 'image/jpeg'
            return mimetype
    else:
        def get_mime_type(path):
            ifile=gio.File(path)
            info=ifile.query_info(gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE)
            return info.get_content_type()

    def app_info_get_all_for_type(itype):
        return gio.app_info_get_all_for_type(itype)

    def app_info_get_default_for_type(mime):
        return gio.app_info_get_default_for_type(mime)

    def copy_file(src,dest,overwrite=False,follow_symlinks=True):
        try:
            flags=gio.FILE_COPY_TARGET_DEFAULT_PERMS
            if overwrite:
                flags|=gio.FILE_COPY_OVERWRITE
            if not follow_symlinks:
                flags|=gio.FILE_COPY_NOFOLLOW_SYMLINKS
            gio.File.copy(gio.File(src),gio.File(dest),flags=flags)
        except gio.Error:
            raise IOError ##todo: reuse the error message

    def move_file(src,dest,overwrite=False,follow_symlinks=True):
        try:
            flags=gio.FILE_COPY_TARGET_DEFAULT_PERMS
            if overwrite:
                flags|=gio.FILE_COPY_OVERWRITE
            if not follow_symlinks:
                flags|=gio.FILE_COPY_NOFOLLOW_SYMLINKS
            gio.File.move(gio.File(src),gio.File(dest),flags=flags)
        except gio.Error:
            raise IOError ##todo: reuse the error message

    def remove_file(dest):
        try:
            gio.File.delete(gio.File(dest))
        except gio.Error:
            raise IOError ##todo: reuse the error message

    def trash_file(dest):
        try:
            gio.File.trash(gio.File(dest))
        except gio.Error:
            raise IOError ##todo: reuse the error message

except ImportError:
    import gnomevfs
    import subprocess
    import gobject
    import datetime
    print 'Using gnomevfs'

    def get_uri(path):
        return gnomevfs.get_uri_from_local_path(path)

    def get_path_from_uri(uri):
        return gnomevfs.get_local_path_from_uri(uri)

    def get_mime_type(path):
        return gnomevfs.get_mime_type(gnomevfs.get_uri_from_local_path(path))

    class AppInfo:
        def __init__(self,app_data):
            self.app_data=app_data
        def launch():
            subprocess.Popen(self.app_data[2])
        def launch_uris(self,uris):
            subprocess.Popen(self.app_data[2]+' '+' '.join(['"'+gnomevfs.get_local_path_from_uri(u)+'"' for u in uris]),shell=True)
        def get_name(self):
            return self.app_data[1]

    def app_info_get_all_for_type(mime):
        return [AppInfo(app_data) for app_data in gnomevfs.mime_get_all_applications(mime)]

    def app_info_get_default_for_type(mime):
        return app_info_get_all_for_type(mime)[0]

    def copy_file(src,dest,overwrite=False,follow_symlinks=False):
        if not overwrite and os.path.exists(dest):
            raise IOError
        fin=open(src,'rb')
        fout=open(dest,'wb')
        fout.write(fin.read())

    def move_file(src,dest,overwrite=False,follow_symlinks=False):
        os.renames(src,dest)

    def remove_file(dest):
        os.remove(dest)

    def trash_file(src):
        dest_dir=os.path.join(os.path.expanduser('~'),'.local/share/Trash/files')
        fname=os.path.split(src)[1]
        dest=os.path.join(dest_dir,fname)
        dest1=dest
        i=1
        while os.path.exists(dest1):
            dest1=dest+'.%i'%(i,)
            i+=1
        now=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        move_file(src,dest1)

        info_dir=os.path.join(os.path.expanduser('~'),'.local/share/Trash/info')
        info=os.path.join(info_dir,fname+'.trashinfo')
        info_content='''[Trash Info]
Path=%s
DeletionDate=%s
'''%(src,now)
        f=open(info,'wb')
        f.write(info_content)
        f.close()


    class VolumeMonitor(gobject.GObject):
        __gsignals__={
            'mount-added':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_STRING,gobject.TYPE_PYOBJECT,gobject.TYPE_STRING)),
            'mount-removed':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_STRING,gobject.TYPE_PYOBJECT,gobject.TYPE_STRING)),
            }

        def __init__(self):
            gobject.GObject.__init__(self)
            self.vm= gnomevfs.VolumeMonitor()
            self.vm.connect("volume-mounted",self.mount_added)
            self.vm.connect("volume-unmounted",self.mount_removed)
        def mount_added(self,vm,m):
            print 'mount event',vm,m
            self.emit("mount-added",m.get_name(),m.get_icon().get_names(),m.get_root().get_path())
        def mount_removed(self,vm,m):
            print 'unmount event',vm,m
            self.emit("mount-removed",m.get_name(),m.get_icon().get_names(),m.get_root().get_path())
        def get_mount_path_from_device_name(self,unix_device_name):
            for m in self.vm.get_mounted_volumes():
                if m.get_device_type() not in [gnomevfs.DEVICE_TYPE_CAMERA,gnomevfs.DEVICE_TYPE_MEMORY_STICK]:
                    continue
                if m.get_drive().get_device_path() == unix_device_name:
                    path=gnomevfs.get_local_path_from_uri(m.get_activation_uri())
                    return path
        def get_mount_info(self):
            '''
            returns a list of tuples (name,icon_data,fuse path)
            '''
            mdict={}
            mounts=[]
            for m in self.vm.get_mounted_volumes():
                if m.get_device_type() not in [gnomevfs.DEVICE_TYPE_CAMERA,gnomevfs.DEVICE_TYPE_MEMORY_STICK]:
                    continue
                path=gnomevfs.get_local_path_from_uri(m.get_activation_uri())
                name=m.get_display_name()
                icon_names=[m.get_icon()]
                print m.get_device_type(),name,path
                if path not in mdict:
                    vals=[name,icon_names,path]
                    mdict[path]=vals
                    mounts.append(vals)
                else:
                    if len(icon_names)>len(mdict[path][1]):
                        mdict[path][1]=icon_names
                    if len(name)>len(mdict[path][0]):
                        mdict[path][0]=name
            return mounts
    gobject.type_register(VolumeMonitor)
