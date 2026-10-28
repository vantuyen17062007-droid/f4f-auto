"""
Follow4Follow Unified API Client (TikTok, Instagram, Facebook)
==============================================================
Tích hợp toàn bộ API tương tác với hệ thống Follow4Follow:
  - Nền tảng hỗ trợ: TikTok, Instagram, Facebook
  - Đăng nhập lấy Bearer token và sinh chữ ký bảo mật HMAC SHA256
  - Lấy danh sách tài khoản liên kết theo từng nền tảng
  - Lấy danh sách job kiếm coin (Follow, Like, Page-like, ...)
  - Hoàn thành job (complete-job) và bỏ qua job lỗi (skip-job)
  - Tự động tương thích ngược 100% với các phiên bản cũ
"""

import hmac
import hashlib
import time
import sys
import requests
from typing import Optional, Dict, Any, List, Union

# Đảm bảo hiển thị UTF-8 trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class ApiF4F:
    SECRET = b"follow4follow_key"
    BASE_URL = "https://api.follow4follow.net"
    NO_AUTH = {"/user/auth/login"}

    # Danh sách các nền tảng được hỗ trợ
    PLATFORMS = {"tiktok", "instagram", "facebook"}

    def __init__(self, token: Optional[str] = None):
        self.session = requests.Session()
        self.token = token
        self.user = None

    def _headers(self, method: str, path: str) -> Dict[str, str]:
        """Tạo headers kèm chữ ký bảo mật HMAC SHA256 và token xác thực."""
        ts = int(time.time())
        sign = hmac.new(
            self.SECRET,
            f"{ts}:{method.upper()}:{path}".encode(),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "accept": "application/json",
            "x-ts": str(ts),
            "x-sign": sign,
            "origin": "https://follow4follow.net",
            "referer": "https://follow4follow.net/",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if path not in self.NO_AUTH and self.token:
            headers["authorization"] = f"Bearer {self.token}"
        return headers

    def _req(self, method: str, path: str, retries: int = 2, **kwargs) -> Dict[str, Any]:
        """Gửi HTTP request với cơ chế thử lại (retry) khi gặp lỗi mạng tạm thời."""
        timeout = kwargs.pop("timeout", 15)
        last_err = None

        for attempt in range(retries + 1):
            try:
                resp = self.session.request(
                    method=method,
                    url=self.BASE_URL + path,
                    headers=self._headers(method, path),
                    timeout=timeout,
                    **kwargs,
                )
                data = resp.json()

                # Kiểm tra phản hồi lỗi từ server
                status_code = data.get("status_code", resp.status_code)
                if status_code >= 400:
                    msg = data.get("message") or resp.text
                    raise RuntimeError(f"[{status_code}] {msg}")

                return data
            except requests.RequestException as e:
                last_err = e
                if attempt < retries:
                    time.sleep(1.5)
                    continue
                raise RuntimeError(f"Lỗi kết nối F4F: {last_err}")
            except Exception as e:
                raise e

    # ── XÁC THỰC & TÀI KHOẢN F4F ──────────────────────────────────────
    def login(self, username: str, password: str, verbose: bool = True) -> str:
        """
        Đăng nhập tài khoản Follow4Follow và lưu token xác thực.
        """
        res = self._req(
            "POST",
            "/user/auth/login",
            json={"username": username, "password": password},
        )
        d = res["data"]
        self.user = d["user"]
        self.token = d["access_token"]

        if verbose:
            u = self.user
            print(
                f"✓ Đăng nhập F4F thành công: {u.get('username')} | "
                f"Số dư: {u.get('balance')} xu | Chờ duyệt: {u.get('balance_pending')} xu | "
                f"Cấp độ: {u.get('level', {}).get('name', 'Thành viên')}"
            )
        return self.token

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Trả về thông tin người dùng F4F hiện tại."""
        return self.user

    # ── QUẢN LÝ TÀI KHOẢN LIÊN KẾT (CHUNG CHO MỌI NỀN TẢNG) ────────────
    def get_accounts(self, platform: str, page: int = 1) -> Dict[str, Any]:
        """
        Lấy danh sách tài khoản đã liên kết trên F4F theo nền tảng.
        - platform: 'tiktok' | 'instagram' | 'facebook'
        - page: Số trang (mặc định 1)
        """
        plat = platform.lower().strip()
        params = {
            "type": plat,
            "page": str(page),
        }
        return self._req("GET", "/user/account/list", params=params)

    def get_active_accounts(self, platform: str) -> List[Dict[str, Any]]:
        """
        Lọc danh sách các tài khoản đang ở trạng thái 'Hoạt động' của nền tảng chỉ định.
        """
        res = self.get_accounts(platform)
        acc_list = res.get("data", {}).get("data", [])
        return [acc for acc in acc_list if acc.get("status") == "Hoạt động"]

    # Wrapper tiện ích theo từng nền tảng
    def get_acc_tik(self, page: int = 1) -> Dict[str, Any]:
        """Lấy danh sách nick TikTok liên kết."""
        return self.get_accounts("tiktok", page)

    def get_acc_ig(self, page: int = 1) -> Dict[str, Any]:
        """Lấy danh sách nick Instagram liên kết."""
        return self.get_accounts("instagram", page)

    def get_acc_fb(self, page: int = 1) -> Dict[str, Any]:
        """Lấy danh sách nick Facebook liên kết."""
        return self.get_accounts("facebook", page)

    # ── NHẬN JOB KIẾM COIN (CHUNG CHO MỌI NỀN TẢNG) ───────────────────
    def get_jobs(
        self,
        platform: str,
        uid: str,
        type_job: str = "follow",
        refresh: str = "1",
    ) -> Dict[str, Any]:
        """
        Lấy danh sách job kiếm coin từ F4F.
        - platform: 'tiktok' | 'instagram' | 'facebook'
        - uid:
            + TikTok: Handle/username (ví dụ: 'vn.nguyn1257')
            + Instagram: Username (ví dụ: 'van__tuyen')
            + Facebook: UID Facebook (ví dụ: '61593852894636')
        - type_job:
            + TikTok: 'follow', 'like'
            + Instagram: 'follow'
            + Facebook: 'like', 'follow', 'page-like', 'share', 'comment'
        """
        plat = platform.lower().strip()
        params = {
            "platform": plat,
            "type": type_job,
            "refresh": str(refresh),
            "uid": str(uid),
        }
        return self._req("GET", "/user/earn-coin", params=params)

    # Wrapper tiện ích theo từng nền tảng
    def get_job_tiktok(self, uid: str, type_job: str = "follow") -> Dict[str, Any]:
        """Lấy job TikTok."""
        return self.get_jobs("tiktok", uid, type_job=type_job)

    def get_job_ig(self, username: str, type_job: str = "follow") -> Dict[str, Any]:
        """Lấy job Instagram."""
        return self.get_jobs("instagram", username, type_job=type_job)

    def get_job_fb(self, uid: str, type_job: str = "like") -> Dict[str, Any]:
        """Lấy job Facebook."""
        return self.get_jobs("facebook", uid, type_job=type_job)

    # Tương thích với signature cũ: get_job(uid, type_job="follow")
    def get_job(self, uid: str, type_job: str = "follow", platform: str = "tiktok") -> Dict[str, Any]:
        """Hàm lấy job tương thích 100% với code cũ (mặc định TikTok)."""
        return self.get_jobs(platform, uid, type_job=type_job)

    # ── HOÀN THÀNH JOB (COMPLETE-JOB) ─────────────────────────────────
    def complete_job_api(
        self,
        platform: str,
        job_id: Union[int, str],
        account_id: Union[int, str],
        type_job: str = "follow",
    ) -> Dict[str, Any]:
        """
        Báo cáo hoàn thành job để nhận coin.
        - platform: 'tiktok' | 'instagram' | 'facebook'
        - job_id: ID của job nhận từ get_jobs
        - account_id: ID nội bộ của nick trên F4F
        - type_job: Loại job ('follow', 'like', ...)
        """
        payload = {
            "job_id": int(job_id),
            "account_id": int(account_id),
            "type": platform.lower().strip(),
            "type_job": type_job,
        }
        return self._req("POST", "/user/earn-coin/complete-job", json=payload)

    def complete_job(
        self,
        arg1: Union[str, int],
        arg2: Union[int, str],
        arg3: Union[int, str] = "follow",
        arg4: str = "follow",
    ) -> Dict[str, Any]:
        """
        Hỗ trợ cả 2 dạng gọi:
        1. Gọi chuẩn mới: complete_job('tiktok'|'instagram'|'facebook', job_id, account_id, type_job)
        2. Gọi tương thích cũ: complete_job(job_id, account_id, type_job='follow') -> tự hiểu là TikTok
        """
        if isinstance(arg1, str) and arg1.lower() in self.PLATFORMS:
            # Dạng 1: platform, job_id, account_id, type_job
            return self.complete_job_api(arg1, arg2, arg3, type_job=arg4)
        else:
            # Dạng 2: job_id, account_id, type_job (TikTok mặc định)
            return self.complete_job_api("tiktok", arg1, arg2, type_job=str(arg3))

    def complete_job_ig(self, job_id: int, account_id: int, type_job: str = "follow") -> Dict[str, Any]:
        """Hoàn thành job Instagram."""
        return self.complete_job_api("instagram", job_id, account_id, type_job=type_job)

    def complete_job_fb(self, job_id: int, account_id: int, type_job: str = "like") -> Dict[str, Any]:
        """Hoàn thành job Facebook."""
        return self.complete_job_api("facebook", job_id, account_id, type_job=type_job)

    # ── BỎ QUA JOB (SKIP-JOB) ─────────────────────────────────────────
    def skip_job_api(
        self,
        platform: str,
        job_id: Union[int, str],
        account_id: Union[int, str],
        uid: str,
        object_id: str,
    ) -> Dict[str, Any]:
        """
        Bỏ qua job khi đối tượng không khả dụng, bị chặn hoặc lỗi.
        - platform: 'tiktok' | 'instagram' | 'facebook'
        """
        payload = {
            "job_id": int(job_id),
            "account_id": int(account_id),
            "uid": str(uid),
            "object_id": str(object_id),
            "type": platform.lower().strip(),
        }
        return self._req("POST", "/user/earn-coin/skip-job", json=payload)

    def skip_job(
        self,
        arg1: Union[str, int],
        arg2: Union[int, str],
        arg3: Union[int, str],
        arg4: str,
        arg5: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Hỗ trợ cả 2 dạng gọi:
        1. Gọi chuẩn mới: skip_job('tiktok'|'instagram'|'facebook', job_id, account_id, uid, object_id)
        2. Gọi tương thích cũ: skip_job(job_id, account_id, uid, object_id) -> tự hiểu là TikTok
        """
        if isinstance(arg1, str) and arg1.lower() in self.PLATFORMS:
            # Dạng 1: platform, job_id, account_id, uid, object_id
            return self.skip_job_api(arg1, arg2, arg3, arg4, arg5 or "")
        else:
            # Dạng 2: job_id, account_id, uid, object_id (TikTok mặc định)
            return self.skip_job_api("tiktok", arg1, arg2, str(arg3), arg4)

    # Tương thích tên hàm cũ trong code f4f_tiktok.py
    skip_job_fb = skip_job


# ── CÁC ALIAS TƯƠNG THÍCH TOÀN DIỆN ──────────────────────────────────
F4F = ApiF4F
f4f = ApiF4F
F4FInstagram = ApiF4F
f4f_ig = ApiF4F


if __name__ == "__main__":
    import os
    import json

    print("═════════════════════════════════════════════════════════════")
    print("      Follow4Follow Unified API (TikTok, Instagram, FB)      ")
    print("═════════════════════════════════════════════════════════════\n")

    cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(cfg_path):
        print("[!] Không tìm thấy config.json để test.")
        sys.exit(0)

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    user = cfg.get("f4f_user")
    pwd = cfg.get("f4f_pass")

    if not user or user == "your_f4f_username":
        print("[!] Vui lòng cấu hình f4f_user và f4f_pass trong config.json trước khi test.")
        sys.exit(0)

    client = ApiF4F()
    client.login(user, pwd)

    # Kiểm tra lần lượt cả 3 nền tảng
    platforms = [
        ("tiktok", "TikTok", "follow"),
        ("instagram", "Instagram", "follow"),
        ("facebook", "Facebook", "like"),
    ]

    for plat_key, plat_name, default_job_type in platforms:
        print(f"\n── {plat_name.upper()} ──────────────────────────────────────")
        try:
            accs = client.get_active_accounts(plat_key)
            print(f"• Số tài khoản hoạt động: {len(accs)}")
            for a in accs:
                name_display = a.get("username") or a.get("name") or a.get("uid")
                print(f"   └─ Nick: @{name_display} (ID: {a.get('id')})")

            if accs:
                target_acc = accs[0]
                # Chọn UID hợp lệ theo từng nền tảng
                if plat_key == "instagram":
                    query_uid = target_acc.get("username")
                elif plat_key == "tiktok":
                    query_uid = target_acc.get("name")
                else:  # facebook
                    query_uid = target_acc.get("uid")

                job_res = client.get_jobs(plat_key, query_uid, type_job=default_job_type)
                jobs = job_res.get("data", {}).get("jobs", [])
                print(f"• Số job ({default_job_type}) khả dụng: {len(jobs)}")
                for j in jobs[:2]:
                    print(f"   └─ Job #{j.get('id')}: {j.get('type_job')} @{j.get('object_id')} -> +{j.get('reward_amount')} xu")
        except Exception as e:
            print(f"• Lỗi kiểm tra {plat_name}: {e}")
