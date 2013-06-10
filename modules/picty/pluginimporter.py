#!/usr/bin/python

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

##todo: need to add location of userplugins to sys.path

import sys, os, os.path

import settings

#find the plugins by scanning the plugin directories
try:
    zfilename = os.path.split(os.path.split(__file__)[0])[0]
    if zfilename.endswith('library.zip'):
        #on the windows py2exe build the plugins are stored in the library.zip
        #package of modules. Need to use zipfile to find them
        import zipfile
        z = zipfile.ZipFile(zfilename)
        plugins=['picty.plugins.'+os.path.splitext(os.path.split(n)[1])[0]
                    for n in z.namelist()
                        if n.startswith('picty/plugins') and not n.startswith('_')]
    else:
        plugins=['picty.plugins.'+os.path.splitext(n)[0]
            for n in os.listdir(os.path.join(os.path.dirname(__file__),'plugins'))
                if not n.startswith('_')]
except:
    plugins=[]

try:
    userplugins=['userplugins.'+os.path.splitext(path)[0] for path in os.listdir(os.path.join(settings.settings_dir,'plugins')) if not n.startswith('_')]
except:
    userplugins=[]

#converting to set ensures a unique set of plugins
plugins = set(plugins)
userplugins = set(userplugins)

#import the global and user modules containing plugins
for p in plugins:
    try:
        print 'Importing system plugin',p
        __import__(p)
    except:
        import sys
        import traceback
        tb_text=traceback.format_exc(sys.exc_info()[2])
        print >>sys.stderr,'Error importing system plugin',p
        print >>sys.stderr,tb_text
for p in userplugins:
    try:
        print 'Importing user plugin',p
        __import__(p)
    except:
        import sys
        import traceback
        tb_text=traceback.format_exc(sys.exc_info()[2])
        print 'Error importing user plugin',p
        print tb_text


