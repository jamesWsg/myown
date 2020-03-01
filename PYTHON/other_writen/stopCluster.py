import logging
from snack import * 
from ezs3.cluster import ClusterManager
from ezs3.config import Ezs3CephConfig
from ezs3.gwgroup import GatewayGroupManager
from ezs3.utils import *
from ezs3.log import EZLog

logger = EZLog.get_logger(__name__)
EZLog.init_handler(logging.DEBUG, "/var/log/ezcloudstor/ezs3-stop-cluster.log")

class StopClusterAndShutDown:
    def __init__(self):
        self.cluster = ClusterManager()
        self.config = Ezs3CephConfig()
        self.all_nodes = self.cluster.list_nodes()
        self.mdses = self.config.get_mds_confs()
		
        self._ceph_conf = Ezs3CephConfig();
        self.myip = get_interface_ipv4(
            self._ceph_conf.get_storage_interface()
        )

    def stop_cluster(self):
        # stop cluster service and shutdown all hosts
        self._stop_general_service()
        self._stop_gateway_service()
        self._stop_ceph_service()
        self._shutdown_host()
    
    def _stop_general_service(self):
    	#stop general services
        total_steps = len(self.mdses) + len(self.all_nodes)
        general_services = [
            'ezs3-multiregion-agent',
            'ezsnapsched',
            'ezqos',
            'ezgwvm',
            'ezs3-agent',
            'ezmonitor'
        ]

        for node in self.all_nodes:
            try:
                for service in general_services:
                    output = do_cmd(
                        "ssh {} 'ezservice {} stop'".format(node, service),
                        timeout=15,
                        force=True
                    )
            except Exception as e:
                logger.warn(
                    "Error occur when stop general services on node " \
                        "{}: {}.".format(node, str(e))
                )

    def _stop_gateway_service(self):
    	# stop gateway services
        gateway_services = [
            'ezbackup-agent',
	    'ezcopy-agent',
            'ezfs-agent',
	    'eziscsi-rbd-cleaner',
	    'ezfs-gw',
	    'eziscsi',
	    'ezfs'
        ]
		
        for mds in self.mdses:
            try:
                for service in gateway_services:
                    output = do_cmd(
                        "ssh {} 'ezservice {} stop'".format(mds['host'], service),
                        timeout=30,
                        force=True
                    )
            except Exception as e:
		        logger.warn(
		            "Error occur when stop gateway services on node " \
		                "{}: {}.".format(mds["host"], str(e))
		        )

    def _stop_ceph_service(self):
        # stop ceph service
        do_cmd("ezs3-ha service_ceph -a stop mds > /dev/null 2>&1")
        do_cmd("ezs3-ha service_ceph -a stop mon > /dev/null 2>&1")
        do_cmd("ezs3-ha service_ceph -a stop osd > /dev/null 2>&1")

    def _shutdown_host(self):
        # shutdown all hosts but my host last
        self.all_nodes.remove(self.myip);
        try:
            for node in self.all_nodes:
                do_cmd("ssh {} 'poweroff'".format(node), 20, True)
                logger.info("start to poweroff node {}".format(node))
        
        except Exception as e:
    	    logger.warn(
    	        "Error occur when shutdown host on node " \
    	            "{}: {}.".format(node, str(e))
    	    )
    
    	do_cmd("poweroff")


stop=StopClusterAndShutDown()
stop.stop_cluster()
