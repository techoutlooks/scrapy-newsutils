"""
Upload binary files to Google Cloud Storage bucket
Nota:
Example usages:

>>> bucket = "leeram-news"
>>> url = "https://unsplash.com/photos/hteGzeFuB7w"
>>> upload_blob_from_url(url, bucket)
>>> get_storage_client().create_bucket(bucket)

Requisite: set gcloud env
>>> sa_json = "path/to/gcloud_service_account.json"
>>> os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = sa_json


Docs:
 - [gcloud](https://gcloud.readthedocs.io/en/latest/storage-buckets.html)
 - [make bucket public](https://cloud.google.com/storage/docs/access-control/making-data-public)

"""

import hashlib
import io
import uuid
from typing import List
from urllib.parse import urlparse
from pathlib import Path

import requests
from google.cloud import storage
from google.cloud.storage import Bucket, Blob

from newsutils.logging import LoggingMixin


__all__ = (
    "set_bucket_public_iam", "get_storage_client",
    "upload_blob_from_url", "upload_blob_from_bytesio",
    "get_object_size", "get_object_name",
)


# storage logger instance
logger = LoggingMixin()
logger._logger_name = __file__.rsplit("/", 1)[-1]


_storage_client: storage.Client = None


def get_storage_client(sa_json: str):
    """
    requires env `GOOGLE_APPLICATION_CREDENTIALS`
    """
    global _storage_client
    if not _storage_client:
        _storage_client = storage.Client.from_service_account_json(sa_json) \
            if sa_json else storage.Client()
    return _storage_client


def get_object_size(buffer: io.BytesIO):
    # last `buffer.seek(0)` to restore the file pointer
    size, _ = buffer.seek(0, 2), buffer.seek(0)
    return size


def get_object_name(buffer: io.BytesIO, url: str, nonce: str = None):
    """ Fabricate a predictable object name for upload.
    Name is predictable digest calculated from the file's name+ext, size, and nonce.
    Leave nonce to `None` to generate unique filenames.
    """
    path = Path(urlparse(url).path)
    obj_name = hashlib.md5("".join([
        path.name, str(get_object_size(buffer)), nonce or str(uuid.uuid4())
    ]).encode()).hexdigest()

    # append extension if any
    return f"{obj_name}{path.suffix}".strip(".")


def upload_blob_from_url(url, bucket, name=None, nonce=None, raise_exc=True, **kwargs):
    """
    :param Bucket or str bucket: bucket name or instance
    :param str url: source web url
    :param str name: destination blob name or auto-generated
    :param nonce: Leave nonce to `None` to generate unique filenames (random on every call).
    :param bool raise_exc: logs silently if False
    :rtype Blob
    """
    try:
        r = requests.get(url)
        r.raise_for_status()
        buffer = io.BytesIO(r.content)
        content_type = r.headers.get('Content-Type')
        if not name:
            name = get_object_name(buffer, url, nonce)

        return upload_blob_from_bytesio(buffer, content_type, name, bucket, **kwargs)

    except Exception as e:
        logger.log_info(f"failed uploading to {bucket}: {url}")
        logger.log_debug(str(e))

        if raise_exc:
            raise


def upload_blob_from_bytesio(buffer, content_type, name, bucket, **kwargs) -> Blob:
    """
    :param io.IOBase buffer: io object support read & seek
    :param str content_type: content type eg. 'image/jpeg'
    :param Bucket or str bucket: bucket name or instance
    :param str name: destination blob name or auto-generated
    """

    if not isinstance(bucket, Bucket):
        bucket = get_storage_client().get_bucket(bucket)

    blob = bucket.blob(name)
    blob.upload_from_string(buffer.read(), content_type=content_type, **kwargs)
    return blob


def set_bucket_public_iam(
    bucket_name: str = "your-bucket-name",
    members: List[str] = ["allUsers"],
):
    """Set a public IAM Policy to bucket"""

    bucket = get_storage_client().bucket(bucket_name)
    policy = bucket.get_iam_policy(requested_policy_version=3)
    policy.bindings.append({
        "role": "roles/storage.objectViewer", "members": members})

    bucket.set_iam_policy(policy)
    logger.info(f"Bucket {bucket.name} is now publicly readable")

