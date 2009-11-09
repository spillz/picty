#!/usr/bin/python

'''

    phraymd
    Copyright (C) 2009  Damien Moore

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

import sys
import os
import os.path

from plugins import tagui

try:
    plugins=['phraymd.plugins.'+path[:-3] for path in os.listdir(os.path.join(os.path.dirname(__file__),'plugins')) if path.endswith('.py') and not path.startswith('_')]
except:
    plugins=[]
try:
    userplugins=['userplugins.'+path[:-3] for path in os.listdir(os.path.join(settings.settings_dir,'plugins')) if path.endswith('.py') and not path.startswith('_')]
except:
    userplugins=[]

###print plugins
###for p in plugins:
###    __import__(p)

'''import user modules containing plugins'''
for p in plugins:
    try:
        print 'Importing system plugin',p
        __import__(p)
    except:
        import sys
        import traceback
        tb_text=traceback.format_exc(sys.exc_info()[2])
        print 'Error importing system plugin',p
        print tb_text
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


