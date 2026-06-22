"""Sincronización del CSV en Tigris (Fly storage).

Comandos:

    # Verifica si el objeto remoto existe (devuelve 0 si existe, 1 si no)
    python scripts/upload_csv_to_tigris.py check <bucket> <key>

    # Sube si falta o si el tamaño difiere del archivo local
    python scripts/upload_csv_to_tigris.py sync <bucket> <key> <local_file>

Reemplaza ``fly storage objects put`` (removido en flyctl 0.4.59).
Requiere las variables de entorno AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY y
AWS_ENDPOINT_URL_S3 (las inyecta ``fly storage create`` en el etl).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def _client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("AWS_ENDPOINT_URL_S3", "https://fly.storage.tigris.dev"),
        region_name=os.getenv("AWS_REGION", "auto"),
    )


def check(bucket: str, key: str) -> int:
    """Sale 0 si el objeto existe, 1 si no."""
    try:
        head = _client().head_object(Bucket=bucket, Key=key)
        size_mb = head["ContentLength"] / 1024 / 1024
        print(f"EXISTS bucket={bucket} key={key} size={size_mb:.1f}MB")
        return 0
    except ClientError as exc:
        if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
            print(f"MISSING bucket={bucket} key={key}")
            return 1
        raise


def sync(bucket: str, key: str, local: Path) -> int:
    """Sube ``local`` si el remoto no existe o tiene tamaño distinto."""
    if not local.is_file():
        print(f"SKIP local missing: {local}", file=sys.stderr)
        return 2
    local_size = local.stat().st_size

    needs_upload = True
    try:
        head = _client().head_object(Bucket=bucket, Key=key)
        if head["ContentLength"] == local_size:
            print(f"OK in-sync ({local_size / 1024 / 1024:.1f}MB)")
            needs_upload = False
        else:
            remote_mb = head["ContentLength"] / 1024 / 1024
            local_mb = local_size / 1024 / 1024
            print(f"DRIFT remote={remote_mb:.1f}MB local={local_mb:.1f}MB → re-upload")
    except ClientError as exc:
        if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
            print(f"MISSING → uploading {local_size / 1024 / 1024:.1f}MB")
        else:
            raise

    if needs_upload:
        _client().upload_file(str(local), bucket, key)
        head = _client().head_object(Bucket=bucket, Key=key)
        print(f"UPLOADED {head['ContentLength'] / 1024 / 1024:.1f}MB")
    return 0


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "check":
        return check(sys.argv[2], sys.argv[3])
    if cmd == "sync":
        if len(sys.argv) != 5:
            print(__doc__, file=sys.stderr)
            return 2
        return sync(sys.argv[2], sys.argv[3], Path(sys.argv[4]))
    print(f"Unknown command: {cmd}", file=sys.stderr)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
