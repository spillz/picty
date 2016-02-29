
if __name__ == '__main__':
    import sys, os.path
    sys.path.insert(0, os.path.abspath('../modules'))
    from picty.metadata.metadata2 import load_metadata, save_metadata
    import shutil
    shutil.copyfile('test.png','test1.png')
    class Item:
        meta = None
        thumb = None
        uid = '1'
        def mark_meta_saved(self):
            pass

    try:
        print 'Test 1'
        item = Item()
        assert(load_metadata(item, 'test1.png'))
        item.meta['Title'] = 'The Title'
        item.meta['Keywords'] = ['keyword1', 'keyword2']
        assert(save_metadata(item, 'test1.png'))
        print 'Test 1 passed'

        print 'Test 2'
        item2 = Item()
        assert(load_metadata(item2, 'test1.png'))
        assert(item2.meta['Title'] == 'The Title')
        assert(item2.meta['Keywords'] == ['keyword1', 'keyword2'])
        del item2.meta['Keywords']
        save_metadata(item2, 'test1.png')
        print 'Test 2 passed'

        print 'Test 3'
        item3 = Item()
        load_metadata(item3, 'test1.png')
        assert(item3.meta['Title'] == 'The Title')
        assert('Keywords' not in item3.meta)
        print 'Test 3 passed'

        print 'All tests passed'
    finally:
        import os
        os.remove('test1.png')
