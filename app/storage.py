"""Local filesystem and S3-compatible object storage adapter."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterable


def backend_name() -> str:
    value = os.environ.get("SALES_STORAGE_BACKEND", "local").strip().lower()
    if value not in {"local", "s3"}:
        raise RuntimeError("SALES_STORAGE_BACKEND must be 'local' or 's3'")
    return value


def is_s3() -> bool:
    return backend_name() == "s3"


@lru_cache(maxsize=1)
def _client():
    import boto3
    endpoint = os.environ.get("S3_ENDPOINT_URL")
    access_key = os.environ.get("S3_ACCESS_KEY")
    secret_key = os.environ.get("S3_SECRET_KEY")
    if not endpoint or not access_key or not secret_key:
        raise RuntimeError("S3_ENDPOINT_URL, S3_ACCESS_KEY and S3_SECRET_KEY are required for S3 storage")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=os.environ.get("S3_REGION", "us-east-1"),
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        use_ssl=os.environ.get("S3_USE_SSL", "false").lower() == "true",
    )


def _bucket() -> str:
    value = os.environ.get("S3_BUCKET")
    if not value:
        raise RuntimeError("S3_BUCKET is required for S3 storage")
    return value


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    _client().put_object(Bucket=_bucket(), Key=key, Body=data, ContentType=content_type)


def get_bytes(key: str) -> bytes:
    response = _client().get_object(Bucket=_bucket(), Key=key)
    try:
        return response["Body"].read()
    finally:
        response["Body"].close()


def exists(key: str) -> bool:
    try:
        _client().head_object(Bucket=_bucket(), Key=key)
        return True
    except Exception as exc:
        response = getattr(exc, "response", {})
        code = str(response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def delete(key: str) -> None:
    _client().delete_object(Bucket=_bucket(), Key=key)


def list_keys(prefix: str) -> list[str]:
    paginator = _client().get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=_bucket(), Prefix=prefix):
        keys.extend(item["Key"] for item in page.get("Contents", []))
    return keys


def reset_client_for_tests() -> None:
    _client.cache_clear()
