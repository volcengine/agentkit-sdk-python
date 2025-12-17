# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific governing permissions and
# limitations under the License.

import os
import logging
from dataclasses import dataclass, field
from agentkit.utils.misc import generate_random_id
from agentkit.toolkit.config.dataclass_utils import AutoSerializableMixin
from agentkit.toolkit.config.constants import DEFAULT_TOS_BUCKET_TEMPLATE_NAME

try:
    import tos

    TOS_AVAILABLE = True
except ImportError:
    TOS_AVAILABLE = False
    tos = None

logger = logging.getLogger(__name__)


@dataclass
class TOSServiceConfig(AutoSerializableMixin):
    """Configuration for TOS (Tos Object Storage) service."""

    region: str = field(default="", metadata={"description": "Cloud region"})
    endpoint: str = field(
        default="",
        metadata={
            "description": "Custom endpoint URL; if empty, resolved from PlatformConfig"
        },
    )
    bucket: str = field(default="", metadata={"description": "Bucket name"})
    prefix: str = field(default="", metadata={"description": "Object key prefix"})


class TOSService:
    """Wrapper for Volcano Engine TOS (Object Storage) service."""

    def __init__(self, config: TOSServiceConfig):
        """Initialize TOS service with configuration.

        Args:
            config: TOS service configuration

        Raises:
            ImportError: If TOS SDK is not installed
        """
        if not TOS_AVAILABLE:
            raise ImportError("TOS SDK not installed. Install with: pip install tos")

        self.config = config
        self.client = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the TOS client."""
        try:
            from agentkit.platform import VolcConfiguration

            # Use configured region if available
            region = self.config.region.strip() if self.config.region else None
            config = VolcConfiguration(region=region)
            creds = config.get_service_credentials("tos")
            ep = config.get_service_endpoint("tos")

            self.client = tos.TosClientV2(
                creds.access_key,
                creds.secret_key,
                ep.host,
                ep.region,
            )
            # Expose the actual region resolved by VolcConfiguration
            self.actual_region = ep.region

            logger.info(
                f"TOS client initialized: bucket={self.config.bucket}, region={ep.region}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize TOS client: {str(e)}")
            raise

    def upload_file(self, local_path: str, object_key: str) -> str:
        """Upload a file to TOS.

        Args:
            local_path: Local file path
            object_key: Object key in TOS

        Returns:
            Accessible URL of the uploaded file

        Raises:
            FileNotFoundError: If local file does not exist
            tos.exceptions.TosClientError: If TOS client error occurs
            tos.exceptions.TosServerError: If TOS server error occurs
        """
        try:
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Local file not found: {local_path}")

            logger.info(f"Uploading file: {local_path} -> {object_key}")

            self.client.put_object_from_file(
                bucket=self.config.bucket, key=object_key, file_path=local_path
            )

            url = f"https://{self.config.bucket}.{self.config.endpoint}/{object_key}"
            logger.info(f"File uploaded successfully: {url}")
            return url

        except tos.exceptions.TosClientError as e:
            logger.error(f"TOS client error: {e.message}")
            raise
        except tos.exceptions.TosServerError as e:
            logger.error(f"TOS server error: {e.code} - {e.message}")
            raise
        except Exception as e:
            logger.error(f"Upload failed: {str(e)}")
            raise

    def download_file(self, object_key: str, local_path: str) -> bool:
        """Download a file from TOS.

        Args:
            object_key: Object key in TOS
            local_path: Local path to save the file

        Returns:
            True if download succeeded, False otherwise

        Note:
            TODO: Implement file download functionality
        """
        try:
            logger.info(f"Downloading file: {object_key} -> {local_path}")

            # TODO: Implement download steps:
            # 1. Check if object exists
            # 2. Download file from TOS
            # 3. Save to local path

            return True

        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            return False

    def delete_file(self, object_key: str) -> bool:
        """Delete a file from TOS.

        Args:
            object_key: Object key in TOS

        Returns:
            True if deletion succeeded or file doesn't exist, False on error
        """
        try:
            logger.info(f"Deleting file: {object_key}")

            self.client.delete_object(bucket=self.config.bucket, key=object_key)
            logger.info(f"File deleted: {object_key}")
            return True

        except tos.exceptions.TosServerError as e:
            if e.status_code == 404:
                # Treat non-existent file as successful deletion
                logger.warning(f"File not found (already deleted): {object_key}")
                return True
            logger.error(f"Delete failed: {e.code} - {e.message}")
            return False
        except Exception as e:
            logger.error(f"Delete failed: {str(e)}")
            return False

    def file_exists(self, object_key: str) -> bool:
        """Check if a file exists in TOS.

        Args:
            object_key: Object key in TOS

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(bucket=self.config.bucket, key=object_key)
            return True

        except tos.exceptions.TosServerError as e:
            if e.status_code == 404:
                return False
            logger.error(f"Failed to check file existence: {e.code} - {e.message}")
            return False
        except Exception as e:
            logger.error(f"Failed to check file existence: {str(e)}")
            return False

    def list_files(self, prefix: str = "") -> list:
        """List files in TOS with optional prefix filter.

        Args:
            prefix: Object key prefix to filter results

        Returns:
            List of file objects, or empty list on error

        Note:
            TODO: Implement file listing functionality
        """
        try:
            # TODO: Implement list_objects with prefix filtering
            return []

        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            return []

    def bucket_exists(self) -> bool:
        """Check if the configured bucket exists.

        Returns:
            True if bucket exists, False otherwise
        """
        try:
            self.client.head_bucket(bucket=self.config.bucket)
            logger.info(f"Bucket exists: {self.config.bucket}")
            return True

        except tos.exceptions.TosServerError as e:
            if e.status_code == 404:
                logger.warning(f"Bucket not found: {self.config.bucket}")
                return False
            logger.error(f"Failed to check bucket existence: {e.code} - {e.message}")
            return False
        except Exception as e:
            logger.error(f"Failed to check bucket existence: {str(e)}")
            return False

    def create_bucket(self) -> bool:
        """Create the configured bucket.

        Returns:
            True if bucket was created or already exists

        Raises:
            tos.exceptions.TosServerError: If creation fails (except for 409 conflict)
            Exception: For other unexpected errors
        """
        try:
            logger.info(f"Creating bucket: {self.config.bucket}")

            self.client.create_bucket(bucket=self.config.bucket)
            logger.info(f"Bucket created: {self.config.bucket}")
            return True

        except tos.exceptions.TosServerError as e:
            if e.status_code == 409:
                # Bucket already exists - treat as success
                logger.warning(f"Bucket already exists: {self.config.bucket}")
                return True
            logger.error(f"Failed to create bucket: {e.code} - {e.message}")
            raise e
        except Exception as e:
            logger.error(f"Failed to create bucket: {str(e)}")
            raise e

    @staticmethod
    def generate_bucket_name(prefix: str = "agentkit") -> str:
        """Generate a unique bucket name from template.

        Args:
            prefix: Bucket name prefix (used as fallback if template rendering fails)

        Returns:
            Generated bucket name conforming to TOS naming requirements

        Raises:
            ValueError: If template contains unresolved variables after rendering
        """
        import re
        from agentkit.utils.template_utils import render_template

        bucket_name = DEFAULT_TOS_BUCKET_TEMPLATE_NAME
        bucket_name = render_template(bucket_name)

        # Verify template was fully rendered (no unresolved variables remain)
        if "{{" in bucket_name and "}}" in bucket_name:
            raise ValueError(
                f"Bucket name template not fully rendered, contains unresolved variables: {bucket_name}"
            )

        # Ensure only valid characters (TOS allows lowercase letters, numbers, hyphens)
        bucket_name = re.sub(r"[^a-z0-9-]", "-", bucket_name)

        # Enforce TOS naming constraints: 3-63 characters
        if len(bucket_name) > 63:
            bucket_name = bucket_name[:63]
        elif len(bucket_name) < 3:
            bucket_name = f"{prefix}-bucket-{generate_random_id(4)}".lower()

        return bucket_name
