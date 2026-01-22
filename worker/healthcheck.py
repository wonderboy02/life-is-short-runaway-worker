"""
Healthchecks.io Ping 스레드

60초마다 Healthchecks.io에 ping을 보내 Worker가 살아있음을 알립니다.
3분 이상 ping이 없으면 Healthchecks.io가 Slack으로 알림을 보냅니다.
"""
import time
import threading
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class HealthcheckPinger:
    """
    Healthchecks.io에 주기적으로 ping을 보내는 클래스
    """

    def __init__(self, ping_url: Optional[str], interval_seconds: int = 60):
        """
        Args:
            ping_url: Healthchecks.io ping URL (예: https://hc-ping.com/your-uuid)
            interval_seconds: ping 간격 (초, 기본 60초)
        """
        self.ping_url = ping_url
        self.interval_seconds = interval_seconds
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self):
        """백그라운드 스레드 시작"""
        if not self.ping_url:
            logger.warning("⚠️ HEALTHCHECK_PING_URL이 설정되지 않았습니다. Healthcheck ping을 건너뜁니다.")
            return

        if self.running:
            logger.warning("Healthcheck pinger가 이미 실행 중입니다.")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"✅ Healthcheck pinger 시작 (간격: {self.interval_seconds}초)")

    def stop(self):
        """백그라운드 스레드 중지"""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Healthcheck pinger 중지됨")

    def _run(self):
        """백그라운드 스레드 메인 루프"""
        while self.running:
            try:
                self._send_ping()
            except Exception as e:
                logger.error(f"Healthcheck ping 오류: {e}")

            # 다음 ping까지 대기
            time.sleep(self.interval_seconds)

    def _send_ping(self):
        """Healthchecks.io에 ping 전송"""
        try:
            response = requests.get(self.ping_url, timeout=10)
            if response.status_code == 200:
                logger.debug(f"✅ Healthcheck ping 성공")
            else:
                logger.warning(f"⚠️ Healthcheck ping 실패 (status: {response.status_code})")
        except requests.RequestException as e:
            logger.error(f"❌ Healthcheck ping 실패: {e}")


# 전역 인스턴스
_pinger: Optional[HealthcheckPinger] = None


def start_healthcheck_pinger(ping_url: Optional[str], interval_seconds: int = 60):
    """
    Healthcheck pinger 시작 (전역)

    Args:
        ping_url: Healthchecks.io ping URL
        interval_seconds: ping 간격 (초)
    """
    global _pinger
    if _pinger is None:
        _pinger = HealthcheckPinger(ping_url, interval_seconds)
        _pinger.start()


def stop_healthcheck_pinger():
    """Healthcheck pinger 중지 (전역)"""
    global _pinger
    if _pinger:
        _pinger.stop()
        _pinger = None
