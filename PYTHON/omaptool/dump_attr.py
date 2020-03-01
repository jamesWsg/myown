#!/usr/bin/python

import leveldb
import sys
import re
import struct

if len(sys.argv) < 2:
    print "Usage: {} DB_PATH".format(sys.argv[0])
    exit(0)

def obj_name(escname):
    return escname.replace("%e", ".").replace("%p", "%").replace("%u", "_")

db = leveldb.LevelDB(sys.argv[1])
seqkey = re.compile('^_HOBJTOSEQ_\x00([^\.]*)\.')
attrkey = re.compile('^_USER_([0-9]{16})_AXATTR_\x00(.+)$')
omapkey = re.compile('^_USER_([0-9]{16})_USER_\x00(.+)$')
obj2seq = {}
seq2obj = {}
for kv in db.RangeIter(fill_cache = False):
    key = kv[0]
    m = seqkey.search(key)
    if m:
        obj = obj_name(m.group(1))
        seq = struct.unpack_from('<Q', kv[1], 6)[0]
        obj2seq[obj] = seq
        seq2obj[seq] = obj
        print "Obj: \"{}\" -> {}".format(obj, seq)
        continue

    m = attrkey.search(key)
    if m:
        seq = int(m.group(1))
        if seq in seq2obj:
            attr_name = m.group(2)
            print "Attr: {}->{} len({})".format(seq2obj[seq], attr_name, len(kv[1]))
        else:
            print "Attr: UNKNOWN_OBJ({})->{} len({})".format(seq, attr_name, len(kv[1]))
        continue

    m = omapkey.search(key)
    if m:
        seq = int(m.group(1))
        if seq in seq2obj:
            omap_name = m.group(2)
            if omap_name == "pg_log_object_head" or omap_name == "pg_log_object_tail":
                print "OMAP: {}->{}={}".format(seq2obj[seq], omap_name, struct.unpack('<I', kv[1])[0])
            else:
                print kv[0]
                print "OMAP: {}->{} len({})".format(seq2obj[seq], omap_name, len(kv[1]))
        else:
            print "OMAP: UNKNOW_OBJ({})->{} len({})".format(seq, omap_name, len(kv[1]))
        continue

    print "OtherKey: {}".format(kv[0])

