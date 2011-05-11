import gtk
import os.path

import settings

'''Registers new icons with gtk.  Tries to use already existing icons
if they are available, otherwise it loads them from files.'''

ICON_INFO = [
  ('phraymd-rotate-left', 'phraymd-rotate-left.png'),
  ('phraymd-rotate-right', 'phraymd-rotate-right.png'),
  ('phraymd-sidebar', 'phraymd-sidebar.png'),
  ('phraymd-image-crop', 'phraymd-image-crop.png'),
  ('phraymd-image-rotate', 'phraymd-image-rotate.png'),
  ('phraymd-image-write', 'phraymd-image-write.png'),
  ('phraymd-transfer', 'phraymd-transfer.png'),
  ('phraymd-web-upload', 'phraymd-web-upload.png'),
  ('phraymd-map', 'phraymd-map.png'),
  ]

filename=os.path.abspath(__file__)
if filename.startswith('/usr/share/phraymd/phraymd/register_icons.py'):
    icon_path='/usr/share/phraymd/icons/'
else:
    icon_path=os.path.join(os.path.split(os.path.split(os.path.split(filename)[0])[0])[0],'icons/')
print 'REGISTERING ICONS IN',icon_path

def register_iconset(icon_info):
  iconfactory = gtk.IconFactory()
  stock_ids = gtk.stock_list_ids()
  for stock_id, file in icon_info:
      # only load image files when our stock_id is not present
      if stock_id not in stock_ids:
          pixbuf = gtk.gdk.pixbuf_new_from_file(icon_path+file)
          iconset = gtk.IconSet(pixbuf)
          iconfactory.add(stock_id, iconset)
  iconfactory.add_default()

register_iconset(ICON_INFO)
