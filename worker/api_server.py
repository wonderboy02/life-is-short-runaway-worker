"""
알리고 카카오 API 프록시 서버

Vercel에서 알리고 API를 호출할 때 이 서버를 통해 프록시합니다.
친구 컴퓨터의 고정 IP를 알리고 화이트리스트에 등록하여 사용합니다.
"""
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import logging

# 로거 설정
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="Life is Short - Aligo Proxy",
    description="알리고 카카오 API 프록시 서버",
    version="1.0.0"
)

# 알리고 API 기본 URL
ALIGO_API_BASE = "https://kakaoapi.aligo.in"


@app.get("/health")
async def health_check():
    """
    헬스체크 엔드포인트

    UptimeRobot 등 외부 모니터링 서비스에서 사용
    """
    return {
        "status": "ok",
        "service": "aligo-proxy",
        "message": "Aligo proxy is running"
    }


@app.post("/proxy/aligo/{path:path}")
async def proxy_aligo(path: str, request: Request):
    """
    알리고 API 프록시

    POST /proxy/aligo/akv10/token/create/30/s/
    → https://kakaoapi.aligo.in/akv10/token/create/30/s/

    Args:
        path: 알리고 API 경로 (예: akv10/token/create/30/s/)
        request: FastAPI Request 객체

    Returns:
        알리고 API 응답
    """
    try:
        # 요청 바디 읽기
        body = await request.body()

        # 알리고 API URL 구성
        aligo_url = f"{ALIGO_API_BASE}/{path}"

        # 알리고 API로 요청 전달
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                aligo_url,
                content=body,
                headers={
                    "Content-Type": request.headers.get("content-type", "application/x-www-form-urlencoded"),
                }
            )

        logger.info(f"Aligo API 프록시: {path} - Status {response.status_code}")

        # 알리고 API 응답 반환
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )

    except httpx.TimeoutException:
        logger.error(f"Aligo API 타임아웃: {path}")
        return JSONResponse(
            status_code=504,
            content={"error": "Aligo API timeout"}
        )
    except Exception as e:
        logger.error(f"Aligo API 프록시 오류: {path} - {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Proxy error: {str(e)}"}
        )


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "Life is Short - Aligo Proxy",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "proxy": "/proxy/aligo/{path}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
