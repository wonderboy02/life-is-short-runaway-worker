"""
IP 변경 감지 및 Slack 알림

1시간마다 공인 IP를 확인하고, 변경되면 Slack으로 알림을 보냅니다.
알리고 화이트리스트를 수동으로 재등록해야 함을 알립니다.
"""
import time
import threading
import requests
import logging
from typing import Optional
import json

logger = logging.getLogger(__name__)


class IPMonitor:
    """
    공인 IP 변경을 모니터링하고 Slack 알림을 보내는 클래스
    """

    def __init__(self, slack_webhook_url: Optional[str], check_interval_seconds: int = 3600):
        """
        Args:
            slack_webhook_url: Slack Webhook URL
            check_interval_seconds: IP 체크 간격 (초, 기본 3600초 = 1시간)
        """
        self.slack_webhook_url = slack_webhook_url
        self.check_interval_seconds = check_interval_seconds
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_known_ip: Optional[str] = None

    def start(self):
        """백그라운드 스레드 시작"""
        if not self.slack_webhook_url:
            logger.warning("⚠️ SLACK_WEBHOOK_URL이 설정되지 않았습니다. IP 모니터링을 건너뜁니다.")
            return

        if self.running:
            logger.warning("IP monitor가 이미 실행 중입니다.")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"✅ IP 모니터 시작 (체크 간격: {self.check_interval_seconds}초)")

    def stop(self):
        """백그라운드 스레드 중지"""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("IP 모니터 중지됨")

    def _run(self):
        """백그라운드 스레드 메인 루프"""
        # 시작 시 현재 IP 확인
        self.last_known_ip = self._get_public_ip()
        if self.last_known_ip:
            logger.info(f"📍 현재 공인 IP: {self.last_known_ip}")
            self._send_slack_notification(
                f"🟢 Worker 시작됨\n현재 공인 IP: `{self.last_known_ip}`\n알리고 화이트리스트에 등록되어 있는지 확인하세요."
            )

        while self.running:
            try:
                self._check_ip_change()
            except Exception as e:
                logger.error(f"IP 체크 오류: {e}")

            # 다음 체크까지 대기
            time.sleep(self.check_interval_seconds)

    def _check_ip_change(self):
        """IP 변경 확인 및 알림"""
        current_ip = self._get_public_ip()

        if not current_ip:
            logger.warning("⚠️ 공인 IP를 가져올 수 없습니다.")
            return

        if self.last_known_ip and current_ip != self.last_known_ip:
            # IP가 변경됨!
            logger.warning(f"⚠️ IP 변경 감지: {self.last_known_ip} → {current_ip}")
            self._send_slack_notification(
                f"⚠️ *IP 주소가 변경되었습니다!*\n\n"
                f"이전 IP: `{self.last_known_ip}`\n"
                f"새 IP: `{current_ip}`\n\n"
                f"📋 *조치 필요:*\n"
                f"1. 알리고 관리 페이지 접속\n"
                f"2. 화이트리스트에서 기존 IP 삭제\n"
                f"3. 새 IP `{current_ip}` 등록"
            )
            self.last_known_ip = current_ip
        else:
            logger.debug(f"✅ IP 변경 없음: {current_ip}")

    def _get_public_ip(self) -> Optional[str]:
        """
        공인 IP 주소 조회

        여러 서비스를 시도하여 안정성을 높입니다.
        """
        services = [
            "https://api.ipify.org",
            "https://ifconfig.me",
            "https://icanhazip.com",
        ]

        for service in services:
            try:
                response = requests.get(service, timeout=10)
                if response.status_code == 200:
                    ip = response.text.strip()
                    logger.debug(f"공인 IP 조회 성공 ({service}): {ip}")
                    return ip
            except Exception as e:
                logger.debug(f"IP 조회 실패 ({service}): {e}")
                continue

        return None

    def _send_slack_notification(self, message: str):
        """
        Slack으로 알림 전송

        Args:
            message: 전송할 메시지
        """
        if not self.slack_webhook_url:
            return

        try:
            payload = {
                "text": message,
                "username": "Worker IP Monitor",
                "icon_emoji": ":robot_face:"
            }

            response = requests.post(
                self.slack_webhook_url,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                logger.info("✅ Slack 알림 전송 성공")
            else:
                logger.warning(f"⚠️ Slack 알림 전송 실패 (status: {response.status_code})")

        except Exception as e:
            logger.error(f"❌ Slack 알림 전송 오류: {e}")


# 전역 인스턴스
_monitor: Optional[IPMonitor] = None


def start_ip_monitor(slack_webhook_url: Optional[str], check_interval_seconds: int = 3600):
    """
    IP 모니터 시작 (전역)

    Args:
        slack_webhook_url: Slack Webhook URL
        check_interval_seconds: IP 체크 간격 (초)
    """
    global _monitor
    if _monitor is None:
        _monitor = IPMonitor(slack_webhook_url, check_interval_seconds)
        _monitor.start()


def stop_ip_monitor():
    """IP 모니터 중지 (전역)"""
    global _monitor
    if _monitor:
        _monitor.stop()
        _monitor = None
