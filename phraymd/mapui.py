import sys
print sys.path
sys.path.append('/usr/local/lib/python2.5/site-packages/gtk-2.0')

import osmgpsmap

import os
import gtk
import osmgpsmap

gtk.gdk.threads_init()

class MapFrame(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self,False, 0)
        hbox = gtk.HBox(False, 0)

        self.osm = osmgpsmap.GpsMap(
            tile_cache=os.path.expanduser('~/Maps/OpenStreetMap'),
            tile_cache_is_full_path=True
        )
        self.osm.connect('button-release-event', self.map_clicked)
        self.osm.connect('button-press-event', self.map_clicked)
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


    def print_tiles(self,osm):
        if osm.get_property('tiles-queued') != 0:
            print osm.get_property('tiles-queued'), 'tiles queued'
        return True

    def zoom_in_clicked(self,button, osm):
        osm.set_zoom(osm.get_property('zoom') + 1)

    def zoom_out_clicked(self,button, osm):
        osm.set_zoom(osm.get_property('zoom') - 1)

    def home_clicked(self,button, osm):
        osm.set_mapcenter(-44.39, 171.25, 12)

    def cache_clicked(self,button, osm):
        bbox = osm.get_bbox()
        osm.download_maps(
            bbox[0],bbox[1],bbox[2],bbox[3], #was *bbox
            zoom_start=osm.get_property('zoom'),
            zoom_end=osm.get_property('max-zoom')
        )

    def map_clicked(self,osm, event):
        if event.button==1 and event.type==gtk.gdk._2BUTTON_PRESS:
            coords=osm.get_co_ordinates(event.x, event.y)
            self.latlon_entry.set_text(
                'latitude %s longitude %s c %s,%s x %s y %s' % (
                    osm.get_property('latitude'),
                    osm.get_property('longitude'),
                    coords[0],
                    coords[1],
                    event.x,event.y
                    ))
##            osm.set_mapcenter(coords[1], coords[0], osm.get_property('zoom'))
        elif event.button==1 and event.type==gtk.gdk.BUTTON_RELEASE:
            pass
##            self.latlon_entry.set_text(
##                'latitude %s longitude %s' % (
##                    osm.get_property('latitude'),
##                    osm.get_property('longitude')
##                )
##            )

