# LevelDB Tool

## Compile

```shell
g++ leveldb_tool.c -o leveldb_tool -l leveldb
```

## Usage

Replicate OSD X's level db from `/data/osd.X/current/omap` to `/data/osd.X/current/omap_new`:

```shell
level_db -i X
```

**PS**: Before running this command, you should stop OSD X by running command `service ceph stop osd.X` first. Otherwise, you will see error like:

```shell
Unable to open/create test database './testdb'
IO error: lock /data/osd.0/current/omap/LOCK: Resource temporarily unavailable
```

