"""
obsync.py: common library for ezobsync and s3backup
"""
from boto.exception import S3ResponseError
from boto.s3.connection import OrdinaryCallingFormat, SubdomainCallingFormat
from boto.s3.connection import S3Connection
from boto.s3.key import Key
from boto.s3.multipart import MultiPartUpload
from lxml import etree
from ezs3.log import EZLog
import boto
import errno
import hashlib
import os
from StringIO import StringIO
import tempfile
import time
import traceback
import xattr
import shutil

try:
    import cloudfiles
except ImportError:
    cloudfiles = None

logger = EZLog.get_logger(__name__)

ACL_XATTR = "rados.acl"
META_XATTR_PREFIX = "rados.meta."
BREAK_POINT_META = "break_point"
CONTENT_TYPE_XATTR = "rados.content_type"
# for FileStore xattr
SRC_MULTIPART_ETAG_XATTR = "rados.meta.srcetag"
MD5_XATTR = "rados.md5"
MTIME_XATTR = "rados.mtime"

# It is also in-memory chunk size; don't set it too large!
MULTIPART_THRESH = 10485760
# For S3 backup from breakpoint,100MB
BREAKPOINT_THRESHOLD = 100 * 1024 * 1024


class ObsyncException(Exception):
    def __init__(self, ty, e):
        if (isinstance(e, str)):
            # from a string
            self.tb = "".join(traceback.format_stack())
            self.comment = e
        else:
            # from another exception
            self.tb = traceback.format_exc(100000)
            self.comment = None
        self.ty = ty


class ObsyncTemporaryException(ObsyncException):
    """
    A temporary obsync exception.
    The user may want to retry the operation that failed.
    We can create one of these from a string or from another exception.
    """
    def __init__(self, e):
        ObsyncException.__init__(self, "temporary", e)


class ObsyncPermanentException(ObsyncException):
    """
    A permanent obsync exception.
    We can create one of these from a string or from another exception.
    """
    def __init__(self, e):
        ObsyncException.__init__(self, "permanent", e)


def test_xattr_support(path):
    test_file = path + "/$TEST"
    f = open(test_file, 'w')
    f.close
    try:
        xattr.set(test_file, "test", "123", namespace=xattr.NS_USER)
        if xattr.get(test_file, "test", namespace=xattr.NS_USER) != "123":
            raise ObsyncPermanentException(
                "test_xattr_support: failed to set an xattr and "
                "read it back.")
    except IOError:
        exc = "You do not appear to have xattr support at {}".format(path)
        logger.error(exc)
        raise ObsyncPermanentException(exc)
    finally:
        os.unlink(test_file)


def xattr_is_metadata(k):
    # miscellaneous user-defined metadata
    if (k[:len(META_XATTR_PREFIX)] == META_XATTR_PREFIX):
        return True
    # content-type
    elif (k == CONTENT_TYPE_XATTR):
        return True
    return False


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError, exc:
        if exc.errno != errno.EEXIST:
            raise ObsyncTemporaryException(exc)
        if not os.path.isdir(path):
            raise ObsyncTemporaryException(exc)


def bytes_to_str(b):
    return ''.join(["%02x" % ord(x) for x in b]).strip()


def get_md5(f, block_size=2**20):
    mtime = os.stat(f.name).st_mtime
    try:
        stored_md5 = xattr.get(f.name, MD5_XATTR, namespace=xattr.NS_USER)
        stored_mtime = xattr.get(f.name, MTIME_XATTR, namespace=xattr.NS_USER)
        if str(mtime) == stored_mtime:
            return stored_md5
    except IOError as e:
        if e.errno != errno.ENODATA:
            raise

    md5 = hashlib.md5()
    while True:
        data = f.read(block_size)
        if not data:
            break
        md5.update(data)
    md5sum = md5.hexdigest()
    file_set_md5(f.name, md5sum, mtime)

    return md5sum


def file_set_md5(path, md5, mtime=None):
    if not mtime:
        mtime = str(os.stat(path).st_mtime)
    xattr.set(path, MD5_XATTR, md5, namespace=xattr.NS_USER)
    xattr.set(path, MTIME_XATTR, str(mtime), namespace=xattr.NS_USER)


def strip_prefix(prefix, s):
    if not (s[0:len(prefix)] == prefix):
        return None
    return s[len(prefix):]


def etag_to_md5(etag):
    if (etag[:1] == '"'):
        start = 1
    else:
        start = 0
    if (etag[-1:] == '"'):
        end = -1
    else:
        end = None
    return etag[start:end]


# Escaping functions.
#
# Valid names for local files are a little different than valid object
# names for S3. So these functions are needed to translate.
#
# Basically, in local names, every sequence starting with a dollar sign is
# reserved as a special escape sequence. If you want to create an S3 object
# with a dollar sign in the name, the local file should have a double dollar
# sign ($$).
#
# TODO: translate local files' control characters into escape sequences.
# Most S3 clients (boto included) cannot handle control characters in S3 object
# names.
# TODO: check for invalid utf-8 in local file names. Ideally, escape it, but
# if not, just reject the local file name. S3 object names must be valid
# utf-8.
#
# ----------        -----------
# In S3             Locally
# ----------        -----------
# foo/              foo$slash
#
# $money            $$money
#
# obj-with-acl      obj-with-acl
#                  .obj-with-acl$acl
def s3_name_to_local_name(s3_name):
    # Now we treat an object which names end with slash as a local folder
    return s3_name

def local_name_to_s3_name(local_name):
    # Now we treat a local folder as a prefix object
    return local_name

###### ACLs #######
READ = 1
WRITE = 2
READ_ACP = 4
WRITE_ACP = 8
FULL_CONTROL = READ | WRITE | READ_ACP | WRITE_ACP

PERM_MAP = {
    "FULL_CONTROL": FULL_CONTROL,
    "READ": READ,
    "WRITE": WRITE,
    "READ_ACP": READ_ACP,
    "WRITE_ACP": WRITE_ACP
}


def perm_to_str_list(perm):
    perms = []
    if perm == FULL_CONTROL:
        perms.append("FULL_CONTROL")
    elif (perm & READ):
        perms.append("READ")
    elif (perm & WRITE):
        perms.append("WRITE")
    elif (perm & READ_ACP):
        perms.append("READ_ACP")
    elif (perm & WRITE_ACP):
        perms.append("WRITE_ACP")
    return perms


ACL_TYPE_CANON_USER = "canon:"
ACL_TYPE_EMAIL_USER = "email:"
ACL_TYPE_GROUP = "group:"
ALL_ACL_TYPES = [ACL_TYPE_CANON_USER, ACL_TYPE_EMAIL_USER, ACL_TYPE_GROUP]

S3_GROUP_AUTH_USERS = ACL_TYPE_GROUP + "AuthenticatedUsers"
S3_GROUP_ALL_USERS = ACL_TYPE_GROUP + "AllUsers"
S3_GROUP_LOG_DELIVERY = ACL_TYPE_GROUP + "LogDelivery"

NS = "http://s3.amazonaws.com/doc/2006-03-01/"
NS2 = "http://www.w3.org/2001/XMLSchema-instance"


def get_user_type(utype):
    for ut in [ACL_TYPE_CANON_USER, ACL_TYPE_EMAIL_USER, ACL_TYPE_GROUP]:
        if utype[:len(ut)] == ut:
            return ut
    raise ObsyncPermanentException("unknown user type for user %s" % utype)


def strip_user_type(utype):
    for ut in [ACL_TYPE_CANON_USER, ACL_TYPE_EMAIL_USER, ACL_TYPE_GROUP]:
        if utype[:len(ut)] == ut:
            return utype[len(ut):]
    raise ObsyncPermanentException("unknown user type for user %s" % utype)


def grantee_attribute_to_user_type(utype):
    if (utype == "Canonical User"):
        return ACL_TYPE_CANON_USER
    elif (utype == "CanonicalUser"):
        return ACL_TYPE_CANON_USER
    elif (utype == "Group"):
        return ACL_TYPE_GROUP
    elif (utype == "Email User"):
        return ACL_TYPE_EMAIL_USER
    elif (utype == "EmailUser"):
        return ACL_TYPE_EMAIL_USER
    else:
        raise ObsyncPermanentException("unknown user type for user %s" % utype)


def user_type_to_attr(t):
    if (t == ACL_TYPE_CANON_USER):
        return "CanonicalUser"
    elif (t == ACL_TYPE_GROUP):
        return "Group"
    elif (t == ACL_TYPE_EMAIL_USER):
        return "EmailUser"
    else:
        raise ObsyncPermanentException("unknown user type %s" % t)


def add_user_type(user):
    """
    All users that are not specifically marked as something else
    are treated as canonical users
    """
    for atype in ALL_ACL_TYPES:
        if (user[:len(atype)] == atype):
            return user
    return ACL_TYPE_CANON_USER + user


class AclGrant(object):
    def __init__(self, user_id, display_name, permission):
        self.user_id = user_id
        self.display_name = display_name
        self.permission = permission

    def translate_users(self, xusers):
        # Keep in mind that xusers contains user_ids of the form "type:value"
        # So typical contents might be like { canon:XYZ => canon.123 }
        if self.user_id in xusers:
            self.user_id = xusers[self.user_id]
            # It's not clear what the new pretty-name should be, so just leave it blank.
            self.display_name = None

    def equals(self, rhs):
        if self.user_id != rhs.user_id:
            return False
        if self.permission != rhs.permission:
            return False
        # ignore display_name
        return True


class AclPolicy(object):
    def __init__(self, owner_id, owner_display_name, grants):
        self.owner_id = owner_id
        self.owner_display_name = owner_display_name
        self.grants = grants  # dict of { string -> ACLGrant }

    @staticmethod
    def create_default(owner_id):
        grants = {}
        grants[ACL_TYPE_CANON_USER + owner_id] = \
            AclGrant(ACL_TYPE_CANON_USER + owner_id, None, FULL_CONTROL)
        return AclPolicy(owner_id, None, grants)

    @staticmethod
    def from_xml(s):
        root = etree.parse(StringIO(s))

        owner_id_node = root.find("{%s}Owner/{%s}ID" % (NS, NS))
        owner_id = owner_id_node.text
        owner_display_name = root.find("{%s}Owner/{%s}DisplayName" % (NS, NS))
        if owner_display_name is not None:
            owner_display_name = owner_display_name.text

        grantlist = root.findall("{%s}AccessControlList/{%s}Grant" % (NS, NS))
        grants = {}

        for g in grantlist:
            grantee = g.find("{%s}Grantee" % NS)
            if "type" in grantee.attrib:
                grantee_type = grantee.attrib["type"]
            else:
                grantee_type = grantee.attrib["{%s}type" % NS2]

            user_type = grantee_attribute_to_user_type(grantee_type)

            if user_type == ACL_TYPE_CANON_USER:
                user_id = grantee.find("{%s}ID" % NS).text
                display_name = grantee.find("{%s}DisplayName" % NS)
                if display_name is not None:
                    display_name = display_name.text
            elif user_type == ACL_TYPE_EMAIL_USER:
                user_id = grantee.find("{%s}EmailAddress" % NS).text
                display_name = None
            elif user_type == ACL_TYPE_GROUP:
                user_id = grantee.find("{%s}URI" % NS).text
                display_name = None
            else:
                raise ObsyncPermanentException("unknown ACL grantee type")

            permission = g.find("{%s}Permission" % NS).text
            perm = PERM_MAP[permission]
            grant_user_id = user_type + user_id
            if grant_user_id not in grants:
                grants[grant_user_id] = AclGrant(grant_user_id, display_name, perm)
            else:
                grants[grant_user_id].permission |= perm

        return AclPolicy(owner_id, owner_display_name, grants)

    def to_xml(self):
        root = etree.Element("AccessControlPolicy", nsmap={None: NS})
        owner = etree.SubElement(root, "Owner")
        id_elem = etree.SubElement(owner, "ID")
        id_elem.text = self.owner_id
        if self.owner_display_name:
            display_name_elem = etree.SubElement(owner, "DisplayName")
            display_name_elem.text = self.owner_display_name

        access_control_list = etree.SubElement(root, "AccessControlList")
        for k, g in self.grants.items():
            perms = perm_to_str_list(g.permission)
            for perm in perms:
                grant_elem = etree.SubElement(access_control_list, "Grant")
                grantee_elem = etree.SubElement(
                    grant_elem, "{%s}Grantee" % NS, nsmap={None: NS, "xsi": NS2})

                user_type = get_user_type(g.user_id)
                grantee_elem.set("{%s}type" % NS2, user_type_to_attr(user_type))

                if user_type == ACL_TYPE_CANON_USER:
                    user_id_elem = etree.SubElement(grantee_elem, "{%s}ID" % NS)
                    user_id_elem.text = strip_user_type(g.user_id)
                    if g.display_name:
                        display_name_elem = etree.SubElement(
                            grantee_elem, "{%s}DisplayName" % NS)
                        display_name_elem.text = g.display_name
                elif user_type == ACL_TYPE_EMAIL_USER:
                    email_elem = etree.SubElement(
                        grantee_elem, "{%s}EmailAddress" % NS)
                    email_elem.text = strip_user_type(g.user_id)
                elif user_type == ACL_TYPE_GROUP:
                    group_elem = etree.SubElement(grantee_elem, "{%s}URI" % NS)
                    group_elem.text = strip_user_type(g.user_id)
                else:
                    raise ObsyncPermanentException("unknown ACL grantee type")

                permission_elem = etree.SubElement(grant_elem, "{%s}Permission" % NS)
                permission_elem.text = perm
        return etree.tostring(root, encoding="UTF-8")

    def translate_users(self, xusers):
        # Owner ids are always expressed in terms of canonical user id
        user = ACL_TYPE_CANON_USER + self.owner_id
        if (user in xusers):
            self.owner_id = strip_user_type(xusers[user])
            self.owner_display_name = ""

        for k, g in self.grants.items():
            g.translate_users(xusers)

    def get_all_users(self):
        """ Get a list of all user ids referenced in this ACL """
        users = {}
        users[ACL_TYPE_CANON_USER + self.owner_id] = 1
        for k, g in self.grants.items():
            users[k] = 1
        return users.keys()

    def set_owner(self, owner_id):
        self.owner_id = owner_id
        self.owner_display_name = ""

    def equals(self, rhs):
        if (self.owner_id != rhs.owner_id):
            return False
        for k, g in self.grants.items():
            if k not in rhs.grants:
                return False
            if not g.equals(rhs.grants[k]):
                return False
        for l, r in rhs.grants.items():
            if l not in self.grants:
                return False
            if not r.equals(self.grants[l]):
                return False
        return True


class Object(object):

    def __init__(self, name, md5, size, meta):
        if isinstance(name, unicode):
            self.name = name
        else:
            self.name = name.decode('UTF-8')
        self.md5 = md5
        self.size = int(size)
        if SRC_MULTIPART_ETAG_XATTR in meta:
            self.md5 = meta[SRC_MULTIPART_ETAG_XATTR]
            del meta[SRC_MULTIPART_ETAG_XATTR]
        self.meta = meta
        self.is_folder = False
        if name.endswith("/"):
            self.is_folder = True

    def __str__(self):
        return u"(name: {}, size: {}: md5: {}, meta: {}, is_folder: {})".format(self.name, self.size, self.md5, self.meta, self.is_folder)

    def should_check_etags(self, rhs, check_etags):
        if check_etags == "never":
            return False
        if check_etags == "relaxed":
            logger.debug(
                "ETAGS: --check-etags={0}, self.md5 = {1}, rhs.md5 = {2}"
                .format(check_etags, self.md5, rhs.md5)
            )
            return not ('-' in self.md5 or '-' in rhs.md5)
        return True

    def equals(self, rhs, ignore_empty_s3_meta=False, cmp_etag="always"):
        if self.is_folder and rhs.is_folder:
            if (self.name != rhs.name):
                logger.debug("EQUALS: self.name = %s, rhs.name = %s" % (self.name, rhs.name))
                return False
            return True
        else:
            if (self.name != rhs.name):
                logger.debug("EQUALS: self.name = %s, rhs.name = %s" % (self.name, rhs.name))
                return False
            if (self.should_check_etags(rhs, cmp_etag) and self.md5 != rhs.md5):
                logger.debug("EQUALS: self.md5 = %s, rhs.md5 = %s" % (self.md5, rhs.md5))
                return False
            if (self.size != rhs.size):
                logger.debug("EQUALS: self.size = %d, rhs.size = %d" % (self.size, rhs.size))
                return False
            for k, v in self.meta.items():
                if k not in rhs.meta:
                    logger.debug("EQUALS: rhs.meta lacks key %s" % k)
                    return False
                if (rhs.meta[k] != v):
                    logger.debug(
                        "EQUALS: self.meta[%s] = %s, rhs.meta[%s] = %s" % (k, v, k, rhs.meta[k])
                    )
                    return False
            if self.meta or not ignore_empty_s3_meta:
                for k, v in rhs.meta.items():
                    if k not in self.meta:
                        logger.debug("EQUALS: self.meta lacks key %s" % k)
                        return False
            logger.debug("EQUALS: the objects are equal.")
            return True

    def local_name(self):
        local_name = s3_name_to_local_name(self.name)
        if not isinstance(local_name, unicode):
            local_name = local_name.decode('UTF-8')
        return local_name

    def local_path(self, base):
        if not isinstance(base, unicode):
            base = base.decode('UTF-8')
        if self.is_folder:
            full_path = os.path.join(base, self.name)
        else:
            full_path = os.path.join(base, self.local_name())
        return full_path.encode('UTF-8')

    @staticmethod
    def from_file(obj_name, path):
        f = open(path, 'r')
        try:
            md5 = get_md5(f)
        finally:
            f.close()
        size = os.path.getsize(path)
        meta = {}
        try:
            xlist = xattr.get_all(path, namespace=xattr.NS_USER)
        except IOError, e:
            if e.errno == 2:
                return meta
            else:
                raise ObsyncTemporaryException(e)
        for k, v in xlist:
            if xattr_is_metadata(k):
                meta[k] = v
        #print "Object.from_file: path="+path+",md5=" + bytes_to_str(md5) +",size=" + str(size)
        return Object(obj_name, md5, size, meta)

    @staticmethod
    def from_folder(obj_name, path):
        return Object(obj_name, 'd41d8cd98f00b204e9800998ecf8427e', 0, {})


class Store(object):
    @staticmethod
    def make_store(type, is_dst, create, akey, skey, dry_run, **kwargs):
        if (type == 's3'):
            try:
                store = S3Store(kwargs['host'], kwargs['bucket'],
                                kwargs['prefix'], create, akey, skey, dry_run,
                                is_secure=True)
                logger.info("Connect to S3 store via HTTPS successfully.")
            except Exception as e:
                store = S3Store(kwargs['host'], kwargs['bucket'],
                                kwargs['prefix'], create, akey, skey, dry_run,
                                is_secure=False)
                logger.info("Connect to S3 store via HTTP successfully.")
            return store
        elif (type == 'swift'):
            return SwiftStore(kwargs['host'], kwargs['bucket'],
                              kwargs['prefix'], create, akey, skey, dry_run,
                              False)
        elif (type == 'file'):
            return FileStore(kwargs['path'], create, dry_run,
                             kwargs.get('follow_symlinks', False))
        raise ObsyncPermanentException('Unknown store type: "%s"' % type)


class LocalCopy(object):

    def __init__(self, obj_name, path, path_is_temp):
        self.obj_name = obj_name
        self.path = path
        self.path_is_temp = path_is_temp

    def remove(self):
        if self.path_is_temp and (self.path is not None):
            os.unlink(self.path)
        self.path = None
        self.path_is_temp = False

    def __del__(self):
        self.remove()


class LocalAcl(object):

    @staticmethod
    def from_xml(obj_name, xml):
        acl_policy = AclPolicy.from_xml(xml)
        return LocalAcl(obj_name, acl_policy)

    @staticmethod
    def get_empty(obj_name):
        return LocalAcl(obj_name, None)

    def __init__(self, obj_name, acl_policy):
        self.obj_name = obj_name
        self.acl_policy = acl_policy

    def equals(self, rhs, ignore_empty_s3_acl=False):
        """ Compare two LocalAcls """
        if self.acl_policy is None:
            return (ignore_empty_s3_acl or rhs.acl_policy is None)
        if rhs.acl_policy is None:
            return (self.acl_policy is None)
        return self.acl_policy.equals(rhs.acl_policy)

    def translate_users(self, xusers):
        """ Translate the users in this ACL """
        if (self.acl_policy is None):
            return
        self.acl_policy.translate_users(xusers)

    def set_owner(self, owner_id):
        if (self.acl_policy is None):
            return
        self.acl_policy.set_owner(owner_id)

    def write_to_xattr(self, file_name):
        """ Write this ACL to an extended attribute """
        if (self.acl_policy is None):
            return
        xml = self.acl_policy.to_xml()
        xattr.set(file_name, ACL_XATTR, xml, namespace=xattr.NS_USER)


###### S3 store #######
def s3_key_to_meta(k):
    meta = {}
    if (k.__dict__.has_key("content_type")):
        meta[CONTENT_TYPE_XATTR] = k.content_type
    for k, v in k.metadata.items():
        meta[META_XATTR_PREFIX + k] = v
    return meta


def meta_to_s3_key(key, meta):
    for k, v in meta.items():
        if (k == CONTENT_TYPE_XATTR):
            key.set_metadata("Content-Type", v)
        elif (k[:len(META_XATTR_PREFIX)] == META_XATTR_PREFIX):
            k_name = k[len(META_XATTR_PREFIX):]
            key.set_metadata(k_name, v)
        else:
            raise ObsyncPermanentException("can't understand meta entry: %s" % k)


def meta_to_dict(meta):
    result = {}
    for k, v in meta.items():
        if (k == CONTENT_TYPE_XATTR):
            result["Content-Type"] = v
        elif (k[:len(META_XATTR_PREFIX)] == META_XATTR_PREFIX):
            k_name = k[len(META_XATTR_PREFIX):]
            result[k_name] = v
        else:
            raise ObsyncPermanentException("can't understand meta entry: %s" % k)
    return result


class S3StoreIterator(object):
    """S3Store iterator"""
    def __init__(self, bucket, blrs):
        self.bucket = bucket
        self.blrs = blrs

    def __iter__(self):
        return self

    def next(self):
        # This will raise StopIteration when there are no more objects to
        # iterate on
        key = self.blrs.next()
        # Issue a HEAD request to get content-type and other metadata
        k = self.bucket.get_key(key.name)
        ret = Object(key.name, etag_to_md5(key.etag), key.size, s3_key_to_meta(k))
        return ret


class S3Store(Store):
    def __init__(self, host, bucket_name, object_prefix, create, akey, skey,
                 dry_run, is_secure):
        self.host = host
        self.bucket_name = bucket_name
        self.key_prefix = object_prefix
        self.dry_run = dry_run

        self.conn = S3Connection(calling_format=OrdinaryCallingFormat(),
                                 host=self.host, is_secure=is_secure,
                                 aws_access_key_id=akey, aws_secret_access_key=skey)

        try:
            self.bucket = self.conn.get_bucket(self.bucket_name)
        except S3ResponseError as e:
            if e.status == 301: # Moved Permanently, try subdomain format
                self.conn = S3Connection(
                    calling_format=SubdomainCallingFormat(),
                    host=self.host, is_secure=is_secure,
                    aws_access_key_id=akey,
                    aws_secret_access_key=skey
                )
                try:
                    self.bucket = self.conn.get_bucket(self.bucket_name)
                except S3ResponseError as e:
                    if e.status == 404:
                        self.bucket = None
                    else:
                        raise e
            elif e.status == 404:
                self.bucket = None
            else:
                raise e

        if self.bucket is None: # Not Found
            if create:
                if not self.dry_run:
                    self.bucket = self.conn.create_bucket(self.bucket_name)
            else:
                raise ObsyncPermanentException(
                    "The bucket does not exist and we are not to create it."
                )

    def __str__(self):
        return "s3://" + self.host + "/" + self.bucket_name + "/" + self.key_prefix

    def get_acl(self, obj):
        acl_xml = self.bucket.get_xml_acl(obj.name)
        return LocalAcl.from_xml(obj.name, acl_xml)

    def make_local_copy(self, obj):
        k = Key(self.bucket)
        k.key = obj.name
        temp_file = tempfile.NamedTemporaryFile(prefix='/run/shm/', mode='w+b', delete=False).name
        try:
            k.get_contents_to_filename(temp_file)
        except Exception, e:
            os.unlink(temp_file)
            raise ObsyncTemporaryException(e)
        return LocalCopy(obj.name, temp_file, True)

    def all_objects(self):
        if self.bucket is None:
            return []
        blrs = self.bucket.list(prefix=self.key_prefix)
        return S3StoreIterator(self.bucket, blrs.__iter__())

    def get_object_size(self, obj):
        k = self.bucket.get_key(obj.name)
        if (k is None):
            return 0
        return k.size

    def locate_object(self, obj):
        if self.bucket is None:
            return None
        k = self.bucket.get_key(obj.name)
        if (k is None):
            logger.debug(u"S3Store: cannot locate obj: {}".format(obj.name))
            return None
        else:
            logger.debug(u"S3Store: located obj: {}".format(obj.name))
        return Object(obj.name, etag_to_md5(k.etag), k.size, s3_key_to_meta(k))

    def multipart_upload(self, store, acl, obj):
        pass

    def query_existing_multipart_uploads_in_s3(self, obj):
        multipart_uploads_filter = {'key_marker': obj.name}
        all_multipart_uploads = self.bucket.get_all_multipart_uploads(**multipart_uploads_filter)
        if len(all_multipart_uploads) >= 1:
            logger.debug(u"S3Store: multipart_uploads exists '{}'".format(obj.name))
            existing_parts = []
            mpu = MultiPartUpload(self.bucket)
            mpu.key_name = obj.name
            mpu.bucket_name = self.bucket_name
            mpu.id = all_multipart_uploads[0].id

            all_parts = mpu.get_all_parts()
            for one_parts in all_parts:
                response_part = {
                    'part_number': one_parts.part_number,
                    'etag': one_parts.etag.replace('"', ''),
                    'size': one_parts.size
                }
                existing_parts.append(response_part)
            return {'mpu': mpu, 'parts': existing_parts}

        else:
            return None

    def get_obj_ioctx_md5(self, ioctx):
        if self.dry_run:
            return ''
        m = hashlib.md5()
        m.update(ioctx.read())
        md5 = m.hexdigest()
        ioctx.seek(0)

        return md5

    def upload(self, src, obj):
        if self.dry_run:
            return

        logger.debug(u"S3Store: upload obj '{}'".format(obj.name))

        if obj.size <= MULTIPART_THRESH:
            k = Key(self.bucket)
            k.key = obj.name
            meta_to_s3_key(k, obj.meta)
            ioctx = src.get_obj_ioctx(obj)
            k.set_contents_from_file(ioctx)
        else:
            if obj.size >= BREAKPOINT_THRESHOLD:
                existing_multipart_upload = self.query_existing_multipart_uploads_in_s3(obj)
            else:
                # For small files,just upload them again
                existing_multipart_upload = None

            if existing_multipart_upload is not None:
                logger.info(u"S3Store: uploading file from breakpoint: '{}'".format(obj.name))
                # There some parts in S3,keep uploading ...
                mpu = existing_multipart_upload['mpu']
                try:
                    remaining = obj.size
                    part_num = 0
                    part_size = MULTIPART_THRESH

                    while remaining > 0:
                        current_part_num = part_num + 1
                        offset = part_num * part_size
                        length = min(remaining, part_size)
                        ioctx = src.get_obj_ioctx(obj, offset, length)

                        local_etag = unicode(self.get_obj_ioctx_md5(ioctx))
                        found_part = False
                        for one_part in existing_multipart_upload['parts']:
                            # we'd better check etag.
                            if current_part_num == one_part['part_number'] and \
                                    length == one_part['size'] and \
                                    local_etag == one_part['etag']:
                                found_part = True
                                break
                        if found_part is False:
                            logger.debug(u"S3Store: uploading part: '{}'".format(current_part_num))
                            mpu.upload_part_from_file(ioctx, current_part_num)
                        else:
                            logger.debug(u"S3Store: found part: '{}'".format(current_part_num))

                        remaining -= length
                        part_num += 1

                    logger.info(u"S3Store: Ready to complete_upload: '{}'".format(obj.name))
                    mpu.complete_upload()
                except Exception as e:
                    # Something is wrong.Maybe there are garbage data.Remove them.
                    logger.warning(u"S3Store: Something is wrong.cancel_upload: '{}'".format(obj.name))
                    mpu.cancel_upload()
                    raise e

            else:
                mpu = self.bucket.initiate_multipart_upload(obj.name, metadata=meta_to_dict(obj.meta))
                try:
                    remaining = obj.size
                    part_num = 0
                    part_size = MULTIPART_THRESH

                    while remaining > 0:
                        offset = part_num * part_size
                        length = min(remaining, part_size)
                        ioctx = src.get_obj_ioctx(obj, offset, length)
                        mpu.upload_part_from_file(ioctx, part_num + 1)
                        remaining -= length
                        part_num += 1

                    mpu.complete_upload()
                except Exception as e:
                    # Do NOT cancel for large file.We will use previous parts in future.
                    if obj.size < BREAKPOINT_THRESHOLD:
                        mpu.cancel_upload()
                    raise e

    def set_acl(self, src_acl, obj):
        if src_acl.acl_policy is not None:
            xml = src_acl.acl_policy.to_xml()
            try:
                def fn():
                    self.bucket.set_xml_acl(xml, obj.name)
                do_with_s3_retries(fn)
            except boto.exception.S3ResponseError, e:
                logger.error(
                    "ERROR SETTING ACL on object '{}'\n"
                    "************* ACL: *************\n"
                    "{}\n"
                    "********************************\n"
                    .format(obj.name, str(xml))
                )
                raise ObsyncTemporaryException(e)

    def remove(self, obj):
        if self.dry_run:
            return
        self.bucket.delete_key(obj.name)
        logger.debug("S3Store: removed %s", obj.name)

    def clear(self):
        pass

    def get_obj_ioctx(self, obj, offset=None, length=None):
        k = self.bucket.get_key(obj.name)
        if k is None:
            return None
        ioctx = StringIO()
        headers = None
        if offset is not None and length is not None:
            headers = {
                "Range": "bytes={}-{}".format(offset, offset+length-1)
            }
        k.get_contents_to_file(ioctx, headers)
        ioctx.seek(0)
        return ioctx


# Some S3 servers offer "eventual consistency."
# What this means is that after a change has been made, like the creation of an
# object, it takes some time for this change to become visible to everyone.
# This potentially includes the client making the change.
#
# This means we need to implement a retry mechanism for certain operations.
# For example, setting the ACL on a newly created object may fail with an
# "object not found" error if the object creation hasn't yet become visible to
# us.
def do_with_s3_retries(fn):
    if (os.environ.has_key("DST_CONSISTENCY") and
            os.environ["DST_CONSISTENCY"] == "eventual"):
        sleep_times = [5, 10, 60, -1]
    else:
        sleep_times = [-1]
    for stime in sleep_times:
        try:
            fn()
            return
        except boto.exception.S3ResponseError, e:
            if (stime == -1):
                raise ObsyncTemporaryException(e)
            logger.warning(
                "encountered s3 response error: %s: " \
                    "retrying operation after %d second delay",
                str(e), str(stime)
            )
            time.sleep(stime)


###### Swift store #######
def swift_object_to_meta(obj):
    meta = {}
    if (obj.__dict__.has_key("content_type")):
        meta[CONTENT_TYPE_XATTR] = obj.content_type
    for k, v in obj.metadata.items():
        meta[META_XATTR_PREFIX + k] = v
    return meta


def meta_to_swift_object(obj, meta):
    for k, v in meta.items():
        if (k == CONTENT_TYPE_XATTR):
            obj.metadata["Content-Type"] = v
        elif (k[:len(META_XATTR_PREFIX)] == META_XATTR_PREFIX):
            k_name = k[len(META_XATTR_PREFIX):]
            obj.metadata[k_name] = v
        else:
            raise ObsyncPermanentException("can't understand meta entry: %s" % k)
        obj.sync_metadata()


class SwiftStoreIterator(object):
    """SwiftStore iterator"""
    def __init__(self, container, object_list):
        self.container = container
        self.generator = (o for o in object_list)

    def __iter__(self):
        return self

    def next(self):
        # This will raise StopIteration when there are no more objects to
        # iterate on
        obj = self.generator.next()
        obj = self.container.get_object(obj.name)
        ret = Object(obj.name, etag_to_md5(obj._etag), obj.size, swift_object_to_meta(obj))
        return ret


class SwiftStore(Store):
    def __init__(self, authurl, container_name, object_prefix, create, akey,
                 skey, dry_run, is_secure):
        self.host = authurl
        self.container_name = container_name
        self.object_prefix = object_prefix
        self.dry_run = dry_run

        self.conn = cloudfiles.get_connection(
            username=akey, api_key=skey, authurl=self.host
        )
        try:
            self.container = self.conn.get_container(self.container_name)
        except cloudfiles.errors.NoSuchContainer:
            self.container = None

        if self.container is None:
            if create:
                if not self.dry_run:
                    self.container = self.conn.create_container(
                        self.container_name
                    )
            else:
                raise ObsyncPermanentException(
                    "%s: no such container as %s" % (self.host, self.container_name)
                )

    def __str__(self):
        return "swift://{}/{}/{}".format(
            self.host, self.container_name, self.object_prefix
        )

    def get_acl(self, obj):
        raise NotImplementedError   # We always use --no-preserve-acls right now

    def make_local_copy(self, obj):
        o = self.container.get_object(obj.name)
        temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False).name
        try:
            o.save_to_filename(temp_file)
        except Exception, e:
            os.unlink(temp_file)
            raise ObsyncTemporaryException(e)
        return LocalCopy(obj.name, temp_file, True)

    def all_objects(self):
        if self.container is None:
            return []
        object_list = self.container.get_objects(prefix=self.object_prefix)
        return SwiftStoreIterator(self.container, object_list)

    def locate_object(self, obj):
        if self.container is None:
            return None
        try:
            o = self.container.get_object(obj.name)
        except cloudfiles.errors.NoSuchObject:
            return None
        return Object(obj.name, etag_to_md5(o._etag), o.size, swift_object_to_meta(o))

    def upload(self, src, obj):
        if self.dry_run:
            return

        logger.debug(u"SwiftStore: upload obj '{}'".format(obj.name))

        o = self.container.create_object(obj.name)

        if obj.size <= MULTIPART_THRESH:
            ioctx = src.get_obj_ioctx(obj)
            o.write(ioctx)
            meta_to_swift_object(o, obj.meta)
        else:
            raise NotImplementedError("obj size too large. not supported")

    def set_acl(self, src_acl, obj):
        if src_acl.acl_policy is not None:
            #FIXME: no acls for swift yet
            pass

    def remove(self, obj):
        if self.dry_run:
            return
        self.container.delete_object(obj.name)
        logger.debug("SwiftStore: removed %s", obj.name)

    def clear(self):
        pass

    def get_obj_ioctx(self, obj, offset=None, length=None):
        try:
            o = self.container.get_object(obj.name)
            ioctx = StringIO()
            if offset is None or length is None:
                o.read(buffer=ioctx)
            else:
                o.read(offset=offset, size=length, buffer=ioctx)
            ioctx.seek(0)
            return ioctx
        except cloudfiles.errors.NoSuchObject:
            return None


###### FileStore #######
class FileStoreIterator(object):
    """FileStore iterator"""
    def __init__(self, base, follow_symlinks=False):
        self.base = base
        self.generator = os.walk(base, followlinks=follow_symlinks)
        self.path = ""
        self.files = []

    def __iter__(self):
        return self

    def next(self):
        while True:
            if (len(self.files) == 0):
                self.path, dirs, self.files = self.generator.next()
                self.files.extend(dirs)
                continue
            path = os.path.join(self.path, self.files[0])
            self.files = self.files[1:]
            # Ignore non-files when iterating.
            if os.path.isfile(path):
                obj_name = local_name_to_s3_name(path[len(self.base)+1:])
                return Object.from_file(obj_name, path)
            elif os.path.isdir(path):
                return Object.from_folder(path[len(self.base)+1:] + "/", path)


class FileStore(Store):
    def __init__(self, url, create, dry_run, follow_symlinks=False):
        # Parse the file url
        self.base = url
        self.dry_run = dry_run
        self.follow_symlinks = follow_symlinks
        if (self.base[-1:] == '/'):
            self.base = self.base[:-1]
        if create:
            if not self.dry_run:
                mkdir_p(self.base)
        elif not os.path.isdir(self.base):
            raise ObsyncPermanentException("NonexistentStore")

        if os.path.isdir(self.base):
            test_xattr_support(self.base)

    def __str__(self):
        return "file://" + self.base

    def get_acl(self, obj):
        try:
            xml = xattr.get(obj.local_path(self.base), ACL_XATTR,
                            namespace=xattr.NS_USER)
        except IOError, e:
            #print "failed to get XML ACL from %s" % obj.local_name()
            if e.errno == 61:
                return LocalAcl.get_empty(obj.name)
            raise ObsyncPermanentException(e)
        return LocalAcl.from_xml(obj.name, xml)

    def make_local_copy(self, obj):
        return LocalCopy(obj.name, obj.local_path(self.base), False)

    def all_objects(self):
        if os.path.isdir(self.base):
            return FileStoreIterator(self.base, self.follow_symlinks)
        else:
            return []

    def locate_object(self, obj):
        path = obj.local_path(self.base)
        if obj.is_folder:
            found = os.path.isdir(path)
            if found:
                return Object.from_folder(obj.name, path)
            else:
                return None
        else:
            found = os.path.isfile(path)
            logger.debug("FileStore::locate_object: %s object '%s'",
                         "found" if found else "did not find", obj.name)
            if (not found):
                return None
            return Object.from_file(obj.name, path)

    def upload(self, src, obj):
        if self.dry_run:
            return

        logger.debug(u"FileStore: upload obj '{}'".format(obj.name))

        lname = obj.local_name()
        d = os.path.join(self.base, lname).encode("UTF-8")
        mkdir_p(os.path.dirname(d))

        if obj.is_folder:
            d = os.path.join(self.base, obj.name).encode("UTF-8")
            mkdir_p(d)
        else:
            if obj.size <= MULTIPART_THRESH:
                ioctx = src.get_obj_ioctx(obj)
                with open(d, "wb") as f:
                    f.write(ioctx.read())
            else:
                try:
                    break_point = 0
                    offset = 0
                    if os.path.isfile(d):
                        try:
                            value = xattr.get(d, BREAK_POINT_META, namespace=xattr.NS_USER)
                            break_point = int(value)
                            logger.info('break point for {} is {}'.format(d, break_point))
                        except Exception as e:
                            logger.error(u"failed to get break_point xatr for {} {}".format(d,str(3)))
                            pass

                    if break_point % MULTIPART_THRESH != 0 or break_point > obj.size:
                        logger.info('break point for {} is {}'.format(d, break_point))
                        break_point = 0;

                    remaining = obj.size - break_point
                    part_num = break_point / MULTIPART_THRESH
                    part_size = MULTIPART_THRESH

                    seek_first = False
                    if break_point != 0:
                        seek_first = True
                        open_option = "r+b"
                    else:
                        open_option = "wb"

                    with open(d, open_option) as f:
                        while remaining > 0:
                            offset = part_num * part_size
                            length = min(remaining, part_size)
                            ioctx = src.get_obj_ioctx(obj, offset, length)
                            if seek_first:
                                f.seek(offset)
                                seek_first = False
                            f.write(ioctx.read())
                            remaining -= length
                            part_num += 1

                    if break_point != 0:
                        f = open(d, 'r')
                        try:
                            md5 = get_md5(f)
                        finally:
                            f.close()
                        if md5 != obj.md5:
                            logger.info("file md5 {} is not equal to {}".format(md5, obj.md5))
                            remaining = break_point
                            part_num = 0
                            part_size = MULTIPART_THRESH

                            with open(d, open_option) as f:
                                while remaining > 0:
                                    offset = part_num * part_size
                                    length = min(remaining, part_size)
                                    ioctx = src.get_obj_ioctx(obj, offset, length)
                                    f.write(ioctx.read())
                                    remaining -= length
                                    part_num += 1
                    try:
                        xattr.remove(d, BREAK_POINT_META, namespace=xattr.NS_USER)
                    except Exception as e:
                        pass

                except Exception as e:
                    if break_point == 0 and offset >= 10* MULTIPART_THRESH:
                        xattr.set(d, BREAK_POINT_META, str(int(offset)),namespace=xattr.NS_USER)
                        logger.error('failed to upload ,set break point to {}'.format(offset))
                    raise e

        # Store metadata in extended attributes
        file_set_md5(d, obj.md5)
        for k, v in obj.meta.items():
            xattr.set(d, k, v, namespace=xattr.NS_USER)

    def set_acl(self, src_acl, obj):
        if not obj.is_folder:
            lname = obj.local_name()
            d = os.path.join(self.base, lname).encode("UTF-8")
            mkdir_p(os.path.dirname(d))
            src_acl.write_to_xattr(d)

    def remove(self, obj):
        if self.dry_run:
            return
        path = os.path.join(self.base, obj.name.encode("UTF-8"))
        try:
            if os.path.isfile(path):
                os.unlink(path)
            if os.path.isdir(path):
                shutil.rmtree(path)
        except Exception:
            logger.warning("FileStore: remove %s failed", obj.name)

        logger.debug("FileStore: removed %s", obj.name)

    def clear(self):
        for entry in os.listdir(self.base):
            path = os.path.join(self.base, entry)
            if os.path.isfile(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)

    def get_obj_ioctx(self, obj, offset=None, length=None):
        if obj.is_folder:
            return StringIO("")
        else:
            path = obj.local_path(self.base)
            found = os.path.isfile(path)
            if not found:
                return None
            with open(path, "rb") as f:
                if offset is not None:
                    f.seek(offset)
                if length is not None:
                    return StringIO(f.read(length))
                else:
                    return StringIO(f.read())
