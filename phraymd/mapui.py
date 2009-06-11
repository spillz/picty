import sys
print sys.path
sys.path.append('/usr/local/lib/python2.5/site-packages/gtk-2.0')

import os
import gtk
import math
import imageinfo

try:
    import osmgpsmap
except:
    pass

gtk.gdk.threads_init()

class MapFrame(gtk.VBox):
    def __init__(self,worker):
        gtk.VBox.__init__(self,False, 0)
        hbox = gtk.HBox(False, 0)
        self.worker=worker

        self.ignore_release=False

        try:
            self.osm = osmgpsmap.GpsMap(
                tile_cache=os.path.expanduser('~/Maps/OpenStreetMap'),
                tile_cache_is_full_path=True
            )
            self.osm.connect('button-release-event', self.map_clicked)
            self.osm.connect('button-press-event', self.map_clicked)
        except:
            self.osm=gtk.HBox()
        self.latlon_entry = gtk.Entry()

        zoom_in_button = gtk.Button(stock=gtk.STOCK_ZOOM_IN)
        zoom_in_button.connect('clicked', self.zoom_in_clicked, self.osm)
        zoom_out_button = gtk.Button(stock=gtk.STOCK_ZOOM_OUT)
        zoom_out_button.connect('clicked', self.zoom_out_clicked, self.osm)
        home_button = gtk.Button(stock=gtk.STOCK_HOME)
        home_button.connect('clicked', self.home_clicked, self.osm)
        cache_button = gtk.Button('Cache')
        cache_button.connect('clicked', self.cache_clicked, self.osm)

        self.pack_start(self.osm)
        hbox.pack_start(zoom_in_button)
        hbox.pack_start(zoom_out_button)
        hbox.pack_start(home_button)
        hbox.pack_start(cache_button)
        self.pack_start(hbox, False)
        self.pack_start(self.latlon_entry, False)

        target_list=[('image-filename', gtk.TARGET_SAME_APP, 1)]
        self.osm.drag_dest_set(gtk.DEST_DEFAULT_ALL, target_list,
                gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY)
        self.osm.connect("drag-data-received",self.drag_receive_signal)
        self.update_map_items()

    def drag_receive_signal(self, osm, drag_context, x, y, selection_data, info, timestamp):
        if selection_data.type=='image-filename':
            path=selection_data.data
            import imageinfo
            item=imageinfo.Item(path,0)
            ind=self.worker.collection.find(item)
            if ind<0:
                return False
            item=self.worker.collection(ind)
            if item.thumb:
                coords=osm.get_co_ordinates(x, y)
                lat=coords[0]/math.pi*180
                lon=coords[1]/math.pi*180
                import imagemanip
                pb=imagemanip.scale_pixbuf(item.thumb,40)
                osm.add_image(lat,lon,pb)
                imageinfo.set_coords(item,lat,lon)
                self.update_map_items()

    def print_tiles(self,osm):
        if osm.get_property('tiles-queued') != 0:
            print osm.get_property('tiles-queued'), 'tiles queued'
        return True

    def zoom_in_clicked(self,button, osm):
        osm.set_zoom(osm.get_property('zoom') + 1)
        self.update_map_items()

    def zoom_out_clicked(self,button, osm):
        osm.set_zoom(osm.get_property('zoom') - 1)
        self.update_map_items()

    def home_clicked(self,button, osm):
        osm.set_mapcenter(-44.39, 171.25, 12)
        self.update_map_items()

    def cache_clicked(self,button, osm):
        bbox = osm.get_bbox()
        osm.download_maps(
            bbox[0],bbox[1],bbox[2],bbox[3], #was *bbox, but that doesn't work
            zoom_start=osm.get_property('zoom'),
            zoom_end=osm.get_property('max-zoom')
        )

    def map_clicked(self,osm, event):
        if event.button==1 and event.type==gtk.gdk._2BUTTON_PRESS:
            ##todo: if 2nd BUTTON_PRESS occurs affer _2BUTTON_PRESS, need to wait until after that event before zooing
            self.ignore_release=True
            osm.set_zoom(osm.get_property('zoom') + 1)
            return
        if event.button==1 and event.type==gtk.gdk.BUTTON_RELEASE and not self.ignore_release:
            coords=osm.get_co_ordinates(event.x, event.y)
            lat=coords[0]/math.pi*180
            lon=coords[1]/math.pi*180
            osm.set_mapcenter(lat, lon, osm.get_property('zoom'))
            self.latlon_entry.set_text(
                    'latitude %s longitude %s' % (
                    osm.get_property('latitude'),
                    osm.get_property('longitude'),)
                    )
        self.update_map_items()
        self.ignore_release=False

    def update_map_items(self):
        '''adds images to the map that are in the current view'''
        if not self.osm.window:
            return
        w,h=self.osm.window.get_size()
        coords_tl=self.osm.get_co_ordinates(0,0)
        coords_br=self.osm.get_co_ordinates(w-1,h-1)
        self.osm.clear_images()
        lat0=coords_tl[0]/math.pi*180
        lon0=coords_tl[1]/math.pi*180
        lat1=coords_br[0]/math.pi*180
        lon1=coords_br[1]/math.pi*180
        self.worker.request_map_images((lat0,lon0,lat1,lon1),self.update_map_items_signal)

    def update_map_items_signal(self,list_pairs):
        '''notification of a list of images'''
        for l in list_pairs:
            print 'update',l
            lat,lon=imageinfo.get_coords(l[0])
            self.osm.add_image(lat,lon,l[1])
