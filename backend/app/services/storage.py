"""Private document object storage backends (local private filesystem and S3-compatible)."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


@dataclass(frozen=True)
class StorageStatus:
    provider: str
    configured: bool
    mode: str
    detail: str


class StorageBackend(Protocol):
    provider_name: str

    def put_object(self, key: str, data: bytes, content_type: str) -> None: ...

    def get_object(self, key: str) -> bytes: ...

    def delete_object(self, key: str) -> None: ...

    def status(self) -> StorageStatus: ...


def _validate_key(key: str) -> Path:
    if not key or key.startswith("/") or "\\" in key:
        raise ValueError("Invalid storage key")
    rel = Path(key)
    if any(part in ("", ".", "..") for part in rel.parts):
        raise ValueError("Invalid storage key traversal")
    return rel


class LocalPrivateStorage:
    """Private filesystem store outside static web roots; never exposed directly via HTTP."""

    provider_name = "LOCAL"

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir.resolve()

    def _path(self, key: str) -> Path:
        rel = _validate_key(key)
        target = (self.base_dir / rel).resolve()
        if not target.is_relative_to(self.base_dir):
            raise ValueError("Storage path escapes root directory")
        return target

    def put_object(self, key: str, data: bytes, content_type: str) -> None:  # noqa: ARG002
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)

    def get_object(self, key: str) -> bytes:
        target = self._path(key)
        if not target.is_file():
            raise FileNotFoundError(key)
        return target.read_bytes()

    def delete_object(self, key: str) -> None:
        target = self._path(key)
        if target.is_file():
            target.unlink()

    def status(self) -> StorageStatus:
        return StorageStatus(
            provider="local",
            configured=True,
            mode="LOCAL_DEVELOPMENT",
            detail=f"Private local storage directory ({self.base_dir}). Served only via authenticated API endpoints.",
        )


class S3StorageBackend:
    """S3-compatible private object storage (AWS S3 or MinIO)."""

    provider_name = "S3"

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
    ) -> None:
        import boto3

        self.bucket = bucket
        self.endpoint_url = endpoint_url
        kwargs: dict = {"region_name": region}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        if access_key_id and secret_access_key:
            kwargs["aws_access_key_id"] = access_key_id
            kwargs["aws_secret_access_key"] = secret_access_key
        self.client = boto3.client("s3", **kwargs)

    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        _validate_key(key)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get_object(self, key: str) -> bytes:
        _validate_key(key)
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def delete_object(self, key: str) -> None:
        _validate_key(key)
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def status(self) -> StorageStatus:
        mode = "LOCAL_DEVELOPMENT" if self.endpoint_url and "minio" in self.endpoint_url else "LIVE"
        return StorageStatus(
            provider="s3",
            configured=True,
            mode=mode,
            detail=f"S3 bucket '{self.bucket}'" + (f" via {self.endpoint_url}" if self.endpoint_url else ""),
        )


_storage_override: StorageBackend | None = None


def set_storage_override(backend: StorageBackend | None) -> None:
    global _storage_override
    _storage_override = backend


def get_storage() -> StorageBackend:
    if _storage_override is not None:
        return _storage_override
    s = get_settings()
    if s.storage_provider == "s3":
        if not s.s3_bucket:
            raise RuntimeError("S3 storage selected but S3_BUCKET is not configured.")
        return S3StorageBackend(
            bucket=s.s3_bucket,
            region=s.s3_region,
            endpoint_url=s.s3_endpoint_url,
            access_key_id=s.s3_access_key_id,
            secret_access_key=s.s3_secret_access_key,
        )
    return LocalPrivateStorage(Path(s.storage_local_dir))
