import gtk

#python standard lib imports
from datetime import date, datetime, timedelta
import time

from phraymd import dialogs, metadata

class SearchBox(gtk.HBox):
    def __init__(self):
        gtk.HBox.__init__(self)
        self.filter_combo=gtk.ComboBoxEntry()
        self.entry=self.filter_combo.child
#        self.entry.connect("activate",self.set_filter_text)
#        self.entry.connect("changed",self.filter_text_changed)

        try:
            self.entry.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY,gtk.STOCK_CLEAR)
            self.entry_no_icons=False
        except:
            print 'ERROR SETTING FILTER ENTRY'
            import sys,traceback
            tb_text=traceback.format_exc(sys.exc_info()[2])
            print tb_text
            self.entry_no_icons=True

        cell_text = gtk.CellRendererText()
        cell_pb = gtk.CellRendererPixbuf()
#        self.filter_combo.pack_start(cell_pb)
        self.filter_combo.pack_start(cell_text)
        self.filter_combo.add_attribute(cell_pb, 'pixbuf', 3)
        self.filter_combo.add_attribute(cell_text, 'text', 0)
        #icon=self.widget_render_source.render_icon(icon,self.size)
        #pb=gtk.image_new_from_stock(gtk.STOCK_CLOSE,gtk.ICON_SIZE_MENU)
        pb=self.filter_combo.render_icon(gtk.STOCK_CLOSE,gtk.ICON_SIZE_MENU)
        #self.filter_combo.set_wrap_width(3)

        self.search_options=[
            # combo text, search query, tooltip, pixbuf, callback
            ('Changed','changed','View images with unsaved changes',None,None),
            ('-','',None,None),
            ('Selected','selected','View images that have been selected',None,None),
            ('Unselected','!selected','View images that have been selected',None,None),
            ('-','',None,None),
            ('Tags...',self.tag_cb,'View images that have been tagged',None,None),
            ('Tagged','tagged','View images that have been tagged',None,None),
            ('Untagged','!tagged','View images the have not been tagged',None,None),
            ('Geo-tagged','geotagged','View images that have geographic location metadata',None,None),
            ('-','',None,None),
            ('Date Taken...',self.taken_cb,'View images that were taken in a specified date range',None,None),
            ('Taken Today',self.taken_today_cb,'View images that were taken today',None,None),
            ('Taken Last Week',self.taken_last_week_cb,'View images that were taken in the last week',None,None),
            ('Taken Last Month',self.taken_last_month_cb,'View images that were taken in the last month',None,None),
            ('-','',None,None),
            ('Date Last Modified...',self.mod_cb,'View images that were last modified in a specified date range',None,None),
            ('Last Modified Today',self.mod_today_cb,'View images that were modified today',None,None),
            ('Last Modified a Week Ago',self.mod_last_week_cb,'View images that were modified in the last week',None,None),
            ('Last Modified a Month Ago',self.mod_last_month_cb,'View images that were modified in the last month',None,None),
            #('-','',None,None),
            ]
        liststore = gtk.ListStore(str, gtk.gdk.Pixbuf)
        for s in self.search_options:
            liststore.append([s[0],pb])
        self.filter_combo.set_row_separator_func(self.sep_fn)
        self.filter_combo.set_model(liststore)
        self.filter_combo.connect('changed', self.changed_cb)
        self.filter_combo.show()
        self.pack_start(self.filter_combo)
        return

    def sep_fn(self,model,iter,data=None):
        if model[iter][0]!='-':
            return False
        else:
            return True

    def changed_cb(self, combobox):
        key_mods=gtk.gdk.display_get_default().get_pointer()[3]
        prefix=''
        if key_mods&(gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
            prefix='lastview&'
        model = combobox.get_model()
        index = combobox.get_active()
        if index > -1:
            print model[index][0], 'selected'
            if type(self.search_options[index][1])!=str:
                terms=self.search_options[index][1]()
                if terms==None:
                    return
                self.entry.set_text(prefix+terms)
            else:
                self.entry.set_text(prefix+self.search_options[index][1])
            self.entry.activate()

    def tag_cb(self):
        response,tag_text=dialogs.entry_dialog("Search by Tags","Enter tags to search for separate by spaces (enclose tags with spaces in \"quotes\"")
        if response==1:
            return None
        tags=metadata.tag_split(tag_text)
        print '####TAG_SEARCH',tags
        tag_search=''
        for t in tags:
            if tag_search:
                tag_search+="&"
            tag_search+='tag="%s"'%(t,)
        print '####TAG SEARCH',tag_search
        return tag_search

    def taken_cb(self):
        result,date_from,date_to=dialogs.date_range_entry_dialog("Search By Date Taken","Select A Date Range")
        if result!=0:
            return None
        search_str=''
        if date_from:
            search_str+='date>="%s"'%(str(date_from))
        if date_to:
            if search_str:
                search_str+='&'
            search_str+='date<="%s"'%(str(date_to))
        if not search_str:
            return None
        return search_str

    def taken_today_cb(self):
        today=date.fromtimestamp(time.time())
        return 'date>="%s"'%(str(today),)

    def taken_last_week_cb(self):
        now=date.fromtimestamp(time.time())
        lastweek=now-timedelta(days=7)
        return 'date>="%s"'%(str(lastweek),)

    def last_month(self):
        now=date.fromtimestamp(time.time())
        day=now.day
        if now.month>1:
            while day>=1:
                try:
                    lastmonth=date(now.year,now.month-1,day)
                    break
                except:
                    day-=1
        else:
            while day>=1:
                try:
                    lastmonth=date(now.year-1,12,day)
                    break
                except:
                    day-=1
        return lastmonth

    def taken_last_month_cb(self):
        return 'date>="%s"'%(str(self.last_month()))

    def mod_cb(self):
        result,date_from,date_to=dialogs.date_range_entry_dialog("Search By Last Modified Date","Select A Date Range")
        if result!=0:
            return None
        search_str=''
        if date_from:
            search_str+='mdate>="%s"'%(str(date_from))
        if date_to:
            if search_str:
                search_str+='&'
            search_str+='mdate<="%s"'%(str(date_to))
        if not search_str:
            return None
        return search_str

    def mod_today_cb(self):
        today=date.fromtimestamp(time.time())
        return 'mdate>="%s"'%(str(today),)

    def mod_last_week_cb(self):
        now=date.fromtimestamp(time.time())
        lastweek=now-timedelta(days=7)
        return 'mdate>="%s"'%(str(lastweek),)

    def mod_last_month_cb(self):
        return 'mdate>="%s"'%(str(self.last_month()))

