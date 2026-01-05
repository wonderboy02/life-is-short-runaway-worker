"""
File download/upload utilities
"""
import requests
from pathlib import Path
from typing import Optional


def download_file(url: str, dest_path: str, timeout: int = 300) -> str:
    """
    Download file from URL to destination path

    Args:
        url: Download URL (typically presigned URL)
        dest_path: Destination file path
        timeout: Request timeout in seconds

    Returns:
        Destination path if successful

    Raises:
        Exception if download fails
    """
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        # Ensure directory exists
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return dest_path

    except Exception as e:
        raise Exception(f"File download failed: {str(e)}")


def upload_file(file_path: str, presigned_url: str, content_type: str, timeout: int = 300) -> bool:
    """
    Upload file to presigned URL

    Args:
        file_path: Path to file to upload
        presigned_url: Presigned upload URL
        content_type: MIME type (e.g., "video/mp4")
        timeout: Request timeout in seconds

    Returns:
        True if successful

    Raises:
        Exception if upload fails
    """
    try:
        with open(file_path, 'rb') as f:
            response = requests.put(
                presigned_url,
                data=f,
                headers={'Content-Type': content_type},
                timeout=timeout
            )
            response.raise_for_status()

        return True

    except Exception as e:
        raise Exception(f"File upload failed: {str(e)}")


def cleanup_file(file_path: str):
    """
    Delete file if it exists

    Args:
        file_path: Path to file to delete
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
    except Exception:
        pass  # Ignore cleanup errors


def get_content_type(file_extension: str) -> str:
    """
    Get MIME type from file extension

    Args:
        file_extension: File extension (e.g., "mp4", "jpg")

    Returns:
        MIME type string
    """
    content_types = {
        'mp4': 'video/mp4',
        'mov': 'video/quicktime',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp'
    }

    ext = file_extension.lower().lstrip('.')
    return content_types.get(ext, 'application/octet-stream')
