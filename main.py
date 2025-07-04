import asyncio
from fastapi import FastAPI, Query, HTTPException, Request
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

app = FastAPI()

limiter = Limiter(key_func=get_remote_address, default_limits=["5/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

async def get_tiktok_video_url(video_page_url: str) -> str:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(video_page_url, wait_until="networkidle")
            video_url = await page.eval_on_selector("video", "video => video.src")
            await browser.close()
            if not video_url:
                raise HTTPException(status_code=404, detail="未找到视频地址")
            return video_url
    except PlaywrightTimeoutError:
        raise HTTPException(status_code=504, detail="访问 TikTok 超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")

@app.get("/")
async def root():
    return {"message": "TikTok 下载 API 正常运行"}

@app.get("/download")
@limiter.limit("5/minute")
async def download(request: Request, url: str = Query(..., description="TikTok 视频链接")):
    video_url = await get_tiktok_video_url(url)
    return {"video_url": video_url}
