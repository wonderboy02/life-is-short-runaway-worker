# Worker 개발팀 전달 가이드

**프로젝트**: Runway Worker for Life is Short
**목적**: Next.js API에서 video task를 가져와 Runway Gen-4/Veo API로 추론 후 결과를 Supabase Storage에 업로드
**배포**: Docker 기반 Linux 서버

---

## 📋 목차

1. [개요](#1-개요)
2. [준비물](#2-준비물)
3. [구현 순서](#3-구현-순서)
4. [API 스펙](#4-api-스펙)
5. [Runway 모델 정보](#5-runway-모델-정보)
6. [테스트](#6-테스트)
7. [배포](#7-배포)
8. [FAQ](#8-faq)

---

## 1. 개요

### 1.1 아키텍처

```
┌─────────────────────────────────────────┐
│  Next.js API (이미 구현됨)               │
│  - video_items 테이블 관리               │
│  - Worker API 엔드포인트 제공            │
└─────────────┬───────────────────────────┘
              │ HTTP/REST
              ↓
┌─────────────────────────────────────────┐
│  Runway Worker (구현 필요)              │
│  1. Polling: task 요청                  │
│  2. Download: 사진 다운로드             │
│  3. Runway API: I2V 생성                │
│  4. Upload: 비디오 업로드               │
│  5. Report: 결과 보고                   │
└─────────────────────────────────────────┘
```

### 1.2 프로세스 흐름

```
1. [POLL] Worker → Next.js API
   "다음 task 주세요" (5초마다)

2. [RECEIVE] Next.js API → Worker
   {
     item_id: "uuid-123",
     photo_storage_path: "photos/...",
     prompt: "Slow dolly-in, subject breathes...",
     inference_provider: "gen4_turbo",
     frame_num: 121
   }

3. [DOWNLOAD] Worker → Supabase Storage
   Presigned URL로 사진 다운로드

4. [PROCESS] Worker → Runway API
   POST /v1/image_to_video
   → Task ID 받기
   → 폴링으로 완료 대기 (5초마다 체크)
   → 비디오 URL 받기

5. [UPLOAD] Worker → Supabase Storage
   Presigned URL로 비디오 업로드

6. [REPORT] Worker → Next.js API
   POST /api/worker/report
   {
     status: "completed",
     video_storage_path: "generated-videos/uuid-123.mp4"
   }
```

### 1.3 기존 WAN Worker 대비 변경사항

**유지 (95%)**:
- ✅ 폴링 루프 (`worker.py`)
- ✅ API 통신 (`api_client.py`)
- ✅ 파일 다운로드/업로드 (`storage.py`)
- ✅ 로깅 (`logger.py`)

**교체 (5%)**:
- ❌ ~~`inference.py` (로컬 모델)~~ → ✅ `runway_client.py` (Runway API)

---

## 2. 준비물

### 2.1 필수 항목

| 항목 | 설명 | 획득 방법 |
|------|------|----------|
| **Runway API Key** | Runway ML API 인증 키 | https://runwayml.com 회원가입 후 발급 |
| **Worker API Key** | Next.js API 인증 토큰 | 백엔드 팀에서 발급 (32자 이상) |
| **Next.js API URL** | Next.js API 엔드포인트 | 예: `https://life-is-short-landing.vercel.app/api` |
| **Linux 서버** | Docker 실행 환경 | Railway, Render, DigitalOcean 등 (CPU만 필요) |

### 2.2 권장 서버 스펙

- **CPU**: 1 Core 이상
- **메모리**: 2GB 이상
- **GPU**: 불필요 (Runway가 클라우드에서 처리)
- **디스크**: 10GB 이상
- **비용**: $5-10/월

### 2.3 Git 레포지토리

```bash
# 새 레포 생성
https://github.com/wonderboy02/life_is_short_runway_worker
```

---

## 3. 구현 순서

### 📍 Step 1: 프로젝트 초기 설정 (10분)

```bash
# 1. 레포 생성 및 클론
mkdir life_is_short_runway_worker
cd life_is_short_runway_worker
git init

# 2. 디렉토리 구조 생성
mkdir -p worker scripts docs temp logs

# 3. 기본 파일 생성
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
touch .gitignore
```

**`.gitignore` 내용**:
```gitignore
__pycache__/
*.pyc
.env
worker/config.yaml
logs/
temp/
.vscode/
.idea/
```

---

### 📍 Step 2: 기존 코드 복사 (30분)

**다음 파일을 WAN Worker 레포에서 복사**:

| 파일 | 출처 | 변경 필요 |
|------|------|----------|
| `worker/logger.py` | life_is_short_wan_inference | ❌ 변경 없음 |
| `worker/storage.py` | life_is_short_wan_inference | ❌ 변경 없음 |
| `worker/api_client.py` | life_is_short_wan_inference | ⚠️ `worker_type` 추가 |
| `worker/worker.py` | life_is_short_wan_inference | ⚠️ `inference.py` → `runway_client.py` 교체 |

**⚠️ 수정 필요한 부분**:

**`api_client.py`**:
```python
def __init__(self, base_url: str, worker_token: str, worker_id: str,
             worker_type: str = "runway", timeout: int = 30):  # 🆕 worker_type 추가
    # ...
    self.worker_type = worker_type

def get_next_task(self, lease_duration_seconds: int = 600):
    payload = {
        "worker_id": self.worker_id,
        "worker_type": self.worker_type,  # 🆕 추가
        "lease_duration_seconds": lease_duration_seconds
    }
```

---

### 📍 Step 3: Runway Client 구현 (2시간)

**`worker/runway_client.py` 새로 작성**:

**핵심 메서드**:
```python
class RunwayClient:
    def generate_video(
        self,
        input_image_path: str,
        output_video_path: str,
        prompt: str,
        model: str,  # "gen4_turbo", "gen4.5_turbo", etc.
        duration: float = 5.0,
        ratio: str = "1280:720"
    ) -> str:
        """
        Image-to-Video 생성

        Returns:
            생성된 비디오 경로
        """
        # 1. 이미지를 data URI로 변환
        image_uri = self._image_to_data_uri(input_image_path)

        # 2. Runway API 요청
        task_id = self._create_i2v_task(image_uri, prompt, model, duration, ratio)

        # 3. 완료까지 폴링 (5초마다)
        video_url = self._wait_for_completion(task_id, timeout=600)

        # 4. 비디오 다운로드
        self._download_video(video_url, output_video_path)

        return output_video_path
```

**전체 코드**: `docs/runway-worker-implementation-guide.md` 참고

---

### 📍 Step 4: Worker 메인 로직 수정 (1시간)

**`worker/worker.py` 수정**:

```python
from runway_client import RunwayClient  # 🆕

class RunwayWorker:
    def __init__(self, config_path: str):
        # ...
        self.runway_client = RunwayClient(
            api_key=self.config["runway_api_key"],
            model=self.config.get("runway_model", "gen4_turbo"),
            timeout=600
        )

    def process_task(self, task: Dict):
        # ...
        inference_provider = task.get("inference_provider", "gen4_turbo")

        # 모델 매핑
        model_map = {
            "wan_local": None,  # Skip (다른 worker가 처리)
            "gen4_turbo": "gen4_turbo",
            "gen4.5_turbo": "gen4.5_turbo",
            "gen3a_turbo": "gen3a_turbo",
            "veo3": "veo3",
            "veo3.1": "veo3.1",
            "veo3.1_fast": "veo3.1_fast"
        }

        model = model_map.get(inference_provider, "gen4_turbo")

        # frame_num → duration 변환
        duration = (task.get("frame_num") or 121) / 24.0
        duration = max(2.0, min(10.0, duration))  # 2-10초 제한

        # Runway 호출
        self.runway_client.generate_video(
            input_image_path=str(temp_input),
            output_video_path=str(temp_output),
            prompt=task["prompt"],
            model=model,
            duration=duration,
            ratio="1280:720"
        )
```

---

### 📍 Step 5: 설정 파일 작성 (20분)

**`requirements.txt`**:
```txt
requests==2.31.0
pyyaml==6.0.1
Pillow==10.2.0
python-json-logger==2.0.7
python-dotenv==1.0.0
```

**`.env.example`**:
```bash
# Next.js API
NEXT_API_URL=https://life-is-short-landing.vercel.app/api
WORKER_API_KEY=your-worker-token

# Runway API
RUNWAY_API_KEY=rw_sk_xxxxxxxxxxxxxxxxxxxx

# Worker
WORKER_ID=runway-worker-001
WORKER_TYPE=runway
POLLING_INTERVAL=5

# Paths
TEMP_DIR=./temp
LOG_DIR=./logs
```

**`worker/config.yaml.example`**:
```yaml
vercel_api_url: "${NEXT_API_URL}"
worker_token: "${WORKER_API_KEY}"
worker_id: "${WORKER_ID}"
worker_type: "runway"

polling_interval: 5
lease_duration_seconds: 600
heartbeat_interval: 120

runway_api_key: "${RUNWAY_API_KEY}"
runway_model: "gen4_turbo"
runway_timeout: 600
runway_poll_interval: 5

temp_dir: "./temp"
log_dir: "./logs"
auto_cleanup_temp: true
```

---

### 📍 Step 6: Docker 설정 (30분)

**`Dockerfile`**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker/ ./worker/
COPY scripts/ ./scripts/

RUN mkdir -p temp logs

HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
  CMD bash scripts/health_check.sh || exit 1

CMD ["python", "-u", "worker/worker.py", "worker/config.yaml"]
```

**`docker-compose.yml`**:
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
```

**`scripts/health_check.sh`**:
```bash
#!/bin/bash

if ! pgrep -f "worker.py" > /dev/null; then
    echo "Worker process not found"
    exit 1
fi

LOG_FILE=$(ls -t logs/*.log 2>/dev/null | head -1)
if [ -z "$LOG_FILE" ]; then
    echo "No log file found"
    exit 1
fi

if [ $(find "$LOG_FILE" -mmin -5 | wc -l) -eq 0 ]; then
    echo "Worker seems stuck"
    exit 1
fi

echo "Worker healthy"
exit 0
```

---

### 📍 Step 7: 로컬 테스트 (1시간)

```bash
# 1. 환경변수 설정
cp .env.example .env
nano .env  # RUNWAY_API_KEY, WORKER_API_KEY 입력

cp worker/config.yaml.example worker/config.yaml

# 2. Python 로컬 실행
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python worker/worker.py

# 3. Docker 테스트
docker-compose build
docker-compose up
```

**기대 로그**:
```
2025-01-05 15:30:45 [INFO] [runway-worker-001] Worker initialized
2025-01-05 15:30:45 [INFO] [runway-worker-001] Next.js API: https://...
2025-01-05 15:30:45 [INFO] [runway-worker-001] Runway Model: gen4_turbo
2025-01-05 15:30:50 [INFO] [runway-worker-001] [POLLING] Requesting next task...
2025-01-05 15:30:50 [INFO] [runway-worker-001] [IDLE] No task available
```

---

### 📍 Step 8: 배포 (30분)

```bash
# Linux 서버에 접속
ssh user@your-server.com

# 레포 클론
git clone https://github.com/wonderboy02/life_is_short_runway_worker.git
cd life_is_short_runway_worker

# 환경변수 설정
cp .env.example .env
nano .env  # 실제 키 입력

cp worker/config.yaml.example worker/config.yaml
nano worker/config.yaml  # worker_id 수정

# Docker 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

---

## 4. API 스펙

### 4.1 Next.js → Worker

#### GET /api/worker/next-task

**Request**:
```json
{
  "worker_id": "runway-worker-001",
  "worker_type": "runway",
  "lease_duration_seconds": 600
}
```

**Response (Task 있음)**:
```json
{
  "success": true,
  "data": {
    "item_id": "uuid-123",
    "group_id": "uuid-456",
    "photo_id": "uuid-789",
    "photo_storage_path": "photos/uuid-456/uuid-789_original.jpg",
    "prompt": "Slow dolly-in, subject breathes gently, preserve identity",
    "frame_num": 121,
    "inference_provider": "gen4_turbo",
    "leased_until": "2025-01-05T12:30:00Z"
  }
}
```

**Response (Task 없음)**:
```json
{
  "success": true,
  "data": null
}
```

#### POST /api/worker/presign (Download)

**Request**:
```json
{
  "operation": "download",
  "storage_path": "photos/uuid-456/uuid-789_original.jpg"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "url": "https://supabase.co/...?token=...",
    "expires_in": 600
  }
}
```

#### POST /api/worker/presign (Upload)

**Request**:
```json
{
  "operation": "upload",
  "video_item_id": "uuid-123",
  "file_extension": "mp4"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "url": "https://supabase.co/...?token=...",
    "storage_path": "generated-videos/uuid-123.mp4",
    "expires_in": 1800
  }
}
```

#### POST /api/worker/report

**Request (Success)**:
```json
{
  "item_id": "uuid-123",
  "worker_id": "runway-worker-001",
  "status": "completed",
  "video_storage_path": "generated-videos/uuid-123.mp4",
  "runway_task_id": "runway-xyz789"  // optional
}
```

**Request (Failure)**:
```json
{
  "item_id": "uuid-123",
  "worker_id": "runway-worker-001",
  "status": "failed",
  "error_message": "Runway: Image content violates content policy"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "message": "Task completed",
    "item_id": "uuid-123"
  }
}
```

#### POST /api/worker/heartbeat

**Request**:
```json
{
  "item_id": "uuid-123",
  "worker_id": "runway-worker-001",
  "extend_seconds": 300
}
```

**Response**:
```json
{
  "success": true
}
```

---

### 4.2 Worker → Runway API

#### POST /v1/image_to_video

**Headers**:
```
Authorization: Bearer {RUNWAY_API_KEY}
X-Runway-Version: 2024-11-06
Content-Type: application/json
```

**Request**:
```json
{
  "model": "gen4_turbo",
  "promptImage": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "promptText": "Slow dolly-in, subject breathes gently",
  "duration": 5.0,
  "ratio": "1280:720"
}
```

**Response**:
```json
{
  "id": "runway-task-abc123"
}
```

#### GET /v1/tasks/{task_id}

**Headers**:
```
Authorization: Bearer {RUNWAY_API_KEY}
X-Runway-Version: 2024-11-06
```

**Response (Running)**:
```json
{
  "id": "runway-task-abc123",
  "status": "RUNNING"
}
```

**Response (Success)**:
```json
{
  "id": "runway-task-abc123",
  "status": "SUCCEEDED",
  "output": ["https://runway.../video.mp4"]
}
```

**Response (Failed)**:
```json
{
  "id": "runway-task-abc123",
  "status": "FAILED",
  "failure": "Image content violates content policy"
}
```

---

## 5. Runway 모델 정보

### 5.1 지원 모델 전체 목록

| 모델 | 속도 | 품질 | 권장 용도 | 비용 (추정) |
|------|------|------|----------|------------|
| `gen4_turbo` ⭐ | 빠름 | 좋음 | 프로덕션 기본 | $0.05/분 |
| `gen4.5_turbo` ⭐ | 빠름 | 더 좋음 | 프로덕션 권장 | $0.06/분 |
| `gen3a_turbo` | 매우 빠름 | 보통 | 빠른 프로토타입 | $0.03/분 |
| `veo3` | 느림 | 최고 | 최고 품질 필요 시 | $0.12/분 |
| `veo3.1` | 중간 | 최고 | 품질+속도 균형 | $0.10/분 |
| `veo3.1_fast` | 빠름 | 좋음 | 빠른 고품질 | $0.07/분 |

⚠️ **비용은 추정치**입니다. 실제 가격은 Runway 공식 사이트 확인 필요.

### 5.2 모델 선택 가이드

**일반적인 사용**:
- ✅ `gen4_turbo` 또는 `gen4.5_turbo` (균형 잡힌 선택)

**빠른 테스트**:
- ✅ `gen3a_turbo` (가장 빠름, 비용 낮음)

**최고 품질**:
- ✅ `veo3.1` (품질+속도 균형)
- ✅ `veo3` (최고 품질, 느림)

### 5.3 코드에서 모델 매핑

**TypeScript (Next.js)**:
```typescript
export const RUNWAY_MODELS = {
  gen4_turbo: { name: 'Gen-4 Turbo', speed: 'fast', quality: 'good' },
  'gen4.5_turbo': { name: 'Gen-4.5 Turbo', speed: 'fast', quality: 'better' },
  gen3a_turbo: { name: 'Gen-3 Alpha Turbo', speed: 'very-fast', quality: 'ok' },
  veo3: { name: 'Veo 3', speed: 'slow', quality: 'best' },
  'veo3.1': { name: 'Veo 3.1', speed: 'medium', quality: 'best' },
  'veo3.1_fast': { name: 'Veo 3.1 Fast', speed: 'fast', quality: 'good' },
  wan_local: { name: 'WAN Local (GPU)', speed: 'very-slow', quality: 'good' }
} as const;

export type InferenceProvider = keyof typeof RUNWAY_MODELS;
```

**Python (Worker)**:
```python
RUNWAY_MODELS = {
    "gen4_turbo": "gen4_turbo",
    "gen4.5_turbo": "gen4.5_turbo",
    "gen3a_turbo": "gen3a_turbo",
    "veo3": "veo3",
    "veo3.1": "veo3.1",
    "veo3.1_fast": "veo3.1_fast",
    "wan_local": None  # Skip (다른 worker)
}

def get_runway_model(inference_provider: str) -> str:
    """inference_provider → Runway API 모델명"""
    return RUNWAY_MODELS.get(inference_provider, "gen4_turbo")
```

---

## 6. 테스트

### 6.1 Unit Test

**`tests/test_runway_client.py`**:
```python
import pytest
from worker.runway_client import RunwayClient

def test_image_to_data_uri():
    client = RunwayClient(api_key="test")
    uri = client._image_to_data_uri("test_image.jpg")
    assert uri.startswith("data:image/jpeg;base64,")

def test_create_task_requires_api_key():
    with pytest.raises(Exception):
        client = RunwayClient(api_key="")
        client._create_i2v_task(...)
```

### 6.2 Integration Test

**실제 Runway API 테스트**:
```bash
python scripts/test_runway_api.py
```

**`scripts/test_runway_api.py`**:
```python
#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from worker.runway_client import RunwayClient

load_dotenv()

api_key = os.getenv("RUNWAY_API_KEY")
if not api_key:
    print("❌ RUNWAY_API_KEY not set")
    sys.exit(1)

client = RunwayClient(api_key=api_key, model="gen4_turbo")

# Test image-to-video
try:
    result = client.generate_video(
        input_image_path="test_assets/sample.jpg",
        output_video_path="test_output.mp4",
        prompt="Camera slowly zooms in",
        model="gen4_turbo",
        duration=5.0
    )
    print(f"✅ Success: {result}")
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)
```

### 6.3 End-to-End Test

1. **Next.js에서 Task 생성**:
   - Admin UI에서 사진 업로드
   - 추론 방식 `gen4_turbo` 선택
   - Task 생성

2. **Worker 로그 확인**:
   ```bash
   docker-compose logs -f
   ```

3. **기대 결과**:
   - Task 받음 → 사진 다운로드 → Runway 호출 → 완료 대기 → 비디오 업로드 → 성공 보고

4. **Supabase 확인**:
   - `video_items` 테이블에서 `status = 'completed'`
   - `generated_video_url`에 presigned URL 있음

---

## 7. 배포

### 7.1 Railway 배포 (추천)

```bash
# Railway CLI 설치
npm install -g @railway/cli

# 로그인
railway login

# 프로젝트 생성
railway init

# 환경변수 설정
railway variables set RUNWAY_API_KEY=rw_sk_...
railway variables set WORKER_API_KEY=...
railway variables set NEXT_API_URL=https://...

# 배포
railway up
```

### 7.2 Render 배포

1. **Render.com 접속**
2. **New → Background Worker**
3. **GitHub 레포 연결**
4. **설정**:
   - **Docker Command**: `docker-compose up`
   - **Environment Variables**: `.env` 내용 입력
5. **Deploy**

### 7.3 VPS (DigitalOcean, Linode)

```bash
# 서버 접속
ssh root@your-server-ip

# Docker 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 레포 클론
git clone https://github.com/wonderboy02/life_is_short_runway_worker.git
cd life_is_short_runway_worker

# 환경변수 설정
cp .env.example .env
nano .env

# 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

---

## 8. FAQ

### Q1. Worker가 Task를 받지 못합니다.

**A: 체크리스트**
1. `worker_type: "runway"` 설정 확인
2. Next.js API URL이 올바른지 확인
3. `WORKER_API_KEY`가 유효한지 확인
4. Next.js API 로그 확인 (`/api/worker/next-task`)

### Q2. Runway API 호출이 실패합니다.

**A: 가능한 원인**
1. **API Key 오류**: `RUNWAY_API_KEY` 확인
2. **크레딧 부족**: Runway 계정 확인
3. **Content Policy 위반**: 이미지에 부적절한 내용
4. **모델명 오류**: `gen4_turbo` 등 정확한 이름 사용

### Q3. 비디오 업로드가 실패합니다.

**A: 가능한 원인**
1. **Presigned URL 만료**: 30분 제한 (Runway 생성 시간 고려)
2. **파일 크기 초과**: Supabase Storage 제한 확인
3. **네트워크 오류**: 재시도 로직 확인

### Q4. Worker가 멈춥니다.

**A: 체크리스트**
1. **로그 확인**: `docker-compose logs -f`
2. **헬스체크**: `bash scripts/health_check.sh`
3. **재시작**: `docker-compose restart`
4. **메모리 확인**: `docker stats`

### Q5. 여러 Worker를 동시에 실행할 수 있나요?

**A: 가능합니다**
```bash
# Worker 1
WORKER_ID=runway-worker-001 docker-compose up -d

# Worker 2 (다른 서버에서)
WORKER_ID=runway-worker-002 docker-compose up -d
```

Lease 기반 큐라서 중복 처리 없음.

### Q6. WAN Worker와 Runway Worker를 함께 사용하려면?

**A: 가능합니다**
- WAN Worker: `worker_type: "wan"`, `wan_local` task만 처리
- Runway Worker: `worker_type: "runway"`, Runway 모델 task만 처리

Next.js API가 `worker_type`에 따라 필터링.

---

## 📚 참고 문서

### 필수 읽기
1. **`docs/runway-worker-implementation-guide.md`** ⭐ - 전체 코드 및 구현 가이드
2. **`docs/runway-worker-architecture.md`** - 아키텍처 설계
3. **Runway API Docs**: https://docs.dev.runwayml.com/api

### 선택 읽기
- **기존 WAN Worker 레포**: https://github.com/wonderboy02/life-is-short-wan-inference
- **Next.js 프로젝트**: https://github.com/wonderboy02/life_is_short_landing

---

## 🎯 요약 체크리스트

### 구현 전
- [ ] Runway API Key 발급
- [ ] Worker API Key 받기
- [ ] Linux 서버 준비 (또는 Railway/Render 계정)

### 구현
- [ ] 레포 생성 및 디렉토리 구조 설정
- [ ] 기존 코드 복사 (`logger.py`, `storage.py`, `api_client.py`)
- [ ] `runway_client.py` 새로 작성
- [ ] `worker.py` 수정 (Runway 통합)
- [ ] 설정 파일 작성 (`requirements.txt`, `.env`, `config.yaml`)
- [ ] Docker 설정 (`Dockerfile`, `docker-compose.yml`)

### 테스트
- [ ] 로컬 Python 실행 테스트
- [ ] Docker 로컬 실행 테스트
- [ ] Runway API 연동 테스트
- [ ] End-to-End 테스트 (Next.js → Worker → Runway)

### 배포
- [ ] 서버에 배포
- [ ] 로그 확인
- [ ] 모니터링 설정

---

**작성일**: 2025-01-05
**작성자**: Backend Team
**버전**: 1.0
**문의**: Slack #backend-team
