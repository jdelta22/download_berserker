"""Convert downloaded manga chapter images into PDF files."""

import logging
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import img2pdf
from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_DPI = 96  # force fixed DPI, ignoring (possibly wrong) JPEG metadata


def is_valid_image(path: Path, min_size_px: int = 10) -> Tuple[bool, Optional[str]]:
    """Check whether an image opens correctly and has a reasonable size."""
    try:
        with Image.open(path) as img:
            img.verify()  # detects corruption
        with Image.open(path) as img:  # reopen since verify() invalidates the object
            w, h = img.size
            if w < min_size_px or h < min_size_px:
                return False, f"dimensions too small ({w}x{h})"
        return True, None
    except Exception as e:
        return False, f"corrupted or unreadable ({e})"


def convert_chapter_to_pdf(chapter_dir: Path, dpi: int = DEFAULT_DPI) -> dict:
    """
    Convert a single chapter's images into a PDF.

    Args:
        chapter_dir: Path to the chapter folder (must contain an "imagens" subfolder,
            e.g. capitulos/capitulo_001/imagens).
        dpi: Fixed DPI to use for the PDF layout.

    Returns:
        dict with keys:
            success (bool)
            pdf_path (Optional[str])
            total_images (int)
            valid_images (int)
            error (Optional[str])
    """
    result = {
        "success": False,
        "pdf_path": None,
        "total_images": 0,
        "valid_images": 0,
        "error": None,
    }

    images_dir = chapter_dir / "imagens"
    if not images_dir.is_dir():
        msg = f"'images' folder not found in {chapter_dir.name}"
        logger.warning(msg)
        result["error"] = msg
        return result

    images = sorted(images_dir.glob("page_*.jpeg"))
    result["total_images"] = len(images)
    if not images:
        msg = f"No images found in {chapter_dir.name}"
        logger.warning(msg)
        result["error"] = msg
        return result

    valid_images: List[Path] = []
    for img in images:
        ok, reason = is_valid_image(img)
        if ok:
            valid_images.append(img)
        else:
            logger.warning("%s: skipping %s — %s", chapter_dir.name, img.name, reason)

    result["valid_images"] = len(valid_images)
    if not valid_images:
        msg = f"No valid images left after check in {chapter_dir.name}"
        logger.warning(msg)
        result["error"] = msg
        return result

    pdf_path = chapter_dir / f"{chapter_dir.name}.pdf"

    try:
        layout_fun = img2pdf.get_layout_fun(None, None, None, None, dpi)
        with open(pdf_path, "wb") as pdf:
            pdf.write(
                img2pdf.convert(
                    [str(img) for img in valid_images],
                    dpi=dpi,
                    layout_fun=layout_fun,
                )
            )
        logger.info(
            "Created: %s (%d/%d pages)",
            pdf_path,
            len(valid_images),
            len(images),
        )
        result["success"] = True
        result["pdf_path"] = str(pdf_path)

    except Exception as e:
        logger.exception("Failed to convert %s: %s", chapter_dir.name, e)
        result["error"] = str(e)

    return result


def convert_all_chapters(
    chapters_root: str = "capitulos",
    dpi: int = DEFAULT_DPI,
    progress_callback: Optional[Callable[[int, int, dict], None]] = None,
) -> List[dict]:
    """
    Convert every chapter found under chapters_root into a PDF.

    Args:
        chapters_root: Root folder containing chapter subfolders (default "capitulos").
        dpi: Fixed DPI to use for the PDF layout.
        progress_callback: Optional callback(current, total, chapter_result)
            invoked after each chapter is processed. Useful for a GUI progress bar.

    Returns:
        List of result dicts, one per chapter (same shape as convert_chapter_to_pdf).
    """
    root = Path(chapters_root)
    chapter_dirs = [d for d in root.iterdir() if d.is_dir()] if root.is_dir() else []
    results = []

    total = len(chapter_dirs)
    for i, chapter_dir in enumerate(chapter_dirs, start=1):
        res = convert_chapter_to_pdf(chapter_dir, dpi=dpi)
        results.append(res)
        if progress_callback:
            progress_callback(i, total, res)

    return results