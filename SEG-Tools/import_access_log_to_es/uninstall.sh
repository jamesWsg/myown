#!/bin/sh

rm -f /etc/cron.d/import_access_log

rm -f /usr/local/bin/import_radosgw_access_log_to_es.py
rm -f /etc/ezs3/import_radosgw_access_log_to_es.conf


echo "Uninstallation finished."
