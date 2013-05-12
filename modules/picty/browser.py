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


##standard python lib imports
import threading
import os
import os.path
import subprocess
import time
import datetime
import bisect
import gobject

import sys
sys.path.insert(0,'/usr/share') ##private module location on installed version

##gtk imports and init
import gobject
import gtk
import pango
gobject.threads_init()
gtk.gdk.threads_init()

## local imports
import settings
import viewer
import backend
import dialogs
import pluginmanager
import viewsupport
import io

import imagemanip

class ImageBrowser(gtk.HBox):
    '''
    a widget designed to display a collection of images
    in an image collection.
    '''
    # constants for selection modes (not used currently)
    MODE_NORMAL=1
    MODE_TAG=2

    # various constants for XDS (Drag save) implementation
    TARGET_TYPE_URI_LIST = 0
    TARGET_TYPE_XDS = 1
    TARGET_TYPE_IMAGE = 2
    XDS_ATOM = gtk.gdk.atom_intern("XdndDirectSave0")
    TEXT_ATOM = gtk.gdk.atom_intern("text/plain")
    XDS_SUCCESS = "S"
    XDS_FAILURE = "F"
    XDS_ERROR = "E"

    ##todo: need signals to notify of collection changes, view changes
    ##also want to submit all changes to items, view or collection through the worker thread
    __gsignals__={
        'activate-item':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_INT,gobject.TYPE_PYOBJECT)),
        'context-click-item':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_INT,gobject.TYPE_PYOBJECT)),
        'view-changed':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,tuple()),
        'collection-online-state':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,gobject.TYPE_BOOLEAN)),
        'view-rebuild-complete':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,tuple()),
        'status-updated':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_FLOAT,gobject.TYPE_GSTRING)),
        'backstatus-updated':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_BOOLEAN,gobject.TYPE_GSTRING)),
        'tag-row-dropped':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT)),
        'uris-dropped':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,gobject.TYPE_PYOBJECT))
        }
    def __init__(self,hover_cmds=()):
        '''
        init takes an optional list or tuple describing onmouseover shortcuts buttons
        '''
        gtk.HBox.__init__(self)
        self.hover_cmds=hover_cmds
        self.configure_geometry()
        self.lock=threading.Lock()

#        self.active_view=active_view
#        self.active_collection=active_collection

        self.neededitem=None

        self.mode=self.MODE_NORMAL

        self.pressed_ind=-1
        self.pressed_item=None
        self.last_selected_ind=-1
        self.last_selected=None
        self.button_press_block=False

        self.focal_item=None

        self.shift_state=False

        self.pixbuf_thumb_fail=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,True,8,128,128)
        self.pixbuf_thumb_load=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,True,8,128,128)
        self.pixbuf_thumb_fail.fill(0xC0000080)
        self.pixbuf_thumb_load.fill(0xFFFFFF20)

        self.geo_view_offset=0
        self.offsetx=0
        self.geo_ind_view_first=0
        self.geo_ind_view_last=1
        self.hover_ind=-1
        self.command_highlight_ind=-1
        self.command_highlight_bd=False

        self.imarea=gtk.DrawingArea()
        self.imarea.set_property("can-focus",True)
        self.imarea.set_size_request(160,160)
        self.imarea.set_property("has-tooltip",True)
        self.imarea.connect("query-tooltip",self.drawable_tooltip_query)

        self.scrolladj=gtk.Adjustment()
        self.vscroll=gtk.VScrollbar(self.scrolladj)
        self.vscroll.set_property("has-tooltip",True)
        self.vscroll.connect("query-tooltip",self.scroll_tooltip_query)

        self.vbox=gtk.VBox()
        self.vbox.pack_start(self.imarea)
        self.vbox.show()

        self.bbox=gtk.HBox()
        self.bbox.pack_start(self.vbox)
        self.bbox.pack_start(self.vscroll,False)
        self.bbox.show()

        self.hpane=gtk.HPaned()
        self.hpane.add1(self.bbox)
        self.hpane.show()
        self.pack_start(self.hpane)

        self.imarea.connect("realize",self.realize_signal)
        self.imarea.connect("configure_event",self.configure_signal)
        self.imarea.connect("expose_event",self.expose_signal)

        self.mouse_hover=False
        self.imarea.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.imarea.connect("motion-notify-event",self.mouse_motion_signal)
        self.imarea.add_events(gtk.gdk.LEAVE_NOTIFY_MASK)
        self.imarea.connect("leave-notify-event",self.mouse_leave_signal)
        self.imarea.add_events(gtk.gdk.ENTER_NOTIFY_MASK)
        self.imarea.connect("enter-notify-event",self.mouse_enter_signal)

        self.scrolladj.connect("value-changed",self.scroll_signal)
        self.imarea.add_events(gtk.gdk.SCROLL_MASK)
        self.imarea.connect("scroll-event",self.scroll_signal_pane)
        self.imarea.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.imarea.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
        self.imarea.connect("button-press-event",self.button_press)
        self.imarea.connect("button-release-event",self.button_press)

        self.imarea.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.imarea.add_events(gtk.gdk.KEY_RELEASE_MASK)
        self.imarea.connect("key-press-event",self.key_press_signal)
        self.imarea.connect("key-release-event",self.key_press_signal)

        target_list=[('image-filename', gtk.TARGET_SAME_APP, self.TARGET_TYPE_IMAGE)] #("XdndDirectSave0", 0, self.TARGET_TYPE_XDS),
        target_list=gtk.target_list_add_uri_targets(target_list,self.TARGET_TYPE_URI_LIST)
#        target_list=gtk.target_list_add_text_targets(target_list,self.TARGET_TYPE_URI_LIST)
        self.imarea.drag_source_set(gtk.gdk.BUTTON1_MASK,
                  target_list,gtk.gdk.ACTION_COPY)#| gtk.gdk.ACTION_MOVE)
                  #gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE |  gtk.gdk.ACTION_COPY)

        target_list=[('tag-tree-row', gtk.TARGET_SAME_APP, 0)]
        target_list=gtk.target_list_add_uri_targets(target_list,1)
        self.imarea.drag_dest_set(gtk.DEST_DEFAULT_ALL,
                target_list,
                gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_COPY)

        self.imarea.connect("drag-data-get",self.drag_get_signal)
        self.imarea.connect("drag-begin", self.drag_begin_signal)
        self.imarea.connect("drag-end",self.drag_end_signal)
        self.imarea.connect("drag-data-received",self.drag_receive_signal)
        self.imarea.connect("drag-motion",self.drag_motion_signal)
        self.imarea.connect("drag-leave",self.drag_leave_signal)
        #self.imarea.drag_source_set_icon_stock('browser-drag-icon')

        self.imarea.show()
        self.vscroll.show()
        self.imarea.grab_focus()

    def resize_pane(self):
        w,h=self.hpane.window.get_size()
        if self.geo_thumbwidth+2*self.geo_pad>=w:
            self.hpane.set_position(w/2)
        else:
            self.hpane.set_position(self.geo_thumbwidth+2*self.geo_pad)

    def add_viewer(self,viewer):
        self.hpane.add2(viewer)
##        self.resize_pane()

    def remove_viewer(self,viewer):
        self.hpane.remove(viewer)

    def drawable_tooltip_query(self,widget,x, y, keyboard_mode, tooltip):
        if self.hover_ind<0:
            return
        cmd=self.get_hover_command(self.hover_ind, x, y)
        if cmd>=0:
            cmd=self.hover_cmds[cmd]
            item=self.active_view(self.hover_ind)
            if cmd.is_active(item,True)>=0:
                tooltip.set_text(cmd.tooltip)
                return True

    def scroll_tooltip_query(self,widget,x, y, keyboard_mode, tooltip):

#        height=widget.window.get_size()[1]
#        yscroll=y*self.scrolladj.upper/height
#        ind=min(len(self.tm.view),max(0,int(yscroll)/(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count))
#        key=self.sort_order.get_active_text()
#        key_fn=imageinfo.sort_keys_str[key]
#        item=self.tm.view(ind)
#        tooltip.set_text(key+': '+str(key_fn(item)))
        return True


    def update_status(self,progress,message):
        self.emit('status-updated',progress,message)

    def update_backstatus(self,progress,message):
        self.emit('backstatus-updated',progress,message)

    def key_press_signal(self,obj,event):
        ##todo: perhaps return true for some of these to prevent further emission
        if event.type==gtk.gdk.KEY_PRESS:
#            if event.keyval==65362: #up
#                self.vscroll.set_value(self.vscroll.get_value()-self.scrolladj.step_increment)
#            elif event.keyval==65364: #dn
#                self.vscroll.set_value(self.vscroll.get_value()+self.scrolladj.step_increment)
#            elif event.keyval==65365: #pgup
#                self.vscroll.set_value(self.vscroll.get_value()-self.scrolladj.page_increment)
#            elif event.keyval==65366: #pgdn
#                self.vscroll.set_value(self.vscroll.get_value()+self.scrolladj.page_increment)
#            elif event.keyval==65360: #home
#                self.vscroll.set_value(self.scrolladj.lower)
#            elif event.keyval==65367: #end
#                self.vscroll.set_value(self.scrolladj.upper)
            if event.keyval==65505: #shift
                self.redraw_view()
            elif event.keyval==65507: #control
                self.redraw_view()
        if event.type==gtk.gdk.KEY_RELEASE:
            if event.keyval==65505: #shift
                self.redraw_view()
            elif event.keyval==65507: #control
                self.redraw_view()

    def get_hover_command(self, ind, x, y):
        offset=ind-self.geo_ind_view_first
        item=self.active_view(ind)
        if item:
            left=(offset%self.geo_horiz_count)*(self.geo_thumbwidth+self.geo_pad)
            left+=self.geo_pad/4
            top=self.geo_ind_view_first*(self.geo_thumbheight+self.geo_pad)/self.geo_horiz_count-int(self.geo_view_offset)
            top+=offset/self.geo_horiz_count*(self.geo_thumbheight+self.geo_pad)
            top+=self.geo_pad/4
            return self.hover_cmds.get_command(x,y,left,top,self.geo_pad/6,item,True)
        return -1

    def item_to_view_index(self,item):
        return self.active_view.find_item(item)

    def item_to_scroll_value(self,item):
        ind=self.item_to_view_index(item)
        return max(0,ind*(self.geo_thumbheight+self.geo_pad)/self.geo_horiz_count)#-self.geo_width/2)

    def multi_select(self,ind_from,ind_to,select=True):
        '''select multiple items in a given array subscript range of the view'''
        self.tm.lock.acquire()
        if ind_to>ind_from:
            for x in range(ind_from,ind_to+1):
                item=self.active_view(x)
                if not item.selected and select:
                    self.active_collection.numselected+=1
                if item.selected and not select:
                    self.active_collection.numselected-=1
                item.selected=select
        else:
            for x in range(ind_from,ind_to-1,-1):
                item=self.active_view(x)
                if not item.selected and select:
                    self.active_collection.numselected+=1
                if item.selected and not select:
                    self.active_collection.numselected-=1
                item.selected=select
        self.tm.lock.release()
        self.emit('view-changed')
        self.redraw_view()

    def select_item(self,ind):
        '''select an item by array index of the view. in tag mode, toggles
        whatever tags are checked in the tag pane'''
        if 0<=ind<len(self.active_view):
            item=self.active_view(ind)
            if self.mode==self.MODE_NORMAL:
                if item.selected:
                    self.active_collection.numselected-=1
                else:
                    self.active_collection.numselected+=1
                item.selected=not item.selected
            self.last_selected=item
            self.last_selected_ind=ind
            self.emit('view-changed')
            self.redraw_view()

    def button_press(self,obj,event):
        '''callback for mouse button presses (handles selections, view double clicks,
            context menu right clicks, mouse overlay clicks)'''
        self.command_highlight_bd=False
        self.imarea.grab_focus()
        self.lock.acquire()
        ind=(int(self.geo_view_offset)+int(event.y))/(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count
        ind+=min(self.geo_horiz_count*(self.geo_thumbheight+self.geo_pad),int(event.x)/(self.geo_thumbwidth+self.geo_pad))
        if ind<0 or ind>len(self.active_view)-1 or event.x==0 and event.y==0 or event.x>=self.geo_horiz_count*(self.geo_thumbheight+self.geo_pad):
            item=None
            ind=-1
        else:
            item=self.active_view(ind)
        if item and event.button==1 and event.type==gtk.gdk._2BUTTON_PRESS:
##            if ind==self.pressed_ind and self.tm.view(ind)==self.pressed_item and event.x<=(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count:
                self.emit("activate-item",ind,item)
                self.button_press_block=True
                if item==self.pressed_item:
                    self.select_item(self.pressed_ind)
        elif event.button==1 and event.type==gtk.gdk.BUTTON_RELEASE:
                if item and not self.button_press_block:
                    self.drop_item=item
                    cmd=self.get_hover_command(ind,event.x,event.y)
                    if cmd>=0 and not event.state&(gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                        cmd=self.hover_cmds.tools[cmd]
                        if ind==self.pressed_ind and item==self.pressed_item and event.x<=(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count:
                            if cmd.is_active(item,self.hover_ind==ind)>=0:
                                cmd.action(cmd,self.pressed_item)
                        self.redraw_view()
                    else:
                        if self.last_selected and event.state&(gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                            ind=self.item_to_view_index(self.last_selected)
                            if ind>=0:
                                self.multi_select(ind,self.pressed_ind,bool(event.state&gtk.gdk.SHIFT_MASK))
                        else:
                            if item==self.pressed_item:
                                self.select_item(self.pressed_ind)
                self.button_press_block=False
        elif item and event.button==1 and event.type==gtk.gdk.BUTTON_PRESS:
            cmd=self.get_hover_command(ind,event.x,event.y)
            if cmd>=0 and not event.state&(gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                self.command_highlight_bd=True
                self.redraw_view()
        elif item and event.button==3 and event.type==gtk.gdk.BUTTON_RELEASE:
            self.emit("context-click-item",ind,item)
        if item and event.button==1 and event.type in (gtk.gdk.BUTTON_PRESS,gtk.gdk._2BUTTON_PRESS):
            self.drag_item=item
            self.pressed_ind=ind
            self.pressed_item=self.active_view(ind)
        else:
            self.pressed_ind=-1
            self.pressed_item=None
        self.lock.release()

    def drag_begin_signal(self, widget, drag_context):
        '''
        callback when user has started dragging one or more items in the browser's image area
        '''
#       NB: self.drag_item is set in the button_press callback instead of here
#        drag_context.source_window.property_change(self.XDS_ATOM, self.TEXT_ATOM, 8,
#                                              gtk.gdk.PROP_MODE_REPLACE,"a")
        if self.command_highlight_ind>=0:
            return True


    def drag_end_signal(self, widget, drag_context):
        '''
        callback when user has finished dragging one or more items in the browser's image area
        '''
        self.drag_item=None
#        drag_context.source_window.property_delete(self.XDS_ATOM) #FOR XDS

    def drag_get_signal(self, widget, drag_context, selection_data, info, timestamp):
        '''
        callback triggered to set the selection_data payload
        (viewer is the source of the drop)
        '''
        if self.drag_item==None:
            return
        if info == self.TARGET_TYPE_IMAGE:
            selection_data.set('image-filename', 8, self.drag_item.uid)
        if info == self.TARGET_TYPE_XDS: #drag save is currently disabled (unnecessary?)
            if self.XDS_ATOM in drag_context.targets:
                typ, fmt, dest = drag_context.source_window.property_get(self.XDS_ATOM,self.TEXT_ATOM)
                success=True
                code = self.XDS_SUCCESS if success else self.XDS_ERROR
                selection_data.set(selection_data.target, 8, code)
            self.drag_item=None
        if info == self.TARGET_TYPE_URI_LIST:
            print 'uri list'
            if not self.drag_item.selected:
                uri=io.get_uri(self.active_collection.get_path(self.drag_item)) #I don't know why, but nautilius expects uris enclosed in quotes
                selection_data.set_uris([uri])
                print 'set uri',uri
            else:
                uris=[]
                i=0
                while i<len(self.active_view):
                    item=self.active_view(i)
                    if item.selected:
                        uri=io.get_uri(self.active_collection.get_path(item))
                        uris.append(uri)
                    i+=1
                selection_data.set_uris(uris)

    def drag_receive_signal(self, widget, drag_context, x, y, selection_data, info, timestamp):
        '''callback triggered to retrieve the selection_data payload
        (browser is the destination of the drop)'''
        ind=(int(self.geo_view_offset)+int(y))/(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count
        ind+=min(self.geo_horiz_count,int(x)/(self.geo_thumbwidth+self.geo_pad))
        ind=max(0,min(len(self.active_view)-1,ind))
        item=self.active_view(ind)
        if selection_data.type=='tag-tree-row':
            data=selection_data.data
            paths=data.split('-')
            self.emit('tag-row-dropped',item,drag_context.get_source_widget(),paths[0]) ##todo: need to pass source widget in case there is more than one tag tree
            return
        uris=selection_data.get_uris()
        if uris: ##todo: do we  actually want to process dropped uris? don't forget to ignore drops from self
            for uri in uris:
                print 'dropped uris',uris
                self.emit('uris-dropped',item,uris)

    def drag_motion_signal(self, widget, drag_context, x, y, timestamp):
        self.redraw_view() ##todo: could do some calcs to see if anything actually needs to be redrawn

    def drag_leave_signal(self, widget, drag_context, timestamp):
        self.redraw_view()

    def recalc_hover_ind(self,x,y):
        '''return the index of the item of the drawable coordinates (x,y)'''
        ind=(int(self.geo_view_offset)+int(y))/(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count
        ind+=min(self.geo_horiz_count,int(x)/(self.geo_thumbwidth+self.geo_pad))
        if ind<0 or ind>len(self.active_view)-1 or x>=(self.geo_thumbheight+self.geo_pad)*self.geo_horiz_count:
            ind=-1
        return ind

    def mouse_motion_signal(self,obj,event):
        '''callback when mouse moves in the viewer area (updates image overlay as necessary)'''
        if not self.mouse_hover:
            return
        ind=self.recalc_hover_ind(event.x,event.y)
        cmd=self.get_hover_command(ind,event.x,event.y)
        if self.hover_ind!=ind or self.command_highlight_ind!=cmd:
            self.hover_ind=ind
            self.command_highlight_ind=cmd
            self.redraw_view()

    def mouse_leave_signal(self,obj,event):
        '''callback when mouse leaves the viewer area (hides image overlays)'''
        self.mouse_hover=False
        if self.hover_ind>=0:
            self.command_highlight_ind=-1
            self.hover_ind=-1
            self.redraw_view()

    def mouse_enter_signal(self,obj,event):
        '''callback when mouse leaves the viewer area (hides image overlays)'''
        self.mouse_hover=True
#        self.redraw_view()

    def redraw_view(self,collection=None):
        '''redraw the view without recomputing geometry or changing position'''
        if collection!=None and collection!=self.active_collection:
            return
        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)

##    def update_info_bar(self):
##        '''refresh the info bar (status bar that displays number of images etc)'''
##        pass
##        ##todo: send a signal about collection updates
##        #self.info_bar.set_label('%i images in collection (%i selected, %i in view)'%(len(self.tm.collection),self.tm.collection.numselected,len(self.tm.view)))

    def resize_and_refresh_view(self,collection=None):
        '''update geometry, scrollbars, redraw the thumbnail view'''
        if collection==None or collection!=self.active_collection:
            return
        self.emit('view-changed')
        self.update_geometry()
        ##self.update_required_thumbs()
        self.update_scrollbar()
#        self.update_info_bar()
        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)

    def collection_online(self,collection):
        self.emit('collection-online-state',collection,collection.online)

    def collection_offline(self,collection):
        self.emit('collection-online-state',collection,collection.online)

    def post_build_view(self):
        '''callback function to receive notification from worker that
        view has finished rebuilding'''
        self.emit('view-rebuild-complete')
#        self.tagframe.refresh(self.tm.view.tag_cloud)

    def update_view(self):
        '''reset position, update geometry, scrollbars, redraw the thumbnail view'''
        self.geo_view_offset=0
        self.resize_and_refresh_view()

    def scroll_signal_pane(self,obj,event):
        '''scrolls the view on mouse wheel motion'''
        if event.direction==gtk.gdk.SCROLL_UP:
            self.scroll_up(max(1,self.geo_thumbheight+self.geo_pad)/5)
        if event.direction==gtk.gdk.SCROLL_DOWN:
            self.scroll_down(max(1,self.geo_thumbheight+self.geo_pad)/5)

    def scroll_signal(self,obj):
        '''signal response when the scroll position changes'''
        self.geo_view_offset=self.scrolladj.get_value()
#        self.update_geometry()
        self.update_view_index_range()
        ##self.update_required_thumbs()
        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)
        self.vscroll.trigger_tooltip_query()

    def update_scrollbar(self):
        '''called to resync the scrollbar to changes in view geometry'''
        upper=len(self.active_view)/self.geo_horiz_count
        if len(self.active_view)%self.geo_horiz_count!=0:
            upper+=1
        upper=upper*(self.geo_thumbheight+self.geo_pad)
        self.scrolladj.set_all(value=self.geo_view_offset, lower=0,
                upper=upper,
                step_increment=max(1,self.geo_thumbheight+self.geo_pad)/5,
                page_increment=self.geo_height, page_size=self.geo_height)

    def scroll(self,direction):
        if direction=='up':
            self.vscroll.set_value(self.vscroll.get_value()-self.scrolladj.step_increment)
        if direction=='dn':
            self.vscroll.set_value(self.vscroll.get_value()+self.scrolladj.step_increment)
        if direction=='pgup':
            self.vscroll.set_value(self.vscroll.get_value()-self.scrolladj.page_increment)
        if direction=='pgdn':
            self.vscroll.set_value(self.vscroll.get_value()+self.scrolladj.page_increment)
        if direction=='home':
            self.vscroll.set_value(self.scrolladj.lower)
        if direction=='end':
            self.vscroll.set_value(self.scrolladj.upper)


    def scroll_up(self,step=10):
        '''call to scroll the view up by step pixels'''
        self.vscroll.set_value(self.vscroll.get_value()-step)

    def scroll_down(self,step=10):
        '''call to scroll the view down by step pixels'''
        self.vscroll.set_value(self.vscroll.get_value()+step)

    def configure_geometry(self):
        '''first time initialization of geometry (called from __init__)'''
        self.geo_thumbwidth=128
        self.geo_thumbheight=128
        self.geo_pad=32
        self.geo_view_offset=0
        self.geo_screen_offset=0
        self.geo_ind_view_first=0
        self.geo_ind_view_last=0
        self.geo_horiz_count=1

    def update_view_index_range(self):
        '''computes the first and last indices in the view'''
        self.geo_ind_view_first = int(self.geo_view_offset/(self.geo_thumbheight+self.geo_pad))*self.geo_horiz_count
        self.geo_ind_view_last = self.geo_ind_view_first+self.geo_horiz_count*(2+self.geo_height/(self.geo_thumbheight+self.geo_pad))

    def update_geometry(self,recenter=False):
        '''recompute the changeable parts of the geometry (usually called in response to window
           size changes, or changes to the number of items in the collection'''
        nudge=self.calc_screen_offset()
        self.geo_horiz_count=max(int(self.geo_width/(self.geo_thumbwidth+self.geo_pad)),1)
        self.geo_view_offset_max=max(1,(self.geo_thumbheight+self.geo_pad)+(len(self.active_view)-1)*(self.geo_thumbheight+self.geo_pad)/self.geo_horiz_count)
        self.geo_view_offset=max(0,min(self.geo_view_offset_max-self.geo_height,self.geo_view_offset))
        if recenter:
            if self.focal_item!=None:
                ind=self.item_to_view_index(self.focal_item)
            else:
                ind=-1
            if self.geo_ind_view_first<=ind<=self.geo_ind_view_last:
                self.center_view_offset(ind)
            else:
                self.set_view_offset(self.geo_ind_view_first)
                self.geo_view_offset-=nudge
        #print 'geo',self.geo_view_offset
        self.update_view_index_range()

    def update_required_thumbs(self):
        #self.lock.acquire()
        onscreen_items=self.active_view.get_items(self.geo_ind_view_first,min(self.geo_ind_view_last,len(self.active_view)))
        self.tm.request_thumbnails(onscreen_items) ##todo: caching ,fore_items,back_items
        #self.lock.release()

    def calc_screen_offset(self):
        '''computes how much to offset the first item in the view from the top of the screen (this should be negative)'''
        return int(self.geo_ind_view_first/self.geo_horiz_count)*(self.geo_pad+self.geo_thumbheight)-self.geo_view_offset

    def set_view_offset(self,index):
        '''reset the view offset position to keep the first item on screen after a window size change'''
        self.geo_view_offset=int(index/self.geo_horiz_count)*(self.geo_pad+self.geo_thumbheight)+self.geo_screen_offset
        self.geo_view_offset=max(0,min(self.geo_view_offset_max-self.geo_height,self.geo_view_offset))

    def center_view_offset(self,index):
        '''center the view on particular item in the view (receives an index)'''
        self.geo_screen_offset=0
        self.geo_view_offset=int(index/self.geo_horiz_count)*(self.geo_pad+self.geo_thumbheight)-self.geo_height/2+(self.geo_pad+self.geo_thumbheight)/2
        self.geo_view_offset=max(0,min(self.geo_view_offset_max-self.geo_height,self.geo_view_offset))

    def configure_signal(self,obj,event):
        '''callback received when the window size of the drawing area changes'''
        self.geo_width=event.width
        self.geo_height=event.height
        self.update_geometry(True)
        self.update_scrollbar()
        ##self.update_required_thumbs()
        self.imarea.grab_focus()
##        self.imarea.window.invalidate_rect((0,0,self.geo_width,self.geo_height),True)

    def expose_signal(self,event,arg):
        '''callback received when part of the drawing area needs to be shown'''
        self.realize_signal(event)

    def realize_signal(self,event):
        '''calback to render the view - received when the drawing area needs to be shown'''
        if self.active_view==None: ##Nothing to draw yet
            return
        request_thumbs=False
        self.lock.acquire()
        drawable = self.imarea.window
        gc = drawable.new_gc()
        colormap=drawable.get_colormap()
        grey = colormap.alloc_color(0x5000,0x5000,0x5000)
        lgrey = colormap.alloc_color(0xB000,0xB000,0xB000)
        lblue = colormap.alloc_color(0x5000,0x8000,0xD000)
        blue = colormap.alloc_color(0x0500,0x0500,0xA000)
        dblue = colormap.alloc_color(0x1000,0x1000,0x5000)
        gold = colormap.alloc_color(0xEF00,0xF700,0x4900)
        white = colormap.alloc_color('white')
        black = colormap.alloc_color('black')
        green = colormap.alloc_color('green')
        red = colormap.alloc_color('red')
        gc_s = drawable.new_gc(foreground=lgrey,background=lgrey)
        gc_h = drawable.new_gc(foreground=lblue,background=lblue)
        gc_v = drawable.new_gc(foreground=gold)
        gc_g = drawable.new_gc(foreground=green)
        gc_r = drawable.new_gc(foreground=red)


#        drawable.set_background(black)
#        drawable.clear()

        hover_item=None
        if self.mouse_hover:
            mouse_loc=self.imarea.get_pointer()
            self.hover_ind=self.recalc_hover_ind(*mouse_loc)
            self.command_highlight_ind=self.get_hover_command(self.hover_ind,*mouse_loc)

            (mx,my)=self.imarea.get_pointer()
            if 0<=mx<drawable.get_size()[0] and 0<=my<drawable.get_size()[1]:
                self.hover_ind=self.recalc_hover_ind(mx,my)
            else:
                self.hover_ind=-1
            if self.hover_ind>=0:
                hover_item=self.active_view(self.hover_ind)
            else:
                hover_item=None
        ##TODO: USE draw_drawable to shift screen for small moves in the display (scrolling)
        display_space=True
        imgind=self.geo_ind_view_first
        x=0
        y=self.calc_screen_offset()
        drawable.clear()
        i=imgind
        neededitem=None
        while i<self.geo_ind_view_last:
            if 0<=i<len(self.active_view):
                item=self.active_view(i)
            else:
                break
            if self.last_selected_ind>=0 and self.hover_ind>=0 and (self.last_selected_ind>=i>=self.hover_ind or self.last_selected_ind<=i<=self.hover_ind):
                key_mods=gtk.gdk.display_get_default().get_pointer()[3]
                if key_mods&(gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                    if self.last_selected:
                        if key_mods&gtk.gdk.SHIFT_MASK:
                            drawable.draw_rectangle(gc_g, True, int(x), int(y),
                                int(self.geo_thumbwidth+self.geo_pad), int(self.geo_thumbheight+self.geo_pad))
                        else:
                            drawable.draw_rectangle(gc_r, True, int(x), int(y),
                                int(self.geo_thumbwidth+self.geo_pad), int(self.geo_thumbheight+self.geo_pad))
            if hover_item==item or self.command_highlight_ind<0 and item.selected and hover_item and hover_item.selected:
                drawable.draw_rectangle(gc_h, True, int(x+2), int(y+2),
                    int(self.geo_thumbwidth+self.geo_pad-4), int(self.geo_thumbheight+self.geo_pad-4))
            if item.selected:
                drawable.draw_rectangle(gc_s, True, int(x+5), int(y+5),
                    int(self.geo_thumbwidth+self.geo_pad-10), int(self.geo_thumbheight+self.geo_pad-10))
#           todo: come up with a scheme for highlighting images
            if item==self.focal_item:
                try:
                    th=self.active_view(i).thumb
                    (thumbwidth,thumbheight)=th.get_width(),th.get_height()
                    adjy=self.geo_pad/2+(128-thumbheight)/2-6
                    adjx=self.geo_pad/2+(128-thumbwidth)/2-6
                    drawable.draw_rectangle(gc_v, True, int(x+adjx), int(y+adjy), thumbwidth+12, thumbheight+12)
                except:
                    pass
#            drawable.draw_rectangle(gc, True, x+self.geo_pad/4, y+self.geo_pad/4, self.geo_thumbwidth+self.geo_pad/2, self.geo_thumbheight+self.geo_pad/2)
            fail_item=False
            #print item,item.meta,item.thumb,item.cannot_thumb
            if item.thumb==None:
                if not self.active_collection.load_thumbnail(item):
                    request_thumbs=True
            if item.thumb:
                th=self.active_view(i).thumb
                (thumbwidth,thumbheight)=th.get_width(),th.get_height()
                adjy=self.geo_pad/2+(128-thumbheight)/2
                adjx=self.geo_pad/2+(128-thumbwidth)/2
                drawable.draw_pixbuf(gc, item.thumb, 0, 0,int(x+adjx),int(y+adjy))
            elif item.thumb==False:
                (thumbwidth,thumbheight)=(0,0)
                adjy=self.geo_pad/2
                adjx=self.geo_pad/2
                drawable.draw_pixbuf(gc, self.pixbuf_thumb_fail, 0, 0,int(x+adjx),int(y+adjy))
            else:
                (thumbwidth,thumbheight)=(0,0)
                adjy=self.geo_pad/2
                adjx=self.geo_pad/2
                drawable.draw_pixbuf(gc, self.pixbuf_thumb_load, 0, 0,int(x+adjx),int(y+adjy))
            if self.mouse_hover and self.hover_ind==i or item.is_meta_changed() or item.selected or fail_item:
                if self.hover_ind==i or item.selected:
                    a,b=self.active_collection.get_browser_text(item)
                    if a or b:
                        a=a.replace('&','&amp;')
                        b=b.replace('&','&amp;')
                        l=self.imarea.create_pango_layout('')
                        if a and b:
#                            l.set_markup('<span size="6000">'+'w'*25+'</span>')
#                            print 'layout pixel size smaller',l.get_pixel_size()
                            l.set_markup('<b><span size="9000">'+a+'</span></b>\n<span size="7000">'+b+'</span>')
                        elif a:
                            l.set_markup('<b><span size="9000">'+a+'</span></b>')
                        elif b:
                            l.set_markup('<span size="7000">'+b+'</span>')
                        l.set_width((self.geo_thumbwidth+self.geo_pad*3/4)*pango.SCALE)
                        l.set_wrap(pango.WRAP_WORD_CHAR)
                        lx=int(x+self.geo_pad/4)
                        ly=max(y+30,int(y+self.geo_pad+self.geo_thumbheight-l.get_pixel_size()[1]-self.geo_pad/4))
                        w,h=l.get_pixel_size()
                        overlay_height=int(y+self.geo_pad/2+thumbheight+(self.geo_thumbheight-thumbheight)/2-ly)
                        if overlay_height>0 and thumbwidth>0:
                            overlay_pb=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,True,8,thumbwidth,overlay_height)
                            overlay_pb.fill(0x0000007f)
                            drawable.draw_pixbuf(None,overlay_pb,0,0,int(x+self.geo_pad/2+(self.geo_thumbwidth-thumbwidth)/2),int(ly),-1,-1)
                        drawable.draw_layout(gc,int(lx),int(ly),l,white)
                offx=self.geo_pad/4
                offy=self.geo_pad/4
                self.hover_cmds.simple_render_with_highlight(self.command_highlight_ind if self.hover_ind==i else -1,self.command_highlight_bd,item,self.hover_ind==i,drawable,gc,x+offx,y+offy,self.geo_pad/6)
            i+=1
            x+=self.geo_thumbwidth+self.geo_pad
            if x+self.geo_thumbwidth+self.geo_pad>self.geo_width:
                y+=self.geo_thumbheight+self.geo_pad
                if y>self.geo_height+self.geo_pad:
                    break
                else:
                    x=0
        self.lock.release()
        if request_thumbs:
            self.update_required_thumbs()

gobject.type_register(ImageBrowser)
