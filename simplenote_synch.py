# -*- coding: utf-8 -*-
"""
SimpleNote synch app by/for BillSeitz, started Aug'2012.

Basic idea: synch SimpleNote cloud with my PrivateWiki (PikiPiki) NoteBook.

PikiPiki data details
 * each page is a separate file
 * no file extension
 * name = ID

SimpleNote data details
 * note-list is just meta-data, including a 'key': {u'modifydate': u'1317174909.000000', u'tags': [], u'deleted': 0, u'createdate': u'1317174909.000000', u'systemtags': [], u'version': 1, u'syncnum': 1, u'key': u'ffe4842edf1c11e1947c751bbceef730', u'minversion': 1}
 * an individual note has content like: ({u'modifydate': u'1317174909.000000', u'tags': [], u'deleted': 0, u'createdate': u'1317174909.000000', u'systemtags': [], u'content': 'ContentMarketing\n\nMarketIng by creating Content\r\n * WordOfMouth\r\n * SEO\r\n * SocialMedia\r\n\r\nsee PatrickMcKenzie writing (LongTail BingoCard creation)\r\n\r\nsee MfSeoContentStrategy\r\n', u'version': 1, u'syncnum': 1, u'key': u'ffe4842edf1c11e1947c751bbceef730', u'minversion': 1}, 0)
  * so note that "name" of note (which corresponds to the filename) is just the first line of the note's 'content', the ID is the 'key'
  * note that the meta-data in the list is all included in the single-note content (duh) - all that you add from the note itself is the 'content'
  * 'modifydate' seems the key field for making synch decision - timezone?
  
Approach:
 * create/maintain pickle holding all the data
  * last-synch-complete-datetime
  * simplenote-cloud-notes - key, name (requires scraping), modifydate
   * have dictionary of dictionaries 'notes' keyed from key: {'ffe4842edf1c11e1947c751bbceef730': {'name': 'ContentMarketing', 'modifydate': 1317174909.000000}....}
   * another 'name_keys' dictionary mapping from name to key: {'ContentMarketing': 'ffe4842edf1c11e1947c751bbceef730', ....}
 * when run synch:
  * get all files mod since last-synch
  * get all cloud notes mod since last-synch
  * any local notes not in cloud already (not in 'name_keys'): add to cloud, add to 'notes', add to 'name_keys'
  * any cloud notes not in local files already: add to local, add to pickle
  * any files mod both sides since synch: issue!
  * remaining notes have been changed on just 1 side- push to other side, update pickle
 
"""

import os, cPickle
# setup
try:
   from simplenote_synch_config import *
except ImportError:
   pass
path = os.getcwd()
path_text = os.path.join(path, 'text')
pfile_name = 'simplenote.pkl' # hold mapping dictionaries
pfile_full = os.path.join(path, pfile_name)
pfile_raw_name = 'simplenote_raw.pkl' # just raw get_note_list() results
pfile_raw = os.path.join(path, pfile_raw_name)

def pickleread():
    print 'doing pickleread'
    pkl_file = open(pfile_full, 'rb')
    global last_synch_finish, notes, name_keys
    last_synch_finish = cPickle.load(pkl_file)
    notes = cPickle.load(pkl_file)
    name_keys = cPickle.load(pkl_file)
    pkl_file.close()

def picklewrite():
    print 'doing picklewrite'
    pkl_file = open(pfile_full, 'wb')
    cPickle.dump(last_synch_finish, pkl_file)
    cPickle.dump(notes, pkl_file)
    cPickle.dump(name_keys, pkl_file)
    pkl_file.close()

def map_update(note, dedupe=0): # update the map dictionaries - need key, content, name, and moddate
    global last_synch_finish, notes, name_keys
    #key = note['key']
    #name = note['name']
    #print 'key, name', key, name
    #print 'notes', notes
    if dedupe == 1: # don't check whether duplicating name
        if note['name'] in name_keys:
            return 'dupe'
    notes[note['key']] = note
    name_keys[note['name']] = note['key']
    return ''
    
def push_new(filename, moddate): # push new local file into cloud for first time
    content = filename + '\n\n' + filename.read()
    n = {'content': content, 'modifydate': moddate}
    note_ret = SimpleNote.add_note(n)
    note_ret['name'] = filename
    map_update(note)

def push_file(fname): # push local file to cloud - may be new or change
    global last_synch_finish, notes, name_keys
    f_full = os.path.join(path_text, fname)
    f_moddate = os.path.getmtime(f_full)
    f_content = file(f_full).read()
    n_content = fname + '\n\n' + f_content
    if fname in name_keys: # already in map, so already in cloud
        print fname, 'already in cloud, updating'
        key = name_keys[fname]
        note = notes[key]
        note['modifydate'] = f_moddate
        note['content'] = n_content
        (note, status) = simplenote.update_note(note)
        if status > -1:
            print fname, 'updated in cloud, updating map'
            notes[key]['modifydate'] = f_moddate
        else:
            print fname, 'update to cloud failed!'
    else: # adding to cloud for first time
        print fname, 'not in cloud, adding for first time now'
        note = {'content': n_content, 'modifydate': f_moddate}
        (note, status) = simplenote.update_note(note)
        if status > -1: 
            print fname, 'added to cloud, now adding to map'
            note['name'] = fname
            map_update(note)
            
def cloud_raw_list_grab(): # return (possibly-cached) raw list of notes - doesn't include name/content
    if os.path.exists(pfile_raw):
        print 'using cached pickle of raw notes'
        pkl_file = open(pfile_raw, 'rb')
        c_notes = cPickle.load(pkl_file)
        pkl_file.close()
        print len(c_notes), 'raw notes in cloud list'
        return c_notes
    else:
        print 'calling get_note_list()'
        (c_notes, status) = simplenote.get_note_list()
        if status == -1:
            print 'cloud_raw_list_grab failed', status, c_notes
            return False
        else:
            pkl_file = open(pfile_raw, 'wb')
            cPickle.dump(c_notes, pkl_file)
            pkl_file.close()
            print len(c_notes), 'raw notes in cloud list'
            return c_notes

def map_create(): # dump any existing pickle file of maps and create new one
    global last_synch_finish, notes, name_keys
    if os.path.exists(pfile_full):
        os.remove(pfile_full)
    last_synch_finish = 0
    notes = {}
    name_keys = {}
    print 'getting notes list now'
    c_notes = cloud_raw_list_grab()
    if not c_notes:
        print 'failed, exiting'
    else:
        print 'got %d notes metadata, starting scraping' % (len(c_notes))
        i = 0
        for note in c_notes:
            i = i+1
            print 'Getting note %d %s' % (i, note['key'])
            (c_note, status) = simplenote.get_note(note['key'])
            if status == -1:
                print 'failed', status, c_note
                break
            print 'Success getting note %d %s' % (i, note['key'])
            #c_note = c_note[0]
            name = c_note['content'].split('\n',1)[0]
            print "Note %s has name %s" % (note['key'], name)
            c_note['name'] = name
            c_mod = float(c_note['modifydate'])
            if c_mod > last_synch_finish:
                last_synch_finish = c_mod
                print 'Updated last_synch_finish to %d' % (last_synch_finish)
            map_update(c_note)
        picklewrite()

def dedupe_and_map_create(dump_pickle=0): # scrape cloud, dedupe on name, and build new local pickle cache
    global last_synch_finish, notes, name_keys
    if dump_pickle:
        if os.path.exists(pfile_full):
            os.remove(pfile_full)
        last_synch_finish = 0
        notes = {}
        name_keys = {}
    else:
        pickleread()
    print 'getting notes list now'
    c_notes = cloud_raw_list_grab()
    if not c_notes:
        print 'failed, exiting'
    else:
        print 'got %d notes metadata, starting scraping' % (len(c_notes))
        i = 0
        for note in c_notes:
            if note['key'] in notes:
                continue # don't bother scraping again
            i = i+1
            print 'Getting note %d %s' % (i, note['key'])
            (c_note, status) = simplenote.get_note(note['key'])
            if status == -1:
                print 'failed', status, c_note
                break
            print 'Success getting note %d %s' % (i, note['key'])
            #c_note = c_note[0]
            name = c_note['content'].split('\n',1)[0]
            print "Note %s has name %s" % (note['key'], name)
            c_note['name'] = name
            c_mod = float(c_note['modifydate'])
            if c_mod > last_synch_finish:
                last_synch_finish = c_mod
                print 'Updated last_synch_finish to %d' % (last_synch_finish)
            if map_update(c_note, 1) == 'dupe':
                print 'deleting cloud note', name, note['key']
                simplenote.delete_note(note['key'])
        picklewrite()

def map_show(): # show what's been cached in map, assuming all consistent
    pickleread()
    print 'last_synch_finish', last_synch_finish
    print len(notes), 'notes'
    print len(name_keys), 'keys'
    fname = 'MetroCard' #'Journal2012'
    key = name_keys[fname]
    print 'note', fname, notes[key]

def map_dupe_check(): # check local map file for name dupes
	pickleread()
	for note in notes:
		#print type(note), note
		print '%s\t%s' % (notes[note]['name'], notes[note]['key'])

def dedupe_from_map(): # catch dupes in map, delete from cloud and map and raw-map
	pickleread()
	key_names_list = []
	for name in name_keys:
		key = name_keys[name]
		key_names_list.append(key)
	i = 0
	import copy
	cnotes = copy.deepcopy(notes)
	for name in cnotes:
		key = cnotes[name]['key']
		if key not in key_names_list:
			i = i + 1
			print 'will kill', i, key
			simplenote.delete_note(key)
			del notes[key]
	picklewrite()

def moddate_compare(): 
    """
    Goal: pick a file previously synched, that has a simple name, compare timestamps
    File chosen: MusicLesson - last edited Aug05, synched since then
    """
    fname = "MusicLesson"
    pickleread()
    key = name_keys[fname]
    c_moddate = notes[key]['modifydate']
    l_moddate = os.path.getmtime(os.path.join(path_text, fname))
    import time
    print 'current time', time.time()
    print fname, 'cloud, local', c_moddate, l_moddate #outcome - match at 1344182336.000000
    fname = 'Journal2012'
    j_moddate = os.path.getmtime(os.path.join(path_text, fname))
    print fname, j_moddate

def push_local_to_cloud(moddate=1344182336.0): # push all files modded since a time into cloud - some will be new, some will be changes
    global last_synch_finish, notes, name_keys
    pickleread()
    flist = os.listdir(path_text)
    for fname in flist:
        f_full = os.path.join(path_text, fname)
        if os.path.isfile(f_full):
            if fname == '.DS_Store':
                continue
            if os.path.getmtime(f_full) > moddate:
                print 'pushing', fname
                if os.path.getmtime(f_full) > last_synch_finish:
                    last_synch_finish = os.path.getmtime(f_full)
                push_file(fname)
    picklewrite()

def last_synch_read(): # this is start of some future code
    (last_synch_finish, notes, name_keys) = pickleread()
    # local_changed = list of files mod since last_synch_finish # filename and moddate
    # cloud_changed = list of notes mod since last_synch_finish # initially just key and moddate
    for f in local_changed:
        if f not in name_keys.keys():
            push_new(f)

from simplenote import Simplenote # http://pypi.python.org/pypi/simplenote/0.2.0
simplenote = Simplenote(username, password)

def cloud_list_create():
    (notes, status) = simplenote.get_note_list() # have to get the whole list
    
if __name__ == '__main__':
    cloud_raw_list_grab()
    # map_create()
    # moddate_compare()
    map_show()
    # push_local_to_cloud()
    # dedupe_and_map_create()
    # map_dupe_check()
    # dedupe_from_map()