import gtk

from picty import viewsupport

#TODO: both of these classes need quite a bit of work to make the completions more useful
# e.g. showing correct completions after a quote

class TagCompletion(gtk.EntryCompletion):
    def __init__(self,entry,index=None):
        gtk.EntryCompletion.__init__(self)
        self.entry=entry
        self.liststore = gtk.ListStore(str, str) #text, icon
        self.update_keywords(index)
        self.set_model(self.liststore)

        cpb=gtk.CellRendererPixbuf()
        cpb.set_property("width",20) ##todo: don't hardcode the width
        self.pack_start(cpb,False)
        self.add_attribute(cpb, 'stock-id', 1)
        cpt=gtk.CellRendererText()
#        cpt.set_propery("weight",800)
        self.pack_start(cpt,False)
        self.add_attribute(cpt, 'text', 0)

        self.set_match_func(self.match_func)
        self.connect('match-selected', self.match_selected)
        entry.set_completion(self)
        self.lpos=0
        self.rpos=0

    def update_keywords(self,index=None):
        self.liststore.clear()
        if not index:
            return
        if 'Keywords' in index.index:
            for r in index.index['Keywords']:
                self.liststore.append([r,gtk.STOCK_ADD])

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

    def match_func(self, completion, key_string, iter):
        self.compute_word_pos()
        word=key_string[self.lpos:self.rpos]
#        if not word:
#            return False
        text = self.liststore.get_value(iter, 0)
        return text.lower().startswith(word)

    def match_selected(self, completion, model, iter):
        self.compute_word_pos()
        pos=self.entry.get_property("cursor-position")
        key_string=self.entry.get_text()
        tok = model[iter][0]
        if ' ' in tok:
            tok = '"'+tok+'"'
        new_string=key_string[0:self.lpos]+tok+key_string[self.rpos:]
        new_pos=self.lpos+len(tok)
        self.entry.set_text(new_string)
        self.entry.set_position(new_pos)
        return True


class SearchCompletion(gtk.EntryCompletion):
    def __init__(self,entry):
        gtk.EntryCompletion.__init__(self)
        self.entry=entry
        self.liststore = gtk.ListStore(str, str, str, str) #text, type, descr, icon
        self.toks  = sorted([(t[0],t[2]) for t in viewsupport.TOKENS])
        self.update_keywords()
        self.set_model(self.liststore)

        cpb=gtk.CellRendererPixbuf()
        cpb.set_property("width",20) ##todo: don't hardcode the width
        self.pack_start(cpb,False)
        self.add_attribute(cpb, 'stock-id', 3)
        cpt=gtk.CellRendererText()
#        cpt.set_propery("weight",800)
        self.pack_start(cpt,False)
        self.add_attribute(cpt, 'text', 0)
        cpt=gtk.CellRendererText()
        self.pack_start(cpt,False)
        self.add_attribute(cpt, 'text', 2)

        self.set_match_func(self.match_func)
        self.connect('match-selected', self.match_selected)
#        entry.connect('changed', self.text_changed)
#        entry.connect('move-cursor', self.move_cursor)
        entry.set_completion(self)
        self.lpos=0
        self.rpos=0

    def update_keywords(self,index=None):
        self.liststore.clear()
        for s in self.toks:
            self.liststore.append([s[0],'TOKENS',s[1],gtk.STOCK_FIND])
        if not index:
            return
        for s in index.index:
            for r in index.index[s]:
                self.liststore.append([r,s,'',gtk.STOCK_ADD])

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
#        if not word:
#            return False
        text = self.liststore.get_value(iter, 0)
        return text.lower().startswith(word)

    def match_selected(self, completion, model, iter):
        self.compute_word_pos()
        pos=self.entry.get_property("cursor-position")
        key_string=self.entry.get_text()
        tok = model[iter][0]
        if ' ' in tok:
            tok = '"'+tok+'"'
        new_string=key_string[0:self.lpos]+tok+key_string[self.rpos:]
        new_pos=self.lpos+len(tok)
        self.entry.set_text(new_string)
        self.entry.set_position(new_pos)
        return True
