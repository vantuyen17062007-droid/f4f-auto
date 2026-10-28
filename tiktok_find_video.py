import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Terminal color styling
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def get_connected_devices():
    """Lấy danh sách các thiết bị ADB đang ở trạng thái 'device'."""
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        devices = []
        for line in res.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except Exception as e:
        print(f"{RED}[!] Không thể chạy adb devices: {e}{RESET}")
        return []


def resolve_device(preferred_serial=None):
    """Xác định serial thiết bị ADB phù hợp."""
    devices = get_connected_devices()
    if not devices:
        return None

    if preferred_serial and preferred_serial != "auto":
        if preferred_serial in devices:
            return preferred_serial
        # Nếu serial dạng IP:port, thử connect
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
    """Tìm package TikTok đang cài đặt trên thiết bị."""
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
    """
    Trích xuất video ID và username từ URL hoặc chuỗi ID thuần túy.
    Hỗ trợ:
      - https://www.tiktok.com/@tuandidau/video/7699698031045790984
      - https://vt.tiktok.com/ZS.../ (tự động theo redirect)
      - 7699698031045790984
    """
    target = str(target_url_or_id).strip()
    
    # 1. Nếu là số ID thuần túy
    if target.isdigit():
        return None, target, f"https://www.tiktok.com/video/{target}"

    # 2. Nếu là short URL (vt.tiktok.com, vm.tiktok.com), theo redirect
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

    # 3. Trích xuất username & video ID bằng regex
    username = None
    u_match = re.search(r"@([a-zA-Z0-9_\.\-]+)", target)
    if u_match:
        username = u_match.group(1)

    v_match = re.search(r"/video/(\d+)", target)
    if v_match:
        video_id = v_match.group(1)
        return username, video_id, target

    # Nếu không khớp mẫu chuẩn, tìm chuỗi số dài nhất (thường là video ID)
    digits = re.findall(r"\d{15,25}", target)
    if digits:
        return username, digits[0], target

    return username, None, target


def open_video_via_adb(serial, package_name, video_id, full_url=None):
    """
    Gửi intent mở trực tiếp video vào TikTok thông qua DeepLinkActivityV2.
    """
    # Lựa chọn scheme dựa trên package
    if "trill" in package_name:
        scheme = "snssdk1180"
    else:
        scheme = "snssdk1233"

    deeplink_uri = f"{scheme}://aweme/detail/{video_id}"

    # Lựa chọn class DeepLinkActivityV2 tương ứng
    if package_name.endswith(".go"):
        cmp_activity = f"{package_name}/.deeplink.DeepLinkActivityV2"
    else:
        cmp_activity = f"{package_name}/com.ss.android.ugc.aweme.deeplink.DeepLinkActivityV2"

    print(f"{CYAN}[*]{RESET} Gửi intent mở video:")
    print(f"    - Device:     {GREEN}{serial}{RESET}")
    print(f"    - Package:    {GREEN}{package_name}{RESET}")
    print(f"    - Video ID:   {GREEN}{video_id}{RESET}")
    print(f"    - URI Scheme: {DIM}{deeplink_uri}{RESET}")

    # Cách 1: Gửi thẳng vào DeepLinkActivityV2 (nhanh, chuẩn xác và không bị nuốt bởi ApplinkHookActivity)
    cmd = [
        "adb", "-s", serial, "shell",
        "am", "start",
        "-n", cmp_activity,
        "-a", "android.intent.action.VIEW",
        "-d", deeplink_uri,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    output = res.stdout.strip()

    # Cách 2: Nếu có lỗi component, fallback sang intent action VIEW thông thường
    if "Error" in output or "does not exist" in output:
        print(f"{YELLOW}[!] Thử fallback intent android.intent.action.VIEW...{RESET}")
        url_to_open = full_url if full_url else deeplink_uri
        cmd_fallback = [
            "adb", "-s", serial, "shell",
            "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", url_to_open,
            "-p", package_name,
        ]
        res = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=8)
        output = res.stdout.strip()

    return output


def inspect_video_ui(serial, expected_author=None, timeout=8):
    """
    Đọc cấu trúc UI trên màn hình sau khi mở video, lấy các thông số chi tiết của video.
    """
    print(f"{CYAN}[*]{RESET} Đang kiểm tra giao diện video trên màn hình (chờ tối đa {timeout}s)...")
    
    start_time = time.time()
    try:
        import uiautomator2 as u2
        d = u2.connect(serial)
    except Exception as e:
        print(f"{YELLOW}[!] uiautomator2 không khả dụng ({e}), sử dụng adb dumpsys...{RESET}")
        d = None

    video_info = {
        "status": "not_detected",
        "author": None,
        "post_time": None,
        "description": None,
        "location": None,
        "audio": None,
        "likes": None,
        "comments": None,
        "favorites": None,
        "shares": None,
        "is_liked": False,
        "is_favorited": False,
        "follow_btn": None,
    }

    if d is None:
        return video_info

    while time.time() - start_time < timeout:
        time.sleep(1.0)
        nodes = []
        try:
            for el in d.xpath("//*").all():
                t = el.attrib.get("text", "").strip()
                desc = el.attrib.get("content-desc", "").strip()
                res = el.attrib.get("resource-id", "")
                bounds = el.attrib.get("bounds", "")
                nodes.append({"text": t, "desc": desc, "id": res, "bounds": bounds})
        except Exception:
            continue

        for n in nodes:
            res_id = n["id"]
            text = n["text"]
            desc = n["desc"]

            # Author name
            if res_id.endswith(":id/title") and text:
                video_info["author"] = text

            # Post time
            if res_id.endswith(":id/tv_post_time") and text:
                video_info["post_time"] = text

            # Description / caption
            if res_id.endswith(":id/desc") and text:
                video_info["description"] = text

            # Location
            if res_id.endswith(":id/sf2") and text:
                video_info["location"] = text

            # Audio
            if res_id.endswith(":id/pog") and desc:
                video_info["audio"] = desc

            # Likes count & status
            if "lượt thích" in desc:
                m = re.search(r"(\d+[\d\.,]*)\s*lượt thích", desc)
                if m:
                    video_info["likes"] = m.group(1)
            elif res_id.endswith(":id/g8b") and text:
                video_info["likes"] = text

            if desc == "Đã thích" or "Bỏ thích" in desc:
                video_info["is_liked"] = True

            # Comments count
            if "bình luận" in desc:
                m = re.search(r"(\d+[\d\.,]*)\s*bình luận", desc)
                if m:
                    video_info["comments"] = m.group(1)
            elif res_id.endswith(":id/ek3") and text:
                video_info["comments"] = text

            # Favorites count & status
            if res_id.endswith(":id/i8_") and text:
                video_info["favorites"] = text
            if "Đã thêm vào mục Yêu thích" in desc:
                video_info["is_favorited"] = True

            # Shares count
            if "lượt chia sẻ" in desc:
                m = re.search(r"(\d+[\d\.,]*)\s*lượt chia sẻ", desc)
                if m:
                    video_info["shares"] = m.group(1)
            elif res_id.endswith(":id/w6z") and text:
                video_info["shares"] = text

            # Follow button
            if "Follow " in desc or "Theo dõi " in desc:
                video_info["follow_btn"] = desc

        # Nếu đã tìm thấy tác giả hoặc mô tả, coi như đã tải xong video
        if video_info["author"] or video_info["description"] or video_info["likes"]:
            video_info["status"] = "success"
            break

    return video_info


def main():
    parser = argparse.ArgumentParser(
        description="Tìm và mở video TikTok bằng ADB thông qua Intent/DeepLink."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="https://www.tiktok.com/@tuandidau/video/7699698031045790984",
        help="Đường dẫn video TikTok hoặc video ID (mặc định: link của đề bài)",
    )
    parser.add_argument(
        "-s", "--serial",
        default=None,
        help="Serial ADB của thiết bị (mặc định: tự động tìm)",
    )
    parser.add_argument(
        "-p", "--package",
        default=None,
        help="Package TikTok (mặc định: tự động phát hiện)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất kết quả dưới định dạng JSON",
    )

    args = parser.parse_args()

    # 1. Xác định Video ID
    username, video_id, clean_url = resolve_video_id(args.url)
    if not video_id:
        print(f"{RED}[!] Không thể trích xuất Video ID từ URL: {args.url}{RESET}")
        sys.exit(1)

    # 2. Xác định Thiết bị ADB
    serial = resolve_device(args.serial)
    if not serial:
        print(f"{RED}[!] Không tìm thấy thiết bị ADB nào đang kết nối.{RESET}")
        print(f"    Hãy cắm cáp hoặc kết nối ADB qua mạng: adb connect <IP:PORT>")
        sys.exit(1)

    # 3. Xác định Package TikTok
    package = args.package or detect_tiktok_package(serial)

    # 4. Mở video
    output = open_video_via_adb(serial, package, video_id, clean_url)

    # 5. Kiểm tra UI và lấy thông tin video
    info = inspect_video_ui(serial, expected_author=username, timeout=6)

    # 6. Hiển thị kết quả
    if args.json:
        result = {
            "device": serial,
            "package": package,
            "video_id": video_id,
            "url": clean_url,
            "adb_output": output,
            "video_details": info,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("\n" + "=" * 55)
    if info["status"] == "success":
        print(f"{GREEN}{BOLD}[✓] ĐÃ TÌM VÀ MỞ THÀNH CÔNG VIDEO TRÊN THIẾT BỊ!{RESET}")
    else:
        print(f"{YELLOW}[!] Lệnh mở video đã gửi nhưng chưa đọc được UI chi tiết.{RESET}")
    print("=" * 55)
    print(f" {BOLD}Tác giả:{RESET}      {GREEN}{info['author'] or username or 'N/A'}{RESET}")
    print(f" {BOLD}Thời gian:{RESET}    {info['post_time'] or 'N/A'}")
    print(f" {BOLD}Mô tả:{RESET}        {info['description'] or 'N/A'}")
    if info["location"]:
        print(f" {BOLD}Địa điểm:{RESET}     {CYAN}{info['location']}{RESET}")
    if info["audio"]:
        print(f" {BOLD}Âm thanh:{RESET}     {info['audio']}")
    print(f" {BOLD}Thống kê:{RESET}")
    print(f"   - Lượt thích:     {YELLOW}{info['likes'] or 'N/A'}{RESET} ({'Đã thích' if info['is_liked'] else 'Chưa thích'})")
    print(f"   - Bình luận:      {YELLOW}{info['comments'] or 'N/A'}{RESET}")
    print(f"   - Yêu thích:      {YELLOW}{info['favorites'] or 'N/A'}{RESET}")
    print(f"   - Lượt chia sẻ:   {YELLOW}{info['shares'] or 'N/A'}{RESET}")
    print(f"   - Trạng thái nút: {info['follow_btn'] or 'N/A'}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
