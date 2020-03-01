# Parsync

## What is parsync?

Parsync is a script that tries to run multiple rsync command in parallel to speed up the sync progress.

## Why not rsync?

* `rsync` is a single process program, it cannot fully take the advantage of multi-cores CPU and high network band width. In short, it is slow.

* `rsync` can be run with tools like `find`, `parallel` and `xargs` to run multiple rsync processes in parallel, e.g.

  ```shell
  find SOURCE_DIR -type f | parallel --will-cite -j 5 rsync -av {} DESTINATION
  ```

  or

  ```shell
  find SOURCE_DIR -type d | xargs -I {} rsync -a {} DESTINATION
  ```

  In the first example, `parallel` will run 5 `rsync` processes to sync files under `SOURCE_DIR` one by one. If those files are large files, it is fine. However, if those are small files like 4KB, `rsync` will still be very slow.

  In the second example, one `rsync` process will be started for each directory under `SOURCE_DIR`. Usually, all files are not evenly spread under these directories which means, at first, `rsync` does run in parallel. But, soon, most of `rsync` processes will finish their work and exit, only the 1 or 2 `rsync` process will still be running. Then, `rsync` will become slow again.

## Usage


```shell
usage: parsync.py [-h] [--bwlimit BWLIMIT] [--id ID] [--parallel PARALLEL]
                  [--no-progress] [-n]
                  source destination ...

Run rsync in parallel. All parameters for parsync MUST be provided before
source as usage shows, any parameter after destination is directly passed to
rsync.

positional arguments:
  source               source of rsync, cannot be empty. DO NOT use syntax
                       like XXX/* for source, use XXX/ or "XXX/*" instead
  destination          destination of rsync, cannot be empty
  args                 additional arguments that will directly be send to
                       rsync

optional arguments:
  -h, --help           show this help message and exit
  --bwlimit BWLIMIT    limit I/O bandwidth; KBytes per second. Default: 0 KB/s
  --id ID              ID of backup task. It is the pid of current process by
                       default
  --parallel PARALLEL  run how many rsync processes in parallel
  --no-progress        do not show progress bar
  -n, --dry-run        perform a trial run with no changes made
```

*P.S.* If you encounter encoding error, add `LC_ALL=en_US.UTF-8` before parsync, e.g.

```shell
LC_ALL=en_US.UTF-8 python parsync.py SOURCE DEST
```
## Example Usage

#### Sync SOURCE to DEST

```shell
parsync.py SOURCE DEST
```

#### Sync files and dirs under SOURCE to DEST

```shell
parsync.py SOURCE/ DEST
```

or

```shell
parsync.py "SOURCE/*" DEST
```

The reason adding `"` around `SOURCE/*` is to avoid `SOURCE/*` being expanded into `SOURCE/a SOURCE/b …` by shell. 

#### Run 100 rsync in parallel

```shell
parsync.py --parallel=100 SOURCE DEST
```

#### Run parsync with bandwidth limit 4000KB/s with 100 rsync in parallel

```shell
parsync.py --parallel=100 --bwlimit=4000 SOURCE DEST
```

or

```shell
parsync.py --parallel=100 SOURCE DEST --bwlimit=40
```

In the first example, the `bwlimit` is passed to parsync and parsync will calculate the `bwlimit` for each rsync process, in this case, 40 KB/s. In the second example, the `bwlimit` is directly passed to rsync without any check or change.

## Test

Run `python test.py` to run unittest for parsync. If you encouter encoding error, add `LC_ALL=en_US.UTF-8` in the beginning of the command, for example: `LC_ALL=en_US.UTF-8 python test.py`

