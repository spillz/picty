import os
from pyinotify import WatchManager, Notifier, ThreadedNotifier, EventsCodes, ProcessEvent

wm=WatchManager()

mask = EventsCodes.IN_DELETE | EventsCodes.IN_CREATE |EventsCodes.IN_DONT_FOLLOW |EventsCodes.IN_MODIFY|EventsCodes.IN_MOVED_FROM|EventsCodes.IN_MOVED_TO  # watched events

class Monitor(ProcessEvent):
    def __init__(self,cb):
        ProcessEvent.__init__(self)
        self.cb=cb
        self.notifier = ThreadedNotifier(wm, self)
        self.notifier.start()
    def process_IN_MODIFY(self, event):
        path=os.path.join(event.path, event.name)
        self.cb(path,'MODIFY')
#        print "Modify: %s" %  path
    def process_IN_MOVED_FROM(self, event):
        path=os.path.join(event.path, event.name)
        self.cb(path,'MOVED_FROM')
#        print "Moved out: %s" %  path
#        if os.path.isdir(path):
#            wm.rm_watch(path,mask,rec=True)
    def process_IN_MOVED_TO(self, event):
        path=os.path.join(event.path, event.name)
        self.cb(path,'MOVED_TO')
#        print "Moved in: %s" %  path
#        if os.path.isdir(path):
#            wm.add_watch(path,mask,rec=True)
    def process_IN_CREATE(self, event):
        path=os.path.join(event.path, event.name)
        self.cb(path,'CREATE')
#        print "Create: %s" %  path
#        if os.path.isdir(path):
#            wm.add_watch(path,mask,rec=True)
    def process_IN_DELETE(self, event):
        path=os.path.join(event.path, event.name)
        self.cb(path,'DELETE')
#        print "Remove: %s" %  path
#        if os.path.isdir(path):
#            wm.rm_watch(path,mask,rec=True)
    def start(self,dir):
        self.wdd = wm.add_watch(dir, mask, rec=True)
    def stop(self,dir):
        wm.rm_watch(self.wdd[dir], rec=True)
        self.notifier.stop()
