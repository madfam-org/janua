"""
File storage service for avatars and other uploads
"""

import os
import uuid
import hashlib
import mimetypes
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from app.config import settings

# Test-compatible imports with fallbacks
try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    # Mock for testing environment
    class ClientError(Exception):
        def __init__(self, error_response, operation_name):
            self.response = error_response

    boto3 = None

try:
    import aiofiles
except ImportError:
    # Mock for testing environment
    aiofiles = None

try:
    import magic
except ImportError:
    # Mock for testing environment
    class MockMagic:
        @staticmethod
        def from_buffer(data, mime=True):
            return "application/octet-stream"

    magic = MockMagic()

logger = logging.getLogger(__name__)


def _is_r2_endpoint(endpoint_host: str) -> bool:
    """
    Securely validate if the endpoint host is a Cloudflare R2 endpoint.

    Uses proper URL parsing to prevent subdomain bypass attacks.
    For example, "evil-r2.cloudflarestorage.com.attacker.com" would fail validation.

    Args:
        endpoint_host: The hostname to validate

    Returns:
        True if the host is a valid Cloudflare R2 endpoint
    """
    # Parse the host to handle potential edge cases
    # If the host doesn't have a scheme, urlparse might not parse correctly
    # so we ensure it's just a hostname comparison
    host = endpoint_host.lower().strip()

    # Valid R2 endpoints end with .r2.cloudflarestorage.com
    # The format is: {account_id}.r2.cloudflarestorage.com
    return host.endswith(".r2.cloudflarestorage.com")


class StorageService:
    """
    File storage service with support for local and S3 storage
    """

    def __init__(self):
        self.storage_type = self._determine_storage_type()
        self.s3_client = None

        if self.storage_type == "s3" and boto3 is not None:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY,
                aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_KEY,
                endpoint_url=f"https://{settings.CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com",
            )
            self.bucket_name = settings.CLOUDFLARE_R2_BUCKET
        else:
            # Local storage (or fallback when S3 dependencies unavailable)
            self.upload_dir = getattr(settings, "UPLOAD_DIR", "/tmp/uploads")
            os.makedirs(self.upload_dir, exist_ok=True)

    def _determine_storage_type(self) -> str:
        """Determine which storage backend to use"""
        if (
            boto3 is not None
            and hasattr(settings, "CLOUDFLARE_R2_ACCESS_KEY")
            and hasattr(settings, "CLOUDFLARE_R2_SECRET_KEY")
            and settings.CLOUDFLARE_R2_ACCESS_KEY
            and settings.CLOUDFLARE_R2_SECRET_KEY
        ):
            return "s3"
        return "local"

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: Optional[str] = None,
        directory: str = "uploads",
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to storage

        Returns:
            dict: File information including URL and metadata
        """
        try:
            # Generate unique filename
            file_extension = os.path.splitext(filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"

            if user_id:
                file_path = f"{directory}/{user_id}/{unique_filename}"
            else:
                file_path = f"{directory}/{unique_filename}"

            # Validate file type
            if not self._validate_file_type(file_content, content_type):
                raise ValueError("Invalid file type")

            # Calculate file hash
            file_hash = hashlib.sha256(file_content).hexdigest()

            # Get or guess content type
            if not content_type:
                content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

            if self.storage_type == "s3":
                url = await self._upload_to_s3(file_content, file_path, content_type, metadata)
            else:
                url = await self._upload_to_local(file_content, file_path, content_type)

            return {
                "url": url,
                "filename": unique_filename,
                "original_filename": filename,
                "path": file_path,
                "size": len(file_content),
                "content_type": content_type,
                "hash": file_hash,
                "storage_type": self.storage_type,
                "uploaded_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"File upload error: {e}")
            raise

    async def _upload_to_s3(
        self,
        file_content: bytes,
        file_path: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Upload file to S3/R2"""
        try:
            # Prepare metadata
            s3_metadata = metadata or {}
            s3_metadata["upload_time"] = datetime.utcnow().isoformat()

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=file_content,
                ContentType=content_type,
                Metadata=s3_metadata,
            )

            # Generate URL using secure endpoint validation
            # Use proper URL parsing to prevent subdomain bypass attacks
            endpoint_host = self.s3_client._endpoint.host
            if _is_r2_endpoint(endpoint_host):
                url = f"https://{self.bucket_name}.{settings.CLOUDFLARE_ACCOUNT_ID}.r2.dev/{file_path}"
            else:
                # Regular S3 URL
                url = f"https://{self.bucket_name}.s3.amazonaws.com/{file_path}"

            return url

        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise

    async def _upload_to_local(self, file_content: bytes, file_path: str, content_type: str) -> str:
        """Upload file to local storage"""
        try:
            # Create full path
            full_path = os.path.join(self.upload_dir, file_path)

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Write file
            async with aiofiles.open(full_path, "wb") as f:
                await f.write(file_content)

            # Return URL path
            return f"/uploads/{file_path}"

        except Exception as e:
            logger.error(f"Local upload error: {e}")
            raise

    async def delete_file(self, file_path: str) -> bool:
        """Delete a file from storage"""
        try:
            if self.storage_type == "s3":
                return await self._delete_from_s3(file_path)
            else:
                return await self._delete_from_local(file_path)
        except Exception as e:
            logger.error(f"File deletion error: {e}")
            return False

    async def _delete_from_s3(self, file_path: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except ClientError as e:
            logger.error(f"S3 deletion error: {e}")
            return False

    async def _delete_from_local(self, file_path: str) -> bool:
        """Delete file from local storage"""
        try:
            full_path = os.path.join(self.upload_dir, file_path)
            if os.path.exists(full_path):
                os.remove(full_path)
            return True
        except Exception as e:
            logger.error(f"Local deletion error: {e}")
            return False

    async def get_file(self, file_path: str) -> Optional[bytes]:
        """Get file content from storage"""
        try:
            if self.storage_type == "s3":
                return await self._get_from_s3(file_path)
            else:
                return await self._get_from_local(file_path)
        except Exception as e:
            logger.error(f"File retrieval error: {e}")
            return None

    async def _get_from_s3(self, file_path: str) -> Optional[bytes]:
        """Get file from S3"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"S3 retrieval error: {e}")
            return None

    async def _get_from_local(self, file_path: str) -> Optional[bytes]:
        """Get file from local storage"""
        try:
            full_path = os.path.join(self.upload_dir, file_path)
            if not os.path.exists(full_path):
                return None

            async with aiofiles.open(full_path, "rb") as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Local retrieval error: {e}")
            return None

    async def generate_presigned_url(self, file_path: str, expires_in: int = 3600) -> Optional[str]:
        """Generate presigned URL for direct upload/download"""
        if self.storage_type != "s3":
            return None

        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": file_path},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Presigned URL generation error: {e}")
            return None

    def _validate_file_type(self, file_content: bytes, claimed_type: Optional[str] = None) -> bool:
        """Validate file type for security"""
        # Allowed MIME types for avatars
        allowed_types = {
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/gif",
            "image/webp",
            "image/svg+xml",
        }

        # Use python-magic to detect actual file type
        try:
            mime = magic.Magic(mime=True)
            detected_type = mime.from_buffer(file_content)

            # Check if detected type is allowed
            if detected_type not in allowed_types:
                logger.warning(f"Invalid file type detected: {detected_type}")
                return False

            # If claimed type is provided, verify it matches
            if claimed_type and claimed_type != detected_type:
                logger.warning(
                    f"File type mismatch: claimed {claimed_type}, detected {detected_type}"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"File type validation error: {e}")
            # Be safe and reject if we can't validate
            return False

    def _validate_file_size(self, file_content: bytes, max_size_mb: int = 5) -> bool:
        """Validate file size"""
        max_size_bytes = max_size_mb * 1024 * 1024
        return len(file_content) <= max_size_bytes

    async def optimize_image(
        self, file_content: bytes, max_width: int = 512, max_height: int = 512, quality: int = 85
    ) -> bytes:
        """Optimize image for storage (resize, compress)"""
        try:
            from PIL import Image
            import io

            # Open image
            img = Image.open(io.BytesIO(file_content))

            # Convert RGBA to RGB if necessary
            if img.mode in ("RGBA", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background

            # Resize if larger than max dimensions
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            # Save optimized image
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            output.seek(0)

            return output.getvalue()

        except Exception as e:
            logger.error(f"Image optimization error: {e}")
            # Return original if optimization fails
            return file_content


# Create singleton instance
storage_service = StorageService()


class AvatarService:
    """Service specifically for handling user avatars"""

    @staticmethod
    async def upload_avatar(
        user_id: str, file_content: bytes, filename: str, content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload user avatar with optimization"""
        try:
            # Validate file size (max 5MB for avatars)
            if not storage_service._validate_file_size(file_content, max_size_mb=5):
                raise ValueError("File size exceeds 5MB limit")

            # Validate file type
            if not storage_service._validate_file_type(file_content, content_type):
                raise ValueError("Invalid image file type")

            # Optimize image
            optimized_content = await storage_service.optimize_image(
                file_content, max_width=512, max_height=512, quality=85
            )

            # Upload to storage
            result = await storage_service.upload_file(
                file_content=optimized_content,
                filename=filename,
                content_type=content_type or "image/jpeg",
                directory="avatars",
                user_id=user_id,
                metadata={"type": "avatar", "user_id": user_id},
            )

            return result

        except Exception as e:
            logger.error(f"Avatar upload error: {e}")
            raise

    @staticmethod
    async def delete_avatar(user_id: str, avatar_path: str) -> bool:
        """Delete user avatar"""
        try:
            return await storage_service.delete_file(avatar_path)
        except Exception as e:
            logger.error(f"Avatar deletion error: {e}")
            return False
