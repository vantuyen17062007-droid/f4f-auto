"""
TikTok Follow4Follow Auto Job Runner (Cross-Platform: PC & Android Termux)
========================================================================
Tối ưu hóa:
  - Tự động nhận diện thiết bị kết nối (PC, USB hoặc Termux Wireless ADB)
  - Tự động nhận diện package TikTok trên máy (com.ss.android.ugc.trill, ...)
  - Tự động lấy danh sách tài khoản TikTok từ f4f (get_acc_tik)
  - Cấu hình tương tác trực tiếp qua console mà không cần mở file config.json
  - Cấu hình human_behavior: chạy sau bao nhiêu job và lướt bao nhiêu video
  - Tự động tắt popup phiền toái (đồng bộ danh bạ, bật thông báo, ...)
  - Cơ chế tự dọn dẹp file log cũ hơn N ngày
"""

import os
import sys
import json
import time
import random
import logging
from datetime import datetime

# UTF-8 cho console (Windows & Linux/Termux)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from f4f_tiktok import f4f
from adbcontrol import AdbController

# ── Quản lý cấu hình ──────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULT_CONFIG = {
    "f4f_user": "",
    "f4f_pass": "",
    "platform": "tiktok",
    "tiktok_uid": "",
    "instagram_username": "",
    "adb_serial": "auto",
    "tiktok_package": "auto",
    "instagram_package": "auto",
    "job_type": "all",
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


def load_config():
    """Tải cấu hình từ config.json hoặc tạo file mặc định nếu chưa có."""
    cfg = DEFAULT_CONFIG.copy()
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                cfg.update(user_cfg)
        except Exception as e:
            print(f"[!] Lỗi đọc config.json: {e}")
    else:
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # Biến môi trường có độ ưu tiên cao nhất nếu được thiết lập
    cfg["f4f_user"] = os.environ.get("F4F_USER", cfg["f4f_user"])
    cfg["f4f_pass"] = os.environ.get("F4F_PASS", cfg["f4f_pass"])
    cfg["tiktok_uid"] = os.environ.get("TIKTOK_UID", cfg["tiktok_uid"])
    cfg["adb_serial"] = os.environ.get("ADB_SERIAL", cfg["adb_serial"])
    cfg["tiktok_package"] = os.environ.get("TIKTOK_PKG", cfg["tiktok_package"])
    return cfg


CONFIG = load_config()

# ── Quản lý Logs ──────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def cleanup_old_logs(days):
    """Tự động xóa các file log cũ để tiết kiệm bộ nhớ máy tính / điện thoại."""
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


cleanup_old_logs(CONFIG.get("auto_clean_logs_days", 7))

log_file = os.path.join(LOG_DIR, f"session_{datetime.now():%Y%m%d_%H%M%S}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
log = logging.getLogger("f4f-runner")

# ── Màu hiển thị ───────────────────────────────────────────────
G = "\033[92m"   # green
Y = "\033[93m"   # yellow
R = "\033[91m"   # red
C = "\033[96m"   # cyan
W = "\033[97m"   # white
D = "\033[0m"    # reset


def banner():
    print(f"""
{C}╔══════════════════════════════════════════════════════╗
║     Follow4Follow Multi-Platform Auto Runner 2.0     ║
║     Hỗ trợ: TikTok & Instagram (PC & Termux)         ║
╚══════════════════════════════════════════════════════╝{D}
""")


def interactive_configure(cfg):
    """
    Trình hướng dẫn thiết lập cấu hình trực quan qua console.
    Người dùng chỉ cần nhập trực tiếp hoặc nhấn Enter để giữ nguyên giá trị trong ngoặc [].
    """
    print(f"\n{C}── CẤU HÌNH THÔNG SỐ CHẠY TOOL ──────────────────────────{D}")
    print(f"{W}(Nhấn Enter để giữ nguyên giá trị mặc định trong ngoặc []){D}\n")

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

    # 4. Delay nghỉ giữa các job
    cur_min = cfg.get("delay_min", 8)
    cur_max_delay = cfg.get("delay_max", 18)
    val_delay = input(f"4. Delay nghỉ giữa các job (giây) (VD: 8-18 hoặc 10) [{cur_min}-{cur_max_delay}]: ").strip()
    if val_delay:
        import re
        nums = [int(n) for n in re.findall(r"\d+", val_delay)]
        if len(nums) >= 2:
            cfg["delay_min"] = min(nums[0], nums[1])
            cfg["delay_max"] = max(nums[0], nums[1])
        elif len(nums) == 1:
            cfg["delay_min"] = nums[0]
            cfg["delay_max"] = nums[0]  # delay cố định đúng số giây này

    # 5. Chế độ lướt feed (Anti-Ban)
    cur_hb = cfg.get("human_behavior", True)
    hb_str = "Y" if cur_hb else "n"
    val_hb = input(f"5. Bật mô phỏng lướt feed chống ban? [Y/n] (Mặc định: {hb_str}): ").strip().lower()
    if val_hb in ("n", "no", "k", "khong"):
        cfg["human_behavior"] = False
    elif val_hb in ("y", "yes", "c", "co") or not val_hb:
        cfg["human_behavior"] = True

    if cfg.get("human_behavior", True):
        # Sau bao nhiêu job thì lướt video
        cur_every = cfg.get("human_behavior_every_n_jobs", 5)
        val_every = input(f"   └─ Sau bao nhiêu job thì lướt video? [{cur_every}]: ").strip()
        if val_every.isdigit() and int(val_every) > 0:
            cfg["human_behavior_every_n_jobs"] = int(val_every)

        # Mỗi lần lướt mấy video
        cur_times = cfg.get("human_behavior_scroll_times", 2)
        val_times = input(f"   └─ Mỗi lần lướt bao nhiêu video? [{cur_times}]: ").strip()
        if val_times.isdigit() and int(val_times) > 0:
            cfg["human_behavior_scroll_times"] = int(val_times)

    # Lưu lại vào config.json
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print(f"\n{G}✓ Đã lưu toàn bộ cấu hình vào config.json!{D}\n")
    except Exception as e:
        print(f"\n{R}[!] Lỗi lưu config.json: {e}{D}\n")

    return cfg


def check_or_prompt_credentials(cfg):
    """
    Kiểm tra và cho phép người dùng chỉnh sửa cấu hình trực tiếp từ terminal.
    - Nếu đã có tài khoản: In bảng tóm tắt và cho tùy chọn Enter (Chạy luôn) hoặc gõ 'c' (Chỉnh sửa).
    - Nếu chưa có: Tự động chạy trình thiết lập cấu hình.
    """
    has_user = bool(cfg.get("f4f_user") and cfg["f4f_user"] not in ("your_f4f_username", ""))
    has_pass = bool(cfg.get("f4f_pass") and cfg["f4f_pass"] not in ("your_f4f_password", ""))

    if not sys.stdin.isatty():
        return cfg

    if has_user and has_pass:
        every_n = cfg.get("human_behavior_every_n_jobs", 5)
        times = cfg.get("human_behavior_scroll_times", 2)
        hb_desc = f"Cứ sau {every_n} jobs -> Lướt {times} video" if cfg.get("human_behavior", True) else "Tắt"

        print(f"{C}┌── Cấu hình hiện tại ────────────────────────────────────────┐{D}")
        print(f"{C}│{D} • Tài khoản F4F : {G}{cfg['f4f_user']:<43}{D}{C}│{D}")
        print(f"{C}│{D} • Chế độ job    : {W}{cfg.get('job_type', 'all'):<43}{D}{C}│{D}")
        print(f"{C}│{D} • Số jobs chạy  : {W}{str(cfg.get('max_jobs_per_session', 50)):<6}{D} │ Delay: {W}{cfg.get('delay_min', 8)}-{cfg.get('delay_max', 18)}s{D}{' '*18}{C}│{D}")
        print(f"{C}│{D} • Chống ban     : {Y}{hb_desc:<43}{D}{C}│{D}")
        print(f"{C}└─────────────────────────────────────────────────────────────┘{D}")

        try:
            choice = input(f"{Y}[?] Nhấn Enter (hoặc 1) để CHẠY NGAY, gõ 2 (hoặc 'c') để cấu hình lại: {D}").strip().lower()
            if choice in ("2", "c", "edit", "config", "s", "sua", "y", "yes"):
                cfg = interactive_configure(cfg)
        except (EOFError, KeyboardInterrupt):
            print("\nĐã hủy.")
            sys.exit(0)
        return cfg

    # Nếu chưa có thông tin
    print(f"{Y}[!] config.json chưa có thông tin tài khoản follow4follow.{D}")
    try:
        cfg = interactive_configure(cfg)
    except (EOFError, KeyboardInterrupt):
        print("\nĐã hủy.")
        sys.exit(0)
    return cfg


def select_platform_menu(cfg):
    """
    Hiển thị menu cho người dùng lựa chọn nền tảng:
    [1] TikTok (Follow & Like video)
    [2] Instagram (Follow trang cá nhân)
    """
    if not sys.stdin.isatty():
        return cfg.get("platform", "tiktok")

    print(f"\n{C}┌── CHỌN NỀN TẢNG KIẾM COIN ────────────────────────────────┐{D}")
    print(f"{C}│{D}  [1] {W}TikTok{D} (Hỗ trợ Follow nick & Like video)                  {C}│{D}")
    print(f"{C}│{D}  [2] {G}Instagram{D} (Hỗ trợ Follow trang cá nhân +35 xu)          {C}│{D}")
    print(f"{C}└─────────────────────────────────────────────────────────────┘{D}")

    cur_plat = cfg.get("platform", "tiktok").lower()
    def_num = "2" if ("ig" in cur_plat or "insta" in cur_plat) else "1"

    try:
        choice = input(f"{Y}[?] Chọn nền tảng [1: TikTok / 2: Instagram] (Enter = [{def_num}]): {D}").strip().lower()
        if choice in ("2", "ig", "insta", "instagram"):
            cfg["platform"] = "instagram"
            log.info(f"{G}✓ Đã chọn nền tảng:{D} {C}Instagram{D}")
            return "instagram"
        else:
            cfg["platform"] = "tiktok"
            log.info(f"{G}✓ Đã chọn nền tảng:{D} {C}TikTok{D}")
            return "tiktok"
    except (EOFError, KeyboardInterrupt):
        print("\nĐã hủy.")
        sys.exit(0)


def select_job_type_menu(cfg):
    """
    Hiển thị menu cho người dùng lựa chọn loại job:
    [1] Follow TikTok
    [2] Like TikTok
    [3] Chạy kết hợp (Cả Follow & Like)
    """
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

    print(f"\n{C}┌── MENU LỰA CHỌN LOẠI JOB ───────────────────────────────────┐{D}")
    print(f"{C}│{D}  [1] {W}Chỉ làm Job Follow TikTok{D}                                 {C}│{D}")
    print(f"{C}│{D}  [2] {W}Chỉ làm Job Like TikTok{D}                                   {C}│{D}")
    print(f"{C}│{D}  [3] {G}Chạy kết hợp cả hai (Follow & Like){D}                       {C}│{D}")
    print(f"{C}└─────────────────────────────────────────────────────────────┘{D}")

    def_num = "3"
    if default_type == "follow":
        def_num = "1"
    elif default_type == "like":
        def_num = "2"

    try:
        choice = input(
            f"{Y}[?] Chọn loại job muốn chạy [1/2/3] (Enter = [{def_num}] {type_labels.get(default_type, 'all')}): {D}"
        ).strip().lower()
        if choice in type_map:
            selected = type_map[choice]
        elif not choice:
            selected = default_type
        else:
            selected = "all"
    except (EOFError, KeyboardInterrupt):
        print("\nĐã hủy.")
        sys.exit(0)

    cfg["job_type"] = selected
    log.info(f"{G}✓ Đã chọn chế độ job:{D} {C}{type_labels.get(selected, selected)}{D}")
    return selected


class JobRunner:
    def __init__(self, job_type="all"):
        self.api = f4f()
        self.adb = None
        self.account_name = None
        self.account_id = None
        self.package_name = None
        self.job_type = job_type
        self.stats = {
            "followed": 0,
            "liked": 0,
            "already": 0,
            "skipped": 0,
            "errors": 0,
            "coins_earned": 0,
        }
        self.jobs_since_human = 0

    def _select_tiktok_account(self):
        """
        Lấy danh sách tài khoản TikTok qua API get_acc_tik():
        - Nếu tiktok_uid đã có trong config.json và khớp -> Dùng ngay, không cần hỏi!
        - Nếu chỉ có 1 tài khoản duy nhất -> Tự động dùng ngay!
        - Nếu có nhiều tài khoản và chưa lưu trong config -> Hiện menu cho chọn rồi lưu lại.
        """
        log.info("Lấy danh sách tài khoản TikTok liên kết...")
        try:
            res = self.api.get_acc_tik()
            acc_list = res.get("data", {}).get("data", [])
        except Exception as e:
            log.error(f"Lỗi gọi API lấy danh sách tài khoản: {e}")
            sys.exit(1)

        if not acc_list:
            log.error(f"{R}Không tìm thấy tài khoản TikTok nào liên kết trên follow4follow.net!{D}")
            log.error("Vui lòng vào website follow4follow.net -> Thêm tài khoản TikTok trước khi chạy tool.")
            sys.exit(1)

        saved_uid = CONFIG.get("tiktok_uid", "").strip()

        # 1. Nếu chỉ có duy nhất 1 tài khoản -> Tự động dùng ngay
        if len(acc_list) == 1:
            chosen = acc_list[0]
            self.account_name = chosen["name"]
            self.account_id = chosen["id"]
            CONFIG["tiktok_uid"] = self.account_name
            log.info(f"{G}✓ Tự động chọn tài khoản TikTok duy nhất:{D} {C}@{self.account_name}{D} (ID: {self.account_id})")
            return

        # 2. Nếu có từ 2 tài khoản trở lên -> Luôn hiện menu để người dùng chọn (Enter = tài khoản mặc định)
        default_idx = 1
        for idx, acc in enumerate(acc_list, start=1):
            if saved_uid and acc.get("name") == saved_uid:
                default_idx = idx
                break

        if not sys.stdin.isatty():
            chosen = acc_list[default_idx - 1]
            self.account_name = chosen["name"]
            self.account_id = chosen["id"]
            CONFIG["tiktok_uid"] = self.account_name
            log.info(f"{G}✓ Đang dùng tài khoản TikTok:{D} {C}@{self.account_name}{D} (ID: {self.account_id})")
            return

        print(f"\n{C}┌── Danh sách tài khoản TikTok liên kết ──────────────────────────┐{D}")
        for idx, acc in enumerate(acc_list, start=1):
            status = acc.get("status", "Hoạt động")
            name = acc.get("name", "")
            acc_id = acc.get("id", "")
            is_def = f" {G}(Mặc định){D}" if idx == default_idx else ""
            print(f"{C}│{D}  [{idx}] {W}@{name:<22}{D} │ ID: {acc_id:<6} │ {status:<9}{is_def} {C}│{D}")
        print(f"{C}└─────────────────────────────────────────────────────────────────┘{D}")

        def_name = acc_list[default_idx - 1]["name"]
        prompt_txt = f"{Y}[?] Chọn tài khoản làm job [1-{len(acc_list)}] (Enter = @{def_name}): {D}"

        selected_idx = default_idx
        try:
            choice = input(prompt_txt).strip()
            if choice.isdigit() and 1 <= int(choice) <= len(acc_list):
                selected_idx = int(choice)
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        chosen = acc_list[selected_idx - 1]
        self.account_name = chosen["name"]
        self.account_id = chosen["id"]
        CONFIG["tiktok_uid"] = self.account_name

        log.info(f"{G}✓ Đã chọn tài khoản TikTok:{D} {C}@{self.account_name}{D} (ID: {self.account_id})")

        # Lưu lại vào config.json để lần sau không cần hỏi lại
        if CONFIG["tiktok_uid"] != saved_uid:
            try:
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(CONFIG, f, indent=2, ensure_ascii=False)
                log.info(f"Đã lưu @{self.account_name} vào config.json cho các lần sau.")
            except Exception:
                pass

    def setup(self):
        """Đăng nhập f4f, chọn tài khoản TikTok và kết nối ADB."""
        if not CONFIG.get("f4f_user") or not CONFIG.get("f4f_pass"):
            log.error("Chưa cấu hình tài khoản follow4follow!")
            sys.exit(1)

        log.info("Đang đăng nhập follow4follow.net ...")
        self.api.login(CONFIG["f4f_user"], CONFIG["f4f_pass"], verbose=False)
        user = self.api.user
        log.info(
            f"{G}✓ Đăng nhập thành công:{D} {user['username']} | "
            f"Coin hiện có: {Y}{user['balance']}{D} | "
            f"Level: {user['level']['name']}"
        )

        # Lấy tài khoản TikTok
        self._select_tiktok_account()

        # Kết nối thiết bị ADB
        serial = CONFIG["adb_serial"]
        log.info(f"Đang kết nối thiết bị ADB ({serial}) ...")
        self.adb = AdbController(serial=serial)
        w, h = self.adb.get_screen_size()
        log.info(f"{G}✓ ADB sẵn sàng:{D} Màn hình {w}x{h}")

        # Xác định package TikTok
        if CONFIG["tiktok_package"] == "auto":
            self.package_name = self.adb.detect_tiktok_package()
        else:
            self.package_name = CONFIG["tiktok_package"]
        log.info(f"TikTok Package: {C}{self.package_name}{D}")

        self._ensure_tiktok_running()

    def _ensure_tiktok_running(self):
        """Bảo đảm ứng dụng TikTok đang chạy trên màn hình."""
        current = self.adb.shell("dumpsys window | grep mCurrentFocus")
        if self.package_name not in current:
            log.info("Khởi động TikTok...")
            self.adb.shell(f"monkey -p {self.package_name} -c android.intent.category.LAUNCHER 1")
            time.sleep(3)

    def process_job(self, job, job_type="follow"):
        """Xử lý quy trình cho 1 job (follow hoặc like)."""
        job_id = job["id"]
        reward = job.get("reward_amount", "?")
        remains = job.get("remains", "?")

        if job_type == "like":
            object_id = job.get("link") or job.get("original_link") or job.get("object_id")
            log.info(f"{'─'*50}")
            log.info(
                f"Job #{job_id} [LIKE] │ {C}{object_id}{D} │ "
                f"Reward: {Y}{reward} coin{D} │ Còn: {remains}"
            )

            # 1. Ghi nhận video hiện tại trước khi mở để so sánh thay đổi
            before_sig = self.adb.get_current_video_info(package=self.package_name)

            # 2. Mở video
            log.info(f"  → Mở video TikTok ...")
            opened = self.adb.open_tiktok_video(object_id, self.package_name)
            if not opened:
                log.warning(f"  {R}✗ Không mở được video{D}")
                self._skip_job(job_id, object_id)
                return "skipped"

            # 3. Chờ tải video & kiểm tra xem video có khả dụng không
            time.sleep(1.5)
            load_status = self.adb.wait_video_loaded(
                package=self.package_name,
                timeout=CONFIG["profile_load_timeout"],
                before_sig=before_sig,
            )
            if load_status == "unavailable" or load_status is False:
                log.warning(f"  {R}✗ Video không khả dụng (đã bị xóa, ẩn hoặc tài khoản riêng tư){D}")
                self._skip_job(job_id, object_id)
                self.adb.back()
                return "skipped"

            # 4. Thực hiện Like
            log.info("  → Kiểm tra trạng thái & Like ...")
            result = self.adb.like_video(
                package=self.package_name,
                load_timeout=CONFIG["profile_load_timeout"],
                verify_timeout=CONFIG["verify_timeout"],
            )

            # 5. Xử lý kết quả trả về
            if result == "clicked":
                log.info(f"  {G}✓ Đã like thành công!{D}")
                ok = self._complete_job(job_id, reward, type_job="like", object_id=object_id)
                self.adb.back()
                return "liked" if ok else "skipped"

            elif result == "already":
                log.info(f"  {Y}● Video đã like từ trước{D}")
                ok = self._complete_job(job_id, reward, type_job="like", object_id=object_id)
                self.adb.back()
                return "already" if ok else "skipped"

            elif result == "click_unverified":
                log.warning(f"  {Y}⚠ Đã nhấn like nhưng chưa kịp cập nhật UI{D}")
                ok = self._complete_job(job_id, reward, type_job="like", object_id=object_id)
                self.adb.back()
                return "liked" if ok else "skipped"

            elif result in ("no_video", "video_unavailable"):
                log.warning(f"  {R}✗ Không tìm thấy nút like / video không khả dụng{D}")
                self._skip_job(job_id, object_id)
                self.adb.back()
                return "skipped"

            else:
                log.warning(f"  {R}✗ Trạng thái không xác định: {result}{D}")
                self._skip_job(job_id, object_id)
                self.adb.back()
                return "skipped"

        else:
            object_id = job.get("object_id")
            log.info(f"{'─'*50}")
            log.info(
                f"Job #{job_id} [FOLLOW] │ {C}@{object_id}{D} │ "
                f"Reward: {Y}{reward} coin{D} │ Còn: {remains}"
            )

            # 1. Mở trang cá nhân
            log.info(f"  → Mở profile @{object_id} ...")
            opened = self.adb.open_tiktok_profile(object_id, self.package_name)
            if not opened:
                log.warning(f"  {R}✗ Không mở được profile{D}")
                self._skip_job(job_id, object_id)
                return "skipped"

            # 2. Chờ tải profile & kiểm tra handle
            time.sleep(1.8)
            self.adb.wait_handle(object_id, package=self.package_name, timeout=CONFIG["profile_load_timeout"])

            # 3. Thực hiện Follow
            log.info("  → Kiểm tra trạng thái & Follow ...")
            result = self.adb.follow_profile(
                package=self.package_name,
                load_timeout=CONFIG["profile_load_timeout"],
                verify_timeout=CONFIG["verify_timeout"],
            )

            # 4. Xử lý kết quả trả về
            if result == "clicked":
                log.info(f"  {G}✓ Đã follow thành công!{D}")
                ok = self._complete_job(job_id, reward, type_job="follow", object_id=object_id)
                self.adb.back()
                return "followed" if ok else "skipped"

            elif result == "already":
                log.info(f"  {Y}● Đã follow từ trước{D}")
                ok = self._complete_job(job_id, reward, type_job="follow", object_id=object_id)
                self.adb.back()
                return "already" if ok else "skipped"

            elif result == "requested":
                log.info(f"  {Y}● Đã gửi yêu cầu follow (tài khoản riêng tư){D}")
                ok = self._complete_job(job_id, reward, type_job="follow", object_id=object_id)
                self.adb.back()
                return "followed" if ok else "skipped"

            elif result == "click_unverified":
                log.warning(f"  {Y}⚠ Đã nhấn follow nhưng chưa kịp cập nhật UI{D}")
                ok = self._complete_job(job_id, reward, type_job="follow", object_id=object_id)
                self.adb.back()
                return "followed" if ok else "skipped"

            elif result == "no_profile":
                log.warning(f"  {R}✗ Không tìm thấy nút follow/profile{D}")
                self._skip_job(job_id, object_id)
                self.adb.back()
                return "skipped"

            else:
                log.warning(f"  {R}✗ Trạng thái không xác định: {result}{D}")
                self._skip_job(job_id, object_id)
                self.adb.back()
                return "skipped"

    def _complete_job(self, job_id, reward, type_job="follow", object_id=None):
        try:
            self.api.complete_job(job_id, self.account_id, type_job=type_job)
            log.info(f"  → Báo hoàn thành: {G}OK{D} (+{reward} coin)")
            self.stats["coins_earned"] += int(reward)
            return True
        except Exception as e:
            err_msg = str(e)
            log.error(f"  → Báo hoàn thành thất bại: {err_msg}")
            # Nếu gặp lỗi 400 (chưa làm job / video lỗi / không khả dụng) -> Tự động SKIP job trên f4f để không bị kẹt!
            if "400" in err_msg or "chưa làm job" in err_msg.lower():
                log.warning(f"  {Y}⚠ Tự động SKIP job #{job_id} trên follow4follow vì video lỗi/không hợp lệ.{D}")
                self._skip_job(job_id, object_id or "")
            return False

    def _skip_job(self, job_id, object_id):
        try:
            self.api.skip_job_fb(job_id, self.account_id, self.account_name, object_id)
            log.info(f"  → Đã skip job #{job_id}")
        except Exception as e:
            log.warning(f"  → Skip thất bại: {e}")

    def run(self, max_jobs=None):
        """Vòng lặp chính xử lý danh sách job."""
        if max_jobs is None:
            max_jobs = CONFIG.get("max_jobs_per_session", 50)

        self.setup()
        consecutive_errors = 0
        total_processed = 0

        # Xác định danh sách loại job cần chạy
        if self.job_type == "follow":
            job_types = ["follow"]
        elif self.job_type == "like":
            job_types = ["like"]
        else:
            job_types = ["follow", "like"]

        types_str = " & ".join(jt.upper() for jt in job_types)
        log.info(f"\n{G}▶ Bắt đầu chạy tự động [{types_str}] (mục tiêu: {max_jobs} jobs){D}\n")

        while total_processed < max_jobs:
            jobs_found_in_round = False

            for jt in job_types:
                if total_processed >= max_jobs:
                    break

                try:
                    data = self.api.get_job(self.account_name, type_job=jt)
                    jobs = data.get("data", {}).get("jobs", [])
                    usage = data.get("data", {}).get("account_daily_usage", {})
                except Exception as e:
                    log.error(f"Lỗi lấy danh sách job [{jt}]: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        log.error("Gặp lỗi liên tiếp, tạm nghỉ 30 giây...")
                        time.sleep(30)
                        consecutive_errors = 0
                    continue

                # Kiểm tra hạn mức ngày
                if usage.get("reached"):
                    log.warning(f"{Y}⚠ Đã đạt giới hạn hôm nay ({jt}): {usage.get('done')}/{usage.get('limit')}{D}")
                    continue

                if jobs:
                    jobs_found_in_round = True
                    log.info(
                        f"[{jt.upper()}] Hôm nay: {usage.get('done', '?')}/{usage.get('limit', '?')} │ "
                        f"Còn lại: {usage.get('remaining', '?')} │ Job có sẵn: {len(jobs)}"
                    )

                for job in jobs:
                    if total_processed >= max_jobs:
                        break

                    result = self.process_job(job, job_type=jt)
                    total_processed += 1
                    self.jobs_since_human += 1

                    if result == "followed":
                        self.stats["followed"] += 1
                        consecutive_errors = 0
                    elif result == "liked":
                        self.stats["liked"] += 1
                        consecutive_errors = 0
                    elif result == "already":
                        self.stats["already"] += 1
                        consecutive_errors = 0
                    elif result == "skipped":
                        self.stats["skipped"] += 1
                        consecutive_errors = 0
                    else:
                        self.stats["errors"] += 1
                        consecutive_errors += 1

                    # Sau bao nhiêu job thì chạy human_behavior (lướt feed video)
                    if CONFIG.get("human_behavior", True):
                        every_n = int(CONFIG.get("human_behavior_every_n_jobs") or 5)
                        scroll_times = int(CONFIG.get("human_behavior_scroll_times") or 2)
                        if every_n > 0 and scroll_times > 0 and self.jobs_since_human >= every_n:
                            log.info(f"  {C}☕ [Anti-Ban] Đã chạy xong {self.jobs_since_human} job(s) -> Lướt feed {scroll_times} video...{D}")
                            self.adb.simulate_human_browse(scroll_times=scroll_times)
                            self.jobs_since_human = 0

                    # Delay ngẫu nhiên giữa các job
                    if total_processed < max_jobs:
                        delay = random.uniform(CONFIG["delay_min"], CONFIG["delay_max"])
                        log.info(f"  ⏳ Chờ {delay:.1f}s ...")
                        time.sleep(delay)

            # Nếu trong vòng quét không tìm thấy job nào ở cả 2 loại
            if not jobs_found_in_round and total_processed < max_jobs:
                log.info(f"{Y}Hết job khả dụng ({types_str}). Chờ 30s rồi thử lại...{D}")
                time.sleep(30)

        self._print_summary()

    def _print_summary(self):
        s = self.stats
        total = s["followed"] + s["liked"] + s["already"] + s["skipped"] + s["errors"]
        print(f"""
{C}╔══════════════════════════════════════════════════╗
║                  KẾT QUẢ PHIÊN                   ║
╠══════════════════════════════════════════════════╣
║  {G}Follow thành công : {s['followed']:>5}{C}                       ║
║  {G}Like thành công   : {s['liked']:>5}{C}                       ║
║  {Y}Đã làm từ trước   : {s['already']:>5}{C}                       ║
║  {Y}Bỏ qua (skip)     : {s['skipped']:>5}{C}                       ║
║  {R}Lỗi               : {s['errors']:>5}{C}                       ║
║  ─────────────────────────                       ║
║  {W}Tổng xử lý        : {total:>5}{C}                       ║
║  {G}Coin kiếm được     : ~{s['coins_earned']:>4}{C}                       ║
╚══════════════════════════════════════════════════╝{D}
""")
        log.info(f"File log: {log_file}")


if __name__ == "__main__":
    banner()
    CONFIG = check_or_prompt_credentials(CONFIG)
    platform = select_platform_menu(CONFIG)

    if platform == "instagram":
        from instagram_runner import InstagramJobRunner
        runner = InstagramJobRunner(config=CONFIG)
    else:
        selected_job_type = select_job_type_menu(CONFIG)
        runner = JobRunner(job_type=selected_job_type)

    try:
        runner.run()
    except KeyboardInterrupt:
        log.info(f"\n{Y}Đã dừng bởi người dùng (Ctrl+C){D}")
        runner._print_summary()
    except Exception as e:
        log.exception(f"{R}Lỗi không xử lý được: {e}{D}")
        runner._print_summary()
