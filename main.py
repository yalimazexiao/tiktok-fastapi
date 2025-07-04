from fastapi import FastAPI, Query, HTTPException
from playwright.async_api import async_playwright
from urllib.parse import urlparse, urlunparse
import logging
import re
import httpx
from fastapi.responses import JSONResponse, RedirectResponse
from datetime import datetime
import asyncio

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局浏览器实例（提高性能）
_browser = None

async def init_browser():
    global _browser
    if not _browser:
        _browser = await async_playwright().start()
    return await _browser.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
        ],
        timeout=60000
    )

def clean_tiktok_url(url: str) -> str:
    """终极URL清洗函数"""
    # 处理网页版分享链接
    url = re.sub(r'\?share_id=.*', '', url)
    
    # 提取核心视频ID
    video_id_match = re.search(r'/video/(\d+)', url)
    if not video_id_match:
        # 处理移动端分享格式
        video_id_match = re.search(r'/v/(\d+)', url)
    
    if video_id_match:
        video_id = video_id_match.group(1)
        return f"https://www.tiktok.com/@placeholder/video/{video_id}"
    
    # 处理短链接
    if 'vm.tiktok.com' in url or 'vt.tiktok.com' in url:
        return url  # 由get_video_url处理重定向
    
    raise ValueError("无效的TikTok链接格式")

async def extract_video_url(page):
    """多重方式提取视频URL"""
    # 方法1：直接从video标签获取
    video_element = await page.query_selector('video')
    if video_element:
        video_url = await video_element.get_attribute('src')
        if video_url:
            return video_url
    
    # 方法2：从页面数据中提取
    try:
        return await page.evaluate("""() => {
            const data = window.__SIGI_STATE__?.ItemModule?.shareInfo?.videoUrl;
            if (data) return data;
            
            const meta = document.querySelector('meta[property="og:video:secure_url"]');
            return meta?.content || null;
        }""")
    except:
        return None

async def get_video_url(url: str):
    browser = None
    try:
        browser = await init_browser()
        context = await browser.new_context(
            viewport={'width': 375, 'height': 812},
            device_scale_factor=3,
            is_mobile=True,
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.tiktok.com/"
            }
        )

        # 高级反检测
        await context.add_init_script("""
            delete navigator.__proto__.webdriver;
            Object.defineProperty(navigator, 'platform', { get: () => 'iPhone' });
            window.chrome = { runtime: {} };
        """)

        page = await context.new_page()
        
        # 处理短链接重定向
        if 'vm.tiktok.com' in url or 'vt.tiktok.com' in url:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            url = page.url

        # 加载目标页面
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # 等待视频元素加载
        try:
            await page.wait_for_selector('video', timeout=15000)
        except:
            logger.warning("未检测到video标签，尝试继续处理")

        # 获取视频URL
        video_url = await extract_video_url(page)
        if not video_url:
            raise ValueError("无法提取视频URL")

        # URL标准化
        if video_url.startswith('//'):
            video_url = 'https:' + video_url
        elif video_url.startswith('/'):
            video_url = 'https://www.tiktok.com' + video_url

        return video_url

    except Exception as e:
        logger.error(f"获取视频URL失败: {str(e)}")
        raise
    finally:
        if browser:
            await browser.close()

@app.get("/download")
async def download(
    url: str = Query(..., description="TikTok链接"),
    redirect: bool = Query(False, description="直接跳转到视频URL")
):
    try:
        logger.info(f"请求URL: {url}")
        cleaned_url = clean_tiktok_url(url)
        logger.info(f"清洗后URL: {cleaned_url}")
        
        video_url = await get_video_url(cleaned_url)
        logger.info(f"成功提取视频URL: {video_url}")

        if redirect:
            return RedirectResponse(url=video_url)
        
        return JSONResponse({
            "status": "success",
            "code": 200,
            "data": {
                "original_url": url,
                "video_url": video_url,
                "download_url": f"{video_url}?download=1",
                "expires_at": (datetime.now() + timedelta(minutes=15)).isoformat()
            },
            "meta": {
                "timestamp": datetime.now().isoformat(),
                "service": "tiktok-dl"
            }
        })

    except ValueError as e:
        logger.warning(f"客户端错误: {str(e)}")
        return JSONResponse(
            {"status": "error", "code": 400, "message": str(e)},
            status_code=400
        )
    except Exception as e:
        logger.error(f"服务器错误: {str(e)}")
        return JSONResponse(
            {"status": "error", "code": 500, "message": "视频获取失败，请稍后重试"},
            status_code=500
        )

@app.get("/")
async def health_check():
    return {"status": "healthy", "version": "2.2.0"}
