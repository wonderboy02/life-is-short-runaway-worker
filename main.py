"""
Life is Short - Runway Worker 통합 실행

다음 기능들을 동시에 실행합니다:
1. Runway Worker (메인 작업 처리)
2. FastAPI 서버 (알리고 프록시)
3. Healthchecks.io Ping (Worker 생존 모니터링)
4. IP Monitor (IP 변경 감지 및 Slack 알림)
"""
import sys
import os
import signal
import threading
import logging
from pathlib import Path

# Worker 모듈 임포트를 위해 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from worker.worker import RunwayWorker
from worker.healthcheck import start_healthcheck_pinger, stop_healthcheck_pinger
from worker.ip_monitor import start_ip_monitor, stop_ip_monitor
from worker.logger import setup_logger
import uvicorn
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로거 설정
logger = setup_logger("main", "main")


def start_fastapi_server():
    """
    FastAPI 서버를 별도 스레드에서 실행
    """
    from worker.api_server import app

    # 환경변수로 로그 레벨 제어 (기본값: info)
    log_level = os.getenv("UVICORN_LOG_LEVEL", "info").lower()
    logger.info(f"🚀 FastAPI 서버 시작 (포트 8000, 로그 레벨: {log_level})...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=log_level)


def main():
    """메인 함수"""
    logger.info("=" * 60)
    logger.info("Life is Short - Runway Worker 시작")
    logger.info("=" * 60)

    # 환경 변수 확인
    healthcheck_url = os.getenv("HEALTHCHECK_PING_URL")
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    worker_id = os.getenv("WORKER_ID", "runway-worker-001")

    logger.info(f"Worker ID: {worker_id}")
    logger.info(f"Healthcheck Ping: {'✅ 활성화' if healthcheck_url else '⚠️ 비활성화'}")
    logger.info(f"IP Monitor: {'✅ 활성화' if slack_webhook_url else '⚠️ 비활성화'}")

    # 1. Healthchecks.io Ping 시작 (60초마다)
    if healthcheck_url:
        start_healthcheck_pinger(healthcheck_url, interval_seconds=60)

    # 2. IP Monitor 시작 (1시간마다)
    if slack_webhook_url:
        start_ip_monitor(slack_webhook_url, check_interval_seconds=3600)

    # 3. FastAPI 서버 시작 (별도 스레드)
    fastapi_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    fastapi_thread.start()
    logger.info("✅ FastAPI 서버 스레드 시작됨")

    # 4. Runway Worker 시작 (메인 스레드)
    config_path = sys.argv[1] if len(sys.argv) > 1 else "worker/config.yaml"

    try:
        worker = RunwayWorker(config_path)

        # Graceful shutdown 핸들러
        def signal_handler(signum, frame):
            logger.info("\n⚠️ 종료 신호 수신됨. Worker를 종료합니다...")
            stop_healthcheck_pinger()
            stop_ip_monitor()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("🚀 Runway Worker 메인 루프 시작...")
        worker.run()

    except KeyboardInterrupt:
        logger.info("\n⚠️ 사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"❌ Worker 실행 오류: {e}", exc_info=True)
    finally:
        stop_healthcheck_pinger()
        stop_ip_monitor()
        logger.info("Worker 종료됨")


if __name__ == "__main__":
    main()
