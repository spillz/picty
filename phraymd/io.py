try:
    print 'Using gio'
    import gio

    def get_uri(path):
        ifile=gio.File(path)
        return ifile.get_uri()

    def get_mime_type(path):
        ifile=gio.File(path)
        info=ifile.query_info(gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE)
        return info.get_content_type()

    def app_info_get_all_for_type(itype):
        return gio.app_info_get_all_for_type(itype)

    def app_info_get_default_for_type(mime):
        return gio.app_info_get_default_for_type(mime)

except:
    import gnomevfs
    print 'Using gnomevfs'

    def get_uri(path):
        return gnomevfs.get_uri_from_local_path(path)

    def get_mime_type(path):
        return gnomevfs.get_mime_type(gnomevfs.get_uri_from_local_path(path))

    class AppInfo:
        def __init__(self,app_data):
            self.app_data=app_data
        def launch():
            subprocess.Popen(self.app_data[2])
        def launch_uris(self,uris):
            subprocess.Popen(self.app_data[2]+' '+' '.join(['"'+u+'"' for u in uris]),shell=True)
        def get_name(self):
            return self.app_data[1]

    def app_info_get_all_for_type(mime):
        return [AppInfo(app_data) for app_data in gnomevfs.mime_get_all_applications(mime)]

    def app_info_get_default_for_type(mime):
        return app_info_get_all_for_type(mime)[0]
