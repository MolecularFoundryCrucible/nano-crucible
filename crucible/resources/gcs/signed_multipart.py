"""Upload a file through the API's signed multipart flow.

The API reserves an upload, signs one URL per 64 MiB part, and assembles the
object on completion. Parts go straight to storage with plain HTTP PUTs, so
no storage credentials or SDK are involved. Signed URLs are bearer
capabilities: they are never logged or included in error messages.

See docs/multipart_upload_api.md in crucible-api for the contract.
"""

import base64
import hashlib
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

PART_SIZE = 64 * 1024 * 1024
SIGN_BATCH = 32
PART_WORKERS = 8
_API_ATTEMPTS = 6
_PART_ATTEMPTS = 3
_MAX_RETRY_AFTER = 60
_COMPLETE_TIMEOUT = 120
_PART_TIMEOUT = 300
_EXPIRY_MARGIN = 30

Progress = Callable[[str, int, int], None]


class SignedMultipartUnavailable(Exception):
    """The server does not offer signed multipart uploads for this file."""


def scan_file(file_path: str, part_size: int = PART_SIZE) -> Tuple[str, str, List[str]]:
    """Return (sha256 hex, whole-file CRC32C, per-part CRC32Cs) in one read pass.

    CRC32C values are canonical base64. Raises RuntimeError if the file
    changes while it is read.
    """
    import google_crc32c

    def encode(checksum):
        return base64.b64encode(checksum.digest()).decode()

    before = os.stat(file_path)
    sha = hashlib.sha256()
    whole = google_crc32c.Checksum()
    parts = []
    with open(file_path, 'rb') as stream:
        while data := stream.read(part_size):
            sha.update(data)
            whole.update(data)
            parts.append(encode(google_crc32c.Checksum(data)))
    after = os.stat(file_path)
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"{file_path} changed while it was being checksummed.")
    return sha.hexdigest(), encode(whole), parts


class _PartReader:
    """A file slice with a known length, so requests streams it with Content-Length."""

    def __init__(self, file_path: str, offset: int, size: int, on_read: Callable[[int], None]):
        self._stream = open(file_path, 'rb')
        self._stream.seek(offset)
        self._size = size
        self._remaining = size
        self._on_read = on_read

    def __len__(self):
        return self._size

    def read(self, amount: int = -1) -> bytes:
        if self._remaining <= 0:
            return b''
        if amount is None or amount < 0 or amount > self._remaining:
            amount = self._remaining
        data = self._stream.read(amount)
        self._remaining -= len(data)
        self._on_read(len(data))
        return data

    def close(self):
        self._stream.close()


def _retry_after(response) -> float:
    try:
        seconds = float(response.headers.get('Retry-After', 5))
    except (TypeError, ValueError, AttributeError):
        seconds = 5
    return min(max(seconds, 1), _MAX_RETRY_AFTER)


def _detail(error) -> str:
    try:
        return str(error.response.json().get('detail') or '')
    except (ValueError, AttributeError):
        return ''


def _disabled(error) -> bool:
    response = getattr(error, 'response', None)
    return (response is not None and response.status_code == 503
            and 'multipart uploads are disabled' in _detail(error).lower())


def _api(client, method: str, path: str, **kwargs):
    """Call the API without the session's retry adapter, honoring Retry-After.

    The adapter would wait out every Retry-After itself, including the one
    on a disabled-route 503 that should trigger the fallback instead.
    """
    for attempt in range(_API_ATTEMPTS):
        last = attempt == _API_ATTEMPTS - 1
        try:
            return client._request(method, path, retry=False, log_body=False, **kwargs)
        except requests.HTTPError as error:
            status = getattr(error.response, 'status_code', None)
            if status in (429, 502, 503, 504) and not last and not _disabled(error):
                time.sleep(_retry_after(error.response))
                continue
            raise
        except (requests.ConnectionError, requests.Timeout):
            if last:
                raise
            time.sleep(min(2 ** attempt, 30))


def _expired(part: Dict) -> bool:
    expires_at = part.get('expires_at')
    if not expires_at:
        return False
    try:
        moment = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
    except ValueError:
        return False
    return (moment - datetime.now(timezone.utc)).total_seconds() < _EXPIRY_MARGIN


class _Upload:
    """One signed multipart session for one file."""

    def __init__(self, client, dsid: str, file_path: str, filename: str,
                 workers: int, progress: Optional[Progress]):
        self.client = client
        self.base = f'/datasets/{dsid}/upload/multipart'
        self.file_path = file_path
        self.filename = filename
        self.workers = workers
        self.progress = progress
        self.size = os.path.getsize(file_path)
        self.upload_id = None
        self.part_checksums: List[str] = []
        self._sent = {}
        self._lock = threading.Lock()
        self._sign_lock = threading.Lock()
        self.part_size = PART_SIZE

    def run(self) -> Tuple[Dict, bool]:
        sha256_hash, crc32c, self.part_checksums = scan_file(self.file_path, PART_SIZE)
        status = self._initiate(sha256_hash)
        if status.get('existing_file') is not None:
            logger.info(f"{self.filename} already exists in the dataset, skipping upload")
            return status['existing_file'], True
        self.upload_id = status['upload_id']
        try:
            self.part_size = status.get('part_size') or PART_SIZE
            if self.part_size != PART_SIZE:
                _, _, self.part_checksums = scan_file(self.file_path, self.part_size)
            self._upload_missing_parts()
            record = _api(self.client, 'post', f'{self.base}/complete',
                          json={'upload_id': self.upload_id, 'sha256_hash': sha256_hash,
                                'crc32c': crc32c},
                          timeout=(self.client._config.connect_timeout, _COMPLETE_TIMEOUT))
        except BaseException:
            self._abort()
            raise
        return record, False

    def _initiate(self, sha256_hash: str) -> Dict:
        body = {'filename': self.filename, 'size': self.size, 'sha256_hash': sha256_hash}
        try:
            return _api(self.client, 'post', f'{self.base}/initiate', json=body,
                        headers={'Idempotency-Key': uuid.uuid4().hex})
        except requests.HTTPError as error:
            status = getattr(error.response, 'status_code', None)
            if (status in (404, 405) and _detail(error) in ('', 'Not Found', 'Method Not Allowed')
                    or _disabled(error)):
                raise SignedMultipartUnavailable(
                    "This server does not offer signed multipart uploads.") from error
            raise

    def _acknowledged_parts(self) -> set:
        acknowledged, marker = set(), None
        while True:
            params = {'part_number_marker': marker} if marker else None
            page = _api(self.client, 'get', f'{self.base}/{self.upload_id}', params=params)
            acknowledged.update(part['part_number'] for part in page.get('parts') or [])
            marker = page.get('next_part_number_marker')
            if not marker:
                return acknowledged

    def _upload_missing_parts(self):
        count = len(self.part_checksums)
        acknowledged = self._acknowledged_parts()
        for number in acknowledged:
            self._sent[number] = self._part_length(number)
        self._report()
        remaining = [n for n in range(1, count + 1) if n not in acknowledged]
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for start in range(0, len(remaining), SIGN_BATCH):
                signed = self._sign(remaining[start:start + SIGN_BATCH])
                list(pool.map(self._put_part, signed))

    def _part_length(self, number: int) -> int:
        return min(self.part_size, self.size - (number - 1) * self.part_size)

    def _sign(self, numbers: List[int]) -> List[Dict]:
        with self._sign_lock:
            body = {'parts': [{'part_number': n, 'crc32c': self.part_checksums[n - 1]}
                              for n in numbers]}
            return _api(self.client, 'post', f'{self.base}/{self.upload_id}/parts',
                        json=body)['parts']

    def _put_part(self, part: Dict):
        number = part['part_number']
        for attempt in range(_PART_ATTEMPTS):
            if _expired(part):
                part = self._sign([number])[0]
            headers = {name: value for name, value in (part.get('headers') or {}).items()
                       if name.lower() != 'content-length'}
            self._sent[number] = 0
            reader = _PartReader(self.file_path, part['offset'], part['size'],
                                 lambda n, number=number: self._advance(number, n))
            try:
                response = requests.put(part['url'], data=reader, headers=headers,
                                        timeout=(10, _PART_TIMEOUT), allow_redirects=False)
            except (requests.ConnectionError, requests.Timeout):
                status = None
            else:
                status = response.status_code
            finally:
                reader.close()
            if status == 200:
                return
            if status is not None and status < 500 and status != 403:
                raise RuntimeError(
                    f"Storage rejected part {number} of {self.filename} (HTTP {status}); "
                    "the file may have changed during the upload.")
            if status == 403:
                part = self._sign([number])[0]
            time.sleep(min(2 ** attempt, 10))
        raise RuntimeError(f"Part {number} of {self.filename} failed after {_PART_ATTEMPTS} attempts.")

    def _advance(self, number: int, amount: int):
        with self._lock:
            self._sent[number] = self._sent.get(number, 0) + amount
        self._report()

    def _report(self):
        if self.progress is not None:
            self.progress(self.filename, min(sum(self._sent.values()), self.size), self.size)

    def _abort(self):
        try:
            _api(self.client, 'delete', f'{self.base}/{self.upload_id}')
        except Exception as error:
            logger.debug(f"Could not abort upload of {self.filename}: {type(error).__name__}")


def upload_file_signed_multipart(client, dsid: str, file_path: str,
                                 max_workers: Optional[int] = None,
                                 progress: Optional[Progress] = None) -> Tuple[Dict, bool]:
    """Upload a file through the signed multipart flow.

    Args:
        client:      CrucibleClient instance.
        dsid:        Dataset MFID.
        file_path:   Local path to the file.
        max_workers: Parts uploaded in parallel (default 8).
        progress:    Called as progress(filename, bytes_done, total) as parts upload.

    Returns:
        Tuple[Dict, bool]: (AssociatedFileRead, was_existing).

    Raises:
        SignedMultipartUnavailable: The server lacks the flow, has it disabled,
            or the file is empty.
    """
    if os.path.getsize(file_path) == 0:
        raise SignedMultipartUnavailable("Empty files cannot use signed multipart uploads.")
    upload = _Upload(client, dsid, file_path, os.path.basename(file_path),
                     max_workers or PART_WORKERS, progress)
    return upload.run()
