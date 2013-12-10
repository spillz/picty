#!/usr/bin/env python

import time
import pygtk
pygtk.require('2.0')
import gtk

class EntryCompletion:
    def __init__(self):
        window = gtk.Window()
        window.connect('destroy', lambda w: gtk.main_quit())
        vbox = gtk.VBox()
        label = gtk.Label('Type a, b, c or d\nfor completion')
        vbox.pack_start(label)
        entry = gtk.Entry()
        self.entry=entry
        vbox.pack_start(entry)
        window.add(vbox)
        completion = gtk.EntryCompletion()
        self.liststore = gtk.ListStore(str)
        for s in ['apple', 'banana', 'cap', 'comb', 'color',
                  'dog', 'doghouse']:
            self.liststore.append([s])
        completion.set_model(self.liststore)
        entry.set_completion(completion)
        completion.set_text_column(0)
        completion.set_match_func(self.match_func)
        completion.connect('match-selected', self.match_selected)
#        entry.connect('changed', self.text_changed)
#        entry.connect('move-cursor', self.move_cursor)
        entry.connect('activate', self.activate_cb)
        self.lpos=0
        self.rpos=0
        window.show_all()

    def compute_word_pos(self):
        pos=self.entry.get_property("cursor-position")
        key_string=self.entry.get_text()
        lpos=pos
        while lpos>0 and key_string[lpos-1].isalnum():
            lpos-=1
        rpos=pos
        while rpos<len(key_string) and key_string[rpos].isalnum():
            rpos+=1
        self.rpos=rpos
        self.lpos=lpos

#    def text_changed(self,editable):
#        self.compute_word_pos()
#
#    def move_cursor(self, entry, step, count, extend_selection):
#        self.compute_word_pos()

    def match_func(self, completion, key_string, iter):
        self.compute_word_pos()
        word=key_string[self.lpos:self.rpos]
        if not word:
            return False
        text = self.liststore.get_value(iter, 0)
#        print key_string, word, text, text.startswith(word)
        return text.startswith(word)

    def match_selected(self, completion, model, iter):
        self.compute_word_pos()
        print model[iter][0], 'was selected'
        pos=self.entry.get_property("cursor-position")
        key_string=self.entry.get_text()
        new_string=key_string[0:self.lpos]+model[iter][0]+key_string[self.rpos:]
        new_pos=self.lpos+len(model[iter][0])
        self.entry.set_text(new_string)
        self.entry.set_position(new_pos)
        return True

    def activate_cb(self, entry):
        text = entry.get_text()
        if text:
            if text not in [row[0] for row in self.liststore]:
                self.liststore.append([text])
                entry.set_text('')
        return

def main():
    gtk.main()
    return

if __name__ == "__main__":
    ec = EntryCompletion()
    main()
