#!/usr/bin/python

import leveldb
import sys
import re
import struct

if len(sys.argv) < 5:
    print "Usage: {} DB_PATH ObjectName Key Val [Key Val]*".format(sys.argv[0])
    exit(0)

def obj_name(escname):
    return escname.replace("%e", ".").replace("%p", "%").replace("%u", "_")

db = leveldb.LevelDB(sys.argv[1])
seqkey = re.compile('^_HOBJTOSEQ_\x00([^\.]*)\.')
attrkey = re.compile('^_USER_([0-9]{16})_AXATTR_\x00(.+)$')
omapkey = re.compile('^_USER_([0-9]{16})_USER_\x00(.+)$')
obj2seq = {}
seq2obj = {}
for kv in db.RangeIter(key_from="_HOBJTOSEQ_", key_to="_I", fill_cache = False):
    key = kv[0]
    m = seqkey.search(key)
    if m:
        obj = obj_name(m.group(1))
        seq = struct.unpack_from('<Q', kv[1], 6)[0]
        obj2seq[obj] = seq
        seq2obj[seq] = obj
        continue

_obj = sys.argv[2]
if not _obj in obj2seq:
    print "Can not find sequence for object: {}".format(_obj)
    exit(1)

idx = 3
_seq = str(obj2seq[_obj]).zfill(16)
while (idx + 1) < len(sys.argv):
    _key = '_USER_{}_USER_\x00{}'.format(_seq, sys.argv[idx])
    _val = ''
    for v in sys.argv[idx + 1].split('\\x')[1:]:
        _val += chr(int(v, 16))
    db.Put(_key, _val, sync = True)
    idx = idx + 2

