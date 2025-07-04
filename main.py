from fastapi import FastAPI, Query, HTTPException
from playwright.async_api import async_playwright, TimeoutError
import asyncio

app = FastAPI()

async def download_tiktok_video(url: str):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 隐藏 webdriver 特征
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

        try:
            await page.goto(url, timeout=60000, wait_until="networkidle")
        except TimeoutError:
            await browser.close()
            raise HTTPException(status_code=408, detail="页面加载超时，可能被验证码阻拦或网络慢")

        try:
            await page.wait_for_selector("video", timeout=15000)
            video_url = await page.eval_on_selector("video", "el => el.src")
        except TimeoutError:
            await browser.close()
            raise HTTPException(status_code=404, detail="页面没有找到视频元素，可能页面被验证码阻拦")

        await browser.close()
        return video_url

@app.get("/download")
async def download(url: str = Query(..., description="TikTok 视频链接")):
    video_link = await download_tiktok_video(url)
    return {"video_url": video_link}
