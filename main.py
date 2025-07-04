from fastapi import FastAPI, Query, HTTPException
from playwright.async_api import async_playwright, TimeoutError
from urllib.parse import urlparse, urlunparse
import logging
import re

app = FastAPI()
logger = logging.getLogger(__name__)

def clean_tiktok_url(url: str) -> str:
    """清洗手机端TikTok链接，保留核心视频路径"""
    # 处理分享短链接（如vm.tiktok.com）
    if re.match(r'https?://vm\.tiktok\.com/', url):
        return url  # 需要后续处理
    
    parsed = urlparse(url)
    path_parts = parsed.path.split('/')
    
    # 提取用户名和视频ID
    if len(path_parts) >= 4 and path_parts[2] == 'video':
        return urlunparse((
            'https',
            'www.tiktok.com',
            f'@{path_parts[1]}/video/{path_parts[3]}',
            '', '', ''
        ))
    return url

async def get_video_url(url: str):
    async with async_playwright() as p:
        browser = None
        try:
            # 移动端浏览器配置
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 375, 'height': 812},
                device_scale_factor=3,
                is_mobile=True,
                locale="en-US"
            )

            page = await context.new_page()
            
            # 绕过自动化检测
            await page.add_init_script("""
                delete navigator.__proto__.webdriver;
            """)

            logger.info(f"正在访问: {url}")
            await page.goto(url, timeout=120000, wait_until="networkidle")
            
            # 多种方式获取视频URL
            video_url = await page.evaluate("""() => {
                const video = document.querySelector('video');
                if (video) return video.src || video.querySelector('source')?.src;
                return null;
            }""")

            if not video_url:
                raise HTTPException(status_code=404, detail="视频元素未找到")

            return video_url

        except TimeoutError:
            raise HTTPException(status_code=408, detail="页面加载超时")
        except Exception as e:
            logger.error(f"抓取错误: {str(e)}")
            raise HTTPException(status_code=500, detail="视频获取失败")
        finally:
            if browser:
                await browser.close()

@app.get("/download")
async def download(url: str = Query(..., description="TikTok链接")):
    try:
        cleaned_url = clean_tiktok_url(url)
        video_url = await get_video_url(cleaned_url)
        
        return {
            "status": "success",
            "original_url": url,
            "video_url": video_url,
            "download_tip": "复制下方URL到浏览器下载",
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15"
        }
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"接口错误: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器处理失败")
