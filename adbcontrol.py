import re
import time
import random
import subprocess
import uiautomator2 as u2
from lxml import etree

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

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


def get_connected_adb_devices():
    """Lấy danh sách các thiết bị ADB đang kết nối ở trạng thái 'device'."""
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        lines = res.stdout.strip().splitlines()[1:]
        devices = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except Exception:
        return []


def resolve_active_device(preferred_serial=None):
    """
    Tự động xác định thiết bị kết nối phù hợp:
    - Nếu có preferred_serial và hợp lệ -> dùng.
    - Nếu preferred_serial == 'auto' hoặc không tìm thấy -> tự động quét thiết bị khả dụng.
    """
    devices = get_connected_adb_devices()

    if preferred_serial and preferred_serial != "auto":
        if preferred_serial in devices:
            return preferred_serial
        # Nếu thiết bị chỉ định là IP:port, thử connect
        if ":" in preferred_serial:
            try:
                subprocess.run(["adb", "connect", preferred_serial], capture_output=True, timeout=5)
                devices = get_connected_adb_devices()
                if preferred_serial in devices:
                    return preferred_serial
            except Exception:
                pass

    if devices:
        return devices[0]

    return preferred_serial if (preferred_serial and preferred_serial != "auto") else None


class AdbController:
    def __init__(self, serial=None, timeout=3):
        # Tự động nhận diện thiết bị khả dụng
        resolved = resolve_active_device(serial)
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
        except Exception as e:
            pass

        self._size = None
        self._tree = None
        self._cached_pkg = None

    def shell(self, command):
        """Chạy lệnh shell trên thiết bị."""
        try:
            return self.d.shell(command).output.strip()
        except Exception as e:
            return ""

    def tap(self, x, y):
        self.d.click(x, y)

    def swipe(self, x1, y1, x2, y2, duration=300):
        self.d.swipe(x1, y1, x2, y2, duration / 1000)

    def back(self):
        self.d.press("back")

    def get_screen_size(self):
        if self._size is None:
            try:
                self._size = tuple(self.d.window_size())
            except Exception:
                return 720, 1600
        return self._size

    def dump_ui_xml(self, xml_name="window_dump.xml", save_file=False, compressed=True):
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
    def _label(node):
        return (node.get("text") or node.get("content-desc") or "").strip().lower()

    @staticmethod
    def _box(node):
        m = BOUNDS.match(node.get("bounds", ""))
        return tuple(map(int, m.groups())) if m else None

    def detect_tiktok_package(self):
        """Tự động kiểm tra package TikTok có trên máy."""
        if self._cached_pkg:
            return self._cached_pkg

        candidates = ["com.ss.android.ugc.trill", "com.zhiliaoapp.musically", "com.zhiliaoapp.musically.go"]
        for pkg in candidates:
            out = self.shell(f"pm path {pkg}")
            if "package:" in out:
                self._cached_pkg = pkg
                return pkg

        self._cached_pkg = "com.ss.android.ugc.trill"
        return self._cached_pkg

    def detect_instagram_package(self):
        """Tự động kiểm tra package Instagram có trên máy."""
        if hasattr(self, "_cached_ig_pkg") and self._cached_ig_pkg:
            return self._cached_ig_pkg

        candidates = ["com.instagram.android", "com.instagram.lite"]
        for pkg in candidates:
            out = self.shell(f"pm path {pkg}")
            if "package:" in out:
                self._cached_ig_pkg = pkg
                return pkg

        self._cached_ig_pkg = "com.instagram.android"
        return self._cached_ig_pkg

    def detect_facebook_package(self):
        """Tự động kiểm tra package Facebook có trên máy."""
        if hasattr(self, "_cached_fb_pkg") and self._cached_fb_pkg:
            return self._cached_fb_pkg

        candidates = ["com.facebook.katana", "com.facebook.lite"]
        for pkg in candidates:
            out = self.shell(f"pm path {pkg}")
            if "package:" in out:
                self._cached_fb_pkg = pkg
                return pkg

        self._cached_fb_pkg = "com.facebook.katana"
        return self._cached_fb_pkg

    def open_instagram_profile(self, target, package_name=None):
        """
        Mở trang cá nhân Instagram linh hoạt:
        - Nhận URL: https://www.instagram.com/gbao_73
        - Nhận handle: @gbao_73 hoặc gbao_73
        """
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

    def dismiss_popups(self, package=None):
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

    def open_tiktok_profile(self, target, package_name=None):
        """
        Mở trang cá nhân TikTok linh hoạt:
        - Nhận URL: https://www.tiktok.com/@tusobutter
        - Nhận handle: @tusobutter hoặc tusobutter
        - Nhận UID số: 671239129312
        """
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

    def open_tiktok_video(self, target, package_name=None):
        """
        Mở trực tiếp video TikTok:
        - Nhận URL: https://www.tiktok.com/@user/video/123456789
        - Nhận short link: https://vt.tiktok.com/...
        - Nhận Video ID: 123456789
        """
        if not package_name or package_name == "auto":
            package_name = self.detect_tiktok_package()

        target = str(target).strip()
        video_id = None

        # 1. Nếu là short URL, theo dõi redirect để lấy full URL
        if "vt.tiktok.com" in target or "vm.tiktok.com" in target:
            try:
                import urllib.request
                req = urllib.request.Request(
                    target,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    target = resp.geturl()
            except Exception:
                pass

        # 2. Trích xuất video ID bằng regex
        v_match = re.search(r"/video/(\d+)", target)
        if v_match:
            video_id = v_match.group(1)
        elif target.isdigit():
            video_id = target
        else:
            digits = re.findall(r"\d{15,25}", target)
            if digits:
                video_id = digits[0]

        # Nếu không trích xuất được ID -> fallback mở qua intent VIEW thông thường
        if not video_id:
            out = self.d.shell([
                "am", "start",
                "-a", "android.intent.action.VIEW",
                "-d", target,
                "-p", package_name,
            ]).output
            return "Error" not in out

        # 3. Mở thẳng bằng DeepLinkActivityV2 tương tự thử nghiệm thực tế
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

    def get_like_state(self, package=None, compressed=True):
        """
        Nhận diện trạng thái Like của video:
        - 'liked' (đã thích video)
        - 'not_liked' (chưa thích kèm tọa độ nút bấm cx, cy)
        - 'no_video' / 'unknown'
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

    def get_current_video_info(self, package=None):
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

    def wait_video_loaded(self, package=None, timeout=6, before_sig=None):
        """
        Chờ giao diện video xuất hiện và kiểm tra tính khả dụng của video:
        - Phát hiện video bị xóa, ẩn hoặc tài khoản riêng tư -> trả về 'unavailable'
        - Phát hiện video đã tải thành công -> trả về True
        - Hết thời gian chờ mà video không đổi -> trả về 'unavailable'
        """
        deadline = time.time() + timeout
        dismissed = False

        error_keywords = [
            "không khả dụng", "không tồn tại", "đã bị xóa", "riêng tư",
            "không thể phát", "unavailable", "removed", "private", "không tìm thấy","Video này không khả dụng", "video không tồn tại", "video đã bị xóa", "video riêng tư"
        ]

        while time.time() < deadline:
            if self.dump_ui_xml(compressed=True):
                # 1. Quét tìm thông báo lỗi video không khả dụng
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

                # Nếu có video signature trước đó, video mới phải khác video cũ
                if before_sig and before_sig != ("", ""):
                    if (cur_title, cur_desc) != before_sig and has_like_btn:
                        return True
                else:
                    if (cur_title or cur_desc) and has_like_btn:
                        return True

            # Thử tắt popup nếu có
            if not dismissed and (time.time() > deadline - timeout / 2):
                if self.dismiss_popups(package=package):
                    dismissed = True
            time.sleep(0.4)

        # Nếu có before_sig mà sau timeout video vẫn giữ nguyên không đổi -> video không mở được
        if before_sig and before_sig != ("", ""):
            cur_sig = self.get_current_video_info(package=package)
            if cur_sig == before_sig:
                return "unavailable"

        return False

    def like_video(self, package=None, load_timeout=6, verify_timeout=3, dry=False):
        """
        Thực hiện like video TikTok và xác minh kết quả.
        Trả về:
          - 'already': video đã được thích từ trước
          - 'clicked': đã nhấn like và xác minh thành công
          - 'click_unverified': đã nhấn like nhưng chưa kịp xác minh UI
          - 'video_unavailable': không tìm thấy nút like / màn hình video
        """
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

        # Nếu không tìm thấy nút bấm like hợp lệ -> video không khả dụng
        if state != "not_liked" or not pos:
            return "video_unavailable"

        # 1. Bấm nút Thích bằng tọa độ chính xác của nút
        self.tap(*pos)

        # 2. Xác minh lại trạng thái sau khi bấm
        deadline = time.time() + verify_timeout
        while time.time() < deadline:
            time.sleep(0.3)
            state, _ = self.get_like_state(package, compressed=True)
            if state == "liked":
                return "clicked"

        return "click_unverified"

    def get_follow_state(self, package=None, compressed=True, row_tolerance=None):
        """
        Nhận diện trạng thái follow (hỗ trợ cả TikTok lẫn Instagram):
        - 'not_followed' (kèm tọa độ nút bấm)
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

        # 1. Khớp bằng Anchor ("Nhắn tin")
        if anchor is not None:
            anchor_y, anchor_h = anchor
            tolerance = row_tolerance or max(anchor_h, 30)
            for state, cx, cy, _ in candidates:
                if abs(cy - anchor_y) <= tolerance:
                    return state, (cx, cy)

        # 2. Fallback nếu không có nút Nhắn tin (TikTok Lite, tài khoản private, tài khoản chặn DM)
        width, height = self.get_screen_size()
        for state, cx, cy, box in candidates:
            # Nút follow profile nằm ở nửa trên màn hình (dưới avatar, trên tab video)
            if height * 0.15 < cy < height * 0.55:
                w = box[2] - box[0]
                h = box[3] - box[1]
                if w >= 80 and h >= 30:
                    return state, (cx, cy)

        return ("no_profile" if anchor is None and not candidates else "unknown"), None

    def wait_handle(self, handle, package=None, timeout=6):
        """Chờ handle của profile xuất hiện."""
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

            # Nếu quá nửa thời gian mà chưa thấy, thử đóng popup nếu có
            if not dismissed_popup and (time.time() > deadline - timeout / 2):
                if self.dismiss_popups(package=package):
                    dismissed_popup = True

            time.sleep(0.4)
        return False

    def follow_profile(self, package=None, load_timeout=6, verify_timeout=3, dry=False):
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

    def simulate_human_browse(self, scroll_times=1):
        """Mô phỏng hành vi người dùng lướt feed n lần trước khi làm job mới."""
        if scroll_times <= 0:
            return
        try:
            self.back()
            time.sleep(1.0)
            w, h = self.get_screen_size()
            x = w // 2
            for _ in range(scroll_times):
                # Xem video hiện tại ngẫu nhiên 2 - 4.5 giây
                time.sleep(random.uniform(2.5, 4.5))
                # Vuốt chuyển sang video tiếp theo
                start_y = int(h * (0.75 + random.uniform(-0.03, 0.03)))
                end_y = int(h * (0.25 + random.uniform(-0.03, 0.03)))
                duration = random.randint(220, 320)
                self.swipe(x, start_y, x, end_y, duration=duration)
            time.sleep(random.uniform(1.8, 3.0))
        except Exception:
            pass
