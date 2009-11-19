try:
    print 'Using gio'
    import gio
    import gobject

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
        def get_mount_info(self):
            '''
            returns a list of tuples (name,icon_data,fuse path)
            '''
            mdict={}
            mounts=[]
            for m in self.vm.get_mounts():
                root=m.get_root()
                name=m.get_name()
                icon_names=m.get_icon().get_names()
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

    def get_mime_type(path):
        ifile=gio.File(path)
        info=ifile.query_info(gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE)
        return info.get_content_type()

    def app_info_get_all_for_type(itype):
        return gio.app_info_get_all_for_type(itype)

    def app_info_get_default_for_type(mime):
        return gio.app_info_get_default_for_type(mime)

    def copy_file(src,dest,overwrite=False,follow_symlinks=False):
        try:
            flags=0
            if overwrite: flags|=gio.G_FILE_COPY_OVERWRITE
            if follow_symlinks: flags|=gio.G_FILE_COPY_NOFOLLOW_SYMLINKS
            gio.File.copy(gio.File(src),gio.File(dest),flags=flags)
        except gio.Error:
            raise IOError ##todo: reuse the error message

    def move_file(src,dest,overwrite=False,follow_symlinks=False):
        try:
            flags=0
            if overwrite: flags|=gio.G_FILE_COPY_OVERWRITE
            if follow_symlinks: flags|=gio.G_FILE_COPY_NOFOLLOW_SYMLINKS
            gio.File.move(gio.File(src),gio.File(dest),flags=flags)
        except gio.Error:
            raise IOError ##todo: reuse the error message

    def remove_file(dest):
        try:
            gio.File.delete(gio.File(dest))
        except gio.Error:
            raise IOError ##todo: reuse the error message

except ImportError:
    import gnomevfs
    import subprocess
    import gobject
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
        def get_mount_info(self):
            '''
            returns a list of tuples (name,icon_data,fuse path)
            '''
            mdict={}
            mounts=[]
            for m in self.vm.get_mounted_volumes():
                if m.get_device_type() not in [gnomevfs.DEVICE_TYPE_CAMERA,gnomevfs.DEVICE_TYPE_MEMORY_STICK,gnomevfs.DEVICE_TYPE_CAMERA]:
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
