#!/usr/bin/env python3
"""
Storage Backend Abstraction Layer

Provides unified interface for different storage backends (local, S3)
to enable transparent switching between storage systems.
"""

import os
import json
import shutil
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Any, BinaryIO
from pathlib import Path

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def read_file(self, file_path: str) -> bytes:
        """Read file contents as bytes."""
        pass
    
    @abstractmethod
    def write_file(self, file_path: str, data: bytes) -> None:
        """Write bytes to file."""
        pass
    
    @abstractmethod
    def read_text(self, file_path: str, encoding: str = 'utf-8') -> str:
        """Read file contents as text."""
        pass
    
    @abstractmethod
    def write_text(self, file_path: str, text: str, encoding: str = 'utf-8') -> None:
        """Write text to file."""
        pass
    
    @abstractmethod
    def read_json(self, file_path: str) -> Any:
        """Read JSON file."""
        pass
    
    @abstractmethod
    def write_json(self, file_path: str, data: Any, indent: int = 2, ensure_ascii: bool = False) -> None:
        """Write data to JSON file."""
        pass
    
    @abstractmethod
    def exists(self, file_path: str) -> bool:
        """Check if file exists."""
        pass
    
    @abstractmethod
    def remove(self, file_path: str) -> None:
        """Remove file."""
        pass
    
    @abstractmethod
    def copy(self, src_path: str, dst_path: str) -> None:
        """Copy file from src to dst."""
        pass
    
    @abstractmethod
    def makedirs(self, dir_path: str, exist_ok: bool = True) -> None:
        """Create directory and parent directories."""
        pass
    
    @abstractmethod
    def list_files(self, dir_path: str, pattern: str = "*") -> List[str]:
        """List files in directory matching pattern."""
        pass
    
    @abstractmethod
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes."""
        pass
    
    @abstractmethod
    def copy_fileobj(self, src_fileobj: BinaryIO, dst_path: str) -> None:
        """Copy file object to destination path."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""
    
    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)
    
    def _resolve_path(self, file_path: str) -> str:
        """Resolve relative path to absolute path within base directory."""
        if os.path.isabs(file_path):
            return file_path
        return os.path.join(self.base_dir, file_path)
    
    def read_file(self, file_path: str) -> bytes:
        """Read file contents as bytes."""
        abs_path = self._resolve_path(file_path)
        with open(abs_path, 'rb') as f:
            return f.read()
    
    def write_file(self, file_path: str, data: bytes) -> None:
        """Write bytes to file."""
        abs_path = self._resolve_path(file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'wb') as f:
            f.write(data)
    
    def read_text(self, file_path: str, encoding: str = 'utf-8') -> str:
        """Read file contents as text."""
        abs_path = self._resolve_path(file_path)
        with open(abs_path, 'r', encoding=encoding) as f:
            return f.read()
    
    def write_text(self, file_path: str, text: str, encoding: str = 'utf-8') -> None:
        """Write text to file."""
        abs_path = self._resolve_path(file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding=encoding) as f:
            f.write(text)
    
    def read_json(self, file_path: str) -> Any:
        """Read JSON file."""
        abs_path = self._resolve_path(file_path)
        with open(abs_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def write_json(self, file_path: str, data: Any, indent: int = 2, ensure_ascii: bool = False) -> None:
        """Write data to JSON file."""
        abs_path = self._resolve_path(file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
    
    def exists(self, file_path: str) -> bool:
        """Check if file exists."""
        abs_path = self._resolve_path(file_path)
        return os.path.exists(abs_path)
    
    def remove(self, file_path: str) -> None:
        """Remove file."""
        abs_path = self._resolve_path(file_path)
        if os.path.exists(abs_path):
            os.remove(abs_path)
    
    def copy(self, src_path: str, dst_path: str) -> None:
        """Copy file from src to dst."""
        abs_src = self._resolve_path(src_path)
        abs_dst = self._resolve_path(dst_path)
        os.makedirs(os.path.dirname(abs_dst), exist_ok=True)
        shutil.copy2(abs_src, abs_dst)
    
    def makedirs(self, dir_path: str, exist_ok: bool = True) -> None:
        """Create directory and parent directories."""
        abs_path = self._resolve_path(dir_path)
        os.makedirs(abs_path, exist_ok=exist_ok)
    
    def list_files(self, dir_path: str, pattern: str = "*") -> List[str]:
        """List files in directory matching pattern."""
        abs_path = self._resolve_path(dir_path)
        if not os.path.exists(abs_path):
            return []
        
        import glob
        search_pattern = os.path.join(abs_path, pattern)
        matches = glob.glob(search_pattern, recursive=True)
        
        # Return relative paths
        return [os.path.relpath(match, self.base_dir).replace(os.sep, '/') for match in matches]
    
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes."""
        abs_path = self._resolve_path(file_path)
        return os.path.getsize(abs_path)
    
    def copy_fileobj(self, src_fileobj: BinaryIO, dst_path: str) -> None:
        """Copy file object to destination path."""
        abs_dst = self._resolve_path(dst_path)
        os.makedirs(os.path.dirname(abs_dst), exist_ok=True)
        with open(abs_dst, 'wb') as dst_file:
            shutil.copyfileobj(src_fileobj, dst_file)


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend."""
    
    def __init__(self, bucket_name: str, region: str = 'us-west-2', auto_sync: bool = False, endpoint_url: Optional[str] = None):
        self.bucket_name = bucket_name
        self.region = region
        self.auto_sync = auto_sync
        self.endpoint_url = endpoint_url # Store it
        
        try:
            import boto3
            from app.core.config import get_settings
            settings = get_settings()
            
            client_config = {'region_name': region}
            if endpoint_url:
                client_config['endpoint_url'] = endpoint_url
            
            # Add AWS credentials if available
            if settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY:
                client_config['aws_access_key_id'] = settings.S3_ACCESS_KEY_ID
                client_config['aws_secret_access_key'] = settings.S3_SECRET_ACCESS_KEY
            
            self.s3_client = boto3.client('s3', **client_config)
            logger.info(f"S3StorageBackend initialized: bucket={bucket_name}, region={region}, endpoint_url={endpoint_url}")
        except ImportError:
            raise ImportError("boto3 required for S3 storage backend. Install with: pip install boto3")
    
    def read_file(self, file_path: str) -> bytes:
        """Read file contents as bytes."""
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
        return response['Body'].read()
    
    def write_file(self, file_path: str, data: bytes) -> None:
        """Write bytes to file."""
        try:
            self.s3_client.put_object(Bucket=self.bucket_name, Key=file_path, Body=data)
            logger.debug(f"Successfully uploaded file to S3: {file_path}")
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {file_path}, error: {e}")
            logger.error(f"Exception type: {type(e)}, Exception args: {e.args}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise
    
    def read_text(self, file_path: str, encoding: str = 'utf-8') -> str:
        """Read file contents as text."""
        data = self.read_file(file_path)
        return data.decode(encoding)
    
    def write_text(self, file_path: str, text: str, encoding: str = 'utf-8') -> None:
        """Write text to file."""
        data = text.encode(encoding)
        self.write_file(file_path, data)
    
    def read_json(self, file_path: str) -> Any:
        """Read JSON file."""
        text = self.read_text(file_path)
        return json.loads(text)
    
    def write_json(self, file_path: str, data: Any, indent: int = 2, ensure_ascii: bool = False) -> None:
        """Write data to JSON file."""
        text = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
        self.write_text(file_path, text)
    
    def exists(self, file_path: str) -> bool:
        """Check if file exists."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except self.s3_client.exceptions.NoSuchKey:
            return False
        except Exception:
            return False
    
    def remove(self, file_path: str) -> None:
        """Remove file."""
        self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
    
    def copy(self, src_path: str, dst_path: str) -> None:
        """Copy file from src to dst."""
        copy_source = {'Bucket': self.bucket_name, 'Key': src_path}
        self.s3_client.copy_object(CopySource=copy_source, Bucket=self.bucket_name, Key=dst_path)
    
    def makedirs(self, dir_path: str, exist_ok: bool = True) -> None:
        """Create directory (no-op for S3)."""
        pass
    
    def list_files(self, dir_path: str, pattern: str = "*") -> List[str]:
        """List files in directory matching pattern."""
        response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=dir_path)
        if 'Contents' not in response:
            return []
        
        files = [obj['Key'] for obj in response['Contents']]
        
        if pattern != "*":
            import fnmatch
            files = [f for f in files if fnmatch.fnmatch(os.path.basename(f), pattern)]
        
        return files
    
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes."""
        response = self.s3_client.head_object(Bucket=self.bucket_name, Key=file_path)
        return response['ContentLength']
    
    def copy_fileobj(self, src_fileobj: BinaryIO, dst_path: str) -> None:
        """Copy file object to destination path."""
        self.s3_client.upload_fileobj(src_fileobj, self.bucket_name, dst_path)
    
    def generate_presigned_url(self, file_path: str, expiry_seconds: int = 3600) -> str:
        """Generate a presigned URL for direct access to S3 object."""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_path},
                ExpiresIn=expiry_seconds
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {file_path}: {e}")
            raise


def create_storage_backend(storage_type: str, **kwargs) -> StorageBackend:
    """Factory function to create storage backend based on type."""
    if storage_type.lower() == 'local':
        base_dir = kwargs.get('base_dir')
        if not base_dir:
            raise ValueError("base_dir required for local storage backend")
        return LocalStorageBackend(base_dir)
    
    elif storage_type.lower() == 's3':
        bucket_name = kwargs.get('bucket_name')
        if not bucket_name:
            raise ValueError("bucket_name required for S3 storage backend")
        
        region = kwargs.get('region', 'us-west-2')
        auto_sync = kwargs.get('auto_sync', False)
        endpoint_url = kwargs.get('endpoint_url') # Get endpoint_url
        return S3StorageBackend(bucket_name, region, auto_sync, endpoint_url=endpoint_url)
    
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")