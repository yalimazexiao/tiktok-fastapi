from fastapi import FastAPI, Query, HTTPException
from playwright.async_api import async_playwright, TimeoutError
from urllib.parse import urlparse, urlunparse
import re

app = FastAPI()

def clean_tiktok_url(url: str) -> str:
    """提取出标准 TikTok 视频链接格式"""
    match = re.search(r'(https?://)?(www|vm)?\.?tiktok\.com/.+?/video/(\d+)', url)
    if match:
        user = re.search(r'@([^/?]+)/video', url)
        username = user.group(1) if user else 'user'
        video_id = match.group(3)
        return f"https://www.tiktok.com/@{username}/video/{video_id}"
    return url

async def get_video_url(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = await browser.new_context(
            viewport={'width': 375, 'height': 812},
            device_scale_factor=3,
            is_mobile=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15"
        )
        page = await context.new_page()

        await page.add_init_script("""
            delete navigator.__proto__.webdriver;
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        try:
            await page.goto(url, timeout=90000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)  # 等待资源加载
            await page.wait_for_selector("video", timeout=15000)
            video_url = await page.eval_on_selector("video", "el => el.src")
            if not video_url:
                video_url = await page.eval_on_selector("video source", "el => el.src")
            return video_url
        except TimeoutError:
            raise HTTPException(status_code=408, detail="页面加载超时或视频元素未加载")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"视频解析失败: {str(e)}")
        finally:
            await browser.close()

@app.get("/download")
async def download(url: str = Query(..., description="TikTok 视频链接")):
    cleaned_url = clean_tiktok_url(url)
    video_url = await get_video_url(cleaned_url)
    if not video_url:
        raise HTTPException(status_code=404, detail="未找到视频链接")
    return {
        "status": "success",
        "video_url": video_url,
        "tip": "请复制链接到浏览器下载"
    }
