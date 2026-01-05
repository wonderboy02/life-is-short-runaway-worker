# Runway Worker for Life is Short

Runway Gen-4/Veo API를 사용한 Image-to-Video 추론 Worker

## 🎯 기능

- Next.js API에서 video task 폴링
- Runway Gen-4 Turbo / Gen-4.5 Turbo / Veo 3.1 I2V 생성
- Supabase Storage에 결과 업로드
- Heartbeat으로 lease 연장
- 자동 재시도 및 에러 처리

## 📋 사전 요구사항 및 서버 설정

### Linux SSH 서버에서 처음 설치하는 경우

#### 1. Docker 설치 확인 및 설치

```bash
# SSH로 서버 접속 후 Docker 설치 확인
docker --version
docker-compose --version
```

**Docker가 설치되어 있지 않다면:**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose

# Docker 서비스 시작 및 부팅 시 자동 시작 설정
sudo systemctl start docker
sudo systemctl enable docker

# 현재 사용자를 docker 그룹에 추가 (sudo 없이 docker 사용 가능)
sudo usermod -aG docker $USER

# 그룹 변경 적용 (재로그인 대신)
newgrp docker

# 설치 확인
docker --version
```

#### 2. 프로젝트 파일 서버에 업로드

**방법 1: Git으로 클론 (추천)**
```bash
cd ~
git clone <your-repository-url> life_is_short_runaway_worker
cd life_is_short_runaway_worker
```

**방법 2: SCP로 파일 복사 (로컬 컴퓨터에서)**
```bash
scp -r /path/to/life_is_short_runaway_worker user@server-ip:/home/user/
```

**방법 3: rsync 사용**
```bash
rsync -avz /path/to/life_is_short_runaway_worker/ user@server-ip:/home/user/life_is_short_runaway_worker/
```

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

### 전체 프로세스 요약 (Linux 서버 처음 설정)

```bash
# 1. Docker 설치 (설치되어 있지 않은 경우)
sudo apt update && sudo apt install -y docker.io docker-compose
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker $USER && newgrp docker

# 2. 프로젝트 클론
git clone <your-repo-url> life_is_short_runaway_worker
cd life_is_short_runaway_worker

# 3. 환경 변수 설정
cp .env.example .env
nano .env  # API 키 입력 후 저장

# 4. 실행
docker-compose up -d

# 5. 로그 확인
docker-compose logs -f
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

### 기본 명령어

```bash
# 빌드
docker-compose build

# 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down

# 재시작 (환경 변수 변경 시 사용 안 됨!)
docker-compose restart

# 상태 확인
docker-compose ps

# 컨테이너 접속
docker-compose exec runway-worker bash
```

### 환경 변수 변경 후 재시작

**.env 파일이나 config.yaml을 수정한 후에는 반드시 다음 명령어 사용:**

```bash
# 방법 1: 컨테이너 중지 후 재시작 (추천)
docker-compose down
docker-compose up -d

# 방법 2: 강제 재생성
docker-compose up -d --force-recreate

# 방법 3: 코드 변경 시 (이미지 재빌드 포함)
docker-compose down
docker-compose up -d --build

# ⚠️ 주의: restart는 환경 변수를 새로 로드하지 않습니다
# docker-compose restart  # 이건 환경 변수 갱신 안 됨!
```

### 환경 변수 확인

```bash
# 실행 중인 컨테이너의 모든 환경 변수 확인
docker-compose exec runway-worker env

# 특정 환경 변수만 확인
docker-compose exec runway-worker printenv RUNWAY_API_KEY
docker-compose exec runway-worker printenv WORKER_API_KEY
docker-compose exec runway-worker printenv NEXT_API_URL
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

## 🔄 자동 재시작 및 부팅 설정

### 프로세스 크래시 시 자동 재시작

`docker-compose.yml`에 이미 `restart: unless-stopped` 설정이 되어 있어 다음이 자동으로 처리됩니다:

- ✅ **프로세스 크래시 시**: 자동 재시작
- ✅ **서버 재부팅 시**: 자동 시작
- ✅ **Docker 데몬 재시작 시**: 자동 시작
- ❌ **수동으로 중지한 경우**: 재시작 안 함 (의도적)

### 서버 부팅 시 자동 실행 설정

Docker 서비스가 부팅 시 자동으로 시작되도록 설정:

```bash
# Docker 서비스 자동 시작 여부 확인
sudo systemctl is-enabled docker
# "enabled"가 나오면 이미 설정됨

# Docker 서비스 부팅 시 자동 시작 활성화
sudo systemctl enable docker

# Docker 서비스 시작
sudo systemctl start docker

# 상태 확인
sudo systemctl status docker
```

### 재시작 정책 변경 (선택 사항)

더 강력한 재시작을 원한다면 `docker-compose.yml` 수정:

```yaml
# restart: unless-stopped  # 기본값 (추천)
restart: always  # 수동 중지해도 재시작 (더 강력함)
```

변경 후 적용:
```bash
docker-compose down
docker-compose up -d
```

### 자동 재시작 테스트

```bash
# 1. 프로세스 강제 종료 테스트
docker kill runway-worker-001
# 몇 초 후 다시 살아나는지 확인
docker-compose ps

# 2. 컨테이너 재시작 횟수 확인
docker inspect runway-worker-001 --format='{{.RestartCount}}'

# 3. 마지막 재시작 시간 확인
docker inspect runway-worker-001 --format='{{.State.StartedAt}}'

# 4. 서버 재부팅 테스트
sudo reboot
# 재접속 후 확인
docker-compose ps
```

### (고급) Systemd 서비스로 관리

더 견고한 관리를 원한다면 systemd 서비스 생성:

```bash
# 서비스 파일 생성
sudo nano /etc/systemd/system/runway-worker.service
```

**서비스 파일 내용:**
```ini
[Unit]
Description=Runway Worker for Life is Short
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/YOUR_USER/life_is_short_runaway_worker
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

**활성화:**
```bash
# YOUR_USER를 실제 사용자명으로 변경한 후
sudo systemctl daemon-reload
sudo systemctl enable runway-worker.service
sudo systemctl start runway-worker.service

# 상태 확인
sudo systemctl status runway-worker.service
```

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

### Q5. 환경 변수를 변경했는데 적용이 안 됩니다.

**해결 방법:**
```bash
# ❌ 잘못된 방법
docker-compose restart  # 환경 변수 새로 로드 안 됨!

# ✅ 올바른 방법
docker-compose down
docker-compose up -d

# 또는
docker-compose up -d --force-recreate
```

`restart` 명령어는 컨테이너를 재시작만 하고 환경 변수를 새로 로드하지 않습니다.
반드시 `down` → `up` 순서로 실행하세요.

### Q6. 서버 재부팅 후 Worker가 자동으로 시작되지 않습니다.

**해결 방법:**
```bash
# Docker 서비스 자동 시작 설정
sudo systemctl enable docker
sudo systemctl start docker

# 확인
sudo systemctl is-enabled docker  # "enabled" 출력되어야 함
```

Docker 서비스가 부팅 시 자동으로 시작되어야 컨테이너도 함께 시작됩니다.

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
