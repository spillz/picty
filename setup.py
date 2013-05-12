#!/usr/bin/env python

from distutils.core import setup

setup(name='picty',
      version='0.2',
      description='picty Photo Manager',
      author='Damien Moore',
      author_email='damien.moore@excite.com',
      url='https://launchpad.net/picty',
      package_dir={'':'modules'},
      packages=['picty','picty.plugins','picty.collectiontypes'],
      scripts=['bin/picty','bin/picty-import', 'bin/picty-open'],
      data_files=[
        ('share/applications',['desktop/picty.desktop','desktop/picty-import.desktop', 'desktop/picty-open.desktop']),
        ('share/pixmaps',['desktop/picty.png']),
        ('share/dbus-1/services',['desktop/org.spillz.picty.service']),
        ('share/picty/icons',['icons/picty-image-crop.png','icons/picty-image-write.png','icons/picty-rotate-right.png',
            'icons/picty-image-rotate.png','icons/picty-rotate-left.png','icons/picty-sidebar.png',
            'icons/picty-polaroids-and-frame.png','icons/picty-transfer.png',
            'icons/picty-map.png'])
        ]
     )
