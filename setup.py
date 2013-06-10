#!/usr/bin/env python
from distutils.core import setup
import os,os.path,sys,platform


def stamp_version():
    version = 'testing-r'+os.popen('bzr revno').read().strip()
    print 'Version',version
    settings = file('modules/picty/settings.py','rb').read()
    settings = settings.replace('{source}',version)
    file('modules/picty/settings.py','wb').write(settings)
    settings = file('picty.iss','rb').read()
    settings = settings.replace('%source%',version)
    file('picty.iss','wb').write(settings)
    return version

version = stamp_version()

if platform.system() != 'Windows':
    from distutils.core import setup

    setup(name='picty',
          version=version,
          description='picty Photo Manager',
          author='Damien Moore',
          author_email='damienlmoore@gmail.com',
          url='https://launchpad.net/picty',
          package_dir={'':'modules'},
          packages=['picty','picty.plugins','picty.collectiontypes','picty.fstools','picty.uitools','picty.metadata'],
          scripts=['bin/picty','bin/picty-import', 'bin/picty-open'],
          data_files=[
            ('share/applications',['desktop/picty.desktop','desktop/picty-import.desktop', 'desktop/picty-open.desktop']),
            ('share/pixmaps',['desktop/picty.png']),
            ('share/dbus-1/services',['desktop/org.spillz.picty.service']),
            ('share/picty/icons',['icons/picty-5-polaroids.png','icons/picty-image-crop.png','icons/picty-image-write.png','icons/picty-rotate-right.png',
                'icons/picty-image-rotate.png','icons/picty-rotate-left.png','icons/picty-sidebar.png',
                'icons/picty-polaroids-and-frame.png','icons/picty-transfer.png',
                'icons/picty-map.png'])
            ]
         )
else:
    import py2exe

    # Find GTK+ installation path
    __import__('gtk')
    m = sys.modules['gtk']
    gtk_base_path = m.__path__[0]

    setup(
        name = 'picty',
        description = 'picty Photo Manager',
        version = version,

        windows = [
                      {
                          'script': 'bin/picty',
                          'icon_resources': [(1, "icons/picty.ico")],
                      }
                  ],

        author='Damien Moore',
        author_email='damienlmoore@gmail.com',
        url='https://launchpad.net/picty',
        package_dir={'':'modules'},
          packages=['picty','picty.plugins','picty.collectiontypes','picty.fstools','picty.uitools','picty.metadata'],
        options = {
                      'py2exe': {
                          'packages':'encodings,picty,picty.collectiontypes,picty.plugins,picty.fstools,picty.uitools,picty.metadata',
                          'includes': ' cairo, pango, pangocairo, atk, gobject, gio, gtk.keysyms',
                      }
                  },

        data_files=[
        ('desktop',['desktop/picty.png']),
        ('icons',['icons/picty-5-polaroids.png','icons/picty-image-crop.png','icons/picty-image-write.png','icons/picty-rotate-right.png',
            'icons/picty-image-rotate.png','icons/picty-rotate-left.png','icons/picty-sidebar.png',
            'icons/picty-polaroids-and-frame.png','icons/picty-transfer.png',
            'icons/picty-map.png']),
        # For GTK+'s built in SVG support
        #        os.path.join(gtk_base_path, '..', 'runtime', 'bin', 'gdk-pixbuf-query-loaders.exe'),
        #        os.path.join(gtk_base_path, '..', 'runtime', 'bin', 'libxml2-2.dll'),
        ]
    )
