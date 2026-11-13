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
import getpass
from typing import Dict, Any

from core.helpers import CYAN, GREEN, YELLOW, RED, WHITE, RESET
from core.ui import (
    render_platform_menu,
    render_saved_config_menu,
    render_job_type_menu,
    HAS_RICH,
    console,
    box,
    Panel,
)

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
    "instagram_sync_delay": 10,
    "human_behavior": True,
    "human_behavior_every_n_jobs": 5,
    "human_behavior_scroll_times": 2,
    "auto_clean_logs_days": 7,
}

# Các khóa lấy từ biến môi trường: không ghi đè/ghi chúng vào config.json.
_ENV_CREDENTIAL_KEYS: set = set()


def _is_tty() -> bool:
    try:
        return bool(sys.stdin and sys.stdin.isatty())
    except Exception:
        return False


def _as_str(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _as_int(value, default: int, minimum: int = 0) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(number, minimum)


def _as_bool(value, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "on", "c", "co"):
        return True
    if text in ("0", "false", "no", "n", "off", "k", "khong"):
        return False
    return default


def _validate_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Chuẩn hóa & kiểm tra kiểu dữ liệu cấu hình trước khi sử dụng."""
    cfg["f4f_user"] = _as_str(cfg.get("f4f_user"), DEFAULT_CONFIG["f4f_user"])
    cfg["f4f_pass"] = _as_str(cfg.get("f4f_pass"), DEFAULT_CONFIG["f4f_pass"])

    platform = _as_str(cfg.get("platform"), DEFAULT_CONFIG["platform"]).lower()
    cfg["platform"] = platform if platform in ("tiktok", "instagram") else "tiktok"

    job_type = _as_str(cfg.get("job_type"), DEFAULT_CONFIG["job_type"]).lower()
    cfg["job_type"] = job_type if job_type in ("all", "follow", "like") else "all"

    for key in ("tiktok_uid", "instagram_username", "adb_serial",
                "tiktok_package", "instagram_package"):
        cfg[key] = _as_str(cfg.get(key), DEFAULT_CONFIG[key])

    cfg["max_jobs_per_session"] = _as_int(
        cfg.get("max_jobs_per_session"),
        DEFAULT_CONFIG["max_jobs_per_session"], minimum=1,
    )
    cfg["delay_min"] = _as_int(
        cfg.get("delay_min"), DEFAULT_CONFIG["delay_min"], minimum=0
    )
    cfg["delay_max"] = _as_int(
        cfg.get("delay_max"), DEFAULT_CONFIG["delay_max"], minimum=cfg["delay_min"]
    )
    if cfg["delay_max"] < cfg["delay_min"]:
        cfg["delay_max"] = cfg["delay_min"]

    cfg["profile_load_timeout"] = _as_int(
        cfg.get("profile_load_timeout"),
        DEFAULT_CONFIG["profile_load_timeout"], minimum=1,
    )
    cfg["verify_timeout"] = _as_int(
        cfg.get("verify_timeout"), DEFAULT_CONFIG["verify_timeout"], minimum=1
    )
    cfg["human_behavior"] = _as_bool(
        cfg.get("human_behavior"), DEFAULT_CONFIG["human_behavior"]
    )
    cfg["human_behavior_every_n_jobs"] = _as_int(
        cfg.get("human_behavior_every_n_jobs"),
        DEFAULT_CONFIG["human_behavior_every_n_jobs"], minimum=1,
    )
    cfg["human_behavior_scroll_times"] = _as_int(
        cfg.get("human_behavior_scroll_times"),
        DEFAULT_CONFIG["human_behavior_scroll_times"], minimum=1,
    )
    cfg["auto_clean_logs_days"] = _as_int(
        cfg.get("auto_clean_logs_days"),
        DEFAULT_CONFIG["auto_clean_logs_days"], minimum=0,
    )
    return cfg


def get_config_path() -> str:
    """Trả về đường dẫn file config hiện có hoặc đường dẫn ưu tiên."""
    if os.path.isfile(PRIMARY_CONFIG_PATH):
        return PRIMARY_CONFIG_PATH
    if os.path.isfile(FALLBACK_CONFIG_PATH):
        return FALLBACK_CONFIG_PATH
    return PRIMARY_CONFIG_PATH


def load_config() -> Dict[str, Any]:
    """Tải cấu hình từ config.json hoặc tạo file mặc định nếu chưa có."""
    global _ENV_CREDENTIAL_KEYS
    _ENV_CREDENTIAL_KEYS = set()

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
    env_map = {
        "f4f_user": "F4F_USER",
        "f4f_pass": "F4F_PASS",
        "platform": "PLATFORM",
        "tiktok_uid": "TIKTOK_UID",
        "instagram_username": "IG_USER",
        "adb_serial": "ADB_SERIAL",
    }
    for key, env_name in env_map.items():
        env_value = os.environ.get(env_name)
        if env_value is not None:
            cfg[key] = env_value
            if key in ("f4f_user", "f4f_pass"):
                _ENV_CREDENTIAL_KEYS.add(key)

    return _validate_config(cfg)


def save_config(cfg: Dict[str, Any]) -> bool:
    """Lưu cấu hình vào file config.json (không ghi đè credential lấy từ ENV)."""
    cfg_file = get_config_path()
    to_save = dict(cfg)

    # Nếu credential đến từ biến môi trường, giữ nguyên giá trị cũ trong file
    # thay vì ghi secret của ENV xuống đĩa.
    if _ENV_CREDENTIAL_KEYS:
        existing: Dict[str, Any] = {}
        if os.path.isfile(cfg_file):
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    existing = loaded
            except Exception:
                existing = {}
        for key in _ENV_CREDENTIAL_KEYS:
            to_save[key] = existing.get(key, DEFAULT_CONFIG.get(key, ""))

    tmp_file = cfg_file + ".tmp"
    try:
        os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, cfg_file)
        try:
            os.chmod(cfg_file, 0o600)
        except OSError:
            pass
        return True
    except Exception as e:
        print(f"[!] Lỗi ghi {cfg_file}: {e}")
        try:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
        except OSError:
            pass
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
    if HAS_RICH and console:
        console.print()
        console.print(
            Panel(
                "[white]Nhập giá trị mới hoặc nhấn [bold yellow]Enter[/bold yellow] để giữ cấu hình hiện tại.[/white]",
                title="[bold cyan]THIẾT LẬP CẤU HÌNH[/bold cyan]",
                border_style="cyan",
                box=box.ROUNDED,
                expand=False,
                padding=(0, 2),
            )
        )
        console.print()
    else:
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
    try:
        val_p = getpass.getpass(p_prompt).strip()
    except (EOFError, KeyboardInterrupt):
        raise
    except Exception:
        # Một số môi trường (IDE/Termux) không hỗ trợ getpass.
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
        val_every = input(f"   └─ Cỡ bao nhiêu job thì lướt feed (ngẫu nhiên ±2 job)? [{cur_every}]: ").strip()
        if val_every.isdigit() and int(val_every) > 0:
            cfg["human_behavior_every_n_jobs"] = int(val_every)

        cur_times = cfg.get("human_behavior_scroll_times", 2)
        val_times = input(f"   └─ Cỡ bao nhiêu video mỗi lần lướt (ngẫu nhiên ±1)? [{cur_times}]: ").strip()
        if val_times.isdigit() and int(val_times) > 0:
            cfg["human_behavior_scroll_times"] = int(val_times)

    # Nền tảng & chế độ job được chọn ở menu đầu tiên (main.py), wizard chỉ
    # tập trung vào thông số phiên chạy nên không hỏi lại ở đây.

    save_config(cfg)
    print(f"\n{GREEN}✓ Đã lưu toàn bộ cấu hình vào config.json!{RESET}\n")
    return cfg


def has_credentials(cfg: Dict[str, Any]) -> bool:
    """Kiểm tra cfg đã có username/password F4F hợp lệ (không phải placeholder)."""
    user = str(cfg.get("f4f_user") or "").strip()
    pwd = str(cfg.get("f4f_pass") or "").strip()
    return bool(user) and user != "your_f4f_username" and bool(pwd) and pwd != "your_f4f_password"


def ensure_credentials(cfg: Dict[str, Any]) -> None:
    """
    Đảm bảo config có thông tin đăng nhập F4F.

    - TTY    : thiếu -> mở wizard; sau wizard vẫn thiếu -> báo lỗi và dừng sớm.
    - Non-TTY: thiếu -> dừng ngay với exit code 1.
    """
    if has_credentials(cfg):
        return

    if not _is_tty():
        print(
            f"{RED}[!] Thiếu F4F_USER/F4F_PASS trong config.json hoặc biến môi trường. "
            f"Không thể chạy ở chế độ không tương tác.{RESET}"
        )
        sys.exit(1)

    print(f"{YELLOW}[!] Chưa có thông tin tài khoản follow4follow.{RESET}")
    cfg.update(interactive_configure(cfg))
    if not has_credentials(cfg):
        print(f"{RED}[!] Vẫn chưa nhập đủ Username/Password follow4follow. Dừng.{RESET}")
        sys.exit(1)


def select_use_saved_config(cfg: Dict[str, Any] = None) -> bool:
    """
    Hỏi người dùng muốn dùng lại cấu hình đã lưu của lần chạy trước (True)
    hay cài đặt lại từ đầu (False). Non-TTY: luôn dùng cấu hình đã lưu.
    """
    if not _is_tty():
        return True

    # Lần đầu chạy / chưa có credential hợp lệ thì bỏ qua câu hỏi, vào wizard luôn.
    if not has_credentials(cfg or {}):
        print(f"{YELLOW}[i] Chưa có cấu hình hợp lệ trong config.json — sẽ mở trình cài đặt.{RESET}")
        return False

    render_saved_config_menu()
    try:
        choice = input(
            f"{CYAN}›{RESET} Chọn [1/2] {CYAN}(Enter = 1 - dùng cấu hình cũ){RESET}: "
        ).strip().lower()
    except KeyboardInterrupt:
        print("\nĐã hủy.")
        sys.exit(130)
    except EOFError:
        print("\nĐã hủy.")
        sys.exit(1)
    return choice not in ("2", "c", "new", "moi", "setup", "sua")


def select_platform_menu(cfg: Dict[str, Any]) -> str:
    """Hiển thị menu cho người dùng lựa chọn nền tảng muốn chạy."""
    current = str(cfg.get("platform", "tiktok")).lower()
    if not _is_tty():
        return "instagram" if ("ig" in current or "insta" in current) else "tiktok"

    render_platform_menu()

    cur_plat = current
    def_num = "2" if ("ig" in cur_plat or "insta" in cur_plat) else "1"

    try:
        choice = input(f"{CYAN}›{RESET} Chọn [1/2] {CYAN}(Enter = {def_num}){RESET}: ").strip().lower()
        if choice in ("2", "ig", "insta", "instagram"):
            cfg["platform"] = "instagram"
            selected = "instagram"
        elif choice in ("1", "tt", "tik", "tiktok"):
            cfg["platform"] = "tiktok"
            selected = "tiktok"
        else:
            # Enter (hoặc lựa chọn không hợp lệ) phải dùng đúng nền tảng mặc định.
            selected = "instagram" if def_num == "2" else "tiktok"
            cfg["platform"] = selected
        return selected
    except KeyboardInterrupt:
        print("\nĐã hủy.")
        sys.exit(130)
    except EOFError:
        print("\nĐã hủy.")
        sys.exit(1)


def select_job_type_menu(cfg: Dict[str, Any]) -> str:
    """Hiển thị menu cho người dùng lựa chọn loại job TikTok."""
    default_type = cfg.get("job_type", "all")
    if default_type not in ("follow", "like", "all"):
        default_type = "all"
    type_map = {
        "1": "follow",
        "2": "like",
        "3": "all",
        "follow": "follow",
        "like": "like",
        "all": "all",
    }

    if not _is_tty():
        return default_type

    render_job_type_menu()

    def_num = "3"
    if default_type == "follow":
        def_num = "1"
    elif default_type == "like":
        def_num = "2"

    try:
        choice = input(
            f"{CYAN}›{RESET} Chọn chế độ [1/2/3] {CYAN}(Enter = {def_num}){RESET}: "
        ).strip().lower()
        if not choice:
            selected = default_type
        elif choice in type_map:
            selected = type_map[choice]
        else:
            print(f"{YELLOW}[!] Lựa chọn không hợp lệ, dùng mặc định: {default_type}{RESET}")
            selected = default_type
        cfg["job_type"] = selected
        return selected
    except KeyboardInterrupt:
        print("\nĐã hủy.")
        sys.exit(130)
    except EOFError:
        print("\nĐã hủy.")
        sys.exit(1)
