'''

    phraymd
    Copyright (C) 2010  Damien Moore

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

##todo: create dbus service file to autostart phraymd if dbus is inactive

server=None

class DBusServer(dbus.service.Object):
    def __init__(self,bus):
        # Here the service name
        bus_name = dbus.service.BusName('org.spillz.phraymd',bus=bus)
        # Here the object path
        dbus.service.Object.__init__(self, bus_name, '/org/spillz/phraymd')

    @dbus.service.method('org.spillz.phraymd',in_signature='s',out_signature='s')
    def media_connected(self, uri):
        import pluginmanager
        pluginmanager.mgr.callback('media_connected',uri)
        print "DBus media connection event for "+uri
        return 'success'

def start():
    global server
    bus=dbus.SessionBus()
    if bus.name_has_owner('org.spillz.phraymd'):
        print 'Another phraymd instance already has the DBus name org.spillz.phraymd'
        return False
        ##could also just abort here and send a bring to front message to phraymd main window
    server = DBusServer(bus)
    print 'Registered dbus server'
    return True

