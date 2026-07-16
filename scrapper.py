"""Manga chapter scraper using Playwright.

Downloads chapter images from readberserk.com and saves them locally.
Designed to be called from a GUI (e.g. CustomTkinter) via asyncio,
typically inside a background thread with its own event loop.
"""

import base64
import logging
import os
from pathlib import Path
from typing import Callable, Optional

from playwright.async_api import async_playwright

# Defensive default: see the matching comment in app.py. Uses setdefault so
# it never overrides a value already set by app.py or the user's own shell.
_BROWSERS_DIR = Path.home() / ".manga_downloader" / "browsers"
_BROWSERS_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(_BROWSERS_DIR))

logger = logging.getLogger(__name__)

BASE_URL = "https://readberserk.com/chapter/berserk-chapter-{chapter}/"
IMAGE_SELECTOR = "img.pages__img"


def normalize_chapter(chapter: str) -> str:
    """
    Normalize a chapter identifier before it's used in a URL or folder name.

    Purely numeric chapters are zero-padded to 3 digits (e.g. "1" -> "001",
    "12" -> "012"), since the source site expects this format in the URL —
    without it, the request can silently resolve to a different chapter.
    Non-numeric identifiers (e.g. "a0", "b0", extra chapters) are left as-is.
    """
    chapter = chapter.strip()
    return chapter.zfill(3) if chapter.isdigit() else chapter


async def download_chapter(
    chapter: str,
    output_root: str = "capitulos",
    headless: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> dict:
    """
    Download all images from a manga chapter.

    Folder structure on disk is kept in Portuguese to match the rest of the
    project: <output_root>/capitulo_<chapter>/imagens/page_XXX.jpeg

    Args:
        chapter: Chapter number/identifier (e.g. "1", "42").
        output_root: Root folder where chapters are stored (default "capitulos").
        headless: Whether to run the browser headless.
        progress_callback: Optional callback(current, total) invoked after
            each image is processed. Useful for updating a GUI progress bar.

    Returns:
        dict with keys:
            success (bool): True if at least one image was downloaded.
            downloaded (int): Number of images successfully downloaded.
            total (int): Total number of images found on the page.
            output_dir (str): Path where images were saved.
            error (Optional[str]): Error message if the whole operation failed.
    """
    chapter = normalize_chapter(chapter)

    output_dir = Path(output_root) / f"capitulo_{chapter}" / "imagens"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "success": False,
        "downloaded": 0,
        "total": 0,
        "output_dir": str(output_dir),
        "error": None,
    }

    target_url = BASE_URL.format(chapter=chapter)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            logger.info("Navigating to %s", target_url)
            await page.goto(target_url, wait_until="networkidle", timeout=0)

            img_locators = page.locator(IMAGE_SELECTOR)
            count = await img_locators.count()
            result["total"] = count
            logger.info("Found %d images for chapter %s", count, chapter)

            downloaded = 0
            for i in range(count):
                img_element = img_locators.nth(i)

                img_url = await img_element.get_attribute("data-src") or await img_element.get_attribute("src")
                if not img_url:
                    logger.warning("Image %d has no src/data-src attribute, skipping", i + 1)
                    if progress_callback:
                        progress_callback(i + 1, count)
                    continue

                file_name = f"page_{i + 1:03d}.jpeg"
                file_path = output_dir / file_name

                try:
                    # Fetch is executed inside the page context so it reuses
                    # the browser's cookies/Cloudflare tokens (avoids CORS issues).
                    js_fetch_script = """
                    async (url) => {
                        const response = await fetch(url);
                        const blob = await response.blob();
                        return new Promise((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        });
                    }
                    """
                    base64_data = await page.evaluate(js_fetch_script, img_url)

                    if base64_data and "," in base64_data:
                        img_b64_clean = base64_data.split(",")[1]
                        img_bytes = base64.b64decode(img_b64_clean)

                        with open(file_path, "wb") as f:
                            f.write(img_bytes)

                        downloaded += 1
                        logger.info("Downloaded: %s", file_name)
                    else:
                        logger.error("Failed to extract image data for image %d", i + 1)

                except Exception as e:
                    logger.exception("Error processing image %d: %s", i + 1, e)

                if progress_callback:
                    progress_callback(i + 1, count)

            await browser.close()

            result["downloaded"] = downloaded
            result["success"] = downloaded > 0

    except Exception as e:
        logger.exception("Failed to download chapter %s: %s", chapter, e)
        result["error"] = str(e)

    return result