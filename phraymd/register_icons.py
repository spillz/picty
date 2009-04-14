import gtk
import os.path

'''Registers new icons with gtk.  Tries to use already existing icons
if they are available, otherwise it loads them from files.'''

ICON_INFO = [
  ('phraymd-rotate-left', 'phraymd-rotate-left.png'),
  ('phraymd-rotate-right', 'phraymd-rotate-right.png'),
  ]

icon_path=os.path.join(os.path.split(__file__)[0],'icons/')

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
