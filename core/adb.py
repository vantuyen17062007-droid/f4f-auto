"""
core/adb.py — Trình điều khiển tự động hóa thiết bị qua ADB & UIAutomator2
========================================================================
Hỗ trợ:
  - Tự động nhận diện thiết bị (USB / Wifi ADB / Termux)
  - Quản lý màn hình, click, swipe, back, dump UI XML
  - Tự động nhận diện package: TikTok (Trill, Musical.ly, Lite), Instagram, Facebook
  - Tự động phát hiện & đóng popup phiền toái
  - Mở profile & video qua Intent
  - Nhận diện trạng thái Like / Follow chính xác
  - Mô phỏng hành vi người thật lướt feed chống checkpoint
"""

import re
import time
import random
import uiautomator2 as u2
from lxml import etree
from typing import Optional, Tuple, Any

from core.helpers import (
    CYAN, GREEN, YELLOW, RED, RESET,
    resolve_device, resolve_video_id
)

BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")

FOLLOW_LABELS = {"follow", "theo dõi", "follow lại", "follow back", "theo dõi lại"}
FOLLOWED_LABELS = {"đã follow", "đang follow", "following", "đã theo dõi", "bạn bè", "friends"}
REQUESTED_LABELS = {"đã yêu cầu", "requested"}
MESSAGE_LABELS = {"nhắn tin", "message"}

POPUP_DISMISS_LABELS = {
    "để sau", "không phải bây giờ", "lúc khác", "hủy", "từ chối",
    "không cho phép", "bỏ qua", "đóng", "not now", "cancel", "dismiss",
    "don't allow", "later", "never", "remind me later", "skip"
}

STATE_BY_LABEL = {
    **{k: "not_followed" for k in FOLLOW_LABELS},
    **{k: "followed" for k in FOLLOWED_LABELS},
    **{k: "requested" for k in REQUESTED_LABELS},
}


class AdbController:
    def __init__(self, serial=None, timeout=3):
        # Tự động nhận diện thiết bị khả dụng
        resolved = resolve_device(serial)
        self.serial = resolved
        if self.serial:
            print(f"{CYAN}[ADB]{RESET} Kết nối thiết bị: {GREEN}{self.serial}{RESET}")
            self.d = u2.connect(self.serial)
        else:
            print(f"{YELLOW}[ADB]{RESET} Không chỉ định serial cụ thể, kết nối mặc định...")
            self.d = u2.connect()

        try:
            self.d.settings["wait_timeout"] = timeout
            self.d.xpath.global_set("timeout", timeout)
        except Exception:
            pass

        self._size = None
        self._tree = None
        self._cached_pkg = None
        self._cached_ig_pkg = None
        self._cached_fb_pkg = None

    def shell(self, command: str) -> str:
        """Chạy lệnh shell trên thiết bị."""
        try:
            return self.d.shell(command).output.strip()
        except Exception:
            return ""

    def tap(self, x: int, y: int):
        self.d.click(x, y)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        self.d.swipe(x1, y1, x2, y2, duration / 1000)

    def back(self):
        self.d.press("back")

    def get_screen_size(self) -> Tuple[int, int]:
        if self._size is None:
            try:
                self._size = tuple(self.d.window_size())
            except Exception:
                return 720, 1600
        return self._size

    def dump_ui_xml(self, xml_name="window_dump.xml", save_file=False, compressed=True) -> bool:
        """Dump UI hierarchy về lxml etree."""
        try:
            xml = self.d.dump_hierarchy(compressed=compressed)
            self._tree = etree.fromstring(xml.encode("utf-8"))
        except Exception:
            self._tree = None
            return False
        if save_file:
            with open(xml_name, "w", encoding="utf-8") as f:
                f.write(xml)
        return True

    @staticmethod
    def _label(node) -> str:
        return (node.get("text") or node.get("content-desc") or "").strip().lower()

    @staticmethod
    def _box(node) -> Optional[Tuple[int, int, int, int]]:
        m = BOUNDS.match(node.get("bounds", ""))
        return tuple(map(int, m.groups())) if m else None

    # ── NHẬN DIỆN PACKAGE TRÊN THIẾT BỊ ──────────────────────────────
    def detect_tiktok_package(self) -> str:
        """Tự động kiểm tra package TikTok có trên máy."""
        if self._cached_pkg:
            return self._cached_pkg

        candidates = [
            "com.ss.android.ugc.trill",
            "com.zhiliaoapp.musically",
            "com.zhiliaoapp.musically.go",
        ]
        for pkg in candidates:
            out = self.shell(f"pm path {pkg}")
            if "package:" in out:
                self._cached_pkg = pkg
                return pkg

        self._cached_pkg = "com.ss.android.ugc.trill"
        return self._cached_pkg

    def detect_instagram_package(self) -> str:
        """Tự động kiểm tra package Instagram có trên máy."""
        if self._cached_ig_pkg:
            return self._cached_ig_pkg

        candidates = ["com.instagram.android", "com.instagram.lite"]
        for pkg in candidates:
            out = self.shell(f"pm path {pkg}")
            if "package:" in out:
                self._cached_ig_pkg = pkg
                return pkg

        self._cached_ig_pkg = "com.instagram.android"
        return self._cached_ig_pkg

    def detect_facebook_package(self) -> str:
        """Tự động kiểm tra package Facebook có trên máy."""
        if self._cached_fb_pkg:
            return self._cached_fb_pkg

        candidates = ["com.facebook.katana", "com.facebook.lite"]
        for pkg in candidates:
            out = self.shell(f"pm path {pkg}")
            if "package:" in out:
                self._cached_fb_pkg = pkg
                return pkg

        self._cached_fb_pkg = "com.facebook.katana"
        return self._cached_fb_pkg

    # ── ĐÓNG POPUP PHIỀN TOÁI ─────────────────────────────────────────
    def dismiss_popups(self, package=None) -> bool:
        """Tự động phát hiện và bấm đóng popup phiền toái (đồng bộ danh bạ, thông báo, v.v.)."""
        if not self.dump_ui_xml(compressed=True):
            return False

        for node in self._tree.iter("*"):
            if package and node.get("package") != package:
                continue
            text = (node.get("text") or "").strip().lower()
            desc = (node.get("content-desc") or "").strip().lower()
            box = self._box(node)
            if not box:
                continue

            for kw in POPUP_DISMISS_LABELS:
                if kw == text or kw == desc:
                    cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
                    self.tap(cx, cy)
                    time.sleep(0.4)
                    return True
        return False

    # ── MỞ PROFILE & VIDEO (TIKTOK & INSTAGRAM) ─────────────────────────
    def open_tiktok_profile(self, target: str, package_name: Optional[str] = None) -> bool:
        """Mở trang cá nhân TikTok linh hoạt (URL, handle, UID)."""
        if not package_name or package_name == "auto":
            package_name = self.detect_tiktok_package()

        target = str(target).strip()
        if target.startswith("http://") or target.startswith("https://"):
            url = target
        elif target.startswith("@"):
            url = f"https://www.tiktok.com/{target}"
        elif target.isdigit():
            scheme = "snssdk1180" if "trill" in package_name else "snssdk1233"
            url = f"{scheme}://user/profile/{target}"
        else:
            url = f"https://www.tiktok.com/@{target}"

        out = self.d.shell([
            "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", url,
            "-p", package_name,
        ]).output
        return "Error" not in out

    def open_instagram_profile(self, target: str, package_name: Optional[str] = None) -> bool:
        """Mở trang cá nhân Instagram linh hoạt (URL, handle)."""
        if not package_name or package_name == "auto":
            package_name = self.detect_instagram_package()

        target = str(target).strip()
        if target.startswith("http://") or target.startswith("https://"):
            url = target
        elif target.startswith("@"):
            url = f"https://www.instagram.com/{target[1:]}"
        else:
            url = f"https://www.instagram.com/{target}"

        out = self.d.shell([
            "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", url,
            "-p", package_name,
        ]).output
        return "Error" not in out

    def open_tiktok_video(self, target: str, package_name: Optional[str] = None) -> bool:
        """Mở trực tiếp video TikTok qua DeepLinkActivityV2."""
        if not package_name or package_name == "auto":
            package_name = self.detect_tiktok_package()

        video_id, full_url = resolve_video_id(target)

        # Nếu không trích xuất được ID -> fallback mở qua intent VIEW thông thường
        if not video_id:
            out = self.d.shell([
                "am", "start",
                "-a", "android.intent.action.VIEW",
                "-d", full_url or target,
                "-p", package_name,
            ]).output
            return "Error" not in out

        # Mở bằng DeepLinkActivityV2
        scheme = "snssdk1180" if "trill" in package_name else "snssdk1233"
        deeplink_uri = f"{scheme}://aweme/detail/{video_id}"

        if package_name.endswith(".go"):
            cmp_activity = f"{package_name}/.deeplink.DeepLinkActivityV2"
        else:
            cmp_activity = f"{package_name}/com.ss.android.ugc.aweme.deeplink.DeepLinkActivityV2"

        out = self.d.shell([
            "am", "start",
            "-n", cmp_activity,
            "-a", "android.intent.action.VIEW",
            "-d", deeplink_uri,
        ]).output

        # Nếu lỗi component, fallback intent VIEW thông thường
        if "Error" in out or "does not exist" in out:
            out = self.d.shell([
                "am", "start",
                "-a", "android.intent.action.VIEW",
                "-d", deeplink_uri,
                "-p", package_name,
            ]).output

        return "Error" not in out

    # ── NHẬN DIỆN & TƯƠNG TÁC LIKE VIDEO ──────────────────────────────
    def get_like_state(self, package=None, compressed=True) -> Tuple[str, Optional[Tuple[int, int]]]:
        """
        Nhận diện trạng thái Like của video:
        - 'liked' (đã thích video)
        - 'not_liked' (chưa thích kèm tọa độ nút bấm cx, cy)
        - 'unknown'
        """
        if not self.dump_ui_xml(compressed=compressed):
            return "unknown", None

        is_liked = False
        like_btn_pos = None

        for node in self._tree.iter("*"):
            if package and node.get("package") != package:
                continue
            desc = (node.get("content-desc") or "").strip()
            desc_lower = desc.lower()
            res_id = (node.get("resource-id") or "").strip()
            selected = (node.get("selected") or "").strip().lower()

            # Nhận biết đã like: content-desc báo "Đã thích" hoặc selected = true
            if "đã thích" in desc_lower or "bỏ thích" in desc_lower:
                is_liked = True
            if (res_id.endswith(":id/g86") or res_id.endswith(":id/g8m")) and selected == "true":
                is_liked = True

            # Tìm tọa độ nút bấm thích
            if desc in ("Thích", "Thích video") or "lượt thích" in desc_lower or res_id.endswith(":id/g8m") or res_id.endswith(":id/g86"):
                box = self._box(node)
                if box and like_btn_pos is None:
                    like_btn_pos = ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)

        if is_liked:
            return "liked", like_btn_pos
        if like_btn_pos is not None:
            return "not_liked", like_btn_pos
        return "unknown", None

    def get_current_video_info(self, package=None) -> Tuple[str, str]:
        """Lấy thông tin (tác giả, mô tả) của video đang hiển thị trên màn hình."""
        if not self.dump_ui_xml(compressed=True):
            return "", ""
        title, desc = "", ""
        for node in self._tree.iter("*"):
            if package and node.get("package") != package:
                continue
            res_id = (node.get("resource-id") or "").strip()
            text = (node.get("text") or "").strip()
            if res_id.endswith(":id/title") and text:
                title = text
            elif res_id.endswith(":id/desc") and text:
                desc = text
        return title, desc

    def wait_video_loaded(self, package=None, timeout=6, before_sig=None) -> Any:
        """Chờ giao diện video xuất hiện và kiểm tra tính khả dụng của video."""
        deadline = time.time() + timeout
        dismissed = False

        error_keywords = [
            "không khả dụng", "không tồn tại", "đã bị xóa", "riêng tư",
            "không thể phát", "unavailable", "removed", "private",
            "không tìm thấy", "video này không khả dụng", "video không tồn tại"
        ]

        while time.time() < deadline:
            if self.dump_ui_xml(compressed=True):
                # 1. Quét tìm thông báo lỗi video
                for node in self._tree.iter("*"):
                    if package and node.get("package") != package:
                        continue
                    text = (node.get("text") or "").strip().lower()
                    desc = (node.get("content-desc") or "").strip().lower()
                    for kw in error_keywords:
                        if kw in text or kw in desc:
                            return "unavailable"

                # 2. Kiểm tra xem video mới đã xuất hiện chưa
                cur_title, cur_desc = "", ""
                has_like_btn = False

                for node in self._tree.iter("*"):
                    if package and node.get("package") != package:
                        continue
                    res = (node.get("resource-id") or "").strip()
                    d_desc = (node.get("content-desc") or "").strip().lower()
                    text = (node.get("text") or "").strip()

                    if res.endswith(":id/title") and text:
                        cur_title = text
                    elif res.endswith(":id/desc") and text:
                        cur_desc = text
                    elif "lượt thích" in d_desc or d_desc == "thích" or res.endswith(":id/g8m") or res.endswith(":id/g86"):
                        has_like_btn = True

                if before_sig and before_sig != ("", ""):
                    if (cur_title, cur_desc) != before_sig and has_like_btn:
                        return True
                else:
                    if (cur_title or cur_desc) and has_like_btn:
                        return True

            if not dismissed and (time.time() > deadline - timeout / 2):
                if self.dismiss_popups(package=package):
                    dismissed = True
            time.sleep(0.4)

        if before_sig and before_sig != ("", ""):
            cur_sig = self.get_current_video_info(package=package)
            if cur_sig == before_sig:
                return "unavailable"

        return False

    def like_video(self, package=None, load_timeout=6, verify_timeout=3, dry=False) -> str:
        """Thực hiện like video TikTok và xác minh kết quả."""
        deadline = time.time() + load_timeout
        state = "unknown"
        pos = None

        while True:
            state, pos = self.get_like_state(package, compressed=True)
            if state == "liked":
                return "already"
            if state == "not_liked" and pos:
                break
            if time.time() >= deadline:
                break
            time.sleep(0.3)

        if dry:
            return state

        if state != "not_liked" or not pos:
            return "video_unavailable"

        self.tap(*pos)

        deadline = time.time() + verify_timeout
        while time.time() < deadline:
            time.sleep(0.3)
            state, _ = self.get_like_state(package, compressed=True)
            if state == "liked":
                return "clicked"

        return "click_unverified"

    # ── NHẬN DIỆN & TƯƠNG TÁC FOLLOW (TIKTOK & INSTAGRAM) ─────────────
    def get_follow_state(self, package=None, compressed=True, row_tolerance=None) -> Tuple[str, Optional[Tuple[int, int]]]:
        """
        Nhận diện trạng thái follow (hỗ trợ cả TikTok lẫn Instagram):
        - 'not_followed' (kèm tọa độ nút bấm cx, cy)
        - 'followed'
        - 'requested'
        - 'no_profile' / 'unknown'
        """
        if not self.dump_ui_xml(compressed=compressed):
            return "unknown", None

        # 0. Ưu tiên nhận diện nút Follow đặc trưng của Instagram (ID: profile_header_follow_button)
        for node in self._tree.iter("*"):
            res_id = (node.get("resource-id") or "").strip()
            if "profile_header_follow_button" in res_id:
                label = self._label(node)
                box = self._box(node)
                if box:
                    cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
                    if any(k in label for k in FOLLOWED_LABELS):
                        return "followed", (cx, cy)
                    if any(k in label for k in REQUESTED_LABELS):
                        return "requested", (cx, cy)
                    if any(k in label for k in FOLLOW_LABELS):
                        return "not_followed", (cx, cy)

        # 1. Khớp bằng Anchor ("Nhắn tin") trên TikTok
        anchor = None
        candidates = []
        for node in self._tree.iter("*"):
            if package and node.get("package") != package:
                continue
            label = self._label(node)
            if label in MESSAGE_LABELS:
                box = self._box(node)
                if anchor is None and box:
                    anchor = ((box[1] + box[3]) // 2, box[3] - box[1])
            elif label in STATE_BY_LABEL:
                box = self._box(node)
                if box:
                    candidates.append((STATE_BY_LABEL[label],
                                       (box[0] + box[2]) // 2, (box[1] + box[3]) // 2, box))

        if anchor is not None:
            anchor_y, anchor_h = anchor
            tolerance = row_tolerance or max(anchor_h, 30)
            for state, cx, cy, _ in candidates:
                if abs(cy - anchor_y) <= tolerance:
                    return state, (cx, cy)

        # 2. Fallback nếu không có nút Nhắn tin (tài khoản riêng tư, Lite, v.v.)
        width, height = self.get_screen_size()
        for state, cx, cy, box in candidates:
            if height * 0.15 < cy < height * 0.55:
                w = box[2] - box[0]
                h = box[3] - box[1]
                if w >= 80 and h >= 30:
                    return state, (cx, cy)

        return ("no_profile" if anchor is None and not candidates else "unknown"), None

    def wait_handle(self, handle: str, package=None, timeout=6) -> bool:
        """Chờ username/handle của profile xuất hiện trên màn hình."""
        if "/" in handle:
            m = re.search(r"@([a-zA-Z0-9_.-]+)", handle)
            if m:
                handle = m.group(1)
        handle = handle.lstrip("@").lower()
        pattern = re.compile(r"(?<![\w.])@?" + re.escape(handle) + r"(?![\w.])")

        deadline = time.time() + timeout
        dismissed_popup = False
        while time.time() < deadline:
            if self.dump_ui_xml(compressed=True):
                for node in self._tree.iter("*"):
                    if package and node.get("package") != package:
                        continue
                    if pattern.search(self._label(node)):
                        return True

            if not dismissed_popup and (time.time() > deadline - timeout / 2):
                if self.dismiss_popups(package=package):
                    dismissed_popup = True

            time.sleep(0.4)
        return False

    def follow_profile(self, package=None, load_timeout=6, verify_timeout=3, dry=False) -> str:
        """Thực hiện nhấn Follow và kiểm tra kết quả."""
        deadline = time.time() + load_timeout
        while True:
            state, pos = self.get_follow_state(package, compressed=True)
            if state == "followed":
                return "already"
            if state == "requested":
                return "requested"
            if state == "not_followed":
                break
            if time.time() >= deadline:
                return state
            time.sleep(0.3)

        if dry:
            return "not_followed"

        # Bấm nút Follow
        self.tap(*pos)

        # Verify sau click
        deadline = time.time() + verify_timeout
        while time.time() < deadline:
            time.sleep(0.3)
            state, _ = self.get_follow_state(package, compressed=True)
            if state in ("followed", "requested"):
                return "clicked"

        return "click_unverified"

    # ── HÀNH VI NGƯỜI THẬT (HUMAN BEHAVIOR / ANTI-BAN) ─────────────────
    def simulate_human_browse(self, scroll_times=1, package_name: Optional[str] = None):
        """Mô phỏng hành vi người dùng lướt feed n lần trước khi làm job mới."""
        if scroll_times <= 0:
            return
        try:
            self.back()
            time.sleep(1.0)

            # Đảm bảo app mục tiêu vẫn đang ở tiền cảnh, nếu thoát ra Home thì mở lại
            if package_name:
                current = self.shell("dumpsys window | grep mCurrentFocus")
                if package_name not in current:
                    self.shell(f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
                    time.sleep(2.0)
                    self.dismiss_popups(package=package_name)

            w, h = self.get_screen_size()
            x = w // 2
            for _ in range(scroll_times):
                time.sleep(random.uniform(2.5, 4.5))
                start_y = int(h * (0.75 + random.uniform(-0.03, 0.03)))
                end_y = int(h * (0.25 + random.uniform(-0.03, 0.03)))
                duration = random.randint(220, 320)
                self.swipe(x, start_y, x, end_y, duration=duration)
            time.sleep(random.uniform(1.8, 3.0))
        except Exception:
            pass
