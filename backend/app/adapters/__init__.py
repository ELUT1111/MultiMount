# Import all adapters to trigger @AdapterRegistry.register decorators
from app.adapters.local_adapter import LocalAdapter  # noqa: F401
from app.adapters.ftp_adapter import FTPAdapter  # noqa: F401
from app.adapters.sftp_adapter import SFTPAdapter  # noqa: F401
from app.adapters.webdav_adapter import WebDAVAdapter  # noqa: F401
from app.adapters.oss_adapter import OSSAdapter  # noqa: F401
from app.adapters.s3_adapter import S3Adapter  # noqa: F401
