try:
    print 'Using gio'
    import gio

    def get_preview_icon_data(path):
        ifile=gio.File(path)
        info=ifile.query_info("preview::icon")
        icon=info.get_attribute_object("preview::icon")
        data,dtype=icon.load()
        return data,dtype

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

except:
    import gnomevfs
    import subprocess
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
