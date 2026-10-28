"""
config/settings.py — Quản lý cấu hình tập trung và tương tác console
===================================================================
Bao gồm:
  - Tải & lưu cấu hình từ config.json hoặc biến môi trường
  - Trình hướng dẫn thiết lập cấu hình trực tiếp qua terminal (không cần sửa file thủ công)
  - Menu lựa chọn nền tảng và chế độ làm job
  - Tự động dọn dẹp các file log cũ để giải phóng bộ nhớ
"""

import os
import sys
import json
import time
import re
from typing import Dict, Any

from core.helpers import CYAN, GREEN, YELLOW, RED, WHITE, RESET

# Đường dẫn thư mục gốc và file config
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_DIR = os.path.dirname(__file__)

# Ưu tiên config/config.json, nếu không tìm thấy sẽ kiểm tra config.json ở thư mục gốc
PRIMARY_CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
FALLBACK_CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")

LOG_DIR = os.path.join(ROOT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

DEFAULT_CONFIG: Dict[str, Any] = {
    "f4f_user": "",
    "f4f_pass": "",
    "platform": "tiktok",
    "tiktok_uid": "",
    "instagram_username": "",
    "job_type": "all",
    "adb_serial": "auto",
    "tiktok_package": "auto",
    "instagram_package": "auto",
    "max_jobs_per_session": 50,
    "delay_min": 8,
    "delay_max": 18,
    "profile_load_timeout": 8,
    "verify_timeout": 3,
    "human_behavior": True,
    "human_behavior_every_n_jobs": 5,
    "human_behavior_scroll_times": 2,
    "auto_clean_logs_days": 7,
}


def get_config_path() -> str:
    """Trả về đường dẫn file config hiện có hoặc đường dẫn ưu tiên."""
    if os.path.isfile(PRIMARY_CONFIG_PATH):
        return PRIMARY_CONFIG_PATH
    if os.path.isfile(FALLBACK_CONFIG_PATH):
        return FALLBACK_CONFIG_PATH
    return PRIMARY_CONFIG_PATH


def load_config() -> Dict[str, Any]:
    """Tải cấu hình từ config.json hoặc tạo file mặc định nếu chưa có."""
    cfg = DEFAULT_CONFIG.copy()
    cfg_file = get_config_path()

    if os.path.isfile(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                cfg.update(user_cfg)
        except Exception as e:
            print(f"[!] Lỗi đọc {cfg_file}: {e}")
    else:
        try:
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # Biến môi trường có độ ưu tiên cao nhất nếu được thiết lập
    cfg["f4f_user"] = os.environ.get("F4F_USER", cfg["f4f_user"])
    cfg["f4f_pass"] = os.environ.get("F4F_PASS", cfg["f4f_pass"])
    cfg["platform"] = os.environ.get("PLATFORM", cfg["platform"])
    cfg["tiktok_uid"] = os.environ.get("TIKTOK_UID", cfg["tiktok_uid"])
    cfg["instagram_username"] = os.environ.get("IG_USER", cfg["instagram_username"])
    cfg["adb_serial"] = os.environ.get("ADB_SERIAL", cfg["adb_serial"])
    return cfg


def save_config(cfg: Dict[str, Any]) -> bool:
    """Lưu cấu hình vào file config.json."""
    cfg_file = get_config_path()
    try:
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[!] Lỗi ghi {cfg_file}: {e}")
        return False


def cleanup_old_logs(days: int = 7):
    """Tự động xóa các file log cũ hơn N ngày để tiết kiệm dung lượng."""
    if days <= 0:
        return
    try:
        now = time.time()
        cutoff = now - (days * 86400)
        for fname in os.listdir(LOG_DIR):
            if fname.endswith(".log"):
                fpath = os.path.join(LOG_DIR, fname)
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
    except Exception:
        pass


def interactive_configure(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Trình hướng dẫn thiết lập cấu hình trực quan qua console."""
    print(f"\n{CYAN}╭─ {WHITE}THIẾT LẬP CẤU HÌNH{CYAN} ─────────────────────────────────────╮{RESET}")
    print(f"{CYAN}│{RESET}  Nhập giá trị mới hoặc nhấn {YELLOW}Enter{RESET} để giữ cấu hình hiện tại. {CYAN}│{RESET}")
    print(f"{CYAN}╰────────────────────────────────────────────────────────────╯{RESET}\n")

    # 1. Tài khoản F4F
    cur_u = cfg.get("f4f_user", "")
    if cur_u in ("your_f4f_username", ""):
        cur_u = ""
    u_prompt = f"1. F4F Username [{cur_u}]: " if cur_u else "1. F4F Username: "
    val_u = input(u_prompt).strip()
    if val_u:
        cfg["f4f_user"] = val_u

    # 2. Mật khẩu F4F
    cur_p = cfg.get("f4f_pass", "")
    if cur_p in ("your_f4f_password", ""):
        cur_p = ""
    masked_p = "••••••••" if cur_p else ""
    p_prompt = f"2. F4F Password [{masked_p}]: " if masked_p else "2. F4F Password: "
    val_p = input(p_prompt).strip()
    if val_p:
        cfg["f4f_pass"] = val_p

    # 3. Số job tối đa
    cur_max = cfg.get("max_jobs_per_session", 50)
    val_max = input(f"3. Số job tối đa muốn chạy phiên này [{cur_max}]: ").strip()
    if val_max.isdigit() and int(val_max) > 0:
        cfg["max_jobs_per_session"] = int(val_max)

    # 4. Delay nghỉ giữa các job (hỗ trợ nhập min-max, min, hoặc Enter)
    cur_min = cfg.get("delay_min", 8)
    cur_max_delay = cfg.get("delay_max", 18)
    val_delay = input(f"4. Delay nghỉ giữa các job (giây) (VD: 8-18 hoặc 10) [{cur_min}-{cur_max_delay}]: ").strip()
    if val_delay:
        nums = [int(n) for n in re.findall(r"\d+", val_delay)]
        if len(nums) >= 2:
            cfg["delay_min"] = min(nums[0], nums[1])
            cfg["delay_max"] = max(nums[0], nums[1])
        elif len(nums) == 1:
            cfg["delay_min"] = nums[0]
            cfg["delay_max"] = nums[0]

    # 5. Chế độ lướt feed (Anti-Ban)
    cur_hb = cfg.get("human_behavior", True)
    hb_str = "Y" if cur_hb else "n"
    val_hb = input(f"5. Bật mô phỏng lướt feed chống ban? [Y/n] (Mặc định: {hb_str}): ").strip().lower()
    if val_hb in ("n", "no", "k", "khong"):
        cfg["human_behavior"] = False
    elif val_hb in ("y", "yes", "c", "co") or not val_hb:
        cfg["human_behavior"] = True

    if cfg.get("human_behavior", True):
        cur_every = cfg.get("human_behavior_every_n_jobs", 5)
        val_every = input(f"   └─ Sau bao nhiêu job thì lướt feed? [{cur_every}]: ").strip()
        if val_every.isdigit() and int(val_every) > 0:
            cfg["human_behavior_every_n_jobs"] = int(val_every)

        cur_times = cfg.get("human_behavior_scroll_times", 2)
        val_times = input(f"   └─ Mỗi lần lướt bao nhiêu video? [{cur_times}]: ").strip()
        if val_times.isdigit() and int(val_times) > 0:
            cfg["human_behavior_scroll_times"] = int(val_times)

    save_config(cfg)
    print(f"\n{GREEN}✓ Đã lưu toàn bộ cấu hình vào config.json!{RESET}\n")
    return cfg


def check_or_prompt_credentials(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Kiểm tra và cho phép chỉnh sửa cấu hình trực tiếp từ terminal."""
    has_user = bool(cfg.get("f4f_user") and cfg["f4f_user"] not in ("your_f4f_username", ""))
    has_pass = bool(cfg.get("f4f_pass") and cfg["f4f_pass"] not in ("your_f4f_password", ""))

    if not sys.stdin.isatty():
        return cfg

    if has_user and has_pass:
        every_n = cfg.get("human_behavior_every_n_jobs", 5)
        times = cfg.get("human_behavior_scroll_times", 2)
        hb_desc = f"Cứ sau {every_n} jobs -> Lướt {times} video" if cfg.get("human_behavior", True) else "Tắt"

        print(f"{CYAN}╭─ {WHITE}SESSION OVERVIEW{CYAN} ───────────────────────────────────────╮{RESET}")
        print(f"{CYAN}│{RESET}  {CYAN}ACCOUNT{RESET}    {GREEN}{cfg['f4f_user']:<48}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {CYAN}JOB MODE{RESET}   {WHITE}{cfg.get('job_type', 'all'):<48}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {CYAN}JOB LIMIT{RESET}  {WHITE}{str(cfg.get('max_jobs_per_session', 50)):<8}{RESET}  {CYAN}DELAY{RESET}  {WHITE}{cfg.get('delay_min', 8)}-{cfg.get('delay_max', 18)}s{RESET}{' ' * 18}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {CYAN}BROWSE{RESET}     {YELLOW}{hb_desc:<48}{CYAN}│{RESET}")
        print(f"{CYAN}╰────────────────────────────────────────────────────────────╯{RESET}")

        try:
            choice = input(f"{CYAN}›{RESET} {WHITE}Enter{RESET} = chạy ngay  {CYAN}|{RESET}  {YELLOW}2/c{RESET} = chỉnh cấu hình  {CYAN}» {RESET}").strip().lower()
            if choice in ("2", "c", "edit", "config", "s", "sua", "y", "yes"):
                cfg = interactive_configure(cfg)
        except (EOFError, KeyboardInterrupt):
            print("\nĐã hủy.")
            sys.exit(0)
        return cfg

    print(f"{YELLOW}[!] Chưa có thông tin tài khoản follow4follow.{RESET}")
    try:
        cfg = interactive_configure(cfg)
    except (EOFError, KeyboardInterrupt):
        print("\nĐã hủy.")
        sys.exit(0)
    return cfg


def select_platform_menu(cfg: Dict[str, Any]) -> str:
    """Hiển thị menu cho người dùng lựa chọn nền tảng muốn chạy."""
    if not sys.stdin.isatty():
        return cfg.get("platform", "tiktok")

    print(f"\n{CYAN}╭─ {WHITE}CHỌN NỀN TẢNG{CYAN} ─────────────────────────────────────────╮{RESET}")
    print(f"{CYAN}│{RESET}  {YELLOW}[1]{RESET}  {WHITE}TikTok{RESET}      {CYAN}Follow tài khoản + Like video{RESET}             {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {YELLOW}[2]{RESET}  {GREEN}Instagram{RESET}  {CYAN}Follow trang cá nhân (+35 xu){RESET}            {CYAN}│{RESET}")
    print(f"{CYAN}╰────────────────────────────────────────────────────────────╯{RESET}")

    cur_plat = cfg.get("platform", "tiktok").lower()
    def_num = "2" if ("ig" in cur_plat or "insta" in cur_plat) else "1"

    try:
        choice = input(f"{CYAN}›{RESET} Chọn [1/2] {CYAN}(Enter = {def_num}){RESET}: ").strip().lower()
        if choice in ("2", "ig", "insta", "instagram"):
            cfg["platform"] = "instagram"
            return "instagram"
        else:
            cfg["platform"] = "tiktok"
            return "tiktok"
    except (EOFError, KeyboardInterrupt):
        print("\nĐã hủy.")
        sys.exit(0)


def select_job_type_menu(cfg: Dict[str, Any]) -> str:
    """Hiển thị menu cho người dùng lựa chọn loại job TikTok."""
    default_type = cfg.get("job_type", "all")
    type_map = {
        "1": "follow",
        "2": "like",
        "3": "all",
        "follow": "follow",
        "like": "like",
        "all": "all",
    }
    type_labels = {
        "follow": "1. Chỉ chạy Follow",
        "like": "2. Chỉ chạy Like",
        "all": "3. Kết hợp (Cả Follow & Like)",
    }

    if not sys.stdin.isatty():
        return cfg.get("job_type", "all")

    print(f"\n{CYAN}╭─ {WHITE}CHẾ ĐỘ JOB TIKTOK{CYAN} ──────────────────────────────────────╮{RESET}")
    print(f"{CYAN}│{RESET}  {YELLOW}[1]{RESET}  {WHITE}FOLLOW ONLY{RESET}   {CYAN}Chỉ follow tài khoản{RESET}                   {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {YELLOW}[2]{RESET}  {WHITE}LIKE ONLY{RESET}     {CYAN}Chỉ like video{RESET}                         {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {YELLOW}[3]{RESET}  {GREEN}MIXED MODE{RESET}    {CYAN}Kết hợp Follow + Like{RESET}                {CYAN}│{RESET}")
    print(f"{CYAN}╰────────────────────────────────────────────────────────────╯{RESET}")

    def_num = "3"
    if default_type == "follow":
        def_num = "1"
    elif default_type == "like":
        def_num = "2"

    try:
        choice = input(
            f"{CYAN}›{RESET} Chọn chế độ [1/2/3] {CYAN}(Enter = {def_num}){RESET}: "
        ).strip().lower()
        selected = type_map.get(choice, default_type if not choice else "all")
    except (EOFError, KeyboardInterrupt):
        print("\nĐã hủy.")
        sys.exit(0)

    cfg["job_type"] = selected
    return selected

    cfg["job_type"] = selected
    return selected
