from fastapi import FastAPI, Query, HTTPException
from playwright.async_api import async_playwright
from urllib.parse import urlparse, urlunparse
import logging
import re
import httpx
from fastapi.responses import JSONResponse

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_tiktok_url(url: str) -> str:
    """彻底清洗手机端TikTok链接"""
    # 处理分享短链接（如vm.tiktok.com）
    if re.match(r'https?://vm\.tiktok\.com/', url):
        try:
            resp = httpx.head(url, follow_redirects=True)
            return resp.url.path.split('?')[0]
        except:
            return url
    
    # 处理标准链接
    parsed = urlparse(url)
    if not parsed.netloc.endswith('tiktok.com'):
        raise ValueError("非TikTok域名")
    
    # 提取核心视频路径（处理带@用户名和不带的情况）
    path_match = re.match(r'/(@[\w\.-]+)/video/(\d+)', parsed.path)
    if path_match:
        return f"https://www.tiktok.com/{path_match.group(1)}/video/{path_match.group(2)}"
    
    # 处理移动端特殊路径
    mobile_match = re.match(r'/v/(\d+)\.html', parsed.path)
    if mobile_match:
        return f"https://www.tiktok.com/@embed/video/{mobile_match.group(1)}"
    
    return url.split('?')[0]

async def get_video_url(url: str):
    async with async_playwright() as p:
        browser = None
        try:
            # 移动端真实配置
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
                ],
                timeout=120000
            )
            
            context = await browser.new_context(
                viewport={'width': 375, 'height': 812},
                device_scale_factor=3,
                is_mobile=True,
                has_touch=True,
                locale="en-US",
                timezone_id="America/Los_Angeles",
                extra_http_headers={
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.tiktok.com/"
                }
            )

            # 高级反检测
            await context.add_init_script("""
                delete navigator.__proto__.webdriver;
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            """)

            page = await context.new_page()
            logger.info(f"正在访问: {url}")
            
            # 智能等待策略
            await page.goto(url, timeout=120000, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle", timeout=30000)

            # 多层视频URL提取
            video_url = await page.evaluate("""() => {
                // 方法1：直接获取video标签
                const video = document.querySelector('video');
                if (video?.src) return video.src;
                
                // 方法2：获取视频组件数据
                const videoData = window.__SIGI_STATE__?.ItemModule?.shareInfo?.videoUrl;
                if (videoData) return videoData;
                
                // 方法3：从meta标签获取
                const meta = document.querySelector('meta[property="og:video:secure_url"]');
                return meta?.content || null;
            }""")

            if not video_url:
                raise ValueError("无法提取视频URL")

            # URL标准化处理
            if video_url.startswith("//"):
                video_url = "https:" + video_url
            elif video_url.startswith("/"):
                video_url = "https://www.tiktok.com" + video_url

            return video_url

        except Exception as e:
            logger.error(f"抓取失败: {str(e)}", exc_info=True)
            raise
        finally:
            if browser:
                await browser.close()

@app.get("/download")
async def download(url: str = Query(..., description="TikTok链接")):
    try:
        logger.info(f"收到请求: {url}")
        
        cleaned_url = clean_tiktok_url(url)
        logger.info(f"清洗后URL: {cleaned_url}")
        
        video_url = await get_video_url(cleaned_url)
        logger.info(f"成功提取: {video_url}")
        
        # 验证视频URL有效性
        async with httpx.AsyncClient() as client:
            resp = await client.head(video_url)
            if resp.status_code != 200:
                raise ValueError("视频URL无效")

        return JSONResponse({
            "status": "success",
            "code": 200,
            "data": {
                "original_url": url,
                "video_url": video_url,
                "direct_download": f"{video_url}&download=1",
                "expires_in": "10分钟"
            },
            "debug": {
                "cleaned_url": cleaned_url,
                "content_type": resp.headers.get("content-type")
            }
        })

    except ValueError as e:
        logger.warning(f"参数错误: {str(e)}")
        return JSONResponse(
            {"status": "error", "code": 400, "message": str(e)},
            status_code=400
        )
    except Exception as e:
        logger.error(f"服务器错误: {str(e)}")
        return JSONResponse(
            {"status": "error", "code": 500, "message": "视频获取失败"},
            status_code=500
        )

# 健康检查端点
@app.get("/")
async def health_check():
    return {"status": "running", "version": "2.1.0"}
