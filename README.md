# Runway Worker for Life is Short

Runway Gen-4/Veo API를 사용한 Image-to-Video 추론 Worker

## 🎯 기능

- Next.js API에서 video task 폴링
- Runway Gen-4 Turbo / Gen-4.5 Turbo / Veo 3.1 I2V 생성
- Supabase Storage에 결과 업로드
- Heartbeat으로 lease 연장
- 자동 재시도 및 에러 처리

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 환경 변수 복사 및 설정
cp .env.example .env
nano .env  # RUNWAY_API_KEY, WORKER_API_KEY 입력

# Config 파일 복사
cp worker/config.yaml.example worker/config.yaml
```

**.env 필수 입력 항목:**
- `RUNWAY_API_KEY`: Runway ML API 키 (https://runwayml.com)
- `WORKER_API_KEY`: Next.js Worker 인증 토큰
- `NEXT_API_URL`: Next.js API URL (기본값 사용 가능)

### 2. Docker 실행

```bash
# 빌드 및 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

### 3. 로그 확인

```bash
# 실시간 로그
tail -f logs/runway-worker-001_*.log

# Docker 로그
docker-compose logs -f runway-worker
```

## 📂 프로젝트 구조

```
life_is_short_runway_worker/
├── worker/                   # Worker 소스코드
│   ├── __init__.py
│   ├── worker.py            # 메인 폴링 루프
│   ├── api_client.py        # Next.js API 클라이언트
│   ├── storage.py           # 파일 다운로드/업로드
│   ├── runway_client.py     # Runway API 클라이언트
│   ├── logger.py            # 로깅
│   └── config.yaml.example  # 설정 템플릿
├── scripts/                 # 유틸리티 스크립트
│   ├── health_check.sh      # Docker 헬스체크
│   └── test_runway_api.py   # Runway API 테스트
├── temp/                    # 임시 파일 (자동 생성)
├── logs/                    # 로그 파일 (자동 생성)
├── .env.example             # 환경 변수 템플릿
├── requirements.txt         # Python 의존성
├── Dockerfile               # Docker 이미지 빌드
├── docker-compose.yml       # Docker Compose 설정
└── README.md                # 이 문서
```

## 🔧 로컬 개발

### Python 가상환경

```bash
# 가상환경 생성
python -m venv venv

# 활성화 (Linux/Mac)
source venv/bin/activate

# 활성화 (Windows)
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 실행
python worker/worker.py
```

### Runway API 테스트

```bash
# API 연결 테스트
python scripts/test_runway_api.py
```

## 📊 지원 모델

| 모델 | 속도 | 품질 | 권장 용도 |
|------|------|------|----------|
| `gen3a_turbo` | 매우 빠름 | 보통 | 빠른 프로토타입 |
| `gen4_turbo` ⭐ | 빠름 | 좋음 | **프로덕션 기본** |
| `gen4.5_turbo` ⭐ | 빠름 | 더 좋음 | **프로덕션 권장** |
| `veo3.1_fast` | 빠름 | 좋음 | 빠른 고품질 |
| `veo3.1` | 중간 | 최고 | 품질+속도 균형 |
| `veo3` | 느림 | 최고 | 최고 품질 필요 시 |

**설정 변경**: `worker/config.yaml`에서 `runway_model` 값 수정

## 🌍 환경 변수

| 변수 | 설명 | 필수 | 기본값 |
|------|------|------|--------|
| `RUNWAY_API_KEY` | Runway API 키 | ✅ | - |
| `WORKER_API_KEY` | Next.js Worker 인증 토큰 | ✅ | - |
| `NEXT_API_URL` | Next.js API URL | ✅ | - |
| `WORKER_ID` | Worker 식별자 | ✅ | `runway-worker-001` |
| `WORKER_TYPE` | Worker 타입 | ❌ | `runway` |
| `POLLING_INTERVAL` | 폴링 간격 (초) | ❌ | `5` |
| `LEASE_DURATION` | Lease 기간 (초) | ❌ | `600` |
| `HEARTBEAT_INTERVAL` | Heartbeat 간격 (초) | ❌ | `120` |

## 🐳 Docker 명령어

```bash
# 빌드
docker-compose build

# 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down

# 재시작
docker-compose restart

# 상태 확인
docker-compose ps

# 컨테이너 접속
docker-compose exec runway-worker bash
```

## 🔍 모니터링

### 헬스체크

```bash
# 수동 헬스체크
bash scripts/health_check.sh

# Docker 헬스 상태
docker inspect runway-worker-001 --format='{{.State.Health.Status}}'
```

### 로그 레벨

로그는 다음 레벨로 출력됩니다:
- `INFO`: 일반 정보 (폴링, task 처리 등)
- `WARNING`: 경고 (heartbeat 실패 등)
- `ERROR`: 에러 (task 실패, API 에러 등)

## ❓ FAQ

### Q1. Worker가 Task를 받지 못합니다.

**체크리스트:**
1. `worker_type: "runway"` 설정 확인
2. Next.js API URL이 올바른지 확인
3. `WORKER_API_KEY`가 유효한지 확인
4. Next.js API 로그 확인 (`/api/worker/next-task`)

### Q2. Runway API 호출이 실패합니다.

**가능한 원인:**
1. **API Key 오류**: `RUNWAY_API_KEY` 확인
2. **크레딧 부족**: Runway 계정 확인
3. **Content Policy 위반**: 이미지에 부적절한 내용
4. **모델명 오류**: `gen4_turbo` 등 정확한 이름 사용

### Q3. 비디오 업로드가 실패합니다.

**가능한 원인:**
1. **Presigned URL 만료**: 30분 제한 (Runway 생성 시간 고려)
2. **파일 크기 초과**: Supabase Storage 제한 확인
3. **네트워크 오류**: 재시도 로직 확인

### Q4. 여러 Worker를 동시에 실행할 수 있나요?

**예, 가능합니다:**
```bash
# Worker 1
WORKER_ID=runway-worker-001 docker-compose up -d

# Worker 2 (다른 서버에서)
WORKER_ID=runway-worker-002 docker-compose up -d
```

Lease 기반 큐라서 중복 처리 없음.

## 📚 관련 문서

- **Runway API Docs**: https://docs.dev.runwayml.com/api
- **프로젝트 가이드**: `WORKER_TEAM_GUIDE.md`
- **구현 가이드**: `runway-worker-implementation-guide.md`
- **아키텍처**: `runway-worker-architecture.md`

## 📄 라이선스

MIT

---

**작성일**: 2025-01-05
**버전**: 1.0.0
**문의**: Slack #backend-team
