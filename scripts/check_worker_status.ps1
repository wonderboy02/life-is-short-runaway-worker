# Worker 상태 진단 스크립트 (Windows PowerShell)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Worker 상태 진단 스크립트" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# 1. Docker 컨테이너 상태 확인
Write-Host "📦 [1/7] Docker 컨테이너 상태" -ForegroundColor Yellow
Write-Host "--------------------------------------"
try {
    docker ps -a | Select-String "runway-worker"
} catch {
    Write-Host "⚠️ runway-worker 컨테이너를 찾을 수 없습니다" -ForegroundColor Red
}
Write-Host ""

# 2. 포트 바인딩 확인
Write-Host "🔌 [2/7] 포트 8000 바인딩 상태" -ForegroundColor Yellow
Write-Host "--------------------------------------"
try {
    docker port runway-worker-001
} catch {
    Write-Host "⚠️ 포트 정보를 가져올 수 없습니다" -ForegroundColor Red
}
Write-Host ""

# 3. 네트워크 리스닝 확인
Write-Host "👂 [3/7] 포트 8000 리스닝 확인" -ForegroundColor Yellow
Write-Host "--------------------------------------"
try {
    $listening = netstat -ano | Select-String ":8000"
    if ($listening) {
        $listening
    } else {
        Write-Host "⚠️ 포트 8000이 리스닝 중이 아닙니다" -ForegroundColor Red
    }
} catch {
    Write-Host "⚠️ 포트 확인 실패" -ForegroundColor Red
}
Write-Host ""

# 4. 로컬 접속 테스트
Write-Host "🏠 [4/7] 로컬 접속 테스트 (localhost:8000)" -ForegroundColor Yellow
Write-Host "--------------------------------------"
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ 로컬 접속 성공" -ForegroundColor Green
    Write-Host $response.Content
} catch {
    Write-Host "❌ 로컬 접속 실패" -ForegroundColor Red
}
Write-Host ""

# 5. 127.0.0.1 접속 테스트
Write-Host "🏠 [5/7] 루프백 접속 테스트 (127.0.0.1:8000)" -ForegroundColor Yellow
Write-Host "--------------------------------------"
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ 루프백 접속 성공" -ForegroundColor Green
    Write-Host $response.Content
} catch {
    Write-Host "❌ 루프백 접속 실패" -ForegroundColor Red
}
Write-Host ""

# 6. 공인 IP 확인
Write-Host "🌍 [6/7] 공인 IP 확인" -ForegroundColor Yellow
Write-Host "--------------------------------------"
try {
    $publicIp = (Invoke-WebRequest -Uri "https://api.ipify.org" -TimeoutSec 5).Content
    Write-Host "✅ 공인 IP: $publicIp" -ForegroundColor Green

    # 7. 공인 IP로 접속 테스트
    Write-Host ""
    Write-Host "🌐 [7/7] 외부 접속 테스트 ($publicIp:8000)" -ForegroundColor Yellow
    Write-Host "--------------------------------------"
    try {
        $response = Invoke-WebRequest -Uri "http://${publicIp}:8000/health" -TimeoutSec 5 -ErrorAction Stop
        Write-Host "✅ 외부 접속 성공" -ForegroundColor Green
        Write-Host $response.Content
    } catch {
        Write-Host "❌ 외부 접속 실패 (방화벽 또는 포트포워딩 필요)" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ 공인 IP를 확인할 수 없습니다" -ForegroundColor Red
}
Write-Host ""

# 8. Docker 로그 확인 (마지막 20줄)
Write-Host "📋 Docker 로그 (마지막 20줄)" -ForegroundColor Yellow
Write-Host "--------------------------------------"
try {
    docker logs --tail 20 runway-worker-001 2>&1
} catch {
    Write-Host "⚠️ 로그를 가져올 수 없습니다" -ForegroundColor Red
}
Write-Host ""

# 9. 방화벽 상태 확인
Write-Host "🔥 Windows 방화벽 상태" -ForegroundColor Yellow
Write-Host "--------------------------------------"
try {
    $firewallRules = netsh advfirewall firewall show rule name=all | Select-String "8000"
    if ($firewallRules) {
        $firewallRules
    } else {
        Write-Host "⚠️ 포트 8000 방화벽 규칙을 찾을 수 없음" -ForegroundColor Red
    }
} catch {
    Write-Host "⚠️ 방화벽 상태를 확인할 수 없습니다" -ForegroundColor Red
}
Write-Host ""

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "진단 완료" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 문제 해결 가이드:" -ForegroundColor Green
Write-Host ""
Write-Host "1. 컨테이너가 실행 중이 아니면:" -ForegroundColor White
Write-Host "   docker-compose up -d --build" -ForegroundColor Gray
Write-Host ""
Write-Host "2. 로컬 접속은 되는데 외부 접속 안 되면 (관리자 권한 필요):" -ForegroundColor White
Write-Host '   netsh advfirewall firewall add rule name="Aligo Proxy" dir=in action=allow protocol=TCP localport=8000' -ForegroundColor Gray
Write-Host ""
Write-Host "3. 포트가 리스닝 중이 아니면:" -ForegroundColor White
Write-Host "   docker-compose logs -f" -ForegroundColor Gray
Write-Host "   (FastAPI 서버 시작 로그 확인)" -ForegroundColor Gray
Write-Host ""
