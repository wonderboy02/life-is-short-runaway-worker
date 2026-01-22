#!/bin/bash

echo "======================================"
echo "Worker 상태 진단 스크립트"
echo "======================================"
echo ""

# 1. Docker 컨테이너 상태 확인
echo "📦 [1/7] Docker 컨테이너 상태"
echo "--------------------------------------"
docker ps -a | grep runway-worker || echo "⚠️ runway-worker 컨테이너를 찾을 수 없습니다"
echo ""

# 2. 포트 바인딩 확인
echo "🔌 [2/7] 포트 8000 바인딩 상태"
echo "--------------------------------------"
docker port runway-worker-001 2>/dev/null || echo "⚠️ 포트 정보를 가져올 수 없습니다"
echo ""

# 3. 네트워크 리스닝 확인
echo "👂 [3/7] 포트 8000 리스닝 확인"
echo "--------------------------------------"
if command -v netstat &> /dev/null; then
    netstat -tlnp 2>/dev/null | grep :8000 || netstat -ano | grep :8000 || echo "⚠️ 포트 8000이 리스닝 중이 아닙니다"
elif command -v ss &> /dev/null; then
    ss -tlnp | grep :8000 || echo "⚠️ 포트 8000이 리스닝 중이 아닙니다"
else
    echo "⚠️ netstat 또는 ss 명령어를 찾을 수 없습니다"
fi
echo ""

# 4. 로컬 접속 테스트
echo "🏠 [4/7] 로컬 접속 테스트 (localhost:8000)"
echo "--------------------------------------"
curl -s -m 5 http://localhost:8000/health && echo "" || echo "❌ 로컬 접속 실패"
echo ""

# 5. 127.0.0.1 접속 테스트
echo "🏠 [5/7] 루프백 접속 테스트 (127.0.0.1:8000)"
echo "--------------------------------------"
curl -s -m 5 http://127.0.0.1:8000/health && echo "" || echo "❌ 루프백 접속 실패"
echo ""

# 6. 공인 IP 확인
echo "🌍 [6/7] 공인 IP 확인"
echo "--------------------------------------"
PUBLIC_IP=$(curl -s -m 5 ifconfig.me || curl -s -m 5 api.ipify.org || curl -s -m 5 icanhazip.com)
if [ -n "$PUBLIC_IP" ]; then
    echo "✅ 공인 IP: $PUBLIC_IP"

    # 7. 공인 IP로 접속 테스트
    echo ""
    echo "🌐 [7/7] 외부 접속 테스트 ($PUBLIC_IP:8000)"
    echo "--------------------------------------"
    curl -s -m 5 http://$PUBLIC_IP:8000/health && echo "" || echo "❌ 외부 접속 실패 (방화벽 또는 포트포워딩 필요)"
else
    echo "❌ 공인 IP를 확인할 수 없습니다"
fi
echo ""

# 8. Docker 로그 확인 (마지막 20줄)
echo "📋 Docker 로그 (마지막 20줄)"
echo "--------------------------------------"
docker logs --tail 20 runway-worker-001 2>&1 || echo "⚠️ 로그를 가져올 수 없습니다"
echo ""

# 9. 방화벽 상태 확인
echo "🔥 방화벽 상태 확인"
echo "--------------------------------------"
if command -v ufw &> /dev/null; then
    echo "UFW 상태:"
    sudo ufw status | grep 8000 || echo "⚠️ 포트 8000이 방화벽에 등록되지 않음"
elif command -v firewall-cmd &> /dev/null; then
    echo "Firewalld 상태:"
    sudo firewall-cmd --list-ports | grep 8000 || echo "⚠️ 포트 8000이 방화벽에 등록되지 않음"
elif command -v netsh &> /dev/null; then
    echo "Windows 방화벽 상태:"
    netsh advfirewall firewall show rule name=all | grep 8000 || echo "⚠️ 포트 8000 규칙을 찾을 수 없음"
else
    echo "⚠️ 방화벽 명령어를 찾을 수 없습니다"
fi
echo ""

echo "======================================"
echo "진단 완료"
echo "======================================"
echo ""
echo "💡 문제 해결 가이드:"
echo ""
echo "1. 컨테이너가 실행 중이 아니면:"
echo "   docker-compose up -d --build"
echo ""
echo "2. 로컬 접속은 되는데 외부 접속 안 되면:"
echo "   - Linux: sudo ufw allow 8000/tcp"
echo "   - Windows: netsh advfirewall firewall add rule name=\"Aligo Proxy\" dir=in action=allow protocol=TCP localport=8000"
echo ""
echo "3. 포트가 리스닝 중이 아니면:"
echo "   docker-compose logs -f"
echo "   (FastAPI 서버 시작 로그 확인)"
echo ""
