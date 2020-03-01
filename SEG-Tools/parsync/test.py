# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function

import os
import shutil
import unittest
import subprocess
from itertools import izip_longest
from functools import wraps


TEST = os.path.normpath(os.path.join(__file__, os.path.pardir, 'test'))
SOURCE = os.path.join(TEST, 'source')
PS_DEST = os.path.join(TEST, 'parsync_dest')
RS_DEST = os.path.join(TEST, 'rsync_dest')

names = {
    'file': {
        'normal': 'file',
        'chinese': '文本文件',
        'space': ' regular file with spaces ',
        '*': 'file*',
        '|': 'file|',
        '=': 'file=',
        '?': 'file?',
        '"': '"file"',
        'unicode': 'fileåß∂ƒ©∆¬',
        'spanish': 'fileáéíóú¿¡üñ',
    },
    'dir': {
        'normal': 'dir',
        'chinese': '文件夹',
        'space': ' dir with spaces ',
        '*': 'dir*',
        '|': 'dir|',
        '=': 'dir=',
        '?': 'dir?',
        '"': '"dir"',
        'unicode': 'diråß∂ƒ©∆¬',
        'spanish': 'diráéíóú¿¡üñ',
    }
}


def turn_to_bytes(obj):
    if isinstance(obj, unicode):
        return obj.encode('utf8')
    elif isinstance(obj, bytearray):
        return bytes(obj)
    else:
        return obj


def ensure_bytes(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        new_args = (turn_to_bytes(arg) for arg in args)
        new_kwargs = {k: turn_to_bytes(v) for k, v in kwargs.items()}
        return func(*new_args, **new_kwargs)
    return wrapper


def touch(name, parent=os.path.curdir):
    path = os.path.join(parent, name)
    try:
        open(path, 'w').close()
    except Exception as e:
        print('Create file [{}] failed, error:\n{}'.format(path, e))


def create_files(parent=os.path.curdir):
    for name in names['file'].values():
        touch(name, parent=parent)


def create_dirs(parent=os.path.curdir):
    for name in names['dir'].values():
        path = os.path.join(parent, name)
        os.mkdir(path)
        touch('example', path)


def create_soft_link():
    cwd = os.getcwd()
    os.chdir(os.path.join(os.path.dirname(__file__), SOURCE))
    os.symlink('dir', 'link_to_dir')
    os.symlink('file', 'link_to_file')

    touch('source')
    os.symlink('source', 'broken_link')
    os.remove('source')

    os.chdir(cwd)


class TestSyncSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST):
            shutil.rmtree(TEST)

        # create souce and destination dirs for testing
        os.mkdir(TEST)
        os.mkdir(SOURCE)

        # create source files and dirs
        create_files(SOURCE)
        create_dirs(SOURCE)
        create_soft_link()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST)

    def setUp(self):
        os.mkdir(PS_DEST)
        os.mkdir(RS_DEST)

    def tearDown(self):
        shutil.rmtree(RS_DEST)
        shutil.rmtree(PS_DEST)

    def base_test(self, source, parallel=None, bwlimit=None, no_progress=True):
        cmd = ['python2', 'parsync.py', source, PS_DEST]
        if no_progress:
            cmd.insert(2, '--no-progress')
        if parallel:
            cmd.insert(2, '--parallel')
            cmd.insert(3, str(parallel))
        if bwlimit:
            cmd.insert(2, '--bwlimit')
            cmd.insert(3, str(bwlimit))

        subprocess.check_call(cmd)
        subprocess.check_call(['rsync', '-aqs', source, RS_DEST])

        parsync_dir_tree = os.walk(PS_DEST)
        rsync_dir_tree = os.walk(RS_DEST)

        for ps, rs in izip_longest(parsync_dir_tree, rsync_dir_tree):
            if ps and rs:
                _, dirs1, files1 = ps
                _, dirs2, files2 = rs
                self.assertEqual(sorted(dirs1), sorted(dirs2))
                self.assertEqual(sorted(files1), sorted(files2))
            else:
                self.assertEqual(ps, rs)
                break

    def test_sync_source_dir_with_progress(self):
        self.base_test(SOURCE, no_progress=False)

    def test_sync_files_under_source_dir(self):
        self.base_test('{}/'.format(SOURCE))

    def test_parsync_with_parallel(self):
        self.base_test(SOURCE, parallel=8)

    def test_parsync_with_parallel_1(self):
        self.base_test(SOURCE, parallel=1)

    def test_parsync_with_bwlimit(self):
        self.base_test(SOURCE, bwlimit=10)

    def test_sync_single_file(self):
        self.base_test(os.path.join(SOURCE, names['file']['normal']))

    def test_sync_file_with_Chinese_name(self):
        self.base_test(os.path.join(SOURCE, names['file']['chinese']))

    @unittest.expectedFailure
    def test_source_not_exist(self):
        self.base_test('not_exist')


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSyncSource)
    unittest.TextTestRunner(verbosity=2).run(suite)
