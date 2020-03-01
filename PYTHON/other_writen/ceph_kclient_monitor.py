import json
from os import path
from ezs3.command import do_cmd
from ezs3.config import Ezs3CephConfig
from ezs3.cluster import ClusterManager, PGState, Role
from ezs3.cluster import GW, RRS
from ezs3.kvstore import get2
from ezs3.log import EZLog
from ezs3.notifications import BigTeraNotificationSettings
from ezs3.thread import SimpleLoopThread
from ezs3.utils import send_notification

logger = EZLog.get_logger(__name__)

CEPH_KCLIENT_MONITOR_CFGKEY = "ceph_kclient_monitor_config"
# for safety we use default filestore_op_thread_suicide_timeout
CEPH_KCLIENT_MONITOR_INTERVAL = 180

class OSDRequest(object):
    def __init__(self, tid, osd_id, pg, oid, ops):
        self.tid = tid
        self.osd = osd_id
        self.pg = pg
        self.oid = oid
        self.ops = ops

    def __eq__(self, other):
        return self.tid == other.tid

    def __hash__(self):
        return int(self.tid)

    def __repr__(self, *args, **kwargs):
        return self.__str__()

    def __str__(self):
        return "{}: (osd.{} {} {} {})".format(self.tid, self.osd, self.pg,
                                              self.oid, ",".join(self.ops))

class CephKClientMonitorThread(SimpleLoopThread):
    def __init__(self):
        SimpleLoopThread.__init__(self, CEPH_KCLIENT_MONITOR_INTERVAL)

    def pre_start(self):
        self.__cluster = ClusterManager()
        self.__my_ip = Ezs3CephConfig().get_storage_ip()
        config_str = get2(CEPH_KCLIENT_MONITOR_CFGKEY)
        if config_str:
            self.__config = json.loads(config_str)
        else:
            self.__config = {"email": False, "repair": False}
        self.__known_osd_requests = set()

    def prepare(self):
        role = Role(self.__my_ip)
        if not (role.has_enabled(GW) or role.has_enabled(RRS)):
            return False
        active_mds = self.__cluster.get_active_mds(15)
        if not active_mds:
            logger.error("Cannot get active MDS.")
            return False
        mds_sessions = json.loads(
            do_cmd("ceph daemon mds.{} session ls".format(active_mds.id),
                   _host=active_mds.ip)
        )
        for session in mds_sessions:
            if "kernel_version" in session["client_metadata"]:
                if session["inst"].split()[1].split(":")[0] == self.__my_ip:
                    self.__ceph_client_id = session["id"]
                    break
        else:
            logger.error("Cannot find my client ID, should not happen!")
            return False
        self.__osdc_path = path.join(
            "/sys/kernel/debug/ceph",
            "{}.client{}".format(self.__cluster.get_fsid(10),
                                 self.__ceph_client_id),
            "osdc"
        )
        return True

    def get_osdc(self):
        requests = set()
        with open(self.__osdc_path) as f:
            for line in f.readlines():
                if line.startswith("Total"):
                    continue
                elements = line.split()
                if len(elements) != 5:
                    logger.warning("Cannot parse line '{}'".format(line))
                    continue
                requests.add(
                    OSDRequest(elements[0], elements[1][3:],
                               elements[2],  # pool + seed of pgid
                               elements[3], elements[4].split(","))
                )
        logger.debug("osdc: {}".format(requests))
        return requests

    def process_hang_osd_requests(self, requests):
        if self.__config["email"]:
            info = {
                "email_sender": BigTeraNotificationSettings.email_sender,
                "email_list": BigTeraNotificationSettings.email_list,
                "full_ratio": BigTeraNotificationSettings.full_ratio,
                "smtp_server": BigTeraNotificationSettings.smtp_server,
                "smtp_encrypt": BigTeraNotificationSettings.smtp_encrypt,
                "smtp_auth": BigTeraNotificationSettings.smtp_auth,
                "smtp_auth_user": BigTeraNotificationSettings.smtp_auth_user,
                "smtp_auth_passwd": BigTeraNotificationSettings.smtp_auth_passwd
            }
            try:
                send_notification("Warning",
                                  "OSD request stuck: {}".format(requests),
                                  info)
            except Exception:
                logger.exception("Failed to send email notification.")
        if self.__config["repair"]:
            # I don't know what other state can trust...
            allowed_state = [PGState.ACTIVE, PGState.CLEAN]
            if not self.__cluster.is_all_pg_in_state(allowed_state):
                logger.warning(
                    "Cannot proceed when cluster PG not in healthy state"
                )
                return
            if self.__cluster.list_full_osds():
                logger.warning("Cannot proceed when there is full OSD")
                return
            # for now we just pick the first request with non-negative OSD ID
            for request in requests:
                if int(request.osd) >= 0:
                    break
            else:
                logger.warning("All stuck requests are for osd-1?")
                return
            logger.debug("Handle stuck request {}.".format(request))
            for osd in self.__cluster.get_osds(15)[1]:
                if osd.id == request.osd:
                    tgt = osd
                    break
            else:
                logger.error("No OSD found? What?")
                return
            # make sure if the request is still in OSD's in_flight_ops
            in_flight_requests = json.loads(
                do_cmd("ceph daemon osd.{} dump_ops_in_flight".format(tgt.id),
                       _host=tgt.ip)
            )
            for op in in_flight_requests["ops"]:
                if len(op["type_data"]) < 3:
                    continue    # subop has no client data
                client_data = op["type_data"][1]
                if client_data["client"][6:] == self.__ceph_client_id and \
                   client_data["tid"] == request.tid:
                    logger.info(
                        "The request {} had still been processed.".format(
                            request
                        )
                    )
                    return
            # do restart, check PG state again!
            if not self.__cluster.is_all_pg_in_state(allowed_state):
                logger.warning(
                    "Cannot proceed when cluster PG not in healthy state"
                )
                return
            try:
                do_cmd("service ceph restart osd.{}".format(tgt.id),
                       timeout=60, _host=tgt.ip)
                logger.info("OSD %s had been restarted!", tgt.id)
            except Exception:
                logger.exception(
                    "Error occurs when restarting OSD {}, please contact " \
                        "the administrator for support.".format(tgt.id)
                )

    def run_in_loop(self):
        try:
            if not self.prepare():
                return
            osd_requests = self.get_osdc()
            remain_set = self.__known_osd_requests & osd_requests
            logger.debug("remain: %s", remain_set)
            if remain_set:
                logger.info(
                    "Found long lasting OSD requests: {}".format(remain_set)
                )
                self.process_hang_osd_requests(remain_set)
            self.__known_osd_requests = osd_requests
        except Exception:
            logger.exception("Error")
