#!/usr/bin/python 

from __future__ import print_function

import os
import sys
from os.path import normpath,basename
import tempfile
import subprocess
import multiprocessing
from optparse import OptionParser


debug = 0
real_parallel = None
def bash_quoted(var):
    escaped = ""
    for chr in var:
        if chr in ('$`\\"'):
            escaped += "\\"
        escaped += chr
    return u'"{}"'.format(escaped)

class DoCommandTimedOut(RuntimeError):
    pass


class DoCommandError(RuntimeError):
    def __init__(self, stderr, errno=0, stdout=''):
        RuntimeError.__init__(self, stderr)
        self.errno, self.stdout, self.stderr = errno, stdout, stderr

    def __str__(self):
        return "DoCommandError: errno {} stdout '{}' stderr '{}'" \
               .format(self.errno, self.stdout, self.stderr)

def do_cmd(cmd, timeout=0, force=False):

    cmdstr = cmd.encode('utf-8')
    if timeout <= 0:
        p = subprocess.Popen([cmdstr],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True,
                             close_fds=True)
        (output, err) = p.communicate()
    else:
        with tempfile.TemporaryFile('w+') as outfp:
            with tempfile.TemporaryFile('w+') as errfp:
                p = subprocess.Popen([cmdstr],
                                     stdout=outfp,
                                     stderr=errfp,
                                     shell=True,
                                     close_fds=True)
                while p.poll() is None:
                    t = min(timeout, 0.1)
                    time.sleep(t)
                    timeout -= t
                    if timeout <= 0:
                        proc = psutil.Process(p.pid)
                        for c in proc.children(recursive=True):
                            c.kill()
                        proc.kill()
                        if force:
                            return ""
                        else:
                            raise DoCommandTimedOut(
                                u"command '{}' timeout".format(cmd)
                            )

                outfp.flush()   # don't know if this is needed
                outfp.seek(0)
                output = outfp.read()
                errfp.flush()   # don't know if this is needed
                errfp.seek(0)
                err = errfp.read()

    # prevent UnicodeDecodeError if invalid char in error/output
    err_str = unicode(err, 'utf-8', 'ignore')
    out_str = unicode(output, 'utf-8', 'ignore')
    if p.returncode != 0:
        if force:
            return ""
        else:
            raise DoCommandError(err, p.returncode, output)


    return output

def rsync_directory_tree_first(source, dest, filter_policy):
    try:
        do_cmd(u'rsync -av -f"+ */" -f"- *" {} {}'.format(bash_quoted(source), bash_quoted(dest)))
    except Exception as e:
        print("failed to rsync directory tree by rsync {}".format(str(e)))
        return -1

    return 0


def generate_rsync_filelist(source, dest, filter_policy):
    
    filename = "/tmp/rsync_{}_filelist.txt".format(basename(normpath(source)))
    try:
        do_cmd(u'rsync --dry-run -avzm --stats --human-readable  {} /tmp ' \
                '| sed -n "/\.\/$/, /^$/p" |grep -v "^./$" |grep -v "^$" > {}'.format(bash_quoted(source), filename))
    except Exception as e:
        print("failed to get filelist of source {}".format(str(e)), file=sys.stderr)
        return -1, None

    return 0, filename

def rsync_prepare(source, dest, filter_policy=None):
    ret = rsync_directory_tree_first(source, dest, filter_policy)
    if ret != 0:
        print("failed to rsync directory tree, quit", file=sys.stderr)
        return 5, None

    ret,filename  = generate_rsync_filelist(source, dest, filter_policy)
    if ret != 0:
        print("failed to generate rsync filelist", file=sys.stderr)
        return 6, None

    return 0, filename

                
def if_dir_total_included_in_section(directory, up_border, bottom_border):
    if bottom_border is None:
        return True, directory

    if bottom_border.startswith(directory):
        return False, None
    else:
        return True, directory

def do_rsync(source, dest, tasks, parallel, index, bwlimit=0):
    ret = 0
    global real_parallel
    for task in tasks:
        cur_source = os.path.join(source,task)
        cur_dest   = os.path.join(dest,task)
        try:
            if bwlimit > 0:
                bwlimit_real = int(float(bwlimit)*parallel/real_parallel.value)
                do_cmd(u"rsync --bwlimit={} -avs {} {}".format(bwlimit_real, bash_quoted(cur_source),bash_quoted(cur_dest)))
            else:
                do_cmd(u"rsync -avs {} {}".format(bash_quoted(cur_source),bash_quoted(cur_dest)))
            print("rsync {} done ! ({})".format(cur_source,index))
        except Exception as e:
            print("error happened while rsync {} info {}".format(cur_source, str(e)), file=sys.stderr)
            ret = 1
            continue

    print("rsync THREAD-{} Finish it tasks, real parallel {}".format(index,real_parallel.value))
    with real_parallel.get_lock():
        real_parallel.value -= 1

    return ret

def _rsync_part(source, up_border, file_vector, bottom_border, dest, parallel, index, bwlimit=0):
    global debug
    rsync_targets = []

    file_begin_flag = True
    allow_merge = False
    top_dir = None
    for item in file_vector:
        if allow_merge == False:
            if os.path.isdir(os.path.join(source,item)):
                allow_merge, top_dir = if_dir_total_included_in_section(item,up_border,bottom_border)
                if allow_merge == True:
                    if debug:
                        print("THREAD-{} allow_merge {} top_dir {}, add to target".format(index,allow_merge,top_dir), file=sys.stdout)
                    rsync_targets.append(top_dir)
            else:
                rsync_targets.append(item)
        else:
            if item.startswith(top_dir):
                if debug:
                    print("THREAD-{} allow_merge ({}), skip {}".format(index,top_dir, item), file=sys.stdout)
                continue
            else:
                allow_merge=False
                if os.path.isdir(os.path.join(source,item)):
                    allow_merge, top_dir = if_dir_total_included_in_section(item,up_border,bottom_border)
                    if allow_merge == True:
                        if debug:
                            print("THREAD-{} allow_merge {} top_dir {}, add to target".format(index,allow_merge,top_dir), file=sys.stdout)
                        rsync_targets.append(top_dir)
                else:
                    if debug:
                        print("THREAD-{} not allow_merge ({}), add {} to tasks ".format(index, top_dir, item), file=sys.stdout)
                    rsync_targets.append(item)
                    
    if debug:
        print("THREAD-{} rsync_target: {}".format(index, rsync_targets))

    return do_rsync(source,dest,rsync_targets, parallel, index, bwlimit)


def rsync_part(source, filelist, total_line, parallel, index, dest, bwlimit=0):
    global debug
    if index >= parallel:
        print("index ({}) is bigger or equal to  parallel ({})".format(index, parallel), file=sys.stderr)
        return 1

    line_cnt = (total_line + parallel -1)/parallel
    begin_line = line_cnt*index 
    end_line = begin_line + line_cnt - 1
    if end_line >= total_line:
        end_line = total_line - 1

    if debug:
        print("total_line {} begin_line {} end_line {}".format(total_line, begin_line, end_line))
    file_vector = []
    
    up_border = None
    bottom_border = None
    with open(filelist) as f:
        line_no = 0
        for line in f:
            if line_no < begin_line:
                if line_no == begin_line-1:
                    up_border = line
                line_no += 1
                continue
            if line_no > end_line:
                bottom_border = line
                break
            file_vector.append(line[:-1])
            line_no += 1

    if debug:
        print("THREAD-{} file_vector{} up_border {} bottom_border {}".format(index,file_vector, up_border, bottom_border),file=sys.stdout)

    # border mean the first file which processed by next thread
    _rsync_part(source, up_border, file_vector, bottom_border, dest, parallel, index, bwlimit)
    return 0


def init(args):
    global real_parallel
    real_parallel = args
    
def rsync_source_to_dest(source, dest, parallel=4, filter_policy=None, bwlimit=0):
    ret, filelist = rsync_prepare(source, dest, filter_policy)
    if ret:
        print("rsync prepare failed, exit",file=sys.stderr)
        return 3

    total_line = sum(1 for line in open(filelist))

    if parallel < 1 or parallel > 100:
        print("Invalid parallel num {}".format(parallel), file=sys.stderr)
        return 4

    real_parallel = multiprocessing.Value('i',parallel)
    pool = multiprocessing.Pool(processes=parallel,initializer=init, initargs = (real_parallel,))
    
    tasks = []
    index = 0 

    while index < parallel:
        tasks.append((source, filelist, total_line, 
                      parallel, index,
                      dest,bwlimit/parallel)
                    )
        index = index + 1

    results = []
    for t in tasks:
        result=pool.apply_async(rsync_part,t)
        results.append(result)

    pool.close()
    pool.join()

    for result in results:
        print(result.get(), file=sys.stdout)
    return 0


def main(argv=None):
    if argv == None:
        argv = sys.argv

    usage = "usage: %prog [option]"
    parser = OptionParser(usage=usage)
    
    parser.add_option(
            "-s","--src",dest="source",
            help="source directory for rsync, must be directory"
    )
    parser.add_option(
            "-d","--dest",dest="dest",
            help="destination directory for rsync, must be directory"
    )
    parser.add_option(
            "-p","--parallel",dest="parallel",
            help="thread num for parallel rsync"
    )
    parser.add_option(
            "-w","--bwlimit",dest="bwlimit",
            help="limit transfer rate , unit is KB"
    )
    parser.add_option(
            "-f","--filter",dest="filter_policy",
            help="filter policy for rsync"
    )

    (options, args) = parser.parse_args()

    if options.source is None:
        print("source directory must specifiy\n", file=sys.stderr)
        return 1

    if options.dest is None:
        print("dest directory must specify\n", file=sys.stderr)
        return 1

    if options.bwlimit is None:
        options.bwlimit = 0

    if options.bwlimit < 0:
        print("bwlimit is less than zero, invalid",file=sys.stderr)
        return 1

    if options.parallel is None:
        options.parallel = 4
    else:
        options.parallel = int(options.parallel)

    global real_parallel
    real_parallel = options.parallel

    if not os.path.isdir(options.source):
        print("source {} is not a directory".format(options.source), file=sys.stderr)
        return 2

    if not os.path.isdir(options.dest):
        print("dest {} is not a directory".format(options.dest), file=sys.stderr)
        return 2

    if options.source[-1] != "/":
        options.source = options.source + "/"

    if options.dest[-1] != "/":
        options.dest = options.dest + "/"

    return rsync_source_to_dest(options.source, options.dest, options.parallel,
                                options.filter_policy, int(options.bwlimit))



if __name__ == "__main__":
    sys.exit(main())
