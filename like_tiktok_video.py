import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request

# Đảm bảo in UTF-8 không bị lỗi mã hóa trên Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Màu sắc hiển thị terminal
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def get_connected_devices():
    """Lấy danh sách các thiết bị ADB đang kết nối."""
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        devices = []
        for line in res.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except Exception as e:
        print(f"{RED}[!] Không thể chạy lệnh adb devices: {e}{RESET}")
        return []


def resolve_device(preferred_serial=None):
    """Tìm thiết bị ADB phù hợp."""
    devices = get_connected_devices()
    if not devices:
        return None

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

    return devices[0]


def detect_tiktok_package(serial):
    """Xác định package TikTok trên thiết bị."""
    candidates = [
        "com.ss.android.ugc.trill",       # TikTok Global / VN
        "com.zhiliaoapp.musically",       # TikTok US / International
        "com.zhiliaoapp.musically.go",    # TikTok Lite
    ]
    for pkg in candidates:
        try:
            res = subprocess.run(
                ["adb", "-s", serial, "shell", f"pm path {pkg}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "package:" in res.stdout:
                return pkg
        except Exception:
            pass
    return "com.ss.android.ugc.trill"


def resolve_video_id(target_url_or_id):
    """Trích xuất Video ID và URL từ link đầu vào."""
    target = str(target_url_or_id).strip()

    if target.isdigit():
        return target, f"https://www.tiktok.com/video/{target}"

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

    v_match = re.search(r"/video/(\d+)", target)
    if v_match:
        return v_match.group(1), target

    digits = re.findall(r"\d{15,25}", target)
    if digits:
        return digits[0], target

    return None, target


def open_video_via_adb(serial, package_name, video_id, full_url=None):
    """Mở thẳng màn hình phát video TikTok qua DeepLinkActivityV2."""
    scheme = "snssdk1180" if "trill" in package_name else "snssdk1233"
    deeplink_uri = f"{scheme}://aweme/detail/{video_id}"

    if package_name.endswith(".go"):
        cmp_activity = f"{package_name}/.deeplink.DeepLinkActivityV2"
    else:
        cmp_activity = f"{package_name}/com.ss.android.ugc.aweme.deeplink.DeepLinkActivityV2"

    print(f"{CYAN}[*]{RESET} Đang mở video TikTok:")
    print(f"    - Thiết bị:  {GREEN}{serial}{RESET}")
    print(f"    - Package:  {GREEN}{package_name}{RESET}")
    print(f"    - Video ID: {GREEN}{video_id}{RESET}")

    cmd = [
        "adb", "-s", serial, "shell",
        "am", "start",
        "-n", cmp_activity,
        "-a", "android.intent.action.VIEW",
        "-d", deeplink_uri,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    if "Error" in res.stdout or "does not exist" in res.stdout:
        fallback_cmd = [
            "adb", "-s", serial, "shell",
            "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", full_url or deeplink_uri,
            "-p", package_name,
        ]
        subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=8)


def like_video(serial, timeout=8):
    """
    Tìm và bấm nút Thích (Trái tim) trên màn hình video TikTok.
    - Kiểm tra trạng thái hiện tại (nếu đã thích thì không bấm lại để tránh bị hủy).
    - Bấm nút thích và xác nhận lại trạng thái thành công.
    """
    import uiautomator2 as u2

    print(f"{CYAN}[*]{RESET} Kết nối UIAutomator và kiểm tra nút Thích (timeout: {timeout}s)...")
    d = u2.connect(serial)

    start_time = time.time()
    like_btn_element = None
    is_already_liked = False
    like_count = None
    author_name = None

    # Vòng lặp chờ màn hình video load
    while time.time() - start_time < timeout:
        time.sleep(1.0)
        nodes = []
        try:
            for el in d.xpath("//*").all():
                nodes.append({
                    "text": el.attrib.get("text", "").strip(),
                    "desc": el.attrib.get("content-desc", "").strip(),
                    "id": el.attrib.get("resource-id", ""),
                    "selected": el.attrib.get("selected", "false"),
                    "bounds": el.attrib.get("bounds", ""),
                })
        except Exception:
            continue

        for n in nodes:
            res_id = n["id"]
            desc = n["desc"]
            text = n["text"]
            selected = n["selected"]

            if res_id.endswith(":id/title") and text:
                author_name = text

            # Kiểm tra xem đã thích chưa
            if "Đã thích" in desc or (res_id.endswith(":id/g86") and selected == "true"):
                is_already_liked = True

            # Lấy số lượt thích hiện tại
            if "lượt thích" in desc:
                m = re.search(r"(\d+[\d\.,]*)\s*lượt thích", desc)
                if m:
                    like_count = m.group(1)
            elif res_id.endswith(":id/g8b") and text:
                like_count = text

            # Nhận diện phần tử nút thích
            if desc == "Thích" or "Thích video" in desc or res_id.endswith(":id/g8m") or res_id.endswith(":id/g86"):
                like_btn_element = n

        if author_name or like_btn_element or is_already_liked:
            break

    # 1. Nếu video đã được thích trước đó
    if is_already_liked:
        print(f"\n{YELLOW}{BOLD}[!] VIDEO ĐÃ ĐƯỢC THÍCH TỪ TRƯỚC!{RESET}")
        print(f"    - Tác giả:       {GREEN}{author_name or 'N/A'}{RESET}")
        print(f"    - Số lượt thích: {YELLOW}{like_count or 'N/A'}{RESET}")
        print(f"    - Không cần bấm lại để tránh hủy thích.\n")
        return True

    # 2. Nếu chưa thích, tiến hành bấm nút Thích
    print(f"{CYAN}[*]{RESET} Phát hiện video chưa thích. Đang tiến hành bấm nút Thích...")

    clicked = False
    # Cách A: Dùng xpath content-desc="Thích" hoặc "Thích video"
    for xpath_query in [
        '//*[@content-desc="Thích"]',
        '//*[contains(@content-desc, "Thích video")]',
        '//*[@resource-id="com.ss.android.ugc.trill:id/g8m"]',
        '//*[@resource-id="com.ss.android.ugc.trill:id/g86"]',
    ]:
        try:
            el = d.xpath(xpath_query)
            if el.exists:
                el.click()
                clicked = True
                print(f"    -> Đã click bằng: {DIM}{xpath_query}{RESET}")
                break
        except Exception:
            pass

    # Cách B: Nếu không click được qua xpath, click theo tọa độ bounds
    if not clicked and like_btn_element and like_btn_element.get("bounds"):
        bounds_str = like_btn_element["bounds"]
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
        if m:
            x1, y1, x2, y2 = map(int, m.groups())
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            d.click(cx, cy)
            clicked = True
            print(f"    -> Đã click theo tọa độ nút: ({cx}, {cy})")

    # Cách C: Fallback nhấp đúp (Double tap) vào giữa màn hình video
    if not clicked:
        w, h = d.window_size()
        cx, cy = w // 2, h // 2
        print(f"    -> Fallback: Nhấp đúp vào giữa màn hình ({cx}, {cy}) để Thích...")
        d.double_click(cx, cy, duration=0.1)
        clicked = True

    # 3. Chờ 1 giây và xác minh lại
    time.sleep(1.0)
    confirmed_liked = False
    new_like_count = None

    try:
        for el in d.xpath("//*").all():
            desc = el.attrib.get("content-desc", "").strip()
            res_id = el.attrib.get("resource-id", "")
            selected = el.attrib.get("selected", "false")
            text = el.attrib.get("text", "").strip()

            if "Đã thích" in desc or (res_id.endswith(":id/g86") and selected == "true"):
                confirmed_liked = True
            if "lượt thích" in desc:
                m = re.search(r"(\d+[\d\.,]*)\s*lượt thích", desc)
                if m:
                    new_like_count = m.group(1)
            elif res_id.endswith(":id/g8b") and text:
                new_like_count = text
    except Exception:
        pass

    print("\n" + "=" * 55)
    if confirmed_liked:
        print(f"{GREEN}{BOLD}[✓] ĐÃ BẤM THÍCH THÀNH CÔNG CHO VIDEO!{RESET}")
    else:
        print(f"{GREEN}{BOLD}[✓] ĐÃ GỬI LỆNH BẤM THÍCH!{RESET}")
    print("=" * 55)
    print(f" {BOLD}Tác giả:{RESET}          {GREEN}{author_name or 'N/A'}{RESET}")
    print(f" {BOLD}Trạng thái:{RESET}       {GREEN}ĐÃ THÍCH (Trái tim đỏ){RESET}")
    print(f" {BOLD}Số lượt thích mới:{RESET} {YELLOW}{new_like_count or like_count or 'N/A'}{RESET}")
    print("=" * 55 + "\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Mở video TikTok và bấm nút Thích (Like) bằng ADB."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="https://www.tiktok.com/@tuandidau/video/7699698031045790984",
        help="Đường dẫn video TikTok hoặc Video ID (mặc định: link của bạn)",
    )
    parser.add_argument(
        "-s", "--serial",
        default=None,
        help="Serial ADB thiết bị (mặc định: tự nhận diện)",
    )
    parser.add_argument(
        "-p", "--package",
        default=None,
        help="Package TikTok (mặc định: tự nhận diện)",
    )

    args = parser.parse_args()

    # 1. Video ID
    video_id, clean_url = resolve_video_id(args.url)
    if not video_id:
        print(f"{RED}[!] Không tìm thấy Video ID hợp lệ từ URL: {args.url}{RESET}")
        sys.exit(1)

    # 2. Thiết bị ADB
    serial = resolve_device(args.serial)
    if not serial:
        print(f"{RED}[!] Không tìm thấy thiết bị ADB nào đang kết nối.{RESET}")
        sys.exit(1)

    # 3. Package TikTok
    package = args.package or detect_tiktok_package(serial)

    # 4. Mở video qua ADB
    open_video_via_adb(serial, package, video_id, clean_url)

    # 5. Bấm Thích video
    like_video(serial, timeout=8)


if __name__ == "__main__":
    main()
