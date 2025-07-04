from fastapi import FastAPI, Query, HTTPException
from playwright.async_api import async_playwright, TimeoutError
import logging
import asyncio

app = FastAPI()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_video_url(url: str):
    async with async_playwright() as p:
        try:
            logger.info(f"Launching browser for URL: {url}")
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-gpu",
                    "--window-size=375,812",
                    "--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
                viewport={'width': 375, 'height': 812},
                device_scale_factor=3,
                is_mobile=True,
                has_touch=True,
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.tiktok.com/",
                }
            )

            await context.add_cookies([{
                'name': 'tt_webid',
                'value': 'your_random_webid_here',
                'domain': '.tiktok.com',
                'path': '/'
            }])

            page = await context.new_page()
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)

            logger.info(f"Navigating to URL: {url}")
            await page.goto(url, timeout=120000, wait_until="networkidle")
            
            # 尝试多种方式获取视频URL
            video_url = None
            try:
                await page.wait_for_selector("video", timeout=30000)
                video_url = await page.eval_on_selector("video", "el => el.src")
                if not video_url:
                    video_url = await page.eval_on_selector("video source", "el => el.src")
            except:
                logger.warning("Standard video selector not found, trying alternative methods")
                try:
                    video_element = await page.query_selector("video")
                    if video_element:
                        video_url = await video_element.get_attribute("src")
                except Exception as e:
                    logger.error(f"Error getting video URL: {str(e)}")

            if not video_url:
                raise HTTPException(status_code=404, detail="无法找到视频URL")

            logger.info(f"Successfully extracted video URL: {video_url}")
            return video_url

        except TimeoutError:
            logger.error("Timeout occurred while loading page")
            raise HTTPException(status_code=408, detail="页面加载超时")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
        finally:
            if 'browser' in locals():
                await browser.close()

@app.get("/download")
async def download(url: str = Query(..., description="TikTok 视频链接")):
    if not url.startswith(("https://www.tiktok.com/", "https://m.tiktok.com/")):
        raise HTTPException(status_code=400, detail="请输入有效的TikTok链接")
    
    try:
        video_url = await get_video_url(url)
        return {
            "status": "success",
            "video_url": video_url,
            "message": "请使用返回的URL直接下载视频"
        }
    except Exception as e:
        logger.error(f"Error in download endpoint: {str(e)}")
        raise
