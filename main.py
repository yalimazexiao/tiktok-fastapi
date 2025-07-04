from fastapi import FastAPI, Query, HTTPException
from playwright.async_api import async_playwright, TimeoutError
import asyncio

app = FastAPI()

async def get_video_url(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-gpu",
                "--window-size=1920,1080"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        try:
            await page.goto(url, timeout=60000, wait_until="load")
            await page.wait_for_selector("video", timeout=30000)
            video_url = await page.eval_on_selector("video", "el => el.src")
            if not video_url:
                video_url = await page.eval_on_selector("video source", "el => el.src")
            await browser.close()
            return video_url
        except TimeoutError:
            await browser.close()
            raise HTTPException(status_code=408, detail="页面加载超时或视频元素未加载")
        except Exception as e:
            await browser.close()
            raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

@app.get("/download")
async def download(url: str = Query(..., description="TikTok 视频链接")):
    video_url = await get_video_url(url)
    return {"video_url": video_url}
