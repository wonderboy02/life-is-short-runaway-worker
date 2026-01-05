# Runway Worker 구현 가이드

**새 레포지토리**: `life_is_short_runway_worker`
**목적**: Runway Gen-4.5 API를 사용한 I2V 추론 Worker

---

## 📋 목차

1. [프로젝트 초기 설정](#1-프로젝트-초기-설정)
2. [디렉토리 구조](#2-디렉토리-구조)
3. [파일별 구현](#3-파일별-구현)
4. [Docker 설정](#4-docker-설정)
5. [로컬 테스트](#5-로컬-테스트)
6. [배포](#6-배포)

---

## 1. 프로젝트 초기 설정

### 1.1 레포지토리 생성

```bash
# 새 디렉토리 생성
mkdir life_is_short_runway_worker
cd life_is_short_runway_worker

# Git 초기화
git init
echo "# Runway Worker for Life is Short" > README.md
git add README.md
git commit -m "Initial commit"

# GitHub 레포 생성 후 연결
git remote add origin https://github.com/wonderboy02/life_is_short_runway_worker.git
git branch -M main
git push -u origin main
```

### 1.2 .gitignore 생성

```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
*.egg-info/
dist/
build/

# Environment
.env
worker/config.yaml

# Logs
logs/
*.log

# Temp files
temp/
*.tmp

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
EOF
```

---

## 2. 디렉토리 구조

```bash
# 디렉토리 생성
mkdir -p worker scripts docs

# 파일 생성
touch worker/__init__.py
touch worker/worker.py
touch worker/api_client.py
touch worker/storage.py
touch worker/runway_client.py
touch worker/logger.py
touch worker/config.yaml.example
touch requirements.txt
touch Dockerfile
touch docker-compose.yml
touch .env.example
touch scripts/health_check.sh
touch scripts/test_runway_api.py
```

**최종 구조**:
```
life_is_short_runway_worker/
├── .gitignore
├── README.md
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── worker/
│   ├── __init__.py
│   ├── worker.py              # 메인 폴링 루프
│   ├── api_client.py          # Next.js API 클라이언트
│   ├── storage.py             # 파일 다운로드/업로드
│   ├── runway_client.py       # Runway API 클라이언트
│   ├── logger.py              # 로깅
│   └── config.yaml.example    # 설정 템플릿
│
├── scripts/
│   ├── health_check.sh        # Docker 헬스체크
│   └── test_runway_api.py     # Runway API 테스트
│
├── temp/                      # 임시 파일 (gitignore)
└── logs/                      # 로그 파일 (gitignore)
```

---

## 3. 파일별 구현

### 3.1 requirements.txt

```txt
# HTTP 클라이언트
requests==2.31.0

# YAML 파싱
pyyaml==6.0.1

# 이미지 처리
Pillow==10.2.0

# 로깅
python-json-logger==2.0.7

# 환경 변수
python-dotenv==1.0.0
```

### 3.2 .env.example

```bash
# Next.js API
NEXT_API_URL=https://life-is-short-landing.vercel.app/api
WORKER_API_KEY=your-worker-token-32-chars-minimum

# Runway API
RUNWAY_API_KEY=rw_sk_xxxxxxxxxxxxxxxxxxxx
RUNWAY_MODEL=gen4_turbo
RUNWAY_TIMEOUT=600

# Worker
WORKER_ID=runway-worker-001
WORKER_TYPE=runway
POLLING_INTERVAL=5
LEASE_DURATION=600
HEARTBEAT_INTERVAL=120

# Paths
TEMP_DIR=./temp
LOG_DIR=./logs
AUTO_CLEANUP_TEMP=true
```

### 3.3 worker/config.yaml.example

```yaml
# Next.js API settings
vercel_api_url: "https://life-is-short-landing.vercel.app/api"
worker_token: "${WORKER_API_KEY}"
worker_id: "${WORKER_ID}"
worker_type: "runway"  # 'runway' or 'wan'

# Polling settings
polling_interval: 5
api_timeout: 30
lease_duration_seconds: 600
heartbeat_interval: 120

# Runway API settings
runway_api_key: "${RUNWAY_API_KEY}"
runway_model: "gen4_turbo"  # or "veo3", "veo3.1_fast"
runway_timeout: 600
runway_poll_interval: 5
runway_default_duration: 5.0
runway_default_ratio: "1280:720"

# Paths
temp_dir: "./temp"
log_dir: "./logs"

# Cleanup
auto_cleanup_temp: true
```

### 3.4 worker/logger.py

**기존 WAN Worker 코드 그대로 복사**:

```python
"""
Logging utilities for Runway Worker
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

def setup_logger(log_dir: str, worker_id: str, log_level: int = logging.INFO) -> logging.Logger:
    """
    Setup logger with file and console handlers

    Args:
        log_dir: Directory to save log files
        worker_id: Worker ID for log filename
        log_level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    # Create log directory
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger(worker_id)
    logger.setLevel(log_level)

    # Clear existing handlers
    logger.handlers.clear()

    # File handler
    log_filename = f"{worker_id}_{datetime.now().strftime('%Y%m%d')}.log"
    log_path = Path(log_dir) / log_filename

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def log_task_start(logger: logging.Logger, item_id: str, group_id: str):
    """Log task start"""
    logger.info("─" * 60)
    logger.info(f"📋 Task Started: {item_id} (group: {group_id})")
    logger.info("─" * 60)


def log_task_complete(logger: logging.Logger, item_id: str, status: str):
    """Log task completion"""
    emoji = "✅" if status == "SUCCESS" else "❌"
    logger.info(f"{emoji} Task Complete: {item_id} ({status})")
    logger.info("─" * 60)
    logger.info("")


def log_step(logger: logging.Logger, step: int, message: str):
    """Log processing step"""
    logger.info(f"[STEP {step}/6] {message}")


def log_error(logger: logging.Logger, message: str, exception: Exception):
    """Log error with exception details"""
    logger.error(f"❌ {message}")
    logger.error(f"Exception: {type(exception).__name__}: {str(exception)}")
```

### 3.5 worker/storage.py

**기존 WAN Worker 코드 그대로 복사**:

```python
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
```

### 3.6 worker/api_client.py

**기존 WAN Worker 코드에서 `worker_type` 추가**:

```python
"""
Next.js API Client for Runway Worker
"""
import requests
from typing import Optional, Dict, Any


class VercelAPIClient:
    """Client for communicating with Next.js backend API"""

    def __init__(self, base_url: str, worker_token: str, worker_id: str,
                 worker_type: str = "runway", timeout: int = 30):
        """
        Initialize API client

        Args:
            base_url: Next.js API base URL
            worker_token: Authentication token
            worker_id: Unique worker identifier
            worker_type: Worker type ('runway' or 'wan')
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.worker_token = worker_token
        self.worker_id = worker_id
        self.worker_type = worker_type
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Worker {worker_token}',
            'Content-Type': 'application/json'
        })

    def get_next_task(self, lease_duration_seconds: int = 600) -> Optional[Dict[str, Any]]:
        """
        Request next available task from the queue

        Returns:
            Task dict with keys: item_id, group_id, photo_id, prompt,
                                photo_storage_path, leased_until, inference_provider
            None if no task available
        """
        url = f"{self.base_url}/worker/next-task"
        payload = {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type,  # 🆕 추가
            "lease_duration_seconds": lease_duration_seconds
        }

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()

            result = response.json()

            # No task available
            if not result.get('success') or result.get('data') is None:
                return None

            return result['data']

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get next task: {str(e)}")

    def get_presigned_download_url(self, storage_path: str) -> Dict[str, Any]:
        """Get presigned URL for downloading input image"""
        url = f"{self.base_url}/worker/presign"
        payload = {
            "operation": "download",
            "storage_path": storage_path
        }

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return result['data']

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get presigned download URL: {str(e)}")

    def get_presigned_upload_url(self, video_item_id: str, file_extension: str = "mp4") -> Dict[str, Any]:
        """Get presigned URL for uploading result video"""
        url = f"{self.base_url}/worker/presign"
        payload = {
            "operation": "upload",
            "video_item_id": video_item_id,
            "file_extension": file_extension
        }

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return result['data']

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get presigned upload URL: {str(e)}")

    def report_task_result(self, item_id: str, status: str,
                          video_storage_path: str = None, error_message: str = None,
                          runway_task_id: str = None) -> bool:  # 🆕 veo → runway
        """
        Report task completion result

        Args:
            item_id: Item ID
            status: "completed" or "failed"
            video_storage_path: Storage path for output video
            error_message: Error message (for failed status)
            runway_task_id: Runway task ID for tracking
        """
        url = f"{self.base_url}/worker/report"
        payload = {
            "item_id": item_id,
            "worker_id": self.worker_id,
            "status": status
        }

        if status == "completed":
            if not video_storage_path:
                raise ValueError("video_storage_path required for status=completed")
            payload["video_storage_path"] = video_storage_path
            if runway_task_id:
                payload["runway_task_id"] = runway_task_id
        elif status == "failed":
            if not error_message:
                raise ValueError("error_message required for status=failed")
            payload["error_message"] = error_message

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return True

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to report task result: {str(e)}")

    def heartbeat(self, item_id: str, extend_seconds: int = 300) -> bool:
        """Send heartbeat to extend task lease"""
        url = f"{self.base_url}/worker/heartbeat"
        payload = {
            "item_id": item_id,
            "worker_id": self.worker_id,
            "extend_seconds": extend_seconds
        }

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return True

        except requests.exceptions.RequestException as e:
            # Heartbeat is optional, don't raise exception
            return False
```

### 3.7 worker/runway_client.py (🆕 새 파일)

```python
"""
Runway ML API Client for I2V Generation
"""
import os
import time
import base64
import requests
from pathlib import Path
from typing import Optional, Dict, Any


class RunwayClient:
    """Client for Runway ML Gen-4 / Veo 3.1 API"""

    def __init__(self, api_key: str, model: str = "gen4_turbo", timeout: int = 600):
        """
        Initialize Runway client

        Args:
            api_key: Runway API key
            model: Model name ('gen4_turbo', 'veo3', 'veo3.1_fast')
            timeout: Task completion timeout in seconds
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = "https://api.runwayml.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Runway-Version": "2024-11-06",
            "Content-Type": "application/json"
        }

    def generate_video(
        self,
        input_image_path: str,
        output_video_path: str,
        prompt: str,
        duration: float = 5.0,
        ratio: str = "1280:720",
        model_override: Optional[str] = None
    ) -> str:
        """
        Generate video from image using Runway I2V

        Args:
            input_image_path: Path to input image
            output_video_path: Path where output video will be saved
            prompt: Text prompt for video generation
            duration: Video duration in seconds (2-10)
            ratio: Video ratio (e.g., "1280:720")
            model_override: Override default model

        Returns:
            Path to generated video file

        Raises:
            Exception if generation fails
        """
        # Validate input
        if not Path(input_image_path).exists():
            raise FileNotFoundError(f"Input image not found: {input_image_path}")

        # Ensure output directory exists
        Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)

        # Convert image to data URI
        image_uri = self._image_to_data_uri(input_image_path)

        # Create I2V task
        model = model_override or self.model
        task_id = self._create_i2v_task(
            image_uri=image_uri,
            prompt=prompt,
            duration=duration,
            ratio=ratio,
            model=model
        )

        # Wait for completion
        video_url = self._wait_for_completion(task_id, timeout=self.timeout)

        # Download video
        self._download_video(video_url, output_video_path)

        return output_video_path

    def _image_to_data_uri(self, image_path: str) -> str:
        """
        Convert image file to data URI

        Args:
            image_path: Path to image file

        Returns:
            Data URI string (e.g., "data:image/jpeg;base64,...")
        """
        with open(image_path, 'rb') as f:
            image_data = f.read()

        # Determine MIME type
        ext = Path(image_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(ext, 'image/jpeg')

        # Encode to base64
        b64_data = base64.b64encode(image_data).decode('utf-8')

        return f"data:{mime_type};base64,{b64_data}"

    def _create_i2v_task(
        self,
        image_uri: str,
        prompt: str,
        duration: float,
        ratio: str,
        model: str
    ) -> str:
        """
        Create Runway I2V generation task

        Returns:
            Task ID
        """
        url = f"{self.base_url}/image_to_video"
        payload = {
            "model": model,
            "promptImage": image_uri,
            "promptText": prompt,
            "duration": duration,
            "ratio": ratio
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result["id"]

        except requests.exceptions.RequestException as e:
            raise Exception(f"Runway task creation failed: {str(e)}")

    def _wait_for_completion(self, task_id: str, timeout: int, poll_interval: int = 5) -> str:
        """
        Poll task until completion

        Args:
            task_id: Runway task ID
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Video URL

        Raises:
            Exception if task fails or times out
        """
        start_time = time.time()
        url = f"{self.base_url}/tasks/{task_id}"

        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                result = response.json()

                status = result.get("status")
                elapsed = int(time.time() - start_time)

                if status == "SUCCEEDED":
                    return result["output"][0]  # Video URL
                elif status == "FAILED":
                    failure_reason = result.get("failure", "Unknown error")
                    raise Exception(f"Runway task failed: {failure_reason}")
                elif status in ["PENDING", "RUNNING"]:
                    # Still processing, continue polling
                    time.sleep(poll_interval)
                else:
                    raise Exception(f"Unknown task status: {status}")

            except requests.exceptions.RequestException as e:
                # Retry on network errors
                time.sleep(poll_interval)

        raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

    def _download_video(self, video_url: str, dest_path: str):
        """
        Download video from Runway URL

        Args:
            video_url: Runway video URL
            dest_path: Destination path
        """
        try:
            response = requests.get(video_url, timeout=300, stream=True)
            response.raise_for_status()

            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        except Exception as e:
            raise Exception(f"Video download failed: {str(e)}")

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get current task status

        Args:
            task_id: Runway task ID

        Returns:
            Task status dict
        """
        url = f"{self.base_url}/tasks/{task_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get task status: {str(e)}")
```

### 3.8 worker/worker.py

**기존 WAN Worker 코드 수정 (inference → runway_client)**:

```python
"""
Runway Worker - Main polling loop for task processing
"""
import os
import sys
import time
import signal
import threading
import yaml
from pathlib import Path
from typing import Dict, Any

# Add worker directory to path
sys.path.insert(0, str(Path(__file__).parent))

from logger import setup_logger, log_task_start, log_task_complete, log_step, log_error
from api_client import VercelAPIClient
from storage import download_file, upload_file, cleanup_file
from runway_client import RunwayClient  # 🆕 Runway 클라이언트


class RunwayWorker:
    """Main worker class for polling and processing tasks"""

    def __init__(self, config_path: str = "worker/config.yaml"):
        """Initialize worker"""
        # Load configuration
        self.config = self._load_config(config_path)

        # Setup logger
        self.logger = setup_logger(
            log_dir=self.config["log_dir"],
            worker_id=self.config["worker_id"]
        )

        # Initialize API client
        self.api_client = VercelAPIClient(
            base_url=self.config["vercel_api_url"],
            worker_token=self.config["worker_token"],
            worker_id=self.config["worker_id"],
            worker_type=self.config.get("worker_type", "runway"),  # 🆕
            timeout=self.config["api_timeout"]
        )

        # Initialize Runway client 🆕
        self.runway_client = RunwayClient(
            api_key=self.config["runway_api_key"],
            model=self.config.get("runway_model", "gen4_turbo"),
            timeout=self.config.get("runway_timeout", 600)
        )

        # Setup temp directory
        Path(self.config["temp_dir"]).mkdir(parents=True, exist_ok=True)

        # Shutdown flag
        self.shutdown_requested = False

        # Heartbeat control
        self.heartbeat_active = False
        self.heartbeat_interval = self.config.get("heartbeat_interval", 120)

        self.logger.info("="*60)
        self.logger.info(f"Worker initialized: {self.config['worker_id']}")
        self.logger.info(f"Next.js API: {self.config['vercel_api_url']}")
        self.logger.info(f"Runway Model: {self.config.get('runway_model', 'gen4_turbo')}")
        self.logger.info("="*60)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Replace environment variables
        for key, value in config.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                config[key] = os.environ.get(env_var, value)

        return config

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal"""
        self.logger.info("Shutdown signal received, finishing current task...")
        self.shutdown_requested = True

    def _heartbeat_loop(self, item_id: str):
        """Background heartbeat loop to extend task lease"""
        while self.heartbeat_active:
            time.sleep(self.heartbeat_interval)
            if not self.heartbeat_active:
                break
            try:
                success = self.api_client.heartbeat(item_id, extend_seconds=300)
                if success:
                    self.logger.info(f"[HEARTBEAT] Lease extended for item {item_id}")
            except Exception as e:
                self.logger.warning(f"[HEARTBEAT] Failed: {e}")

    def process_task(self, task: Dict[str, Any]) -> bool:
        """
        Process a single task

        Args:
            task: Task dictionary from API

        Returns:
            True if task completed successfully, False otherwise
        """
        item_id = task["item_id"]
        group_id = task.get("group_id", "unknown")
        photo_storage_path = task["photo_storage_path"]
        prompt = task.get("prompt", "")
        frame_num = task.get("frame_num")
        inference_provider = task.get("inference_provider", "runway_gen4_turbo")  # 🆕

        log_task_start(self.logger, item_id, group_id)

        # Determine Runway model based on inference_provider 🆕
        if inference_provider == "runway_veo3.1":
            model = "veo3"
        elif inference_provider == "runway_gen4_turbo":
            model = "gen4_turbo"
        else:
            self.logger.warning(f"Unknown provider: {inference_provider}, using gen4_turbo")
            model = "gen4_turbo"

        # Calculate duration from frame_num 🆕
        if frame_num:
            duration = frame_num / 24.0  # 24fps
            duration = max(2.0, min(10.0, duration))  # Clamp to 2-10 seconds
        else:
            duration = self.config.get("runway_default_duration", 5.0)

        # Define temp file paths
        input_filename = Path(photo_storage_path).name
        temp_input = Path(self.config["temp_dir"]) / f"{item_id}_input{Path(input_filename).suffix}"
        temp_output = Path(self.config["temp_dir"]) / f"{item_id}_output.mp4"

        # Start heartbeat thread
        self.heartbeat_active = True
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, args=(item_id,))
        heartbeat_thread.daemon = True
        heartbeat_thread.start()

        runway_task_id = None

        try:
            # Step 1: Get presigned download URL
            log_step(self.logger, 1, "Getting download URL...")
            presign_data = self.api_client.get_presigned_download_url(photo_storage_path)
            download_url = presign_data["url"]

            # Step 2: Download input image
            log_step(self.logger, 2, f"Downloading input image: {input_filename}")
            download_file(download_url, str(temp_input))
            self.logger.info(f"Downloaded to: {temp_input}")

            # Step 3: Run Runway I2V generation 🆕
            log_step(self.logger, 3, "Calling Runway API...")
            self.logger.info(f"Prompt: {prompt}")
            self.logger.info(f"Model: {model}")
            self.logger.info(f"Duration: {duration:.2f}s")
            self.logger.info(f"Ratio: {self.config.get('runway_default_ratio', '1280:720')}")

            self.runway_client.generate_video(
                input_image_path=str(temp_input),
                output_video_path=str(temp_output),
                prompt=prompt,
                duration=duration,
                ratio=self.config.get("runway_default_ratio", "1280:720"),
                model_override=model
            )
            self.logger.info(f"Generation complete: {temp_output}")

            # Step 4: Get presigned upload URL
            log_step(self.logger, 4, "Getting upload URL...")
            presign_data = self.api_client.get_presigned_upload_url(
                video_item_id=item_id,
                file_extension="mp4"
            )
            upload_url = presign_data["url"]
            video_storage_path = presign_data["storage_path"]

            # Step 5: Upload result
            log_step(self.logger, 5, "Uploading result video...")
            upload_file(str(temp_output), upload_url, "video/mp4")
            self.logger.info(f"Uploaded to: {video_storage_path}")

            # Step 6: Report success
            log_step(self.logger, 6, "Reporting task completion...")
            self.api_client.report_task_result(
                item_id=item_id,
                status="completed",
                video_storage_path=video_storage_path,
                runway_task_id=runway_task_id
            )

            log_task_complete(self.logger, item_id, "SUCCESS")

            # Cleanup temp files
            if self.config.get("auto_cleanup_temp", True):
                cleanup_file(str(temp_input))
                cleanup_file(str(temp_output))

            return True

        except Exception as e:
            # Report failure
            log_error(self.logger, f"Task {item_id} failed", e)

            try:
                self.api_client.report_task_result(
                    item_id=item_id,
                    status="failed",
                    error_message=f"Runway: {str(e)}"
                )
            except Exception as report_error:
                log_error(self.logger, "Failed to report task failure", report_error)

            log_task_complete(self.logger, item_id, "FAILED")

            # Cleanup temp files
            cleanup_file(str(temp_input))
            cleanup_file(str(temp_output))

            return False

        finally:
            # Stop heartbeat thread
            self.heartbeat_active = False
            heartbeat_thread.join(timeout=1)

    def run(self):
        """Main polling loop"""
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        self.logger.info("Starting polling loop...")
        self.logger.info(f"Polling interval: {self.config['polling_interval']} seconds")
        self.logger.info("")

        while not self.shutdown_requested:
            try:
                # Get next task
                self.logger.info("[POLLING] Requesting next task...")
                task = self.api_client.get_next_task(
                    lease_duration_seconds=self.config.get("lease_duration_seconds", 600)
                )

                if task is None:
                    self.logger.info("[IDLE] No task available")
                    self.logger.info(f"Waiting {self.config['polling_interval']} seconds...")
                    self.logger.info("")
                    time.sleep(self.config["polling_interval"])
                    continue

                # Process task
                self.logger.info(f"[TASK RECEIVED] item_id: {task['item_id']}")
                self.logger.info("")
                success = self.process_task(task)

                # Brief pause before next poll
                time.sleep(1)

            except KeyboardInterrupt:
                self.logger.info("KeyboardInterrupt received, shutting down...")
                break

            except Exception as e:
                log_error(self.logger, "Error in main loop", e)
                self.logger.info(f"Retrying in {self.config['polling_interval']} seconds...")
                time.sleep(self.config["polling_interval"])

        self.logger.info("Worker shutdown complete")


def main():
    """Entry point"""
    # Get config path from command line or use default
    config_path = sys.argv[1] if len(sys.argv) > 1 else "worker/config.yaml"

    # Create and run worker
    worker = RunwayWorker(config_path)
    worker.run()


if __name__ == "__main__":
    main()
```

---

## 4. Docker 설정

### 4.1 Dockerfile

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY worker/ ./worker/
COPY scripts/ ./scripts/

# Create directories
RUN mkdir -p temp logs

# Make scripts executable
RUN chmod +x scripts/*.sh

# Health check
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
  CMD bash scripts/health_check.sh || exit 1

# Run worker
CMD ["python", "-u", "worker/worker.py", "worker/config.yaml"]
```

### 4.2 docker-compose.yml

```yaml
version: '3.8'

services:
  runway-worker:
    build: .
    container_name: runway-worker-001
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./temp:/app/temp
      - ./worker/config.yaml:/app/worker/config.yaml:ro
    environment:
      - PYTHONUNBUFFERED=1
    networks:
      - runway-network
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'

networks:
  runway-network:
    driver: bridge
```

### 4.3 scripts/health_check.sh

```bash
#!/bin/bash

# Check if worker process is running
if ! pgrep -f "worker.py" > /dev/null; then
    echo "Worker process not found"
    exit 1
fi

# Check if log file exists and is recent
LOG_FILE=$(ls -t logs/*.log 2>/dev/null | head -1)
if [ -z "$LOG_FILE" ]; then
    echo "No log file found"
    exit 1
fi

# Check if log file was modified in the last 5 minutes
if [ $(find "$LOG_FILE" -mmin -5 | wc -l) -eq 0 ]; then
    echo "Worker seems stuck (no recent logs)"
    exit 1
fi

echo "Worker healthy"
exit 0
```

### 4.4 scripts/test_runway_api.py

```python
#!/usr/bin/env python3
"""
Test Runway API connectivity
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")

if not RUNWAY_API_KEY:
    print("❌ RUNWAY_API_KEY not set in .env")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {RUNWAY_API_KEY}",
    "X-Runway-Version": "2024-11-06"
}

# Test API connectivity
try:
    response = requests.get(
        "https://api.runwayml.com/v1/tasks",  # List recent tasks
        headers=headers,
        timeout=10
    )

    if response.status_code == 200:
        print("✅ Runway API connection successful")
        print(f"Response: {response.json()}")
    else:
        print(f"❌ Runway API error: {response.status_code}")
        print(response.text)
        sys.exit(1)

except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)
```

---

## 5. 로컬 테스트

### 5.1 환경 설정

```bash
# .env 파일 생성
cp .env.example .env
nano .env

# 필수 입력:
# - NEXT_API_URL
# - WORKER_API_KEY
# - RUNWAY_API_KEY
```

### 5.2 config.yaml 생성

```bash
cp worker/config.yaml.example worker/config.yaml
```

### 5.3 Python 로컬 실행

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 실행
python worker/worker.py
```

### 5.4 Docker 로컬 실행

```bash
# 빌드
docker-compose build

# 실행
docker-compose up

# 백그라운드 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

---

## 6. 배포

### 6.1 Linux 서버 배포

```bash
# 서버에 접속
ssh user@your-server.com

# 레포 클론
git clone https://github.com/wonderboy02/life_is_short_runway_worker.git
cd life_is_short_runway_worker

# 환경변수 설정
cp .env.example .env
nano .env  # 실제 키 입력

# config.yaml 설정
cp worker/config.yaml.example worker/config.yaml
nano worker/config.yaml  # worker_id 등 수정

# Docker Compose 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

### 6.2 업데이트

```bash
cd life_is_short_runway_worker
git pull origin main
docker-compose down
docker-compose up -d --build
```

### 6.3 모니터링

```bash
# 컨테이너 상태
docker-compose ps

# 실시간 로그
docker-compose logs -f

# 최근 100줄
docker-compose logs --tail=100

# 리소스 사용량
docker stats runway-worker-001
```

---

## 7. README.md

**README.md 파일 내용**:

```markdown
# Runway Worker for Life is Short

Runway Gen-4.5 API를 사용한 Image-to-Video 추론 Worker

## 기능

- Next.js API에서 video task 폴링
- Runway Gen-4 Turbo / Veo 3.1 I2V 생성
- Supabase Storage에 결과 업로드
- Heartbeat으로 lease 연장
- 자동 재시도 및 에러 처리

## 빠른 시작

### 1. 환경 설정

\`\`\`bash
cp .env.example .env
nano .env  # RUNWAY_API_KEY, WORKER_API_KEY 입력

cp worker/config.yaml.example worker/config.yaml
\`\`\`

### 2. Docker 실행

\`\`\`bash
docker-compose up -d
docker-compose logs -f
\`\`\`

### 3. 로그 확인

\`\`\`bash
tail -f logs/runway-worker-001_*.log
\`\`\`

## 구조

- **worker.py**: 메인 폴링 루프
- **runway_client.py**: Runway API 클라이언트
- **api_client.py**: Next.js API 클라이언트
- **storage.py**: 파일 다운로드/업로드

## 환경변수

| 변수 | 설명 | 필수 |
|------|------|------|
| `RUNWAY_API_KEY` | Runway API 키 | ✅ |
| `WORKER_API_KEY` | Next.js Worker 인증 토큰 | ✅ |
| `NEXT_API_URL` | Next.js API URL | ✅ |
| `WORKER_ID` | Worker 식별자 | ✅ |

## 라이선스

MIT
\`\`\`

---

**작성일**: 2025-01-05
**버전**: 1.0
```

