#!/usr/bin/env python

from distutils.core import setup

setup(name='phraymd',
      version='0.2',
      description='phraymd Photo Manager',
      author='Damien Moore',
      author_email='damien.moore@excite.com',
      url='https://launchpad.net/phraymd',
      package_dir={'':'modules'},
      packages=['phraymd','phraymd.plugins','phraymd.plugins.webupload_services'],
      scripts=['bin/phraymd','bin/phraymd-import'],
      data_files=[
        ('share/applications',['desktop/phraymd.desktop','desktop/phraymd-import.desktop']),
        ('share/pixmaps',['desktop/phraymd.png']),
        ('share/dbus-1/services',['desktop/org.spillz.phraymd.service']),
        ('share/phraymd/icons',['icons/phraymd-image-crop.png','icons/phraymd-image-write.png','icons/phraymd-rotate-right.png',
            'icons/phraymd-image-rotate.png','icons/phraymd-rotate-left.png','icons/phraymd-sidebar.png'])
        ]
     )
