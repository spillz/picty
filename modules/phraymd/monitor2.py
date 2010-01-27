import os
import os.path
from pyinotify import *


if 'IN_DELETE' in dir():
    mask = IN_DELETE | IN_CREATE |IN_DONT_FOLLOW |IN_MODIFY|IN_MOVED_FROM|IN_MOVED_TO  # watched events
else:
    mask = EventsCodes.IN_DELETE | EventsCodes.IN_CREATE |EventsCodes.IN_DONT_FOLLOW |EventsCodes.IN_MODIFY|EventsCodes.IN_MOVED_FROM|EventsCodes.IN_MOVED_TO  # watched events

class Monitor(ProcessEvent):
    def __init__(self,dirs,recursive,cb):
        ProcessEvent.__init__(self)
        self.cb=cb
        self.wm=WatchManager()
        self.notifier = ThreadedNotifier(self.wm, self)
        self.notifier.start()
        self.wd=[]
        self.recursive=recursive
        for d in dirs:
            self.wd.append(self.wm.add_watch(d, mask, rec=recursive, auto_add=True))
    def stop(self):
        try:
            for wd in self.wd:
                self.wm.rm_watch(wd.values(),rec=self.recursive)
            self.notifier.stop() ##todo: should be checking if there are any other watches still active?
        except:
            print 'Error removing watch'
            import traceback,sys
            print traceback.format_exc(sys.exc_info()[2])
    def process_IN_MODIFY(self, event):
        path=os.path.join(event.path, event.name)
        self.cb(path,'MODIFY',event.is_dir)
    def process_IN_MOVED_FROM(self, event):
        path=os.path.join(event.path, event.name)
        self.cb(path,'MOVED_FROM',event.is_dir)
    def process_IN_MOVED_TO(self, event):
        path=os.path.join(event.path, event.name)
        self.cb(path,'MOVED_TO',event.is_dir)
    def process_IN_CREATE(self, event):
        path=os.path.join(event.path, event.name)
        self.cb(path,'CREATE',event.is_dir)
    def process_IN_DELETE(self, event):
        path=os.path.join(event.path, event.name)
        self.cb(path,'DELETE',event.is_dir)
    def process_default(self, event=None):
        pass
