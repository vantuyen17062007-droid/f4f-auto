"""
api/f4f_client.py — Follow4Follow Unified API Client (TikTok, Instagram, Facebook)
================================================================================
Tích hợp toàn bộ API tương tác với hệ thống Follow4Follow:
  - Sinh chữ ký bảo mật HMAC SHA256 và quản lý Bearer token
  - Lấy danh sách tài khoản theo từng nền tảng
  - Nhận danh sách job kiếm coin (Follow, Like, Page-like, ...)
  - Hoàn thành job (complete-job) và bỏ qua job lỗi (skip-job)
"""

import hmac
import hashlib
import time
import requests
from typing import Optional, Dict, Any, List, Union


class ApiF4F:
    SECRET = b"follow4follow_key"
    BASE_URL = "https://api.follow4follow.net"
    NO_AUTH = {"/user/auth/login"}

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
        """Đăng nhập tài khoản Follow4Follow và lưu token xác thực."""
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
        return self.user

    # ── QUẢN LÝ TÀI KHOẢN LIÊN KẾT ────────────────────────────────────
    def get_accounts(self, platform: str, page: int = 1) -> Dict[str, Any]:
        """Lấy danh sách nick đã liên kết theo nền tảng ('tiktok' | 'instagram' | 'facebook')."""
        plat = platform.lower().strip()
        params = {"type": plat, "page": str(page)}
        return self._req("GET", "/user/account/list", params=params)

    def get_active_accounts(self, platform: str) -> List[Dict[str, Any]]:
        """Lọc danh sách các tài khoản đang ở trạng thái 'Hoạt động'."""
        res = self.get_accounts(platform)
        acc_list = res.get("data", {}).get("data", [])
        return [acc for acc in acc_list if acc.get("status") == "Hoạt động"]

    def get_acc_tik(self, page: int = 1) -> Dict[str, Any]:
        return self.get_accounts("tiktok", page)

    def get_acc_ig(self, page: int = 1) -> Dict[str, Any]:
        return self.get_accounts("instagram", page)

    def get_acc_fb(self, page: int = 1) -> Dict[str, Any]:
        return self.get_accounts("facebook", page)

    # ── NHẬN JOB KIẾM COIN ───────────────────────────────────────────
    def get_jobs(
        self,
        platform: str,
        uid: str,
        type_job: str = "follow",
        refresh: str = "1",
    ) -> Dict[str, Any]:
        """Lấy danh sách job kiếm coin từ F4F theo nền tảng."""
        plat = platform.lower().strip()
        params = {
            "platform": plat,
            "type": type_job,
            "refresh": str(refresh),
            "uid": str(uid),
        }
        return self._req("GET", "/user/earn-coin", params=params)

    def get_job_tiktok(self, uid: str, type_job: str = "follow") -> Dict[str, Any]:
        return self.get_jobs("tiktok", uid, type_job=type_job)

    def get_job_ig(self, username: str, type_job: str = "follow") -> Dict[str, Any]:
        return self.get_jobs("instagram", username, type_job=type_job)

    def get_job_fb(self, uid: str, type_job: str = "like") -> Dict[str, Any]:
        return self.get_jobs("facebook", uid, type_job=type_job)

    def get_job(self, uid: str, type_job: str = "follow", platform: str = "tiktok") -> Dict[str, Any]:
        return self.get_jobs(platform, uid, type_job=type_job)

    # ── HOÀN THÀNH JOB (COMPLETE-JOB) ─────────────────────────────────
    def complete_job_api(
        self,
        platform: str,
        job_id: Union[int, str],
        account_id: Union[int, str],
        type_job: str = "follow",
    ) -> Dict[str, Any]:
        """Báo cáo hoàn thành job nhận coin."""
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
        if isinstance(arg1, str) and arg1.lower() in self.PLATFORMS:
            return self.complete_job_api(arg1, arg2, arg3, type_job=arg4)
        else:
            return self.complete_job_api("tiktok", arg1, arg2, type_job=str(arg3))

    def complete_job_ig(self, job_id: int, account_id: int, type_job: str = "follow") -> Dict[str, Any]:
        return self.complete_job_api("instagram", job_id, account_id, type_job=type_job)

    def complete_job_fb(self, job_id: int, account_id: int, type_job: str = "like") -> Dict[str, Any]:
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
        """Bỏ qua job khi không khả dụng hoặc lỗi."""
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
        if isinstance(arg1, str) and arg1.lower() in self.PLATFORMS:
            return self.skip_job_api(arg1, arg2, arg3, arg4, arg5 or "")
        else:
            return self.skip_job_api("tiktok", arg1, arg2, str(arg3), arg4)

    skip_job_fb = skip_job


# Các alias tương thích
F4F = ApiF4F
f4f = ApiF4F
F4FInstagram = ApiF4F
f4f_ig = ApiF4F
