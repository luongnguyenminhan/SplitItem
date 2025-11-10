import io
import logging
from typing import Optional

from minio import Minio
from minio.error import S3Error
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

minio_client = None


def get_minio_client() -> Minio:
    global minio_client
    if minio_client is None:
        try:
            minio_client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )

            # Cấu hình bucket policy cho public access ngay khi khởi tạo
            ensure_bucket_public_access(minio_client, settings.MINIO_BUCKET_NAME)
            ensure_bucket_public_access(minio_client, settings.MINIO_PUBLIC_BUCKET_NAME)

        except Exception as e:
            logger.exception(f"MinIO client initialization error: {e}")
            raise
    return minio_client


def ensure_bucket_public_access(client: Minio, bucket_name: str) -> None:
    """Đảm bảo bucket có public read access"""
    try:
        # Tạo bucket nếu chưa tồn tại
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)

        # Cấu hình bucket policy cho public read
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["s3:GetObject", "s3:GetBucketLocation"],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}/*",
                        f"arn:aws:s3:::{bucket_name}",
                    ],
                }
            ],
        }

        import json

        client.set_bucket_policy(bucket_name, json.dumps(policy))

    except Exception as e:
        logger.exception(f"Bucket policy configuration error for {bucket_name}: {e}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type(S3Error),
)
def upload_bytes_to_minio(
    file_bytes: bytes,
    bucket_name: str,
    object_name: str,
    content_type: Optional[str] = None,
) -> bool:
    """Upload file bytes directly to MinIO

    Args:
        file_bytes: File content as bytes
        bucket_name: MinIO bucket name
        object_name: Object name in MinIO
        content_type: Content type (optional)

    Returns:
        bool: Success status
    """
    try:
        client = get_minio_client()

        # Ensure bucket exists
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)

        # Upload bytes directly
        file_size = len(file_bytes)
        file_data = io.BytesIO(file_bytes)
        client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=file_data,
            length=file_size,
            content_type=content_type,
        )

        return True
    except S3Error as e:
        logger.exception(f"MinIO upload error: {e}")
        return False
    except Exception as e:
        logger.exception(f"MinIO upload error: {e}")
        return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type(S3Error),
)
def download_file_from_minio(bucket_name: str, object_name: str) -> Optional[bytes]:
    try:
        client = get_minio_client()
        response = client.get_object(bucket_name, object_name)
        return response.read()
    except S3Error as e:
        logger.exception(f"MinIO download error: {e}")
        return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type(S3Error),
)
def delete_file_from_minio(bucket_name: str, object_name: str) -> bool:
    try:
        client = get_minio_client()
        client.remove_object(bucket_name, object_name)
        return True
    except S3Error as e:
        logger.exception(f"MinIO delete error: {e}")
        return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type(S3Error),
)
def generate_presigned_url(bucket_name: str, object_name: str) -> Optional[str]:
    try:
        # Đảm bảo MinIO client đã được khởi tạo và bucket policy đã được cấu hình
        get_minio_client()

        # Tạo URL public trực tiếp (bucket đã có public policy)
        if hasattr(settings, "MINIO_PUBLIC_URL") and settings.MINIO_PUBLIC_URL:
            public_url = f"{settings.MINIO_PUBLIC_URL.rstrip('/').replace('minio', 'storage')}/{bucket_name}/{object_name}"
        else:
            public_url = f"http://{settings.MINIO_PUBLIC_URL.replace('minio', 'storage')}/{bucket_name}/{object_name}"

        return public_url

    except S3Error as e:
        logger.exception(f"MinIO URL generation error: {e}")
        return None
    except Exception as e:
        logger.exception(f"MinIO URL generation error: {e}")
        return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type(S3Error),
)
def file_exists_in_minio(bucket_name: str, object_name: str) -> bool:
    try:
        client = get_minio_client()
        client.stat_object(bucket_name, object_name)
        return True
    except S3Error:
        return False


def health_check() -> bool:
    try:
        client = get_minio_client()
        client.list_buckets()
        return True
    except Exception as e:
        logger.exception(f"MinIO health check error: {e}")
        return False
