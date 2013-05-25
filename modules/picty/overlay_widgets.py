import gtk, gobject
import overlaytools

def grow(al,rect,pixels):
    r=gtk.gdk.Rectangle(max(rect.x-pixels,al.x),
        max(rect.y-pixels,al.y),
        min(rect.width+2*pixels,al.width),
        min(rect.height+2*pixels,al.height)
        )
    return r
def is_in(pt,rect):
    if rect.x<=pt[0]<rect.x+rect.width:
        if rect.y<=pt[1]<rect.y+rect.height:
            return True
    return False


class ProportionalLayoutChild:
    def __init__(self,widget,left,right,top,bottom):
        self.widget=widget
        self.left=left
        self.right=right
        self.top=top
        self.bottom=bottom
        self.eventbox = None
        self.hidden = False

class ProportionalLayout(gtk.Container):
    '''
    An extension of gtk.Fixed that supports sizing of children and positioning them
    in proportional (instead of pixel) terms
    '''
    def __init__(self,*children):
        gtk.Container.__init__(self)
        self.set_flags (gtk.NO_WINDOW)

        self.children=[]
        for ch in children:
            self.add_with_bg(*ch)

    def do_size_request (self, requisition):
        '''
        request the minimum size such that each child widget can fit within its specified proportions
        '''
        needed_req = [0,0]
        for ch in self.children:
            req = list(ch.widget.size_request())
            try:
                req[0] = int(req[0]/(ch.right-ch.left))
            except:
                pass
            try:
                req[1] = int(req[1]/(ch.top-ch.bottom))
            except:
                pass
            for i in range(2):
                if needed_req[i]<req[i]:
                    needed_req[i]=req[i]
        requisition.width = needed_req[0]
        requisition.height = needed_req[1]

    def do_size_allocate (self, allocation):
        n = len(self.children)
        al = allocation
        for ch in self.children:
            widget = ch.eventbox if ch.eventbox else ch.widget
            left = ch.left
            right = ch.right
            if left == right: #centered
                w = widget.size_request()[0]
                left = int(al.x + left * al.width - w/2)
            elif left is not None and right is not None:
                w = int((right - left)*al.width)
                left = int(al.x + left * al.width)
            elif left is not None: #align right
                w = widget.size_request()[0]
                left = int(al.x + left * al.width)
            elif right is not None: #align left
                w = widget.size_request()[0]
                left = int(al.x + right * al.width - w)

            top = ch.top
            bottom = ch.bottom
            if top == bottom: #centered
                h = widget.size_request()[1]
                top = int(al.y + top * al.height - h/2)
            elif top is not None and bottom is not None:
                h = int((bottom - top)*al.height)
                top = int(al.y + top * al.height)
            elif top is not None: #align bottom
                h = widget.size_request()[1]
                top = int(al.y + top * al.height)
            elif bottom is not None: #align top
                w = widget.size_request()[1]
                top = int(al.x + bottom *al.height - h)

            a=gtk.gdk.Rectangle(left,top,w,h)
            widget.size_allocate(a)

    def do_remove(self,child):
        i=0
        for ch in self.children:
            if ch.widget==child or ch.eventbox==child:
                if ch.eventbox:
                    ch.eventbox.remove(ch.widget)
                    ch.eventbox.unparent()
                else:
                    ch.widget.unparent()
                del self.children[i]
                return
            i+=1

    def add_with_bg(self, widget, x_left, x_right, y_bottom, y_top, bgcolor = None):
        def _set_child_default_background(obj):
            bg_color = obj.style.bg[gtk.STATE_NORMAL]
            obj.modify_bg(gtk.STATE_NORMAL,bg_color)

        ch = ProportionalLayoutChild(widget, x_left, x_right, y_bottom, y_top)
        ch.eventbox = gtk.EventBox()
        ch.eventbox.set_parent(self)
        ch.eventbox.add(widget)
        if bgcolor is None:
            ch.eventbox.connect("realize",_set_child_default_background)
        else:
            ch.eventbox.modify_bg(bgcolor)
        self.children.append(ch)
        self.queue_resize()

    def add(self, widget, x_left, x_right, y_bottom, y_top):
        ch = ProportionalLayoutChild(widget, x_left, x_right, y_bottom, y_top)
        widget.set_parent(self)
        self.children.append(ch)
        self.queue_resize()


    def do_forall (self, include_internals, callback, user_data):
        for ch in self.children:
            if ch.eventbox:
                callback (ch.eventbox, user_data)
            else:
                callback (ch.widget, user_data)

gobject.type_register(ProportionalLayout)

class DrawableOverlay(gtk.EventBox):
    '''
    Widget that holds an EventBox that can be drawn upon and a number of child widgets that are overlaid on top
    The overlaid widgets are arrange in a ProportionalFixed widget
    '''
    __gsignals__={
        'draw':(gobject.SIGNAL_RUN_LAST,gobject.TYPE_NONE,(gtk.gdk.Window,)),
        }
    def __init__(self,*children):
        gtk.EventBox.__init__(self)
        self.set_visible_window(True)
        self.set_app_paintable(True)
        self.layout = ProportionalLayout(*children)
        gtk.EventBox.add(self, self.layout)

    def add_with_bg(self, widget, x_left, x_right, y_bottom, y_top, bgcolor=None):
        self.layout.add_with_bg(widget, x_left, x_right, y_bottom, y_top, bgcolor)

    def add(self, widget, x_left, x_right, y_bottom, y_top):
        self.layout.add(widget, x_left, x_right, y_bottom, y_top)

    def do_expose_event(self, event):
        # Need to modify the background style of all overlaid EventBox widgets
        # because they are transparent by default -- todo: probably better to do this in realize handler
        ##now emit a drawing event
        self.emit('draw',self.window)

gobject.type_register(DrawableOverlay)


class DrawableOverlayHover(DrawableOverlay):
    '''
    A DrawableOverlay where the child widgets are shown when the pointer (i.e. mouse position)
    moves "close" to their position and hidden when the pointer moves away
    '''
    def __init__(self,*children):
        DrawableOverlay.__init__(self,*children)
        #self.layout.set_no_show_all(True)
        self.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.connect("motion-notify-event",self.motion_signal)
        self.add_events(gtk.gdk.ENTER_NOTIFY_MASK)
        self.connect("enter-notify-event",self.enter_signal)
        self.add_events(gtk.gdk.LEAVE_NOTIFY_MASK)
        self.connect("leave-notify-event",self.leave_signal)
        self.visibility_threshold = 20
        for ch in self.layout.children:
            widget=ch.eventbox if ch.eventbox else ch.widget
            if ch.eventbox:
                ch.eventbox.show()
            ch.widget.show()
        self.layout.connect_after("realize",self.layout_realized)

    def hide_child(self, child):
        for ch in self.layout.children:
            widget = ch.eventbox if ch.eventbox else ch.widget
            if ch.widget == child:
                ch.hidden=True
                widget.hide()

    def unhide_child(self, child):
        for ch in self.layout.children:
            widget = ch.eventbox if ch.eventbox else ch.widget
            if ch.widget == child:
                ch.hidden=False
                #widget.show()

    def layout_realized(self,obj):
        for ch in self.layout.children:
            widget=ch.eventbox if ch.eventbox else ch.widget
            widget.hide()

    def enter_signal(self,obj,event):
        '''callback when mouse moves in the viewer area (updates image overlay as necessary)'''
        pos=(event.x,event.y)

    def leave_signal(self,obj,event):
        '''callback when mouse leaves the viewer area (hides image overlays)'''
#        if event.mode!=gtk.gdk.CROSSING_NORMAL:
#            return
        pos=(event.x,event.y)
        al = self.get_allocation()
        al.x=0
        al.y=0
        if not is_in(pos,al):
            for ch in self.layout.children:
                widget = ch.eventbox if ch.eventbox else ch.widget
                widget.hide()

    def motion_signal(self,obj,event):
        '''callback when mouse moves in the viewer area (updates image overlay as necessary)'''
        al = self.get_allocation()
        al.x=0
        al.y=0

        pos=(event.x,event.y)
        for ch in self.layout.children:
            if ch.hidden:
                continue
            widget = ch.eventbox if ch.eventbox else ch.widget
            if is_in(pos,grow(al,widget.get_allocation(),self.visibility_threshold)):
                widget.show()
            else:
                widget.hide()

gobject.type_register(DrawableOverlayHover)

if __name__ == '__main__':
    proplayout = ProportionalLayout()
    proplayout.add_with_bg(gtk.Button('bottom-right'),0.5,1,0.5,1)
    proplayout.add_with_bg(gtk.Button('top-left'),0,0.5,0,0.5)
    proplayout.add_with_bg(gtk.Button('bottom-left-aligned'),0,None,None,1)
    proplayout.add_with_bg(gtk.Button('top-right-aligned'),None,1.0,0,None)
    proplayout.add_with_bg(gtk.Button('centered\nProportionalLayout'),0.5,0.5,0.5,0.5)

    def do_draw(obj,drawable):
        gc = drawable.new_gc()
        colormap=drawable.get_colormap()
        green = colormap.alloc('green')
        drawable.set_background(green)
        drawable.clear()
    def do_draw2(obj,drawable):
        gc = drawable.new_gc()
        colormap=drawable.get_colormap()
        blue = colormap.alloc('blue')
        drawable.set_background(blue)
        drawable.clear()

    drawable = DrawableOverlay()
    drawable.connect('draw',do_draw)
    drawable.add_with_bg(gtk.Button('bottom-right'),0.5,1,0.5,1)
    drawable.add_with_bg(gtk.Button('top-left'),0,0.5,0,0.5)
    drawable.add_with_bg(gtk.Button('bottom-left-aligned'),0,None,None,1)
    drawable.add_with_bg(gtk.Button('top-right-aligned'),None,1.0,0,None)
    drawable.add_with_bg(gtk.Button('centered\nDrawableOverlay'),0.5,0.5,0.5,0.5)

    hdrawable = DrawableOverlayHover()
    hdrawable.connect('draw',do_draw2)
    hdrawable.add_with_bg(gtk.Button('bottom-right'),0.5,1,0.5,1)
    hdrawable.add_with_bg(gtk.Button('top-left'),0,0.5,0,0.5)
    hdrawable.add_with_bg(gtk.Button('bottom-left-aligned'),0,None,None,1)
    hdrawable.add_with_bg(gtk.Button('top-right-aligned'),None,1.0,0,None)
    hdrawable.add_with_bg(gtk.Button('centered\nDrawableOverlayHover'),0.5,0.5,0.5,0.5)

    box = gtk.HBox()
    box.pack_start(proplayout)
    box.pack_start(drawable)
    box.pack_start(hdrawable)

    window = gtk.Window ()
    window.add(box)
    window.set_size_request(600,300)
    window.connect('destroy', lambda window: gtk.main_quit ())
    window.show_all()
    window.present ()

    gtk.main ()


