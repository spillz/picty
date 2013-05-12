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

'''
metadata.py

This module describes the subset of exif, iptc and xmp metadata used by the program
and provides a dictionary to handle conversion between exiv2 formats and the internal
representation
'''

import pyexiv2

if '__version__' in dir(pyexiv2) and pyexiv2.__version__>='0.2':
    print 'Using pyexiv2 version',pyexiv2.__version__
    from metadata2 import *
else:
    print 'Using pyexiv2 version 0.1.x'
    from metadata1 import *
