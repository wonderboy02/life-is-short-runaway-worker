# Runway Gen-4.5 Worker 아키텍처 설계

**프로젝트**: Life is Short - Runway I2V Worker
**목적**: Next.js API에서 video task를 가져와 Runway Gen-4.5로 추론 후 결과를 Supabase Storage에 업로드
**배포**: Docker 기반 Linux 서버
**언어**: Python 3.10+

---

## 📋 목차

1. [전체 아키텍처](#1-전체-아키텍처)
2. [기존 로컬 추론 코드와의 차이점](#2-기존-로컬-추론-코드와의-차이점)
3. [디렉토리 구조](#3-디렉토리-구조)
4. [핵심 컴포넌트](#4-핵심-컴포넌트)
5. [데이터 플로우](#5-데이터-플로우)
6. [Runway API 통합](#6-runway-api-통합)
7. [환경 변수 및 설정](#7-환경-변수-및-설정)
8. [Docker 배포](#8-docker-배포)
9. [Next.js API 연동](#9-nextjs-api-연동)
10. [모니터링 및 로깅](#10-모니터링-및-로깅)
11. [에러 핸들링 및 재시도](#11-에러-핸들링-및-재시도)

---

## 1. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     Next.js API                              │
│  (life_is_short_landing)                                    │
│                                                              │
│  - Groups, Photos 관리                                       │
│  - video_items 테이블 (task queue)                          │
│  - Worker API 엔드포인트:                                    │
│    • POST /api/worker/next-task                             │
│    • POST /api/worker/presign                               │
│    • POST /api/worker/report                                │
│    • POST /api/worker/heartbeat                             │
└────────────────┬────────────────────────────────────────────┘
                 │ HTTP/REST
                 │ (Worker 인증: Bearer Token)
                 ↓
┌─────────────────────────────────────────────────────────────┐
│             Runway Worker (Docker Container)                │
│  (새로 만들 프로젝트: life_is_short_runway_worker)          │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  1. Polling Loop (worker.py)                       │    │
│  │     - 5초마다 Next.js API에 task 요청              │    │
│  │     - Task 없으면 대기, 있으면 처리 시작            │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  2. Download Input (storage.py)                    │    │
│  │     - Presigned URL로 사진 다운로드                │    │
│  │     - 임시 파일로 저장 (temp/xxx_input.jpg)        │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  3. Runway I2V Generation (runway_client.py)       │    │
│  │     - Runway Gen-4.5 API 호출                      │    │
│  │     - Task ID로 폴링하며 완료 대기                  │    │
│  │     - 결과 비디오 URL 받기                          │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  4. Upload Result (storage.py)                     │    │
│  │     - Runway에서 비디오 다운로드                   │    │
│  │     - Presigned URL로 Supabase Storage 업로드      │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  5. Report Result (api_client.py)                  │    │
│  │     - 성공/실패 상태 Next.js API에 보고            │    │
│  │     - video_storage_path 전달                      │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Background:                                                │
│  - Heartbeat Thread (2분마다 lease 연장)                   │
│  - Logger (파일 로그 + stdout)                             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────┐
│                   Runway ML API                              │
│                                                              │
│  POST /v1/image_to_video                                    │
│  - Model: gen4_turbo, veo3.1                                │
│  - Input: promptImage (URL/data URI)                        │
│  - Output: task ID → polling → video URL                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 기존 로컬 추론 코드와의 차이점

### 유지되는 부분 (95%)
- **worker.py**: 폴링 루프, task 처리 로직
- **api_client.py**: Next.js API 통신 (동일)
- **storage.py**: 파일 다운로드/업로드 (동일)
- **logger.py**: 로깅 시스템 (동일)
- **config.yaml**: 설정 파일 구조 (일부 수정)

### 교체되는 부분 (5%)
- ~~**inference.py** (Wan2.2 로컬 모델)~~ → **runway_client.py** (Runway API)
- ~~**preprocess.py** (이미지 리사이즈)~~ → 제거 (Runway가 자동 처리)

### Input/Output 인터페이스 (100% 동일)
```python
# Input
input_image_path: str  # 사진 경로
prompt: str            # Gemini가 생성한 I2V 프롬프트
frame_num: int         # 프레임 수 (선택)

# Output
output_video_path: str  # 생성된 비디오 경로
```

---

## 3. 디렉토리 구조

### 새 레포지토리: `life_is_short_runway_worker`

```
life_is_short_runway_worker/
├── Dockerfile                # Docker 이미지 빌드
├── docker-compose.yml        # 로컬 테스트용
├── requirements.txt          # Python 의존성
├── .env.example             # 환경변수 예시
├── .gitignore               # Git 제외 파일
├── README.md                # 사용 가이드
│
├── worker/                  # Worker 소스코드
│   ├── __init__.py
│   ├── config.yaml          # 설정 파일 (gitignore)
│   ├── worker.py            # 메인 폴링 루프 ✅ 기존과 동일
│   ├── api_client.py        # Next.js API 클라이언트 ✅ 기존과 동일
│   ├── storage.py           # 파일 다운로드/업로드 ✅ 기존과 동일
│   ├── runway_client.py     # 🆕 Runway API 클라이언트 (새로 작성)
│   └── logger.py            # 로깅 유틸 ✅ 기존과 동일
│
├── temp/                    # 임시 파일 (자동 생성)
│   ├── {item_id}_input.jpg
│   └── {item_id}_output.mp4
│
├── logs/                    # 로그 파일 (자동 생성)
│   └── runway-worker-001_20250105.log
│
└── scripts/                 # 유틸리티 스크립트
    ├── test_runway_api.py   # Runway API 테스트
    └── health_check.sh      # 컨테이너 헬스체크
```

---

## 4. 핵심 컴포넌트

### 4.1 worker.py (메인 폴링 루프)

**역할**: Task 폴링, 전체 워크플로우 조율
**변경**: 없음 (기존 코드 그대로)

```python
class RunwayWorker:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.api_client = VercelAPIClient(...)
        self.runway_client = RunwayClient(...)  # 🆕 Runway 클라이언트

    def process_task(self, task: Dict) -> bool:
        """단일 task 처리"""
        # 1. Download input
        # 2. Runway API 호출 🆕
        # 3. Upload result
        # 4. Report success/failure

    def run(self):
        """메인 폴링 루프"""
        while not shutdown_requested:
            task = self.api_client.get_next_task()
            if task:
                self.process_task(task)
            else:
                time.sleep(polling_interval)
```

### 4.2 runway_client.py (🆕 새로 작성)

**역할**: Runway Gen-4.5 API 호출 및 폴링

```python
class RunwayClient:
    def __init__(self, api_key: str, model: str = "gen4_turbo"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.runwayml.com/v1"

    def generate_video(
        self,
        input_image_path: str,
        output_video_path: str,
        prompt: str,
        duration: float = 5.0,  # 초 단위
        ratio: str = "1280:720"
    ) -> str:
        """
        Image-to-Video 생성

        Args:
            input_image_path: 입력 이미지 경로
            output_video_path: 출력 비디오 저장 경로
            prompt: I2V 프롬프트
            duration: 비디오 길이 (2-10초)
            ratio: 비디오 비율

        Returns:
            생성된 비디오 경로
        """
        # 1. 이미지를 data URI로 변환
        image_uri = self._image_to_data_uri(input_image_path)

        # 2. Runway API 요청
        task_id = self._create_i2v_task(
            image_uri=image_uri,
            prompt=prompt,
            duration=duration,
            ratio=ratio
        )

        # 3. 완료까지 폴링
        video_url = self._wait_for_completion(task_id, timeout=600)

        # 4. 비디오 다운로드
        self._download_video(video_url, output_video_path)

        return output_video_path

    def _create_i2v_task(self, ...) -> str:
        """Runway I2V task 생성"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": "2024-11-06",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "promptImage": image_uri,
            "promptText": prompt,
            "duration": duration,
            "ratio": ratio
        }

        response = requests.post(
            f"{self.base_url}/image_to_video",
            headers=headers,
            json=payload
        )

        return response.json()["id"]  # task ID

    def _wait_for_completion(self, task_id: str, timeout: int) -> str:
        """폴링으로 완료 대기"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self._get_task_status(task_id)

            if status["status"] == "SUCCEEDED":
                return status["output"][0]  # video URL
            elif status["status"] == "FAILED":
                raise Exception(f"Runway task failed: {status.get('failure')}")

            time.sleep(5)  # 5초마다 체크

        raise TimeoutError(f"Task {task_id} timed out after {timeout}s")
```

### 4.3 api_client.py (기존 동일)

**역할**: Next.js API 통신
**변경**: `veo_operation_id` → `runway_task_id` (선택)

```python
class VercelAPIClient:
    def report_task_result(
        self,
        item_id: str,
        status: str,
        video_storage_path: str = None,
        error_message: str = None,
        runway_task_id: str = None  # 🆕 Runway task ID 추적
    ) -> bool:
        # 동일한 로직
```

### 4.4 storage.py (기존 동일)

**역할**: 파일 다운로드/업로드
**변경**: 없음

```python
def download_file(url: str, dest_path: str):
    """Presigned URL로 파일 다운로드"""

def upload_file(file_path: str, presigned_url: str, content_type: str):
    """Presigned URL로 파일 업로드"""
```

---

## 5. 데이터 플로우

### 5.1 Task 처리 순서

```
1️⃣ [POLLING] Worker → Next.js API
   POST /api/worker/next-task
   {
     "worker_id": "runway-worker-001",
     "lease_duration_seconds": 600
   }

   ← Response:
   {
     "success": true,
     "data": {
       "item_id": "uuid-123",
       "group_id": "uuid-456",
       "photo_id": "uuid-789",
       "photo_storage_path": "photos/uuid-456/uuid-789_original.jpg",
       "prompt": "Slow dolly-in, subject breathes gently, preserve identity",
       "frame_num": 121,  // optional
       "leased_until": "2025-01-05T12:30:00Z"
     }
   }

2️⃣ [DOWNLOAD] Worker → Next.js API → Supabase Storage
   POST /api/worker/presign
   {
     "operation": "download",
     "storage_path": "photos/..."
   }

   ← Presigned URL → Download image to temp/uuid-123_input.jpg

3️⃣ [RUNWAY] Worker → Runway API
   POST https://api.runwayml.com/v1/image_to_video
   Headers:
     Authorization: Bearer {RUNWAY_API_KEY}
     X-Runway-Version: 2024-11-06
   Body:
   {
     "model": "gen4_turbo",
     "promptImage": "data:image/jpeg;base64,...",
     "promptText": "Slow dolly-in...",
     "duration": 5.0,
     "ratio": "1280:720"
   }

   ← Response: { "id": "runway-task-abc123" }

   → Polling GET /v1/tasks/runway-task-abc123 (5초마다)
   ← PENDING → RUNNING → SUCCEEDED
   ← { "output": ["https://runway.../video.mp4"] }

4️⃣ [UPLOAD] Worker → Runway → temp → Supabase Storage
   - Runway에서 비디오 다운로드 → temp/uuid-123_output.mp4
   - Next.js API에서 Presigned Upload URL 받기
   - Supabase Storage에 업로드

5️⃣ [REPORT] Worker → Next.js API
   POST /api/worker/report
   {
     "item_id": "uuid-123",
     "worker_id": "runway-worker-001",
     "status": "completed",
     "video_storage_path": "generated-videos/uuid-123.mp4",
     "runway_task_id": "runway-task-abc123"  // optional tracking
   }

   → Next.js가 video_items 테이블 업데이트
   → status = "completed", generated_video_url = presigned URL
```

---

## 6. Runway API 통합

### 6.1 인증

```python
headers = {
    "Authorization": f"Bearer {RUNWAY_API_KEY}",
    "X-Runway-Version": "2024-11-06"
}
```

### 6.2 모델 선택

| 모델 | 속도 | 품질 | 용도 |
|------|------|------|------|
| `gen4_turbo` | 빠름 | 좋음 | 프로덕션 권장 |
| `veo3.1` | 느림 | 최고 | 최고 품질 필요 시 |
| `veo3.1_fast` | 중간 | 좋음 | 균형 |

### 6.3 파라미터 매핑

| Next.js Task | Runway API | 변환 |
|--------------|------------|------|
| `prompt` | `promptText` | 그대로 전달 |
| `photo_storage_path` | `promptImage` | Supabase URL → data URI |
| `frame_num` | `duration` | `duration = frame_num / 24` (24fps 기준) |
| - | `ratio` | 고정값 `"1280:720"` (설정 가능) |

**예시 변환**:
- `frame_num: 121` → `duration: 5.04초` (121/24 ≈ 5초)
- `frame_num: 241` → `duration: 10.04초` (최대)

### 6.4 에러 처리

```python
# Runway API 응답 예시
{
  "status": "FAILED",
  "failure": "Image content violates content policy"
}

→ Worker가 Next.js에 보고:
{
  "status": "failed",
  "error_message": "Runway: Image content violates content policy"
}
```

---

## 7. 환경 변수 및 설정

### 7.1 .env

```bash
# Next.js API
NEXT_API_URL=https://life-is-short-landing.vercel.app/api
WORKER_API_KEY=your-worker-token-32-chars-minimum

# Runway API
RUNWAY_API_KEY=rw_sk_xxxxxxxxxxxxxxxxxxxx
RUNWAY_MODEL=gen4_turbo  # or veo3.1, veo3.1_fast

# Worker
WORKER_ID=runway-worker-001
POLLING_INTERVAL=5  # seconds
LEASE_DURATION=600  # 10 minutes
HEARTBEAT_INTERVAL=120  # 2 minutes

# Runway Settings
RUNWAY_DEFAULT_DURATION=5.0  # seconds
RUNWAY_DEFAULT_RATIO=1280:720
RUNWAY_TIMEOUT=600  # 10 minutes for task completion
RUNWAY_POLL_INTERVAL=5  # seconds

# Temp & Logs
TEMP_DIR=./temp
LOG_DIR=./logs
AUTO_CLEANUP_TEMP=true
```

### 7.2 config.yaml (worker/config.yaml)

```yaml
# Next.js API settings
vercel_api_url: "https://life-is-short-landing.vercel.app/api"
worker_token: "${WORKER_API_KEY}"  # 환경변수에서 로드
worker_id: "${WORKER_ID}"

# Polling settings
polling_interval: 5
api_timeout: 30
lease_duration_seconds: 600
heartbeat_interval: 120

# Runway API settings
runway_api_key: "${RUNWAY_API_KEY}"
runway_model: "gen4_turbo"
runway_default_duration: 5.0
runway_default_ratio: "1280:720"
runway_timeout: 600
runway_poll_interval: 5

# Paths
temp_dir: "./temp"
log_dir: "./logs"

# Cleanup
auto_cleanup_temp: true
```

---

## 8. Docker 배포

### 8.1 Dockerfile

```dockerfile
FROM python:3.11-slim

# 작업 디렉토리
WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY worker/ ./worker/
COPY scripts/ ./scripts/

# 임시 디렉토리 생성
RUN mkdir -p temp logs

# 헬스체크
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
  CMD bash scripts/health_check.sh || exit 1

# Worker 실행
CMD ["python", "-u", "worker/worker.py", "worker/config.yaml"]
```

### 8.2 requirements.txt

```txt
# API 통신
requests==2.31.0

# YAML 파싱
pyyaml==6.0.1

# 이미지 처리
Pillow==10.2.0

# Runway SDK (선택 - 공식 SDK 사용 시)
# runwayml==x.x.x

# 로깅
python-json-logger==2.0.7
```

### 8.3 docker-compose.yml (로컬 테스트용)

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

### 8.4 배포 명령어

```bash
# 빌드
docker build -t runway-worker:latest .

# 실행
docker run -d \
  --name runway-worker-001 \
  --env-file .env \
  --restart unless-stopped \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/temp:/app/temp \
  runway-worker:latest

# 로그 확인
docker logs -f runway-worker-001

# 중지/재시작
docker stop runway-worker-001
docker start runway-worker-001
```

---

## 9. Next.js API 연동

### 9.1 필요한 API 엔드포인트 (이미 구현됨 ✅)

| 엔드포인트 | 메서드 | 용도 | 상태 |
|-----------|--------|------|------|
| `/api/worker/next-task` | POST | Task 요청 | ✅ 구현됨 |
| `/api/worker/presign` | POST | Presigned URL | ✅ 구현됨 |
| `/api/worker/report` | POST | 결과 보고 | ✅ 구현됨 |
| `/api/worker/heartbeat` | POST | Lease 연장 | ✅ 구현됨 |

### 9.2 수정 필요 사항

#### ❌ 수정 불필요
기존 API가 모두 호환됩니다!

#### ✅ 선택적 수정 (권장)

**database.ts에서 컬럼명 변경**:
```typescript
// Before
veo_operation_id: string | null

// After (더 명확)
runway_task_id: string | null
```

**마이그레이션** (Supabase SQL Editor):
```sql
ALTER TABLE video_items
  RENAME COLUMN veo_operation_id TO runway_task_id;

-- 타입 재생성
-- npm run gen:types
```

---

## 10. 모니터링 및 로깅

### 10.1 로그 형식

```
2025-01-05 15:30:45,123 [INFO] [runway-worker-001] ============================================================
2025-01-05 15:30:45,124 [INFO] [runway-worker-001] Worker initialized: runway-worker-001
2025-01-05 15:30:45,125 [INFO] [runway-worker-001] Next.js API: https://life-is-short-landing.vercel.app/api
2025-01-05 15:30:45,126 [INFO] [runway-worker-001] Runway Model: gen4_turbo
2025-01-05 15:30:45,127 [INFO] [runway-worker-001] ============================================================
2025-01-05 15:30:50,200 [INFO] [runway-worker-001] [POLLING] Requesting next task...
2025-01-05 15:30:50,500 [INFO] [runway-worker-001] [TASK RECEIVED] item_id: abc-123
2025-01-05 15:30:50,501 [INFO] [runway-worker-001] ──────────────────────────────────────────────────────────────
2025-01-05 15:30:50,502 [INFO] [runway-worker-001] 📋 Task Started: abc-123 (group: def-456)
2025-01-05 15:30:50,503 [INFO] [runway-worker-001] ──────────────────────────────────────────────────────────────
2025-01-05 15:30:51,000 [INFO] [runway-worker-001] [STEP 1/6] Getting download URL...
2025-01-05 15:30:52,100 [INFO] [runway-worker-001] [STEP 2/6] Downloading input image: photo.jpg
2025-01-05 15:30:55,200 [INFO] [runway-worker-001] Downloaded to: temp/abc-123_input.jpg
2025-01-05 15:30:55,300 [INFO] [runway-worker-001] [STEP 3/6] Calling Runway API...
2025-01-05 15:30:55,301 [INFO] [runway-worker-001] Prompt: Slow dolly-in, subject breathes gently
2025-01-05 15:30:55,302 [INFO] [runway-worker-001] Duration: 5.0s, Ratio: 1280:720
2025-01-05 15:30:56,400 [INFO] [runway-worker-001] Runway task created: runway-xyz789
2025-01-05 15:30:56,500 [INFO] [runway-worker-001] Polling for completion (max 600s)...
2025-01-05 15:31:01,600 [INFO] [runway-worker-001] Status: RUNNING (elapsed: 5s)
2025-01-05 15:31:06,700 [INFO] [runway-worker-001] Status: RUNNING (elapsed: 10s)
...
2025-01-05 15:35:30,100 [INFO] [runway-worker-001] Status: SUCCEEDED (elapsed: 274s)
2025-01-05 15:35:31,200 [INFO] [runway-worker-001] [STEP 4/6] Downloading result video...
2025-01-05 15:35:45,300 [INFO] [runway-worker-001] [STEP 5/6] Getting upload URL...
2025-01-05 15:35:46,400 [INFO] [runway-worker-001] [STEP 6/6] Uploading to Supabase Storage...
2025-01-05 15:36:10,500 [INFO] [runway-worker-001] Uploaded to: generated-videos/abc-123.mp4
2025-01-05 15:36:11,600 [INFO] [runway-worker-001] Reporting task completion...
2025-01-05 15:36:12,700 [INFO] [runway-worker-001] ✅ Task Complete: abc-123 (SUCCESS)
2025-01-05 15:36:12,800 [INFO] [runway-worker-001] ──────────────────────────────────────────────────────────────
```

### 10.2 헬스체크 스크립트

**scripts/health_check.sh**:
```bash
#!/bin/bash

# Worker 프로세스 확인
if ! pgrep -f "worker.py" > /dev/null; then
    echo "Worker process not found"
    exit 1
fi

# 최근 로그 확인 (5분 이내)
LOG_FILE=$(ls -t logs/*.log 2>/dev/null | head -1)
if [ -z "$LOG_FILE" ]; then
    echo "No log file found"
    exit 1
fi

# 최근 5분 내 로그가 있는지 확인
if [ $(find "$LOG_FILE" -mmin -5 | wc -l) -eq 0 ]; then
    echo "Worker seems stuck (no recent logs)"
    exit 1
fi

echo "Worker healthy"
exit 0
```

---

## 11. 에러 핸들링 및 재시도

### 11.1 재시도 전략

| 에러 타입 | Worker 재시도 | Next.js 재시도 | 최종 처리 |
|----------|--------------|---------------|----------|
| **Runway API 타임아웃** | ❌ 없음 | ✅ retry_count < 3 | Failed 보고 |
| **Runway Content Policy** | ❌ 없음 | ❌ 없음 | Failed 보고 (영구 실패) |
| **다운로드 실패** | ✅ 3회 (5초 간격) | ✅ retry_count < 3 | Failed 보고 |
| **업로드 실패** | ✅ 3회 (5초 간격) | ✅ retry_count < 3 | Failed 보고 |
| **Runway 일시적 에러** | ✅ 3회 (5초 간격) | ✅ retry_count < 3 | Failed 보고 |

### 11.2 에러 메시지 포맷

```python
# Worker → Next.js
{
  "status": "failed",
  "error_message": "Runway: Image content violates content policy"
}

# Next.js → Database
{
  "status": "failed",
  "error_message": "Runway: Image content violates content policy",
  "retry_count": 1  # 자동 증가
}
```

---

## 📌 다음 단계

### 1단계: 레포지토리 생성
```bash
mkdir life_is_short_runway_worker
cd life_is_short_runway_worker
git init
```

### 2단계: 기존 코드 복사 및 수정
- `worker.py`, `api_client.py`, `storage.py`, `logger.py` 복사
- `runway_client.py` 새로 작성
- `config.yaml` 수정 (Runway 설정 추가)

### 3단계: Docker 환경 구성
- `Dockerfile` 작성
- `docker-compose.yml` 작성
- `.env.example` 작성

### 4단계: 로컬 테스트
```bash
# 환경변수 설정
cp .env.example .env
nano .env  # RUNWAY_API_KEY, WORKER_API_KEY 입력

# Docker 빌드 및 실행
docker-compose up --build

# 로그 확인
docker-compose logs -f
```

### 5단계: Linux 서버 배포
```bash
# 서버에서
git clone <repo-url>
cd life_is_short_runway_worker
cp .env.example .env
nano .env  # 실제 키 입력
docker-compose up -d
```

---

## ❓ FAQ

### Q1. Python vs Node.js?
**A: Python 추천**
- 기존 worker 코드가 Python
- Runway SDK가 Python 지원
- Input/Output 구조 동일하게 유지 가능

### Q2. GPU 필요한가요?
**A: 불필요**
- Worker는 API만 호출 (추론은 Runway 서버에서)
- CPU만으로 충분 (메모리 2GB 이하)

### Q3. 동시에 여러 Worker 실행 가능?
**A: 가능**
- Worker ID만 다르게 설정 (runway-worker-001, 002, ...)
- Lease 기반 큐라서 중복 처리 없음

### Q4. 비용은 얼마나?
**A: Runway API 비용만**
- Worker 서버: $5-10/월 (VPS)
- Runway API: 사용량 기준 (Gen-4 Turbo: 1분당 ~$0.05)

### Q5. frame_num을 duration으로 변환?
**A: 예**
```python
duration = frame_num / 24  # 24fps 기준
# frame_num: 121 → duration: 5.04s
# frame_num: 241 → duration: 10.04s (최대)
```

---

## 📚 참고 문서

- **Runway API Docs**: https://docs.dev.runwayml.com/api
- **기존 Worker 레포**: https://github.com/wonderboy02/life-is-short-wan-inference
- **Next.js 프로젝트**: C:\Users\wondo\dev\life_is_short_landing
- **Database 스키마**: `lib/supabase/database.ts` (video_items 테이블)

---

**작성일**: 2025-01-05
**작성자**: Claude (Anthropic)
**버전**: 1.0
