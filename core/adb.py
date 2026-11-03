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
from typing import Optional, Tuple, Any, Dict

from core.helpers import (
    CYAN, GREEN, YELLOW, RESET,
    resolve_device, resolve_video_id
)

BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")

FOLLOW_LABELS = {"follow", "theo dõi", "follow lại", "follow back", "theo dõi lại"}
FOLLOWED_LABELS = {
    "đã follow", "đang follow", "following", "đã theo dõi",
    "đang theo dõi", "bạn bè", "friends", "followed",
}
REQUESTED_LABELS = {"đã yêu cầu", "yêu cầu đã gửi", "requested", "request sent"}
MESSAGE_LABELS = {"nhắn tin", "message", "gửi tin nhắn"}

LIKE_LABELS = {"thích", "like", "thích video", "like video"}
UNLIKE_LABELS = {"bỏ thích", "unlike", "đã thích", "liked"}
LIKE_RES_IDS = (":id/g86", ":id/g8m")

SAFE_POPUP_LABELS = {
    "để sau", "không phải bây giờ", "lúc khác", "không cho phép", "từ chối",
    "not now", "later", "remind me later", "don't allow", "dismiss",
}
RISKY_POPUP_LABELS = {
    "hủy", "đóng", "bỏ qua", "cancel", "skip", "never",
}
POPUP_DISMISS_LABELS = SAFE_POPUP_LABELS | RISKY_POPUP_LABELS
DIALOG_HINTS = ("dialog", "modal", "popup", "sheet", "alert")
SYSTEM_PACKAGES = (
    "com.android.permissioncontroller",
    "com.google.android.permissioncontroller",
)

STATE_BY_LABEL = {
    **{k: "not_followed" for k in FOLLOW_LABELS},
    **{k: "followed" for k in FOLLOWED_LABELS},
    **{k: "requested" for k in REQUESTED_LABELS},
}


class AdbConnectionError(RuntimeError):
    """Không thể kết nối hoặc điều khiển thiết bị Android qua ADB."""


class AdbController:
    def __init__(self, serial=None, timeout=3):
        # Tự động nhận diện thiết bị khả dụng
        resolved = resolve_device(serial)
        self.serial = resolved
        try:
            if self.serial:
                print(f"{CYAN}[ADB]{RESET} Kết nối thiết bị: {GREEN}{self.serial}{RESET}")
                self.d = u2.connect(self.serial)
            else:
                print(f"{YELLOW}[ADB]{RESET} Không chỉ định serial cụ thể, kết nối mặc định...")
                self.d = u2.connect()

            # Ép uiautomator2 thực hiện một lệnh thật để phát hiện sớm thiết bị offline.
            self.d.window_size()
        except Exception as e:
            raise AdbConnectionError(
                "Không thể kết nối thiết bị Android qua ADB. "
                "Hãy kiểm tra 'adb devices', bật USB debugging hoặc chạy "
                f"'adb connect <ip>:<port>'. Chi tiết: {e}"
            ) from e

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

    def current_package(self) -> str:
        """Trả về package đang ở tiền cảnh (rỗng nếu không xác định được)."""
        try:
            info = self.d.app_current() or {}
            return str(info.get("package") or "")
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

    def get_device_info(self) -> Dict[str, str]:
        """Thông tin cơ bản của thiết bị hiển thị trong bảng Preflight."""
        model = self.shell("getprop ro.product.marketname")
        if not model:
            model = self.shell("getprop ro.product.model")
        android = self.shell("getprop ro.build.version.release")
        try:
            w, h = self.get_screen_size()
        except Exception:
            w = h = 0
        return {
            "serial": self.serial or "(mặc định)",
            "model": model or "Không rõ",
            "android": android or "?",
            "screen": f"{w}x{h}" if w else "?x?",
        }

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
    def _detect_package(self, candidates, keywords, app_name: str) -> str:
        """Tìm package đã cài; thử danh sách ưu tiên trước rồi quét toàn bộ."""
        for pkg in candidates:
            out = self.shell(f"pm path {pkg}")
            if "package:" in out:
                return pkg

        installed = self.shell("pm list packages")
        for line in installed.splitlines():
            pkg = line.replace("package:", "").strip()
            if not pkg:
                continue
            lower = pkg.lower()
            if any(keyword in lower for keyword in keywords):
                return pkg

        raise RuntimeError(
            f"Không tìm thấy ứng dụng {app_name} trên thiết bị. "
            "Hãy cài đặt ứng dụng hoặc cấu hình package chính xác trong config.json."
        )

    def detect_tiktok_package(self) -> str:
        """Tự động kiểm tra package TikTok có trên máy."""
        if self._cached_pkg:
            return self._cached_pkg

        candidates = [
            "com.ss.android.ugc.trill",
            "com.zhiliaoapp.musically",
            "com.zhiliaoapp.musically.go",
        ]
        self._cached_pkg = self._detect_package(
            candidates, ("musically", "trill", "tiktok"), "TikTok"
        )
        return self._cached_pkg

    def detect_instagram_package(self) -> str:
        """Tự động kiểm tra package Instagram có trên máy."""
        if self._cached_ig_pkg:
            return self._cached_ig_pkg

        candidates = ["com.instagram.android", "com.instagram.lite"]
        self._cached_ig_pkg = self._detect_package(
            candidates, ("instagram",), "Instagram"
        )
        return self._cached_ig_pkg

    def detect_facebook_package(self) -> str:
        """Tự động kiểm tra package Facebook có trên máy."""
        if self._cached_fb_pkg:
            return self._cached_fb_pkg

        candidates = ["com.facebook.katana", "com.facebook.lite"]
        self._cached_fb_pkg = self._detect_package(
            candidates, ("facebook", "katana"), "Facebook"
        )
        return self._cached_fb_pkg

    # ── ĐÓNG POPUP PHIỀN TOÁI ─────────────────────────────────────────
    @staticmethod
    def _in_dialog(node) -> bool:
        """Kiểm tra node nằm trong dialog/modal/bottom-sheet hay không."""
        current = node
        for _ in range(6):
            if current is None:
                return False
            cls = (current.get("class") or "").lower()
            res_id = (current.get("resource-id") or "").lower()
            if any(hint in cls or hint in res_id for hint in DIALOG_HINTS):
                return True
            current = current.getparent()
        return False

    def dismiss_popups(self, package=None) -> bool:
        """Tự động phát hiện và bấm đóng popup phiền toái (đồng bộ danh bạ, thông báo, v.v.)."""
        if not self.dump_ui_xml(compressed=True):
            return False

        for node in self._tree.iter("*"):
            node_pkg = node.get("package") or ""
            # Cho phép cả dialog hệ thống (quyền truy cập, thông báo...).
            if (
                package
                and node_pkg != package
                and not node_pkg.startswith(SYSTEM_PACKAGES)
            ):
                continue

            text = (node.get("text") or "").strip().lower()
            desc = (node.get("content-desc") or "").strip().lower()
            matched = ({text, desc} & POPUP_DISMISS_LABELS)
            if not matched:
                continue
            label = next(iter(matched))

            box = self._box(node)
            if not box:
                continue

            clickable = (node.get("clickable") or "").lower() == "true"
            cls = (node.get("class") or "").lower()
            if not (clickable or "button" in cls):
                # Text có thể nằm trong một container clickable.
                parent = node.getparent()
                found = False
                for _ in range(3):
                    if parent is None:
                        break
                    if (parent.get("clickable") or "").lower() == "true":
                        parent_box = self._box(parent)
                        if parent_box:
                            box = parent_box
                            found = True
                        break
                    parent = parent.getparent()
                if not found:
                    continue

            # Các nhãn mơ hồ như "Hủy"/"Đóng"/"Bỏ qua" chỉ được bấm trong dialog.
            if label in RISKY_POPUP_LABELS and not self._in_dialog(node):
                continue

            cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
            self.tap(cx, cy)
            time.sleep(0.4)
            return True
        return False

    # ── MỞ PROFILE & VIDEO (TIKTOK & INSTAGRAM) ─────────────────────────
    def _am_start(self, args) -> bool:
        """Chạy `am start` và trả về True nếu Android không báo lỗi."""
        try:
            out = str(self.d.shell(["am", "start"] + list(args)).output)
        except Exception:
            return False
        return "Error" not in out and "does not exist" not in out

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

        return self._am_start([
            "-a", "android.intent.action.VIEW",
            "-d", url,
            "-p", package_name,
        ])

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

        return self._am_start([
            "-a", "android.intent.action.VIEW",
            "-d", url,
            "-p", package_name,
        ])

    def open_tiktok_video(self, target: str, package_name: Optional[str] = None) -> bool:
        """Mở trực tiếp video TikTok qua DeepLinkActivityV2."""
        if not package_name or package_name == "auto":
            package_name = self.detect_tiktok_package()

        video_id, full_url = resolve_video_id(target)

        # Nếu không trích xuất được ID -> fallback mở qua intent VIEW thông thường
        if not video_id:
            return self._am_start([
                "-a", "android.intent.action.VIEW",
                "-d", full_url or str(target),
                "-p", package_name,
            ])

        # Mở bằng DeepLinkActivityV2
        scheme = "snssdk1180" if "trill" in package_name else "snssdk1233"
        deeplink_uri = f"{scheme}://aweme/detail/{video_id}"

        if package_name.endswith(".go"):
            cmp_activity = f"{package_name}/.deeplink.DeepLinkActivityV2"
        else:
            cmp_activity = f"{package_name}/com.ss.android.ugc.aweme.deeplink.DeepLinkActivityV2"

        ok = self._am_start([
            "-n", cmp_activity,
            "-a", "android.intent.action.VIEW",
            "-d", deeplink_uri,
        ])

        # Nếu lỗi component, fallback intent VIEW thông thường
        if not ok:
            ok = self._am_start([
                "-a", "android.intent.action.VIEW",
                "-d", deeplink_uri,
                "-p", package_name,
            ])

        return ok

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
            clickable = (node.get("clickable") or "").strip().lower() == "true"

            # Không dùng chuỗi "lượt thích" vì đó thường là nhãn số lượng,
            # không phải nút Like; bấm vào đó sẽ không thả tim.
            id_match = any(res_id.endswith(rid) for rid in LIKE_RES_IDS)

            # "Đã like": tùy build TikTok có nhiều dạng nhãn:
            #   - gọn:  'Bỏ thích' / 'Đã thích' / 'Unlike' / 'Liked'
            #   - dài:  'Đã thích video' / 'Bỏ thích video. N lượt thích'
            # Ngoài ra icon Like nhiều build dùng selected=true khi đã thích.
            unlike_hit = (
                desc_lower in UNLIKE_LABELS
                or desc_lower.startswith(("đã thích", "bỏ thích", "unlike", "liked"))
                or ("bỏ thích" in desc_lower)
                or ("unlike" in desc_lower)
            )
            icon_liked = selected == "true" and (
                desc_lower in LIKE_LABELS or id_match
            )

            if unlike_hit or icon_liked:
                is_liked = True

            is_like_button = desc_lower in LIKE_LABELS or (id_match and clickable)
            if is_like_button:
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

    def wait_video_loaded(
        self,
        package=None,
        timeout=6,
        before_sig=None,
    ) -> Any:
        """
        Chờ giao diện video xuất hiện và kiểm tra tính khả dụng của video.

        Tính đúng đắn của video dựa vào DeepLink intent: khi `open_tiktok_video`
        mở `snssdk://aweme/detail/<id>`, chính TikTok là bên resolve video đúng
        theo ID. UI nhiều màn hình không hiển thị username dạng text, nên KHÔNG
        kiểm tra handle ở đây (nếu kiểm sẽ skip mọi job Like).

        Trả về:
        - True: video đã hiển thị (và khác video đang phát trước đó nếu có before_sig).
        - "unavailable": TikTok hiển thị thông báo lỗi (video bị xóa/riêng tư...).
        - "unchanged": bắn deeplink thành công nhưng màn hình không đổi sang video
          đích (sig trùng INTÓC 3s) -> video đích gần như chắc chắn đã bị xóa/
          không mở được. TikTok build trill KHÔNG hiện trang lỗi cho video bị xóa.
        - False: hết thời gian chờ, không xác định được video mới.
        """
        deadline = time.time() + timeout
        dismissed = False
        video_loaded = False
        unchanged_since = None

        error_keywords = [
            "video này không khả dụng", "video không khả dụng",
            "video không tồn tại", "không tìm thấy video này",
            "video đã bị xóa", "video này đã bị xóa", "không thể phát video",
            "tài khoản này là riêng tư", "tài khoản riêng tư",
            "this video is unavailable", "video is unavailable",
            "video is private", "video has been removed",
            "this video has been removed", "sorry, this video",
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

                # 2. Kiểm tra video đã xuất hiện chưa
                cur_title, cur_desc = "", ""
                has_like_btn = False

                for node in self._tree.iter("*"):
                    if package and node.get("package") != package:
                        continue
                    res = (node.get("resource-id") or "").strip()
                    d_desc = (node.get("content-desc") or "").strip().lower()
                    text = (node.get("text") or "").strip()
                    clickable = (node.get("clickable") or "").strip().lower() == "true"

                    if res.endswith(":id/title") and text:
                        cur_title = text
                    elif res.endswith(":id/desc") and text:
                        cur_desc = text
                    elif (
                        d_desc in LIKE_LABELS
                        or d_desc in UNLIKE_LABELS
                        or (clickable and any(res.endswith(rid) for rid in LIKE_RES_IDS))
                    ):
                        has_like_btn = True

                video_loaded = bool((cur_title or cur_desc) and has_like_btn)

                if video_loaded:
                    if not before_sig or before_sig == ("", ""):
                        return True
                    if (cur_title, cur_desc) != before_sig:
                        return True
                    # sig trùng: màn hình không đổi sau deeplink
                    # (deeplink thất bại hoặc đích trùng video đang phát).
                    if unchanged_since is None:
                        unchanged_since = time.time()
                    elif time.time() - unchanged_since >= 4.0:
                        # Video đích bất động suốt 4s sau khi bắn intent
                        # (video tốt thường đổi trang trong 1-3s):
                        # gần như chắc chắn là video bị xóa/chết.
                        return "unchanged"

            if not dismissed and (time.time() > deadline - timeout / 2):
                if self.dismiss_popups(package=package):
                    dismissed = True
            time.sleep(0.4)

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

        # Chờ video ổn định trước khi bấm: sau deeplink, icon Like có thể hiển thị
        # trước khi fragment sẵn sàng nhận tương tác (tap sớm bị nuốt).
        time.sleep(1.0)
        state, pos_check = self.get_like_state(package, compressed=True)
        if state == "liked":
            # Trạng thái đã đổi trong lúc chờ -> không bấm (tránh hủy tim)
            return "already"
        if state == "not_liked" and pos_check:
            pos = pos_check

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
            if package and node.get("package") != package:
                continue
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
        if not handle:
            return False
        if "/" in handle:
            m = re.search(r"@([a-zA-Z0-9_.-]+)", handle)
            if m:
                handle = m.group(1)
        handle = handle.lstrip("@").lower()
        if not handle or handle.isdigit():
            # Không thể đối chiếu handle nếu job chỉ cung cấp UID số.
            return True
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

        if not pos:
            return "unknown"

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
            if package_name and self.current_package() != package_name:
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
        except Exception as e:
            print(f"{YELLOW}[ADB]{RESET} Bỏ qua anti-ban do lỗi thiết bị: {e}")
