import time
import os
from pyinotify import WatchManager, Notifier, ThreadedNotifier, EventsCodes, ProcessEvent

wm=WatchManager()

mask = EventsCodes.IN_DELETE | EventsCodes.IN_CREATE |EventsCodes.IN_DONT_FOLLOW |EventsCodes.IN_MODIFY|EventsCodes.IN_MOVED_FROM|EventsCodes.IN_MOVED_TO  # watched events

class PTmp(ProcessEvent):
    def process_IN_MODIFY(self, event):
        path=os.path.join(event.path, event.name)
        print "Modify: %s" %  path
    def process_IN_MOVED_FROM(self, event):
        path=os.path.join(event.path, event.name)
        print "Moved out: %s" %  path
#        if os.path.isdir(path):
#            wm.rm_watch(path,mask,rec=True)
    def process_IN_MOVED_TO(self, event):
        path=os.path.join(event.path, event.name)
        print "Moved in: %s" %  path
#        if os.path.isdir(path):
#            wm.add_watch(path,mask,rec=True)
    def process_IN_CREATE(self, event):
        path=os.path.join(event.path, event.name)
        print "Create: %s" %  path
#        if os.path.isdir(path):
#            wm.add_watch(path,mask,rec=True)
    def process_IN_DELETE(self, event):
        path=os.path.join(event.path, event.name)
        print "Remove: %s" %  path
#        if os.path.isdir(path):
#            wm.rm_watch(path,mask,rec=True)

notifier = ThreadedNotifier(wm, PTmp())
notifier.start()

wdd = wm.add_watch('/tmp', mask, rec=True)
while True:
    time.sleep(1)

wm.rm_watch(wdd['/tmp'], rec=True)
notifier.stop()


