#include <iostream>
#include <sstream>
#include <string>
#include <unistd.h>
#include <stdlib.h>

#include "leveldb/db.h"

using namespace std;

void usage()
{
	cout << "Replicate level db of osd.X" << endl;
	cout << "-i        id of osd" << endl;
}

int main(int argc, char *argv[])
{
	int c;
	string osd_id;
	while ((c = getopt(argc, argv, "h?i:")) != -1)
	{
		switch (c)
		{
		case 'i':
			osd_id = optarg;
			break;
		case 'h':
		case '?':
			usage();
			exit(1);
		default:
			break;
		}
	}

	if (osd_id.empty())
	{
		cerr << "Must specify an OSD with -i option!" << endl;
		return -1;
	}

	string omap = "/data/osd." + osd_id + "/current/omap";
	string omap_new = "/data/osd." + osd_id + "/current/omap_new";
	// Set up database connection information and open database
	leveldb::DB *db;
	leveldb::DB *db_new;
	leveldb::Options options;
	options.create_if_missing = true;

	leveldb::Status status = leveldb::DB::Open(options, omap, &db);

	if (false == status.ok())
	{
		cerr << "Unable to open/create test database './testdb'" << endl;
		cerr << status.ToString() << endl;
		return -1;
	}

	status = leveldb::DB::Open(options, omap_new, &db_new);
	if (false == status.ok())
	{
		cerr << "Unable to create test database omap_new" << endl;
		cerr << status.ToString() << endl;
		return -1;
	}

	leveldb::Iterator *it = db->NewIterator(leveldb::ReadOptions());
	for (it->SeekToFirst(); it->Valid(); it->Next())
	{
		status = db_new->Put(leveldb::WriteOptions(), it->key(), it->value());
		if (false == status.ok())
		{
			cerr << "Failed to put it->key().ToString()" << endl;
		}
	}
}