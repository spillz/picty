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

import dbus
import dbus.service
import dbus.glib

##todo: create dbus service file to autostart picty if dbus is inactive

server=None

class DBusServer(dbus.service.Object):
    def __init__(self,bus):
        # set service name
        bus_name = dbus.service.BusName('org.spillz.picty',bus=bus)
        # set the object path
        dbus.service.Object.__init__(self, bus_name, '/org/spillz/picty')

    @dbus.service.method('org.spillz.picty',in_signature='s',out_signature='s')
    def media_connected(self, uri):
        import pluginmanager
        pluginmanager.mgr.callback('media_connected',uri)
        print "DBus media connection event for "+uri
        return 'success'

    @dbus.service.method('org.spillz.picty',in_signature='s',out_signature='s')
    def open_uri(self, uri):
        import pluginmanager
        pluginmanager.mgr.callback('open_uri',uri)
        print "DBus open uri event for "+uri
        return 'success'

    @dbus.service.method('org.spillz.phraymd',in_signature='s',out_signature='s')
    def open_device(self, device):
        import pluginmanager
        pluginmanager.mgr.callback('open_device',device)
        print "DBus open device event for "+device
        return 'success'

def start():
    global server
    bus=dbus.SessionBus()
    if bus.name_has_owner('org.spillz.picty'):
        print 'Another picty instance already has the DBus name org.spillz.picty'
        return False
        ##could also just abort here and send a "bring to front" message to picty main window
    server = DBusServer(bus)
    print 'Registered dbus server'
    return True

