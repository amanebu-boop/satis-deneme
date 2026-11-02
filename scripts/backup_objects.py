"""Create a tar archive of every object in the configured S3-compatible bucket."""
from __future__ import annotations

import os
import sys
import tarfile
from pathlib import Path

from app.storage import _bucket, _client


def main() -> int:
    destination = Path(sys.argv[1])
    client = _client()
    paginator = client.get_paginator("list_objects_v2")
    with tarfile.open(destination, "w:gz") as archive:
        for page in paginator.paginate(Bucket=_bucket()):
            for item in page.get("Contents", []):
                key = item["Key"]
                response = client.get_object(Bucket=_bucket(), Key=key)
                try:
                    data = response["Body"].read()
                finally:
                    response["Body"].close()
                info = tarfile.TarInfo(name=key)
                info.size = len(data)
                info.mtime = int(item.get("LastModified").timestamp()) if item.get("LastModified") else 0
                archive.addfile(info, __import__("io").BytesIO(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
