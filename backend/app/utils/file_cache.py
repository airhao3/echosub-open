"""
File operations with caching and optimization utilities.
"""
import os
import shutil
import functools
from pathlib import Path
from typing import Dict, List, Set, Optional, Callable, Any
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

logger = logging.getLogger(__name__)

# In-memory cache for file paths and metadata
_file_metadata_cache: Dict[str, Dict[str, Any]] = {}
_path_resolution_cache: Dict[str, str] = {}
_logged_warnings: Set[str] = set()

# Thread pool for parallel operations
_thread_pool = ThreadPoolExecutor(max_workers=4)


def get_cached_path(file_path: str) -> str:
    """
    Get absolute path with caching to avoid repeated resolution.
    """
    if file_path not in _path_resolution_cache:
        _path_resolution_cache[file_path] = os.path.abspath(file_path)
    return _path_resolution_cache[file_path]


def batch_resolve_paths(paths: List[str]) -> Dict[str, str]:
    """
    Resolve multiple paths in a batch operation.
    """
    return {path: get_cached_path(path) for path in paths}


def log_warning_once(message: str, key: Optional[str] = None) -> None:
    """
    Log a warning message only once per unique key.
    """
    cache_key = key or message
    if cache_key not in _logged_warnings:
        logger.warning(message)
        _logged_warnings.add(cache_key)


class FileBatchProcessor:
    """
    Process files in batches with optimized operations.
    """
    
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    @staticmethod
    def _process_file(file_path: str, operation: Callable, **kwargs) -> Any:
        """Process a single file with error handling."""
        try:
            return operation(file_path, **kwargs)
        except Exception as e:
            log_warning_once(f"Failed to process {file_path}: {str(e)}", f"process_{file_path}")
            return None
    
    def process_files(self, file_paths: List[str], operation: Callable, **kwargs) -> List[Any]:
        """Process multiple files in parallel."""
        if not file_paths:
            return []
            
        # Use thread pool for I/O bound operations
        futures = [
            self.executor.submit(self._process_file, path, operation, **kwargs)
            for path in file_paths
        ]
        
        return [f.result() for f in futures if f.result() is not None]


@lru_cache(maxsize=128)
def get_file_metadata(file_path: str) -> Dict[str, Any]:
    """
    Get file metadata with caching.
    """
    abs_path = get_cached_path(file_path)
    if abs_path not in _file_metadata_cache:
        try:
            stat = os.stat(abs_path)
            _file_metadata_cache[abs_path] = {
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'exists': True
            }
        except OSError:
            _file_metadata_cache[abs_path] = {'exists': False}
    
    return _file_metadata_cache[abs_path].copy()


def batch_copy_files(
    files_dict: Dict[str, List[str]],
    dest_dir: str,
    overwrite: bool = False
) -> Dict[str, List[str]]:
    """
    Copy multiple files to destination directories in an optimized way.
    
    Args:
        files_dict: Dictionary mapping categories to file paths
        dest_dir: Base destination directory
        overwrite: Whether to overwrite existing files
        
    Returns:
        Dictionary of successfully copied files by category
    """
    processor = FileBatchProcessor()
    results = {}
    
    for category, file_paths in files_dict.items():
        if not file_paths:
            continue
            
        category_dir = os.path.join(dest_dir, category)
        os.makedirs(category_dir, exist_ok=True)
        
        def copy_file(src):
            dest = os.path.join(category_dir, os.path.basename(src))
            if not overwrite and os.path.exists(dest):
                return None
            try:
                shutil.copy2(src, dest)
                return dest
            except Exception as e:
                log_warning_once(f"Failed to copy {src} to {dest}: {str(e)}")
                return None
        
        copied = processor.process_files(file_paths, copy_file)
        results[category] = [f for f in copied if f is not None]
    
    return results


def clear_cache() -> None:
    """Clear all caches."""
    global _file_metadata_cache, _path_resolution_cache, _logged_warnings
    _file_metadata_cache.clear()
    _path_resolution_cache.clear()
    _logged_warnings.clear()
    get_file_metadata.cache_clear()


# Initialize a default processor instance
default_processor = FileBatchProcessor()
