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

import gtk

overlay_groups=[] #global colection of all overlay groups

def deregister_all_tools_for_plugin(plugin):
    for g in overlay_groups:
        g.deregister_tools_for_plugin(plugin)

def show_on_hover(item,hover_boolean):
    return hover

def always_active(item,hover):
    return True


class OverlayTool:
    '''
    Class defining a single tool "button" that will be displayed over a thumbnail or fullsize image,
    performing an action when the user selects it.
    name -- unique name of the tool
    action_callback -- action associated with the tool, must have call sig: def action_cb(item)
    active_callback -- callback returning True if the item is active, must have call sig: def active_cb(item,hover)
    always_active -- True if command should always be displayed (active_callback is never called it True)
    icon -- a gtk.gdk.Pixbuf representing the icon
    owner -- 'Main' or the name of a plugin
    '''
    def __init__(self,name,action_callback=None,active_callback=show_on_hover,icon=None,owner='Main',tooltip='This is a tooltip',priority=50):
        self.name=name
        self.action=action_callback
        self.is_active=active_callback
        self.icon=icon
        self.owner=owner
        self.priority=priority
        self.tooltip=tooltip


class OverlayGroup:
    '''
    Call containing the collection of Overlay tool buttons display over a thumbnail or fullsize image
    '''
    def default_active_callback(self,item,hover):
        return hover
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
    def register_tool(self,name,action_callback=None,active_callback=show_on_hover,icon=None,owner='Main',tooltip='This is a tooltip',priority=50):
        new_t=OverlayTool(name,action_callback,active_callback,self.widget_render_source.render_icon(icon,self.size),owner,tooltip,priority)
        for i in range(len(self.tools)):
            if priority>self.tools[i].priority:
                self.tools.insert(i,new_t)
                return
        self.tools.append(new_t)
    def register_tool_for_plugin(self,plugin,name,action_callback=None,active_callback=show_on_hover,icon=None,tooltip='This is a tooltip',priority=50):
        '''
        adds a new tool whose owner is plugin
        '''
        self.register_tool(name,action_callback,active_callback,icon,plugin.name,tooltip,priority)
    def deregister_tools_for_plugin(self,plugin):
        '''
        removes all tools whose owners are plugin
        '''
        print 'deregister tools',plugin.name,len(self.tools),[(t.name,t.owner) for t in self.tools]
        self.tools=[t for t in self.tools if t.owner!=plugin.name]
        print 'deregister tools post',len(self.tools),[(t.name,t.owner) for t in self.tools]
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
            if t.is_active(item,hover_data):
                drawable.draw_pixbuf(gc,t.icon,0,0,int(x+offx),int(y))
            offx+=t.icon.get_width()+xpad
    def simple_render_with_highlight(self,highlight_ind,item,hover_data,drawable,gc,x,y,xpad):
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
            if t.is_active(item,hover_data):
                if i==highlight_ind:
                    w,h=t.icon.get_width(),t.icon.get_height()
                    highlight_pb=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,True,8,w+8,h+8)
                    highlight_pb.fill(0x9090c0a0)
                    drawable.draw_pixbuf(gc,highlight_pb,0,0,int(x+offx-4),int(y-4))
                drawable.draw_pixbuf(gc,t.icon,0,0,int(x+offx),int(y))
            offx+=t.icon.get_width()+xpad
    def get_command(self, x, y, offx, offy, xpad):
        left=offx
        top=offy
        for i in range(len(self.tools)):
            right=left+self.tools[i].icon.get_width()
            bottom=top+self.tools[i].icon.get_height()
            if left<x<=right and top<y<=bottom:
                return i
            left+=self.tools[i].icon.get_width()+xpad
        return -1
