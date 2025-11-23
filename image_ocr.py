
# =====================================================
# OCRATION - OCR Core Engine (OCR.Space) - Improved Version
# - Standard: fast, simple handwriting/printed, no overlay (performance)
# - High: complex handwriting + tables, overlay enabled (better structure)
# - Auto: standard then fallback to high if weak
#
# Tables Reconstruction:
# - Uses OCR.Space TextOverlay word coordinates (Left/Top/Width/Height)
# - Builds rows by Y clustering
# - Builds columns by X clustering (global)
# - Splits into multiple tables when large vertical gaps exist
# =====================================================

import os
import time
import hashlib
import logging
import tempfile
import shutil
from typing import Dict, Any, List, Tuple, Optional, Union
from pathlib import Path

import cv2
import numpy as np
import requests
import base64

# Import logging configuration from the project's logging module
try:
    from logging_config import setup_logging
    setup_logging()
except ImportError:
    # Fallback to basic logging if logging_config is not available
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

logger = logging.getLogger(__name__)

# Constants
OCR_SPACE_API_URL = "https://api.ocr.space/parse/image"
DEFAULT_OCR_LANGUAGE = os.environ.get("OCR_SPACE_LANGUAGE", "eng").strip() or "eng"
_CACHE_MAX_ITEMS = 128
_CACHE_EXPIRY_SECONDS = 3600  # Cache entries expire after 1 hour

# Global variables
_cache = {}        # key -> (timestamp, result)
_cache_order = []  # FIFO
_session = requests.Session()


# =========================
# Security and Configuration Functions
# =========================
def _validate_api_key(api_key: str) -> bool:
    """
    Validate the OCR.Space API key format.

    Args:
        api_key: The API key to validate

    Returns:
        bool: True if the API key appears to be valid
    """
    if not api_key:
        return False

    # Basic validation - OCR.Space keys are typically alphanumeric strings
    # Free keys are often around 10-15 chars.
    if len(api_key) < 10 or len(api_key) > 50:
        return False

    # Check if the key contains only valid characters
    if not all(c.isalnum() or c in "-_" for c in api_key):
        return False

    return True


def _safe_get_api_key() -> Optional[str]:
    """
    Safely retrieve the OCR.Space API key from environment variables.

    Returns:
        Optional[str]: The API key if available and valid, None otherwise
    """
    api_key = os.environ.get("OCR_SPACE_API_KEY")
    if api_key and _validate_api_key(api_key):
        return api_key

    logger.warning("OCR_SPACE_API_KEY is not set or invalid")
    return None


def _validate_image_path(image_path: str) -> bool:
    """
    Validate that the image path is safe and the file exists.

    Args:
        image_path: Path to the image file

    Returns:
        bool: True if the path is safe and file exists
    """
    if not image_path:
        return False

    try:
        # Convert to Path object for safer handling
        path = Path(image_path)

        # Check if the file exists
        if not path.exists() or not path.is_file():
            return False

        # Check file extension for common image formats
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        if path.suffix.lower() not in valid_extensions:
            logger.warning(f"File extension {path.suffix} may not be supported")

        # Additional security checks could be added here
        return True
    except Exception as e:
        logger.error(f"Error validating image path: {str(e)}")
        return False


def _secure_temp_file() -> str:
    """
    Create a secure temporary file path.

    Returns:
        str: Path to a secure temporary file
    """
    temp_dir = tempfile.mkdtemp()
    return os.path.join(temp_dir, f"ocr_image_{int(time.time())}.jpg")


def _cleanup_temp_file(file_path: str) -> None:
    """
    Clean up a temporary file and its parent directory if empty.

    Args:
        file_path: Path to the temporary file to clean up
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)

        # Try to remove the parent directory if it's empty
        parent_dir = os.path.dirname(file_path)
        if os.path.exists(parent_dir) and not os.listdir(parent_dir):
            os.rmdir(parent_dir)
    except Exception as e:
        logger.error(f"Error cleaning up temp file {file_path}: {str(e)}")


# =========================
# Cache Functions
# =========================
def _hash_bytes(b: bytes) -> str:
    """
    Generate a secure hash of the given bytes.

    Args:
        b: Bytes to hash

    Returns:
        str: Hexadecimal hash
    """
    return hashlib.sha256(b).hexdigest()


def _is_cache_entry_expired(timestamp: float) -> bool:
    """
    Check if a cache entry has expired.

    Args:
        timestamp: The timestamp of the cache entry

    Returns:
        bool: True if the entry has expired
    """
    return time.time() - timestamp > _CACHE_EXPIRY_SECONDS


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    """
    Get an item from the cache if it exists and hasn't expired.

    Args:
        key: Cache key

    Returns:
        Optional[Dict[str, Any]]: The cached result or None
    """
    item = _cache.get(key)
    if not item:
        return None

    timestamp, result = item
    if _is_cache_entry_expired(timestamp):
        # Remove expired entry
        _cache.pop(key, None)
        if key in _cache_order:
            _cache_order.remove(key)
        return None

    return result


def _cache_set(key: str, result: Dict[str, Any]) -> None:
    """
    Set an item in the cache, managing cache size and order.

    Args:
        key: Cache key
        result: Result to cache
    """
    if key in _cache:
        _cache[key] = (time.time(), result)
        return

    _cache[key] = (time.time(), result)
    _cache_order.append(key)

    while len(_cache_order) > _CACHE_MAX_ITEMS:
        old = _cache_order.pop(0)
        _cache.pop(old, None)


def _clean_text(text: str) -> str:
    """
    Clean extracted text but PRESERVE LAYOUT.
    Do not collapse spaces or merge lines aggressively.
    """
    if not text:
        return ""

    # Remove carriage returns but keep newlines
    text = text.replace("\r", "")

    # Just strip dragging whitespace from ends of lines, 
    # but keep the structure intact.
    lines = text.split("\n")
    cleaned_lines = [line.rstrip() for line in lines]
    
    return "\n".join(cleaned_lines).strip()


# =========================
# Image preprocessing (tuning)
# =========================
def _read_image(image_path: str) -> np.ndarray:
    """
    Read an image from the specified path.

    Args:
        image_path: Path to the image file

    Returns:
        np.ndarray: The loaded image

    Raises:
        FileNotFoundError: If the image file doesn't exist
        ValueError: If the image cannot be read
    """
    if not _validate_image_path(image_path):
        raise FileNotFoundError(f"Invalid or non-existent image path: {image_path}")

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Failed to read image: {image_path}")

    return img


def _clahe(gray: np.ndarray) -> np.ndarray:
    """
    Apply Contrast Limited Adaptive Histogram Equalization to a grayscale image.

    Args:
        gray: Grayscale image

    Returns:
        np.ndarray: Enhanced image
    """
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _resize_keep_aspect(img: np.ndarray, target_long: int) -> np.ndarray:
    """
    Resize an image while maintaining aspect ratio.

    Args:
        img: Input image
        target_long: Target length of the longer side

    Returns:
        np.ndarray: Resized image
    """
    h, w = img.shape[:2]
    long_side = max(h, w)

    if long_side <= target_long:
        return img

    scale = float(target_long) / float(long_side)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _upscale_if_small(img: np.ndarray, min_long: int) -> np.ndarray:
    """
    Upscale an image if its longest side is smaller than the specified minimum.

    Args:
        img: Input image
        min_long: Minimum length for the longer side

    Returns:
        np.ndarray: Potentially upscaled image
    """
    h, w = img.shape[:2]
    long_side = max(h, w)

    if long_side >= min_long:
        return img

    scale = float(min_long) / float(long_side)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def _prep_standard(img: np.ndarray) -> np.ndarray:
    """
    Apply standard preprocessing to an image for OCR.

    Args:
        img: Input image

    Returns:
        np.ndarray: Preprocessed grayscale image
    """
    img = _resize_keep_aspect(img, target_long=1800)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = _clahe(gray)
    gray = cv2.fastNlMeansDenoising(gray, None, h=8, templateWindowSize=7, searchWindowSize=21)
    return gray


def _prep_high(img: np.ndarray) -> np.ndarray:
    """
    Apply high-quality preprocessing. KEEP RGB.
    """
    img = _resize_keep_aspect(img, target_long=2200)
    img = _upscale_if_small(img, min_long=1600)
    # Simple bilateral to clean noise without destroying color edges
    img = cv2.bilateralFilter(img, d=5, sigmaColor=35, sigmaSpace=35)
    return img


def _prep_extreme(img: np.ndarray) -> np.ndarray:
    """
    Maximum quality. KEEP RGB.
    """
    img = _resize_keep_aspect(img, target_long=2200)
    img = _upscale_if_small(img, min_long=1800)
    
    # Just a light bilateral filter to remove grain, keep original structure
    img = cv2.bilateralFilter(img, d=7, sigmaColor=40, sigmaSpace=40)
    
    return img


def _encode_image_bytes(img: np.ndarray, max_bytes: int = 950_000, use_png: bool = True) -> bytes:
    """
    Encode image to bytes.
    """
    if use_png:
        ok, buf = cv2.imencode(".png", img)
        if ok and len(buf.tobytes()) <= max_bytes:
             return buf.tobytes()
    
    # Fallback to JPG
    quality = 85
    while quality >= 30:
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        data = buf.tobytes()
        if ok and len(data) <= max_bytes:
            return data
        quality -= 10
    
    return data if ok else b""



def _prepare_image_bytes(image_path: str, mode: str) -> Tuple[bytes, str]:
    """
    Prepare an image for OCR by applying preprocessing and encoding to bytes.

    Args:
        image_path: Path to the image file
        mode: Preprocessing mode ("standard" or "high")

    Returns:
        Tuple[bytes, str]: Image bytes and hash of the bytes
    """
    img = _read_image(image_path)

    if mode == "extreme":
        processed = _prep_extreme(img)
    elif mode == "high":
        processed = _prep_high(img)
    else:
        processed = _prep_standard(img)

    b = _encode_image_bytes(processed)
    return b, _hash_bytes(b)


# =========================
# OCR.Space Call (retry)
# =========================
def _call_ocr_space(image_bytes: bytes, language: str, high_quality: bool) -> Dict[str, Any]:
    """
    Call the OCR.Space API with retry logic.

    Args:
        image_bytes: Image bytes to process
        language: Language code for OCR
        high_quality: Whether to use high-quality settings

    Returns:
        Dict[str, Any]: API response or error information
    """
    api_key = _safe_get_api_key()
    if not api_key:
        return {"IsErroredOnProcessing": True, "ErrorMessage": "OCR_SPACE_API_KEY not set or invalid"}

    payload = {
        "apikey": api_key,
        "language": language,
        "OCREngine": 2,  # Always use Engine 2 (Advanced AI, best quality)
        "scale": True,
        "detectOrientation": True,
        "isTable": True if high_quality else False,
        "isOverlayRequired": True,  # ALWAYS TRUE to support layout preservation
    }

    logger.info(f"Sending OCR request (Multipart)... Bytes: {len(image_bytes)}")
    
    # Detect MIME type
    mime = "image/png" if image_bytes.startswith(b"\x89PNG") else "image/jpeg"
    ext = "png" if "png" in mime else "jpg"
    
    files = {"file": (f"image.{ext}", image_bytes, mime)}

    retries = 2 if high_quality else 1
    backoff = 1.4
    
    # FIRST ATTEMPT: Engine 2 (Advanced) - Optimized for RGB/Table
    payload["OCREngine"] = 2
    
    # Engine 2 Configuration: Force maximum accuracy features
    # These override 'high_quality' checks because the User explicitly requested
    # "most effective OCR engine" and "exact layout" preservation.
    payload["scale"] = True
    payload["detectOrientation"] = True
    payload["isTable"] = True
    
    for attempt in range(retries + 1):
        try:
            timeout = 55 if high_quality else 40 # Increased base timeout for strict mode
            resp = _session.post(OCR_SPACE_API_URL, data=payload, files=files, timeout=timeout)

            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt < retries:
                    time.sleep(backoff * (attempt + 1))
                    continue
                return {"IsErroredOnProcessing": True, "ErrorMessage": f"OCR.Space HTTP {resp.status_code}"}

            resp.raise_for_status()
            data = resp.json()
            
            # Check for processing error
            if data.get("IsErroredOnProcessing"):
                 err_msg = str(data.get("ErrorMessage"))
                 logger.error(f"Engine 2 Error: {err_msg}")
                 # NO FALLBACK to Engine 1 (User Request). Return raw error.
                 return data

            return data

        except requests.RequestException as e:
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
                continue
            return {"IsErroredOnProcessing": True, "ErrorMessage": str(e)}

    return {"IsErroredOnProcessing": True, "ErrorMessage": "Unknown OCR.Space error"}


# =========================
# Overlay -> words
# =========================
def _extract_words_from_overlay(parsed_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract words with coordinates from OCR overlay data.
    """
    overlay = parsed_result.get("TextOverlay")
    if not isinstance(overlay, dict):
        return []

    lines = overlay.get("Lines") or []
    words_out = []

    for line in lines:
        words = line.get("Words") or []
        for w in words:
            try:
                text = (w.get("WordText") or "").strip()
                if not text:
                    continue

                left = int(w.get("Left", 0))
                top = int(w.get("Top", 0))
                width = int(w.get("Width", 0))
                height = int(w.get("Height", 0))
                cx = left + width / 2.0
                cy = top + height / 2.0

                words_out.append({
                    "text": text,
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                    "cx": cx,
                    "cy": cy
                })
            except Exception as e:
                logger.warning(f"Error extracting word from overlay: {str(e)}")
                continue

    return words_out


def _median(values: List[float], default: float = 10.0) -> float:
    """
    Calculate the median of a list of values.
    """
    if not values:
        return default

    s = sorted(values)
    n = len(s)
    mid = n // 2

    if n % 2 == 1:
        return float(s[mid])

    return float((s[mid - 1] + s[mid]) / 2.0)


# =========================
# Table reconstruction from word coordinates
# =========================
def _cluster_rows(words: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Cluster words into rows based on their Y coordinates.
    """
    if not words:
        return []

    heights = [max(1, float(w["height"])) for w in words]
    med_h = _median(heights, default=12.0)
    tol = max(6.0, med_h * 0.65)  # y tolerance to be same row

    words_sorted = sorted(words, key=lambda x: x["cy"])
    rows = []
    current = []
    current_y = None

    for w in words_sorted:
        if current_y is None:
            current = [w]
            current_y = w["cy"]
            continue

        if abs(w["cy"] - current_y) <= tol:
            current.append(w)
            # smooth update
            current_y = (current_y * 0.7) + (w["cy"] * 0.3)
        else:
            rows.append(current)
            current = [w]
            current_y = w["cy"]

    if current:
        rows.append(current)

    # sort each row by x
    for r in rows:
        r.sort(key=lambda x: x["cx"])

    return rows


def _cluster_columns_global(rows: List[List[Dict[str, Any]]]) -> List[float]:
    """
    Identify column positions globally across all rows.
    """
    words = [w for r in rows for w in r]
    if not words:
        return []

    widths = [max(1.0, float(w["width"])) for w in words]
    med_w = _median(widths, default=20.0)

    x_centers = sorted([float(w["cx"]) for w in words])
    if not x_centers:
        return []

    # gap threshold - if gap > threshold => new column
    gap_th = max(14.0, med_w * 0.95)

    cols = []
    cluster = [x_centers[0]]

    for x in x_centers[1:]:
        if abs(x - cluster[-1]) <= gap_th:
            cluster.append(x)
        else:
            cols.append(sum(cluster) / len(cluster))
            cluster = [x]

    if cluster:
        cols.append(sum(cluster) / len(cluster))

    # avoid too many columns noise: merge very close centers
    cols_sorted = sorted(cols)
    merged = []
    merge_th = max(10.0, med_w * 0.6)

    for c in cols_sorted:
        if not merged:
            merged.append(c)
        else:
            if abs(c - merged[-1]) <= merge_th:
                merged[-1] = (merged[-1] + c) / 2.0
            else:
                merged.append(c)

    return merged


def _assign_words_to_columns(row: List[Dict[str, Any]], col_centers: List[float]) -> List[str]:
    """
    Assign words in a row to columns based on column centers.
    """
    if not col_centers:
        # fallback: just join row words
        return [" ".join([w["text"] for w in row]).strip()]

    n = len(col_centers)
    cells = [[] for _ in range(n)]

    for w in row:
        cx = float(w["cx"])
        # nearest column center
        best_i = min(range(n), key=lambda i: abs(cx - col_centers[i]))
        cells[best_i].append(w)

    # inside each cell, sort by x and join
    out = []
    for ws in cells:
        ws.sort(key=lambda x: x["cx"])
        out.append(" ".join([x["text"] for x in ws]).strip())

    return out


def _split_tables_by_vertical_gaps(rows: List[List[Dict[str, Any]]]) -> List[List[List[Dict[str, Any]]]]:
    """
    Split row-groups into multiple tables when there are large vertical gaps.
    """
    if not rows:
        return []

    heights = [max(1.0, float(w["height"])) for r in rows for w in r]
    med_h = _median(heights, default=12.0)

    # compute row y centers
    row_cy = []
    for r in rows:
        cy = sum([w["cy"] for w in r]) / max(1, len(r))
        row_cy.append(cy)

    split_th = max(40.0, med_h * 3.2)  # if gap between rows > this -> new table

    tables = []
    current = [rows[0]]

    for i in range(1, len(rows)):
        gap = abs(row_cy[i] - row_cy[i - 1])
        if gap >= split_th and len(current) >= 2:
            tables.append(current)
            current = [rows[i]]
        else:
            current.append(rows[i])

    if current:
        tables.append(current)

    return tables


def _reconstruct_tables_from_overlay_words(words: List[Dict[str, Any]]) -> List[List[List[str]]]:
    """
    Reconstruct tables using a 'Visual Grid' approach (Projection Profile).
    This ensures that columns are consistently detected even if some cells are empty.
    """
    if not words:
        return []

    # 1. Cluster words into Rows based on Y-position
    rows = _cluster_rows(words)
    if not rows:
        return []

    # 2. Split into distinct tables if huge vertical gaps exist
    table_row_groups = _split_tables_by_vertical_gaps(rows)
    tables_out: List[List[List[str]]] = []

    for group in table_row_groups:
        if not group: continue
        
        # --- Visual Grid Construction ---
        # 3. Determine Column Boundaries (X-Projection)
        # Gather all word horizontal intervals
        intervals = []
        for r in group:
            for w in r:
                intervals.append((w["left"], w["left"] + w["width"]))
        
        if not intervals:
            continue
            
        # Determine canvas width
        max_x = int(max(end for _, end in intervals))
        
        # Create a histogram of occupied pixels
        # (Using a simple coordinate array)
        occupied = np.zeros(max_x + 50, dtype=np.int32)
        for (start, end) in intervals:
            occupied[int(start):int(end)] += 1
            
        # Smooth the histogram to bridge small intra-word gaps
        # Increased to 30 to better handle word spacing in high-res images
        kernel_size = 30 # px
        kernel = np.ones(kernel_size)
        smooth = np.convolve(occupied, kernel, mode='same')
        
        # Find peaks (columns) and valleys (separators)
        # Threshold: meaningful column must have significant overlap
        # LOWERED to 0.05 (5%) to catch very sparse columns (e.g. checked checkboxes)
        threshold =  len(group) * 0.05
        if threshold < 1: threshold = 0.5
        
        cols_mask = smooth > threshold
        
        # Extract column segments from the mask
        column_segments = []
        in_col = False
        start = 0
        for x, val in enumerate(cols_mask):
            if val and not in_col:
                in_col = True
                start = x
            elif not val and in_col:
                in_col = False
                column_segments.append((start, x))
        if in_col: column_segments.append((start, len(cols_mask)))
        
        # If no columns detected (rare), fallback to single block
        if not column_segments:
            column_segments = [(0, max_x)]
            
        # 4. Map Words to Grid Cells
        # Structure: grid[row_idx][col_idx] = List[words]
        grid = [[[] for _ in column_segments] for _ in range(len(group))]
        
        for r_idx, r in enumerate(group):
            for w in r:
                cx = w["cx"]
                # Find which column segment this word belongs to
                best_c = -1
                min_dist = float('inf')
                
                for c_idx, (c_start, c_end) in enumerate(column_segments):
                    c_center = (c_start + c_end) / 2
                    # simple check: is cx within segment?
                    if c_start <= cx <= c_end:
                        best_c = c_idx
                        break
                    # fallback: distance
                    dist = abs(cx - c_center)
                    if dist < min_dist:
                        min_dist = dist
                        best_c = c_idx
                
                if best_c != -1:
                    grid[r_idx][best_c].append(w)
                    
        # 5. Build Final String Table
        table_rows = []
        for r_full in grid:
            row_strs = []
            is_empty_row = True
            for cell_words in r_full:
                if not cell_words:
                    row_strs.append("")
                else:
                    is_empty_row = False
                    # Sort words x-wise within the cell
                    cell_words.sort(key=lambda w: w["left"])
                    row_strs.append(" ".join([w["text"] for w in cell_words]))
            
            if not is_empty_row:
                table_rows.append(row_strs)

        if len(table_rows) >= 2:
            tables_out.append(table_rows)

    return tables_out



def _reconstruct_physical_layout(words: List[Dict[str, Any]]) -> str:
    """
    Reconstruct text using a FIXED GRID approach (ASCII Art style).
    This maps the image coordinates to a fixed character grid (e.g., 150 chars wide).
    This guarantees vertical alignment for tables regardless of font size variations.
    """
    if not words:
        return ""
        
    # 1. Cluster into rows (Standard Y-clustering)
    heights = [w["height"] for w in words]
    avg_height = sum(heights) / len(heights) if heights else 15
    y_threshold = avg_height * 0.5 

    words_sorted = sorted(words, key=lambda w: w["top"])
    rows = []
    current_row = []
    current_y = 0
    
    for w in words_sorted:
        cy = w["top"] + (w["height"] / 2)
        if not current_row:
            current_row.append(w)
            current_y = cy
            continue
        if abs(cy - current_y) < y_threshold:
            current_row.append(w)
            n = len(current_row)
            current_y = (current_y * (n - 1) + cy) / n
        else:
            rows.append(current_row)
            current_row = [w]
            current_y = cy
    if current_row:
        rows.append(current_row)

    # 2. Adaptive Spacing Strategy (The "Organic" Approach)
    # Instead of forcing a grid, we respect the relative pixel gaps.
    
    # Global char width estimate
    char_widths = []
    for w in words:
        if len(w["text"]) > 0:
            char_widths.append(w["width"] / len(w["text"]))
    
    if char_widths:
        char_widths.sort()
        global_char_w = char_widths[len(char_widths)//2]
    else:
        global_char_w = 12
        
    # Use a slightly tighter global width to ensure enough spaces are inserted
    # This prevents columns from drifting left.
    global_char_w = max(4, global_char_w * 0.95)
    
    lines = []
    
    for row in rows:
        # Sort by Left
        row.sort(key=lambda w: w["left"])
        
        line_str = ""
        current_pixel_x = min_x
        
        # Use local row statistics if possible for best "line-level" fidelity
        # Unless it's weird, then use global partial fallback
        row_widths = [w["width"]/len(w["text"]) for w in row if len(w["text"])>0]
        if row_widths:
            row_widths.sort()
            local_char_w = row_widths[len(row_widths)//2]
        else:
            local_char_w = global_char_w
        
        local_char_w = max(4, local_char_w)
        
        for i, w in enumerate(row):
            text = w["text"]
            
            # Calculate gap from previous word end
            # We treat the first word as having a gap from the left margin
            if i == 0:
                pixel_gap = max(0, w["left"] - min_x)
            else:
                pixel_gap = max(0, w["left"] - current_pixel_x)
            
            # Determine spaces count
            # Use a slightly aggressive divider (0.6 * char width)
            # This ensures that even small gaps get at least 1 space.
            # We do NOT merge.
            spaces_count = int(pixel_gap / (local_char_w * 0.9))
            
            # Safety: If words are logically separate (i > 0), ensure at least 1 space 
            # if the pixel gap is "visible" (e.g. >= 2px).
            # The User said "don't delete any space".
            # We trust the calculation unless it's overlapping.
            
            if i > 0 and spaces_count == 0 and pixel_gap > 2:
                 spaces_count = 1
            
            line_str += " " * spaces_count
            line_str += text
            
            current_pixel_x = w["left"] + w["width"]
            
        lines.append(line_str)
        
    return "\n".join(lines)


# =========================
# Parse OCR.Space response
# =========================
def _parse_ocr_space(data: Dict[str, Any], want_tables: bool) -> Dict[str, Any]:
    """
    Parse the response from OCR.Space API.
    """
    if not isinstance(data, dict):
        return {"error": "Invalid response", "text": "", "tables": []}

    if data.get("IsErroredOnProcessing"):
        err = data.get("ErrorMessage") or "OCR.Space processing error"
        return {"error": str(err), "text": "", "tables": []}

    results = data.get("ParsedResults") or []
    if not results:
        return {"text": "", "tables": []}

    first = results[0] or {}
    
    # Try Layout Reconstruction first (Preferred)
    parsed_text = ""
    words = _extract_words_from_overlay(first)
    
    if words:
        try:
            parsed_text = _reconstruct_physical_layout(words)
        except Exception as e:
            logger.error(f"Layout reconstruction failed: {e}")
            parsed_text = ""

    # Fallback to standard reading order if reconstruction returned nothing
    if not parsed_text:
        parsed_text = _clean_text(first.get("ParsedText", "") or "")

    tables: List[List[List[str]]] = []
    if want_tables:
        if not words: # Extract if not already done
             words = _extract_words_from_overlay(first)
        tables = _reconstruct_tables_from_overlay_words(words)

    return {"text": parsed_text, "tables": tables}


def _looks_weak(text: str) -> bool:
    """
    Determine if extracted text appears to be weak/low quality.

    Args:
        text: Extracted text

    Returns:
        bool: True if the text appears weak
    """
    if not text:
        return True

    t = text.strip()
    if len(t) < 25:
        return True

    return False


# =========================
# Public API
# =========================
def extract_text_from_path(image_path: str, mode: str = "standard", language: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract text from an image file using OCR.Space API.

    Args:
        image_path: Path to the image file
        mode: Processing mode ("standard", "high", or "auto")
        language: Language code for OCR (optional). Default from OCR_SPACE_LANGUAGE env.

    Returns:
        Dict[str, Any]: Result containing text and optionally tables

    Example:
        >>> result = extract_text_from_path("document.jpg", mode="high", language="eng")
        >>> print(result["text"])
        >>> for table in result["tables"]:
        ...     for row in table:
        ...         print("\t".join(row))
    """
    # Validate inputs
    if not _validate_image_path(image_path):
        return {"error": "Invalid image path", "text": "", "tables": []}

    lang = (language or DEFAULT_OCR_LANGUAGE).strip().lower() or "eng"
    if lang not in ("eng", "ara"):
        lang = "eng"
        logger.warning(f"Unsupported language '{language}', defaulting to 'eng'")

    mode = (mode or "standard").strip().lower()
    if mode not in ("standard", "high", "extreme", "auto"):
        mode = "standard"
        logger.warning(f"Unsupported mode '{mode}', defaulting to 'standard'")

    def run(which: str, high_quality: bool) -> Dict[str, Any]:
        """Internal function to run OCR with specified settings."""
        try:
            image_bytes, h = _prepare_image_bytes(image_path, which)
            cache_key = f"{h}:{lang}:{which}"
            cached = _cache_get(cache_key)
            if cached is not None:
                return cached

            raw = _call_ocr_space(image_bytes=image_bytes, language=lang, high_quality=high_quality)
            parsed = _parse_ocr_space(raw, want_tables=high_quality)

            _cache_set(cache_key, parsed)
            return parsed
        except Exception as e:
            logger.error(f"Error in OCR processing: {str(e)}")
            return {"error": str(e), "text": "", "tables": []}

    if mode == "standard":
        return run("standard", high_quality=False)
    if mode == "extreme":
        # Extreme mode always uses high_quality logic + 5 retries
        return run("extreme", high_quality=True)

    if mode == "high":
        return run("high", high_quality=True)

    # auto mode: try standard first, fall back to high if needed
    std = run("standard", high_quality=False)
    if std.get("error"):
        logger.info("Standard OCR failed, trying high quality")
        return run("high", high_quality=True)

    if _looks_weak(std.get("text", "")):
        logger.info("Standard OCR result appears weak, trying high quality")
        hi = run("high", high_quality=True)
        # choose better text
        if not hi.get("error") and len(hi.get("text", "")) > len(std.get("text", "")):
            return hi
        return std

    return std


# Legacy compatibility functions (if needed)
# These functions maintain compatibility with the original interface
def extract_text_from_image(image: Union[str, np.ndarray], mode: str = "standard", language: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract text from an image (file path or numpy array).

    Args:
        image: Path to image file or numpy array
        mode: Processing mode
        language: Language code

    Returns:
        Dict[str, Any]: OCR result
    """
    if isinstance(image, np.ndarray):
        # Save numpy array to temporary file
        temp_file = _secure_temp_file()
        try:
            cv2.imwrite(temp_file, image)
            result = extract_text_from_path(temp_file, mode, language)
            return result
        finally:
            _cleanup_temp_file(temp_file)
    else:
        # Assume it's a file path
        return extract_text_from_path(image, mode, language)


def read_image(image_path: str) -> np.ndarray:
    """
    Read an image from file.

    Args:
        image_path: Path to the image file

    Returns:
        np.ndarray: Loaded image
    """
    return _read_image(image_path)


def enhance_image(image: np.ndarray, mode: str = "standard") -> np.ndarray:
    """
    Enhance an image for better OCR results.

    Args:
        image: Input image
        mode: Enhancement mode

    Returns:
        np.ndarray: Enhanced image
    """
    if mode == "high":
        return _prep_high(image)
    else:
        return _prep_standard(image)


def get_hocr(image_path: str, language: Optional[str] = None) -> Dict[str, Any]:
    """
    Get hOCR format results from an image.

    Args:
        image_path: Path to the image file
        language: Language code

    Returns:
        Dict[str, Any]: OCR result in hOCR format
    """
    # This is a placeholder - hOCR functionality would need to be implemented
    # based on the OCR.Space API capabilities
    result = extract_text_from_path(image_path, mode="high", language=language)
    return {"hocr": result["text"], "error": result.get("error")}


def parse_hocr(hocr_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse hOCR data.

    Args:
        hocr_data: hOCR data

    Returns:
        Dict[str, Any]: Parsed data
    """
    # This is a placeholder - actual hOCR parsing would need to be implemented
    return {"text": hocr_data.get("hocr", ""), "error": hocr_data.get("error")}


def clean_extracted_text(text: str) -> str:
    """
    Clean extracted text.

    Args:
        text: Raw text

    Returns:
        str: Cleaned text
    """
    return _clean_text(text)


def extract_emails(text: str) -> List[str]:
    """
    Extract email addresses from text.

    Args:
        text: Text to search

    Returns:
        List[str]: Found email addresses
    """
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(email_pattern, text)


def save_in_all_formats(text: str, output_dir: str, base_name: str) -> Dict[str, str]:
    """
    Save text in multiple formats.

    Args:
        text: Text to save
        output_dir: Output directory
        base_name: Base name for files

    Returns:
        Dict[str, str]: Paths to saved files
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    paths = {}

    # Save as plain text
    txt_path = os.path.join(output_dir, f"{base_name}.txt")
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text)
    paths["txt"] = txt_path

    # Save as JSON
    import json
    json_path = os.path.join(output_dir, f"{base_name}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({"text": text}, f, ensure_ascii=False, indent=2)
    paths["json"] = json_path

    return paths
