from fastapi import FastAPI, Query, HTTPException
from playwright.async_api import async_playwright
from urllib.parse import urlparse, unquote
import re
import logging
from datetime import datetime, timedelta
import asyncio

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 浏览器实例缓存（解决500错误）
_browser = None
_last_init_time = None

async def get_browser():
    global _browser, _last_init_time
    if not _browser or (_last_init_time and 
                       (datetime.now() - _last_init_time) > timedelta(minutes=10)):
        if _browser:
            await _browser.close()
        _browser = await async_playwright().start()
        _last_init_time = datetime.now()
    return await _browser.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ],
        timeout=60000
    )

def clean_url(url: str) -> str:
    """终极链接清洗函数（解决400错误）"""
    try:
        # 解码URL防止双重编码
        url = unquote(url)
        
        # 提取视频ID（适配所有平台格式）
        patterns = [
            r'(https?://[^/]+/@[^/]+/video/(\d+))',
            r'(https?://vm\.tiktok\.com/[^/]+)',
            r'(https?://vt\.tiktok\.com/[^/]+)',
            r'(https?://[^/]+/v/(\d+))'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                if 'vm.tiktok.com' in url or 'vt.tiktok.com' in url:
                    return match.group(1)
                return f"https://www.tiktok.com/@{match.group(2)}/video/{match.group(3)}" if len(match.groups()) > 2 else match.group(1)
        
        raise ValueError("无法识别的链接格式")
    except Exception as e:
        logger.error(f"URL清洗失败: {str(e)}")
        raise HTTPException(status_code=400, detail=f"链接格式无效: {str(e)}")

async def fetch_video_url(url: str):
    browser = None
    try:
        browser = await get_browser()
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            extra_http_headers={
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.tiktok.com/"
            }
        )

        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60000)
        
        # 多重检测策略
        video_url = await page.evaluate("""() => {
            // 方法1：直接获取video标签
            const video = document.querySelector('video');
            if (video?.src) return video.src;
            
            // 方法2：从SIGI数据获取
            const sigiData = window.__SIGI_STATE__;
            if (sigiData?.ItemModule) {
                const firstItem = Object.values(sigiData.ItemModule)[0];
                return firstItem?.video?.downloadAddr;
            }
            
            // 方法3：从meta标签获取
            const meta = document.querySelector('meta[property="og:video:secure_url"]');
            return meta?.content || null;
        }""")

        if not video_url:
            raise HTTPException(status_code=404, detail="无法提取视频URL")

        return video_url

    except TimeoutError:
        raise HTTPException(status_code=504, detail="页面加载超时")
    except Exception as e:
        logger.error(f"浏览器操作失败: {str(e)}")
        raise HTTPException(status_code=500, detail="视频获取服务暂时不可用")
    finally:
        if browser:
            await browser.close()

@app.get("/api/download")
async def download_video(
    url: str = Query(..., description="TikTok链接（支持电脑/手机各种格式）"),
    platform: str = Query("auto", description="平台类型：pc/mobile/auto")
):
    try:
        # 平台适配
        if platform == "mobile":
            app.state.user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
        
        cleaned_url = clean_url(url)
        logger.info(f"清洗后URL: {cleaned_url}")
        
        video_url = await fetch_video_url(cleaned_url)
        logger.info(f"获取到视频URL: {video_url}")
        
        return {
            "status": "success",
            "platform": platform,
            "original_url": url,
            "video_url": video_url,
            "download_url": f"{video_url}&download=1",
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException as he:
        raise
    except Exception as e:
        logger.error(f"未知错误: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")

@app.on_event("shutdown")
async def shutdown():
    if _browser:
        await _browser.close()
