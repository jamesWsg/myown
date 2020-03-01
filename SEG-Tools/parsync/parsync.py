#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, division, absolute_import

import os
import sys
from time import sleep
import argparse
from itertools import chain
from subprocess import check_output, CalledProcessError, check_call

try:
    from os import scandir
except ImportError:
    from scandir import scandir

from utils import walk, Pool, lisfile


total_paths = 0
total_tasks = 0
show_progress = True
GROUP_CNT = 10
PATHS = '/tmp/parsync_paths.{}'
paths_file = None
TASKS = '/tmp/parsync_tasks.{}'
tasks_file = None

# this value is used to calculate how long should a progress bar be.
# screen width in IPMI is 100, this value should be smaller than 100,
# so that the progress bar will not be longer than one line
SCREEN_WIDTH = 100


def set_screen_width():
    try:
        output = check_output(['stty', 'size'])
    except CalledProcessError:
        pass    # use default value 30
    else:
        global SCREEN_WIDTH
        try:
            SCREEN_WIDTH = int(output.split()[1])
        except:
            pass


def generate_paths(source='.'):
    if show_progress:
        dot_num = 0
        path_count = 0
        max_dots = SCREEN_WIDTH - len('Generate Paths ')
        sys.stdout.write('Generate Paths ' + ' ' * max_dots)

    with open(paths_file, 'wb', buffering=4194304) as writer:
        if lisfile(source):
            writer.write(source + '\n')
        else:
            for root, dirs, files in walk(source):
                if root != os.path.curdir:  # skip '.'
                    writer.write(root + os.path.sep + '\n')
                for f in files:
                    # DO NOT use str.format() here, it may raise encoding error
                    writer.write(os.path.join(root, f) + '\n')

                if show_progress:
                    path_count += 1
                    if path_count == 1000:
                        if dot_num == max_dots:
                            dot_num = 0
                        sys.stdout.write('\b' * max_dots)
                        dot_num += 1
                        sys.stdout.write('.' * dot_num + ' ' * (max_dots - dot_num))
                        sys.stdout.flush()
                        path_count = 0
    if show_progress:
        print('')


def generate_groups():
    """
    I've tried count line number of a file with 13169031 lines
    1. read file line by line, until the end                            avg 2.3067 s
    2. read N MB file into buffer, count number of '\n', until the end  avg 1.8454 s
    3. open file and load it into mmap(memory map), count line by line  avg 3.0107 s
    4. use "wc -l" command                                              avg 1.0206 s

    "wc -l" is the fastest way to count line number of a file..
    """
    try:
        output = check_output(['wc', '-l', '{}'.format(paths_file)])
    except CalledProcessError as e:
        print('wc failed to get line count, error:\n{}'.format(e))
        raise

    global total_paths
    total_paths = int(output.split()[0])
    line_per_group = (total_paths + GROUP_CNT - 1) // GROUP_CNT

    for group in range(GROUP_CNT):
        begin = line_per_group * group
        end = begin + line_per_group
        yield begin, end


def _generate_tasks_with_progress(group_paths, task_done=None):
    tasks = []
    top_dir = None
    for path in group_paths:
        # remove tailing '\n', do not use str.strip(), because path may end with spaces
        path = path[:-1]
        if path.endswith(os.path.sep):  # is a dir
            # Because rsync is used with '-R', so it's unnecessary to remove tailing '/'
            # path = path[:-1]    # remove tailing os.path.sep
            if top_dir and path.startswith(top_dir):
                task_done.value += 1
                continue

            if group_paths[-1].startswith(path):
                # group may not contain path's all subfolder and files
                if scandir(path):   # path is not an empty folder
                    task_done.value += 1
                    # it will be synced when syncing folders and files it contains
                    continue
                else:               # path is an empty folder
                    task_done.value += 1
                    tasks.append(path)
            else:
                task_done.value += 1
                # all path's subfolders and files are in group
                top_dir = path
                tasks.append(path)
        else:   # not a dir
            if top_dir and path.startswith(top_dir):
                task_done.value += 1
                # path is under top_dir, ignore it
                # it will be synced, when top_dir is synced
                continue
            else:
                task_done.value += 1
                tasks.append(path)
    return tasks


def _generate_tasks_without_progress(group_paths, task_done=None):
    tasks = []
    top_dir = None
    for path in group_paths:
        # remove tailing '\n', do not use str.strip(), because path may end with spaces
        path = path[:-1]
        if path.endswith(os.path.sep):  # is a dir
            # Because rsync is used with '-R', so it's unnecessary to remove tailing '/'
            # path = path[:-1]    # remove tailing '/'
            if top_dir and path.startswith(top_dir):
                continue

            if group_paths[-1].startswith(path):
                # group may not contain path's all subfolder and files
                if scandir(path):   # path is not an empty folder
                    # it will be synced when syncing folders and files it contains
                    continue
                else:               # path is an empty folder
                    tasks.append(path)
            else:
                # all path's subfolders and files are in group
                top_dir = path
                tasks.append(path)
        else:   # not a dir
            if top_dir and path.startswith(top_dir):
                # path is under top_dir, ignore it
                # it will be synced, when top_dir is synced
                continue
            else:
                tasks.append(path)
    return tasks


def generate_tasks(*args, **kwargs):
    if show_progress:
        return _generate_tasks_with_progress(*args, **kwargs)
    else:
        return _generate_tasks_without_progress(*args, **kwargs)


def do_rsync(source, destination, args=None, bwlimit=None, task_done=None):
    if source:
        cmd = ['rsync', '-avqsR', '{}'.format(source), '{}'.format(destination)]
        cmd.extend(args)
        if bwlimit:
            cmd.append('--bwlimit={}'.format(bwlimit))

        try:
            check_call(cmd)
        except CalledProcessError as e:
            print('rsync failed, error:\n{}'.format(e))

        # this task is done, no matter if it is successful or not
        if show_progress:
            task_done.value += 1


def main():
    parser = argparse.ArgumentParser(
        description='Run rsync in parallel. '
                    'All parameters for parsync MUST be provided before source as usage shows, '
                    'any parameter after destination is directly passed to rsync.'
    )
    parser.add_argument('source',
                        help='source of rsync, cannot be empty. DO NOT use syntax '
                             'like XXX/* for source, use XXX/ or "XXX/*" instead')
    parser.add_argument('destination', help='destination of rsync, cannot be empty')
    parser.add_argument('--bwlimit', type=int, default=0,
                        help='limit I/O bandwidth; KBytes per second. Default: 0 KB/s')
    parser.add_argument('--id', default=str(os.getpid()),
                        help='ID of backup task. It is the pid of current process by default')
    parser.add_argument('--parallel', type=int, default=4,
                        help='run how many rsync processes in parallel')
    parser.add_argument('--no-progress', action='store_true', help='do not show progress bar')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='perform a trial run with no changes made')
    parser.add_argument('args', nargs=argparse.REMAINDER,
                        help="additional arguments that will directly be send to rsync")

    options = parser.parse_args()

    # do not use strip(), source and destination may contain leading or tailing spaces
    source = options.source
    destination = os.path.abspath(options.destination)
    tid = options.id
    assert options.parallel > 0, 'parallel parameter must be greater than 0'
    # bwlimit parameter for rsync must be an integer
    bwlimit = int(options.bwlimit / options.parallel) or None
    args = options.args

    global show_progress, paths_file, tasks_file, GROUP_CNT
    show_progress = not options.no_progress
    paths_file = PATHS.format(tid)
    tasks_file = TASKS.format(tid)
    if options.parallel < 10:
        GROUP_CNT = 10
    elif options.parallel > 100:
        GROUP_CNT = 100
    else:
        GROUP_CNT = options.parallel

    if show_progress:
        set_screen_width()

    # remove tailing '*'
    source = source[:-1] if source.endswith('*') else source

    # sync root folder of source to destination or not
    sync_root = not source.endswith(os.path.sep)

    # remove tailing '/', e.g. 'XXX/YYY/' ==> 'XXX/YYY'
    source = os.path.normpath(source)
    # AAA/BBB/CCC ==> AAA/BBB, CCC
    base_dir, source = os.path.split(source)
    if base_dir:
        os.chdir(base_dir)

    if not sync_root:
        os.chdir(source)
        source = os.path.curdir

    if not os.path.exists(paths_file):
        generate_paths(source)

    pool = Pool(processes=options.parallel, show_progress=show_progress)
    if not os.path.exists(tasks_file):
        with open(paths_file, 'rb') as reader:
            paths = reader.readlines()

        result = []
        for start, end in generate_groups():
            result.append(pool.apply_async(generate_tasks, (paths[start:end],)))

        if show_progress:
            max_dots = SCREEN_WIDTH - len('Generating Tasks ') - len(' 100.0%')
            while not all([r.ready() for r in result]):
                try:
                    current_progress = pool.task_done / total_paths
                except ZeroDivisionError:
                    break
                if current_progress > 1:
                    current_progress = 1
                dot_num = int(current_progress * max_dots)
                percentage = '{:>6.1f}%'.format(current_progress * 100)
                progress_bar = 'Generating Tasks ' + '.' * dot_num + ' ' * (max_dots - dot_num) + percentage
                sys.stdout.write('\b' * SCREEN_WIDTH)
                sys.stdout.write(progress_bar)
                sys.stdout.flush()
                sleep(0.1)
            else:
                progress_bar = 'Generating Tasks ' + '.' * max_dots + ' 100.0%'
                sys.stdout.write('\b' * SCREEN_WIDTH)
                sys.stdout.write(progress_bar)
                sys.stdout.flush()

            print('')

        tasks = chain.from_iterable([r.get() for r in result])
        global total_tasks
        with open(tasks_file, 'wb', buffering=4194304) as writer:
            for t in tasks:
                writer.write(t + '\n')
                total_tasks += 1

    if not options.dry_run:
        pool = Pool(processes=options.parallel, show_progress=show_progress)
        try:
            results = []
            with open(tasks_file, 'rb') as reader:
                for task in reader:
                    # task[:-1] is to remove tailing '\n'
                    result = pool.apply_async(do_rsync, (task[:-1], destination, args, bwlimit))
                    results.append(result)

            if show_progress:
                max_dots = SCREEN_WIDTH - len('Syncing ') - len(' 100.0%')
                while results:
                    current_progress = pool.task_done / total_tasks
                    if current_progress > 1:
                        current_progress = 1
                    dot_num = int(current_progress * max_dots)
                    percentage = '{:>6.1f}%'.format(current_progress * 100)
                    progress_bar = 'Syncing ' + '.' * dot_num + ' ' * (max_dots - dot_num) + percentage
                    sys.stdout.write('\b' * SCREEN_WIDTH)
                    sys.stdout.write(progress_bar)
                    sys.stdout.flush()
                    sleep(0.1)

                    results = filter(lambda x: not x.ready(), results)
                else:
                    progress_bar = 'Syncing ' + '.' * max_dots + ' 100.0%'
                    sys.stdout.write('\b' * SCREEN_WIDTH)
                    sys.stdout.write(progress_bar)
                    sys.stdout.flush()
                print('')

        except KeyboardInterrupt:
            pool.terminate()
        else:
            pool.close()
        finally:
            pool.join()

    return 0


if __name__ == '__main__':
    main()
