# -*- coding: utf-8 -*-

import os
import stat
from multiprocessing import Value
from multiprocessing.pool import Pool
from multiprocessing.util import debug

from scandir import scandir


__all__ = ['walk', 'Pool', 'lisfile']


def ensure_unicode(obj):
    return obj if isinstance(obj, unicode) else obj.decode('utf8')


def ensure_bytes(obj):
    if isinstance(obj, unicode):
        return obj.encode('utf8')
    elif isinstance(obj, bytearray):
        return bytes(obj)
    else:
        return obj


def walk(top, onerror=None):
    """A simplified version of scandir.walk().
    It is equals to scandir.walk() with topdown=True, followlinks=False
    """
    dirs = []
    nondirs = []

    try:
        scandir_it = scandir(top)
    except OSError as error:
        if onerror is not None:
            onerror(error)
        return

    while True:
        try:
            try:
                entry = next(scandir_it)
            except StopIteration:
                break
        except OSError as error:
            if onerror is not None:
                onerror(error)
            return

        try:
            is_dir = entry.is_dir(False)
        except OSError:
            is_dir = False

        if is_dir:
            dirs.append(entry.name)
        else:
            nondirs.append(entry.name)

    # Yield before recursion if going top down
    yield top, dirs, nondirs

    # Recurse into sub-directories
    for name in dirs:
        new_path = os.path.join(top, name)
        for entry in walk(new_path, onerror):
            yield entry


def lisfile(path):
    # check if a given path is file or not(do not follow symlinks)
    mode = os.stat(path).st_mode
    if stat.S_ISLNK(mode):
        return True
    else:
        return not stat.S_ISDIR(mode)


def worker(inqueue, outqueue, initializer=None, initargs=(), maxtasks=None, task_done=None):
    assert maxtasks is None or (type(maxtasks) in (int, long) and maxtasks > 0)
    put = outqueue.put
    get = inqueue.get
    if hasattr(inqueue, '_writer'):
        inqueue._writer.close()
        outqueue._reader.close()

    if initializer is not None:
        initializer(*initargs)

    completed = 0
    while maxtasks is None or (maxtasks and completed < maxtasks):
        try:
            task = get()
        except (EOFError, IOError):
            debug('worker got EOFError or IOError -- exiting')
            break

        if task is None:
            debug('worker got sentinel -- exiting')
            break

        job, i, func, args, kwds = task
        try:
            result = (True, func(*args, task_done=task_done, **kwds))
        except Exception, e:
            result = (False, e)
        try:
            put((job, i, result))
        except Exception as e:
            wrapped = MaybeEncodingError(e, result[1])
            debug("Possible encoding error while sending result: %s" % (
                wrapped))
            put((job, i, (False, wrapped)))

        task = job = result = func = args = kwds = None
        completed += 1
    debug('worker exiting after %d tasks' % completed)


class PoolWithProgress(Pool):
    def __init__(self, *args, **kwargs):
        self.task_summary = []
        self.task_done_of_exited_workers = 0
        super(PoolWithProgress, self).__init__(*args, **kwargs)

    @property
    def task_done(self):
        return self.task_done_of_exited_workers + sum((obj.value for obj in self.task_summary))

    def _join_exited_workers(self):
        """Cleanup after any worker processes which have exited due to reaching
        their specified lifetime.  Returns True if any workers were cleaned up.
        """
        cleaned = False
        for i in reversed(range(len(self._pool))):
            worker = self._pool[i]
            if worker.exitcode is not None:
                # worker exited
                debug('cleaning up worker %d' % i)
                worker.join()
                cleaned = True
                del self._pool[i]
                self.task_done_of_exited_workers += self.task_summary[i].value
                del self.task_summary[i]
        return cleaned

    def _repopulate_pool(self):
        """Bring the number of pool processes up to the specified number,
        for use after reaping workers which have exited.
        """
        for i in range(self._processes - len(self._pool)):
            task_done = Value('L', 0)
            w = self.Process(target=worker,
                             args=(self._inqueue, self._outqueue,
                                   self._initializer, self._initargs,
                                   self._maxtasksperchild, task_done)
                             )
            self.task_summary.append(task_done)
            self._pool.append(w)
            w.name = w.name.replace('Process', 'PoolWorker')
            w.daemon = True
            w.start()
            debug('added worker')


class MaybeEncodingError(Exception):
    """Wraps possible unpickleable errors, so they can be
    safely sent through the socket."""

    def __init__(self, exc, value):
        self.exc = repr(exc)
        self.value = repr(value)
        super(MaybeEncodingError, self).__init__(self.exc, self.value)

    def __str__(self):
        return "Error sending result: '%s'. Reason: '%s'" % (self.value,
                                                             self.exc)

    def __repr__(self):
        return "<MaybeEncodingError: %s>" % str(self)


def Pool(show_progress=True, *args, **kwargs):
    if show_progress:
        return PoolWithProgress(*args, **kwargs)
    else:
        return Pool(*args, **kwargs)
