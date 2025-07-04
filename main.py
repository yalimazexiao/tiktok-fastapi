from fastapi import FastAPI, Query, HTTPException
from playwright.async_api import async_playwright, TimeoutError
from urllib.parse import urlparse, urlunparse
import logging
import re

app = FastAPI()
logger = logging.getLogger(__name__)

def clean_tiktok_url(url: str) -> str:
    """清洗 TikTok 链接，去除 query 参数，保留标准格式"""
    parsed = urlparse(url)
    
    # TikTok 标准视频链接路径形如：/@user/video/12345678
    if re.match(r"^/@[\w.-]+/video/\d+$", parsed.path):
        # 保留主路径，去掉参数
        cleaned_url = urlunparse(("https", "www.tiktok.com", parsed.path, "", "", ""))
        return cleaned_url
    return url  # 不匹配就原样返回

async def get_video_url(url: str):
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-gpu",
                    "--window-size=1920,1080",
                ]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
                viewport={'width': 375, 'height': 812},
                device_scale_factor=3,
                is_mobile=True,
                locale="en-US"
            )
            page = await context.new_page()
            await page.add_init_script("""
                delete navigator.__proto__.webdriver;
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)

            print(f"开始访问页面: {url}")
            await page.goto(url, timeout=60000, wait_until="networkidle")
            await page.wait_for_selector("video", timeout=30000)

            # 获取 <video> 标签的 src 或其内部 <source> 的 src
            video_url = await page.eval_on_selector("video", "el => el.src")
            if not video_url:
                video_url = await page.eval_on_selector("video source", "el => el.src")
            
            if not video_url:
                raise HTTPException(status_code=404, detail="视频元素未找到")

            return video_url
        except TimeoutError:
            raise HTTPException(status_code=408, detail="页面加载超时或视频元素未加载")
        except Exception as e:
            logger.error(f"视频抓取失败: {str(e)}")
            raise HTTPException(status_code=500, detail="服务器错误")
        finally:
            if browser:
                await browser.close()

@app.get("/download")
async def download(url: str = Query(..., description="TikTok 视频链接")):
    cleaned_url = clean_tiktok_url(url)
    video_url = await get_video_url(cleaned_url)
    return {
        "status": "success",
        "video_url": video_url
    }
