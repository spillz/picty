'''

    phraymd
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

import gtk

overlay_groups=[] #global colection of all overlay groups

def deregister_all_tools_for_plugin(plugin):
    for g in overlay_groups:
        g.deregister_tools_for_plugin(plugin)

def show_on_hover(item,hover_boolean):
    return hover_boolean-1

def always_active(item,hover):
    return 0


class OverlayTool:
    '''
    Class defining a single tool "button" that will be displayed over a thumbnail or fullsize image,
    performing an action when the user selects it.
    name -- unique name of the tool
    action_callback -- action associated with the tool, must have call sig: def action_cb(item)
    active_callback -- callback returning True if the item is active, must have call sig: def active_cb(item,hover)
    always_active -- True if command should always be displayed (active_callback is never called it True)
    icons -- a list of gtk.gdk.Pixbuf representing possible icon states
    owner -- 'Main' or the name of a plugin
    '''
    def __init__(self,name,action_callback=None,active_callback=show_on_hover,icons=[],owner='Main',tooltip='This is a tooltip',priority=50):
        self.name=name
        self.action=action_callback
        self.is_active=active_callback
        self.icons=icons
        self.owner=owner
        self.priority=priority
        self.tooltip=tooltip


class OverlayGroup:
    '''
    Call containing the collection of Overlay tool buttons display over a thumbnail or fullsize image
    '''
    def default_active_callback(self,item,hover):
        return int(hover)-1
    def __init__(self,widget_render_source,size=gtk.ICON_SIZE_LARGE_TOOLBAR):
        '''
        widget_render_source -- should be a gtk.Widget with a valid render_icon method
        size -- one of the valid ICON_SIZE_* constants
        '''
        self.tools=[]
        self.widget_render_source=widget_render_source
        self.size=size
        overlay_groups.append(self)
    def __getitem__(self,index):
        return self.tools[index]
    def register_tool(self,name,action_callback=None,active_callback=show_on_hover,icons=[],owner='Main',tooltip='This is a tooltip',priority=50):
        icons=[self.widget_render_source.render_icon(icon,self.size) if icon else None for icon in icons]
        new_t=OverlayTool(name,action_callback,active_callback,icons,owner,tooltip,priority)
        for i in range(len(self.tools)):
            if priority>self.tools[i].priority:
                self.tools.insert(i,new_t)
                return
        self.tools.append(new_t)
    def register_tool_for_plugin(self,plugin,name,action_callback=None,active_callback=show_on_hover,icons=None,tooltip='This is a tooltip',priority=50):
        '''
        adds a new tool whose owner is plugin
        '''
        self.register_tool(name,action_callback,active_callback,icons,plugin.name,tooltip,priority)
    def deregister_tools_for_plugin(self,plugin):
        '''
        removes all tools whose owners are plugin
        '''
        self.tools=[t for t in self.tools if t.owner!=plugin.name]
    def simple_render(self,item,hover_data,drawable,gc,x,y,xpad):
        '''
        renders the tools horizontally across the already rendered image in the drawable
        item -- the image object that tools will act upon
        hover_data -- whatever additional data that will help the tool decide whether it needs to render
        drawable -- a gtk.gdk.Drawable that buttons will be drawn on
        gc -- a gtk.gdk.GC (graphic context)
        x -- horizontal offset for drawing in the drawable
        y -- vertical offset for drawing in the drawable
        xpad -- amount of space between tools
        '''
        offx=0
        for t in self.tools:
            active=t.is_active(item,hover_data)
            w=20
            if active>=0:
                drawable.draw_pixbuf(gc,t.icons[active],0,0,int(x+offx),int(y))
                w=t.icons[active].get_width()
            offx+=w+xpad
    def simple_render_with_highlight(self,highlight_ind,button_down,item,hover_data,drawable,gc,x,y,xpad):
        '''
        renders the tools horizontally across the already rendered image in the drawable
        hover_ind -- the number of the tool to highlight
        item -- the image object that tools will act upon
        hover_data -- whatever additional data that will help the tool decide whether it needs to render
        drawable -- a gtk.gdk.Drawable that buttons will be drawn on
        gc -- a gtk.gdk.GC (graphic context)
        x -- horizontal offset for drawing in the drawable
        y -- vertical offset for drawing in the drawable
        xpad -- amount of space between tools
        '''
        offx=0
        for i in xrange(len(self.tools)):
            t=self.tools[i]
            adjx,adjy=0,0
            active=t.is_active(item,hover_data)
            if active>=0 and t.icons and len(t.icons)>0:
                if i==highlight_ind:
                    w,h=t.icons[active].get_width(),t.icons[active].get_height()
                    if button_down:
                        highlight_pb=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,True,8,w+8,h+8)
                        highlight_pb.fill(0x404060a0)
                        drawable.draw_pixbuf(gc,highlight_pb,0,0,int(x+offx-4),int(y-4))
                        highlight_pb=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,True,8,w+6,h+6)
                        highlight_pb.fill(0x606080a0)
                        drawable.draw_pixbuf(gc,highlight_pb,0,0,int(x+offx-3),int(y-3))
                        adjx,adjy=1,1
                    else:
                        highlight_pb=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,True,8,w+8,h+8)
                        highlight_pb.fill(0xa0a0f0a0)
                        drawable.draw_pixbuf(gc,highlight_pb,0,0,int(x+offx-4),int(y-4))
                if len(t.icons)>active and t.icons[active]!=None:
                    drawable.draw_pixbuf(gc,t.icons[active],0,0,int(x+offx+adjx),int(y+adjy))
            if t.icons!=None and len(t.icons)>active and t.icons[active]!=None:
                offx+=t.icons[active].get_width()+xpad
            else:
                offx+=20+xpad
    def get_command(self, x, y, offx, offy, xpad, item, hover_data):
        left=offx
        top=offy
        for i in range(len(self.tools)):
            active=self.tools[i].is_active(item,hover_data)
            t=self.tools[i]
            if t.icons!=None and len(t.icons)>active and t.icons[active]!=None:
                w=t.icons[active].get_width()
                h=t.icons[active].get_height()
            else:
                w,h=(20,20)
            right=left+w
            bottom=top+h
            if left<x<=right and top<y<=bottom:
                return i
            left+=w+xpad
        return -1
