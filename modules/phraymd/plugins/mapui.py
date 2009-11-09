'''

    phraymd - Map and Geotagging Plugin
    Copyright (C) 2009  Damien Moore
    Portions Copyright (C) 2009 John Stowers (python example code from OsmGpsMap)

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

##nasty hack needed because osmgpsmap is in the wrong place
import sys
sys.path.append('/usr/local/lib/python2.5/site-packages/gtk-2.0')
sys.path.append('/usr/lib/python2.5/site-packages/gtk-2.0')

import os
import gtk
import math
import cPickle

##phraymd imports
from phraymd import imageinfo
from phraymd import settings
from phraymd import pluginbase

try:
    import osmgpsmap
    map_source=(
    #('Google Hybrid',osmgpsmap.MAP_SOURCE_GOOGLE_HYBRID),
    #('Google Satellite',osmgpsmap.MAP_SOURCE_GOOGLE_SATTELITE),
    #('Google Satellite Quad',osmgpsmap.MAP_SOURCE_GOOGLE_SATTELITE_QUAD),
    ('Maps for Free',osmgpsmap.MAP_SOURCE_MAPS_FOR_FREE,'mapsforfree'),
    #('Open Aerial Map',osmgpsmap.MAP_SOURCE_OPENAERIALMAP),
    ('Open Street Map',osmgpsmap.MAP_SOURCE_OPENSTREETMAP,'openstreetmap'),
    ('Open Street Map Renderer',osmgpsmap.MAP_SOURCE_OPENSTREETMAP_RENDERER,'openstreetmaprenderer'),
    ('Virtual Earth Satellite',osmgpsmap.MAP_SOURCE_VIRTUAL_EARTH_SATTELITE,'virtualearthsatellite'))
except:
    map_source=tuple()


gtk.gdk.threads_init()

class MapPlugin(pluginbase.Plugin):
    name='MapSidebar'
    display_name='Map Sidebar'
    api_version='0.1.0'
    version='0.1.0'
    def __init__(self):
        print 'INITIALIZED MAP SIDEBAR PLUGIN'
    def plugin_init(self,mainframe,app_init):
        self.mainframe=mainframe
        self.worker=mainframe.tm
        self.mapframe=MapFrame(self.worker)
        places={'Home':(0.0,0.0,1)}
        try:
            print 'Map Plugin: loading map-places file'
            f=open(os.path.join(settings.data_dir,'map-places'),'rb')
            version=cPickle.load(f)
            places=cPickle.load(f)
            f.close()
        except:
            print 'Map Plugin: No map-places file found'
        self.mapframe.set_places(places)
        self.mapframe.show_all()
        self.mainframe.sidebar.append_page(self.mapframe,gtk.Label("Map"))
        self.mainframe.browser.connect("view-rebuild-complete",self.view_rebuild_complete)

    def view_rebuild_complete(self,browser):
        self.mapframe.update_map_items()
    ##TODO: should update map images whenever there are relevent collection changes (will need to maintian list of displayed images) -- may be enough to trap view add/remove and GPS metadata changes
    def plugin_shutdown(self,app_shutdown=False):
        print 'Map Plugin: saving map places'
        f=open(os.path.join(settings.data_dir,'map-places'),'wb') ##todo: datadir must exist??
        cPickle.dump(self.version,f,-1)
        cPickle.dump(self.mapframe.get_places(),f,-1)
        f.close()
        try:
            print 'Map Plugin: saving map places'
            f=open(os.path.join(settings.data_dir,'map-places'),'wb') ##todo: datadir must exist??
            cPickle.dump(self.version,f,-1)
            cPickle.dump(self.mapframe.get_places(),f,-1)
            f.close()
        except:
            print 'Map Plugin: Error saving map places'
        self.mapframe.destroy()
        del self.mapframe



class MapFrame(gtk.VBox):
    def __init__(self,worker):
        gtk.VBox.__init__(self,False, 0)
        hbox = gtk.HBox(False, 0)
        self.worker=worker

        self.ignore_release=False

        self.osm_box=gtk.HBox()
        self.osm=None

        self.latlon_entry = gtk.Entry()
        self.places_combo = gtk.combo_box_entry_new_text()
        self.places_combo.connect("changed",self.set_place_signal)
        self.places={}

        self.source_combo=gtk.combo_box_new_text()
        for s in map_source:
            self.source_combo.append_text(s[0])
        self.source_combo.connect("changed",self.set_source_signal)
        self.source_combo.set_active(1)

        zoom_in_button = gtk.Button(stock=gtk.STOCK_ZOOM_IN)
        zoom_in_button.connect('clicked', self.zoom_in_clicked)
        zoom_out_button = gtk.Button(stock=gtk.STOCK_ZOOM_OUT)
        zoom_out_button.connect('clicked', self.zoom_out_clicked)
        home_button = gtk.Button(stock=gtk.STOCK_HOME)
        home_button.connect('clicked', self.home_clicked)
        add_place_button = gtk.Button(stock=gtk.STOCK_ADD)
        add_place_button.connect('clicked', self.add_place_signal)
        delete_place_button = gtk.Button(stock=gtk.STOCK_REMOVE)
        delete_place_button.connect('clicked', self.delete_place_signal)

#        cache_button = gtk.Button('Cache')
#        cache_button.connect('clicked', self.cache_clicked, self.osm)

        self.pack_start(self.osm_box)
        hbox.pack_start(zoom_in_button)
        hbox.pack_start(zoom_out_button)
        hbox.pack_start(home_button)
#        hbox.pack_start(cache_button)
        self.pack_start(hbox, False)
        hbox_info=gtk.HBox()
        hbox_info.pack_start(self.latlon_entry)
        hbox_info.pack_start(self.source_combo, False)
        self.pack_start(hbox_info,False)
        hbox_place=gtk.HBox()
        hbox_place.pack_start(self.places_combo)
        hbox_place.pack_start(add_place_button,False)
        hbox_place.pack_start(delete_place_button,False)

        self.pack_start(hbox_place, False)
        self.update_map_items()

    def set_places(self,places):
        self.places=places
        self.places_combo.get_model().clear()
        for p in self.places:
            self.places_combo.append_text(p)

    def get_places(self):
        return self.places

    def set_source_signal(self,widget):
            if self.osm:
#                place=(self.osm.get_property('latitude'),self.osm.get_property('longitude'),self.osm.get_property('zoom'))
                ll=self.osm.screen_to_geographic(0,0)
                place=(ll[0],ll[1],self.osm.get_property('zoom'))
                print 'NEW MAP PLACE',place
                self.osm_box.remove(self.osm)
                self.osm.destroy()
            else:
                place=None
##                place=(0.0,0.0,1)
            self.osm = osmgpsmap.GpsMap(
                tile_cache=os.path.join(settings.cache_dir,'maps/')+map_source[widget.get_active()][2],
                tile_cache_is_full_path=True,
                repo_uri=map_source[widget.get_active()][1],
            )
            self.osm.connect('button-release-event', self.map_clicked)
            self.osm.connect('button-press-event', self.map_clicked)
            target_list=[('image-filename', gtk.TARGET_SAME_APP, 1)]
            self.osm.drag_dest_set(gtk.DEST_DEFAULT_ALL, target_list,
                    gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY)
            self.osm.connect("drag-data-received",self.drag_receive_signal)
            self.osm_box.pack_start(self.osm)
            self.osm_box.show_all()
            if place:
                self.osm.set_mapcenter(*place) #todo: this causes an assertion - why?
                self.update_map_items()

    def add_place_signal(self,widget):
        place=self.places_combo.get_active_text()
        print 'adding new place',place,'to',self.places
        if place not in self.places:
            print 'adding new place to combo'
            self.places_combo.append_text(place)
        self.places[place]=(self.osm.get_property('latitude'),
            self.osm.get_property('longitude'),self.osm.get_property('zoom'))

    def delete_place_signal(self,widget):
        i=self.places_combo.get_active()
        place=self.places_combo.get_active_text()
        if i>=0:
            self.places_combo.remove_text(i)
        if place in self.places:
            del self.places[place]
        self.places_combo.child.set_text('')

    def set_place_signal(self,combo):
        place=combo.get_active_text()
        if place in self.places:
            self.osm.set_mapcenter(*self.places[place])
            self.update_latlon_entry(False)
            self.update_map_items()

    def drag_receive_signal(self, osm, drag_context, x, y, selection_data, info, timestamp):
        if selection_data.type=='image-filename':
            path=selection_data.data
            from phraymd import imageinfo
            item=imageinfo.Item(path,0)
            ind=self.worker.collection.find(item)
            if ind<0:
                return False
            item=self.worker.collection(ind)
            if item.thumb:
                coords=osm.get_co_ordinates(x, y)
                lat=coords[0]/math.pi*180
                lon=coords[1]/math.pi*180
                from phraymd import imagemanip
                pb=imagemanip.scale_pixbuf(item.thumb,40)
                self.osm.add_image(lat,lon,pb)
                imageinfo.set_coords(item,lat,lon)
                self.update_map_items()

    def print_tiles(self):
        if self.osm.get_property('tiles-queued') != 0:
            print self.osm.get_property('tiles-queued'), 'tiles queued'
        return True

    def zoom_in_clicked(self, button):
        self.osm.set_zoom(self.osm.get_property('zoom') + 1)
        self.update_latlon_entry()
        self.update_map_items()

    def zoom_out_clicked(self, button):
        self.osm.set_zoom(self.osm.get_property('zoom') - 1)
        self.update_latlon_entry()
        self.update_map_items()

    def home_clicked(self, button):
        if 'Home' in self.places:
            self.osm.set_mapcenter(*self.places['Home'])
        self.update_latlon_entry()
        self.update_map_items()

    def cache_clicked(self, button):
        bbox = self.osm.get_bbox()
        self.osm.download_maps(
            bbox[0],bbox[1],bbox[2],bbox[3], #was *bbox, but that doesn't work
            zoom_start=self.osm.get_property('zoom'),
            zoom_end=self.osm.get_property('max-zoom')
        )

    def update_latlon_entry(self,reset_place=True):
        self.latlon_entry.set_text(
                'latitude %s longitude %s' % (
                self.osm.get_property('latitude'),
                self.osm.get_property('longitude'),)
                )
        if reset_place:
            self.places_combo.child.set_text('')


    def map_clicked(self, osm, event):
        if event.button==1 and event.type==gtk.gdk._2BUTTON_PRESS:
            ##todo: if 2nd BUTTON_PRESS occurs affer _2BUTTON_PRESS, need to wait until after that event before zooing
            self.ignore_release=True
            self.osm.set_zoom(self.osm.get_property('zoom') + 1)
            return
        if event.button==1 and event.type==gtk.gdk.BUTTON_RELEASE and not self.ignore_release:
            coords=self.osm.get_co_ordinates(event.x, event.y)
            lat=coords[0]/math.pi*180
            lon=coords[1]/math.pi*180
            self.osm.set_mapcenter(lat, lon, self.osm.get_property('zoom'))
        self.update_latlon_entry()
        self.update_map_items()
        self.ignore_release=False

    def update_map_items(self):
        '''adds images to the map that are in the current view'''
        if not self.osm or not self.osm.window:
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
            lat,lon=imageinfo.get_coords(l[0])
            self.osm.add_image(lat,lon,l[1])
