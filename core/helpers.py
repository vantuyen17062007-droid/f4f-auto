"""
core/helpers.py — Tiện ích dùng chung trong toàn bộ hệ thống
============================================================
Bao gồm:
  - Mã màu ANSI cho terminal
  - Hàm in banner nhận diện
  - Trích xuất Video ID và mở rộng short link TikTok
  - Quét & phân giải thiết bị ADB kết nối
"""

import os
import re
import sys
import subprocess
import urllib.request
from typing import Optional, Tuple, List

# Đảm bảo hiển thị UTF-8 trên Windows console
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _supports_color() -> bool:
    """Chỉ bật ANSI khi stdout là terminal thật và người dùng không tắt màu."""
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return bool(sys.stdout and sys.stdout.isatty())
    except Exception:
        return False


_COLOR_ENABLED = _supports_color()

# Mã màu Terminal (rỗng khi output bị redirect/pipe để log sạch)
CYAN = "\033[96m" if _COLOR_ENABLED else ""
GREEN = "\033[92m" if _COLOR_ENABLED else ""
YELLOW = "\033[93m" if _COLOR_ENABLED else ""
RED = "\033[91m" if _COLOR_ENABLED else ""
WHITE = "\033[97m" if _COLOR_ENABLED else ""
BOLD = "\033[1m" if _COLOR_ENABLED else ""
DIM = "\033[2m" if _COLOR_ENABLED else ""
RESET = "\033[0m" if _COLOR_ENABLED else ""

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Loại bỏ mã màu ANSI khỏi chuỗi (dùng cho file log)."""
    return ANSI_RE.sub("", str(text))


def get_connected_devices() -> List[str]:
    """Lấy danh sách các thiết bị ADB đang kết nối ở trạng thái 'device'."""
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        devices = []
        for line in res.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except Exception:
        return []


def resolve_device(preferred_serial: Optional[str] = None) -> Optional[str]:
    """
    Tự động phân giải thiết bị ADB phù hợp:
    - Nếu serial là IP:port chưa kết nối -> tự động chạy adb connect.
    - Nếu có thiết bị đang online -> trả về serial đầu tiên.
    - Nếu người dùng chỉ định serial cụ thể nhưng không tìm thấy, KHÔNG tự ý
      dùng thiết bị khác; trả về serial đó để tầng kết nối báo lỗi rõ ràng.
    """
    devices = get_connected_devices()

    if preferred_serial and preferred_serial != "auto":
        if preferred_serial in devices:
            return preferred_serial
        if ":" in preferred_serial:
            try:
                subprocess.run(["adb", "connect", preferred_serial], capture_output=True, timeout=5)
                devices = get_connected_devices()
                if preferred_serial in devices:
                    return preferred_serial
            except Exception:
                pass
        # Không fallback sang thiết bị khác: tránh thao tác nhầm máy.
        return preferred_serial

    if devices:
        return devices[0]

    return None


def extract_handle(target: str) -> Optional[str]:
    """Trích xuất username/handle từ URL hoặc chuỗi @handle."""
    text = str(target or "").strip()
    match = re.search(r"@([A-Za-z0-9_.-]+)", text)
    if match:
        return match.group(1)
    if text and "/" not in text and not text.isdigit():
        return text.lstrip("@")
    return None


def resolve_video_id(target_url_or_id: str) -> Tuple[Optional[str], str]:
    """
    Trích xuất Video ID và Full URL từ link hoặc ID thuần túy:
    - Hỗ trợ: https://www.tiktok.com/@user/video/123456789
    - Hỗ trợ short URL: https://vt.tiktok.com/... hoặc vm.tiktok.com/...
    - Hỗ trợ ID số thuần túy: 7699698031045790984
    """
    target = str(target_url_or_id).strip()

    # 1. Nếu là số ID thuần túy
    if target.isdigit():
        return target, f"https://www.tiktok.com/video/{target}"

    # 2. Nếu là short URL, theo redirect để lấy URL đích
    if "vt.tiktok.com" in target or "vm.tiktok.com" in target:
        try:
            req = urllib.request.Request(
                target,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                target = resp.geturl()
        except Exception:
            pass

    # 3. Trích xuất ID qua mẫu /video/{id}
    v_match = re.search(r"/video/(\d+)", target)
    if v_match:
        return v_match.group(1), target

    # 4. Tìm chuỗi số dài 15-25 ký tự
    digits = re.findall(r"\d{15,25}", target)
    if digits:
        return digits[0], target

    return None, target
