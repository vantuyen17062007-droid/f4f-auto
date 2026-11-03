# Follow4Follow Multi-Platform Auto Tool 2.0 (TikTok & Instagram)
*(Tối ưu hóa chạy đa nền tảng: Máy tính Windows/Linux & Điện thoại Android Termux)*

---

## 📁 Cấu Trúc Thư Mục Dự Án (Project Architecture)

Dự án được tái cấu trúc theo chuẩn Python chuyên nghiệp, module hóa rõ ràng:

```text
TIKTOK/
├── config/                      # Quản lý cấu hình tập trung
│   ├── __init__.py
│   ├── settings.py              # Tải, lưu, wizard tương tác terminal & dọn log
│   ├── config.example.json      # File mẫu cấu hình tham khảo
│   └── config.json              # File cấu hình thực tế (được .gitignore bảo vệ)
│
├── api/                         # Giao tiếp API các bên thứ 3 (F4F)
│   ├── __init__.py
│   └── f4f_client.py            # ApiF4F: HMAC SHA256 & Client đa nền tảng (TikTok, IG, FB)
│
├── core/                        # Tầng lõi điều khiển phần cứng & tự động hóa
│   ├── __init__.py
│   ├── adb.py                   # AdbController: Điều khiển màn hình, click, swipe, intent
│   ├── helpers.py               # Tiện ích chung: Phân giải video ID, URL, thiết bị ADB, mã màu
│   └── ui.py                    # Giao diện Rich UI: Banner, Session Overview, Table tài khoản, Report
│
├── services/                    # Nghiệp vụ tự động hóa theo từng nền tảng
│   ├── __init__.py
│   ├── base_runner.py           # BaseJobRunner: Theo dõi thống kê, delay ngẫu nhiên, anti-ban
│   ├── tiktok_service.py        # TikTokJobRunner: Nghiệp vụ Follow & Like video TikTok
│   └── instagram_service.py     # InstagramJobRunner: Nghiệp vụ Follow Instagram
│
├── tools/                       # Các công cụ kiểm thử & CLI độc lập
│   ├── __init__.py
│   ├── test_tiktok.py           # Test nhanh 1 job TikTok
│   ├── test_instagram.py        # Test nhanh 1 job Instagram
│   ├── like_video_cli.py        # Tool CLI like video trực tiếp theo URL/ID
│   └── find_video_cli.py        # Tool CLI trích xuất Video ID TikTok
│
├── logs/                        # Lưu trữ file log phiên chạy (tự động dọn sau 7 ngày)
│
├── main.py                      # 🚀 ENTRYPOINT CHÍNH (Điều phối chạy toàn bộ tool)
│
├── .gitignore                   # Chặn file nhạy cảm (config.json, logs, ảnh tạm)
├── requirements.txt             # Thư viện Python cần thiết (requests, rich, uiautomator2, lxml)
└── README.md                    # Tài liệu hướng dẫn sử dụng
```

---

## 🌟 Tính Năng Nổi Bật

1. **Giao Diện Terminal Hiện Đại (Rich UI):**
   - Thiết kế chuẩn công thái học với khung viền bo cong (`rounded`), phối màu gradient dịu mắt.
   - Bảng tổng quan phiên chạy (`Session Overview`), menu lựa chọn nền tảng, bảng danh sách tài khoản liên kết (`Rich Table`).
   - Báo cáo kết quả kết thúc phiên (`Session Report`) chi tiết kèm thống kê số xu kiếm được.
   - Tự động fallback mượt mà về ANSI nếu môi trường chưa cài `rich`.
2. **Hỗ Trợ Đa Nền Tảng (TikTok & Instagram):**
   - **TikTok**: Tự động làm job **Follow** trang cá nhân và job **Like video** (hoặc chạy kết hợp cả hai).
   - **Instagram**: Tự động làm job **Follow** trang cá nhân kiếm **+35 xu/job**.
3. **Hợp Nhất API Toàn Diện (`api/f4f_client.py`):**
   - Tích hợp chuẩn API của **TikTok**, **Instagram**, và **Facebook**.
   - Tự động sinh chữ ký bảo mật **HMAC SHA256** và quản lý token phiên.
   - Hỗ trợ lấy nick, lấy job, báo cáo hoàn thành job (`complete-job`) và tự động bỏ qua job lỗi (`skip-job`).
4. **Cơ Chế Điều Khiển ADB & UI Thông Minh (`core/adb.py`):**
   - Mở thẳng trang cá nhân / video qua Android Intent / DeepLinkActivity.
   - Nhận diện chính xác nút Follow (`profile_header_follow_button` trên Instagram, anchor `Nhắn tin` trên TikTok).
   - Tự động kiểm tra trạng thái trước và sau khi tương tác để tránh bị click trùng lặp.
   - Tự động đóng các popup phiền toái (đồng bộ danh bạ, bật thông báo...).
5. **Cấu Hình Tương Tác Trực Tiếp Qua Terminal:**
   - Không cần mở file `config.json` ra sửa thủ công.
   - Luồng khởi động `main.py` theo thứ tự:
     1. **Chọn nền tảng**: `1` TikTok / `2` Instagram (Enter = nền tảng đã lưu).
     2. **Cấu hình này lần?**: Enter (hoặc `1`) = dùng lại giữ nguyên cài đặt cũ, `2` = cài lại (nhập tài khoản, số job, delay, anti-ban). Lần đầu chạy sẽ vào trình cài đặt luôn.
     3. **Kiểm tra tài khoản F4F**: thiếu sẽ được yêu cầu nhập; thiếu vẫn → dừng sớm.
     4. **Với TikTok**: chọn chế độ job `1` Follow / `2` Like / `3` All.
     5. **Bảng SESSION OVERVIEW** tóm tắt toàn bộ trước khi bắt đầu.
   - Nếu chưa có thiết bị ADB khi chạy: tool hướng dẫn kiểm tra và cho **Enter = thử lại / q = thoát** (không crash).
6. **Mô Phỏng Người Thật (Anti-Ban / Checkpoint):**
   - Tùy chỉnh tần suất lướt feed (`human_behavior_every_n_jobs`: cỡ bao nhiêu job thì lướt feed 1 lần — vòng thực tế **ngẫu nhiên ±2 job**).
   - Tùy chỉnh số video mỗi lần lướt (`human_behavior_scroll_times` — lần thực tế **ngẫu nhiên ±1 video**).
7. **Đa Nền Tảng Chạy Được Trên PC Lẫn Điện Thoại:**
   - Hỗ trợ Windows, Linux, macOS.
   - Hỗ trợ chạy trực tiếp trong ứng dụng **Termux** trên điện thoại Android qua Local ADB.

---

## 🖥️ Hướng Dẫn Chạy Trên MÁY TÍNH (PC)

### 1. Cài Đặt Thư Viện Cần Thiết:
```bash
pip install -r requirements.txt
```

### 2. Kết Nối Điện Thoại:
- Bật **Gỡ lỗi USB (USB Debugging)** trên điện thoại và cắm cáp kết nối vào máy tính (hoặc kết nối qua Wifi ADB).
- Kiểm tra thiết bị đã nhận diện:
  ```bash
  adb devices
  ```

### 3. Khởi Chạy Tool:
```bash
python main.py
```
- Tool sẽ hiển thị menu chọn nền tảng:
  - Bấm `1`: Chạy TikTok (chọn tiếp Follow / Like / Cả hai).
  - Bấm `2`: Chạy Instagram (+35 xu/job).

---

## 📱 Hướng Dẫn Chạy Trực Tiếp Trên ĐIỆN THOẠI (Termux)

Bạn có thể chạy tool độc lập ngay trên chính chiếc điện thoại Android bằng **Termux** mà không cần máy tính.

### 1. Cài Đặt Môi Trường Trên Termux:
```bash
pkg update && pkg upgrade -y
pkg install python android-tools git libxml2 libxslt -y
pip install -r requirements.txt
```

### 2. Kích Hoạt Kết Nối ADB Cục Bộ (Local Wireless ADB):
*Dành cho Android 11 trở lên:*
1. Vào **Cài đặt cho nhà phát triển** -> Bật **Gỡ lỗi không dây (Wireless debugging)**.
2. Bấm vào mục Gỡ lỗi không dây -> Chọn **Ghép nối thiết bị bằng mã ghép nối (Pair with pairing code)**.
3. Mở Termux và gõ:
   ```bash
   adb pair 127.0.0.1:<PORT_GHÉP_NỐI>
   ```
   *(Nhập mã PIN 6 số hiển thị trên màn hình)*.
4. Sau khi ghép nối thành công, kết nối ADB:
   ```bash
   adb connect 127.0.0.1:<PORT_KẾT_NỐI>
   ```

### 3. Khởi Chạy Tool:
```bash
python main.py
```

---

## 🛠️ Các Công Cụ Tiện Ích Độc Lập (`tools/`)

Ngoài file chạy chính `main.py`, bạn có thể dùng các công cụ độc lập:

1. **Test 1 job TikTok:**
   ```bash
   python tools/test_tiktok.py
   ```
2. **Test 1 job Instagram:**
   ```bash
   python tools/test_instagram.py
   ```
3. **Like video TikTok trực tiếp qua link:**
   ```bash
   python tools/like_video_cli.py --url https://vt.tiktok.com/ZS.../
   ```
4. **Phân giải Video ID TikTok:**
   ```bash
   python tools/find_video_cli.py --url https://www.tiktok.com/@user/video/123456789
   ```

---

## ⚙️ Cấu Trúc File `config/config.json`

```json
{
  "f4f_user": "your_f4f_username",
  "f4f_pass": "your_f4f_password",
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
  "human_behavior": true,
  "human_behavior_every_n_jobs": 5,
  "human_behavior_scroll_times": 2,
  "auto_clean_logs_days": 7
}
```

Ý nghĩa các trường:

| Trường | Ý nghĩa |
|---|---|
| `f4f_user`, `f4f_pass` | Tài khoản/mật khẩu follow4follow.net (có thể đặt qua `F4F_USER`, `F4F_PASS`) |
| `platform` | `tiktok` hoặc `instagram` |
| `tiktok_uid`, `instagram_username` | Để trống để tự động chọn nick qua API |
| `job_type` | TikTok: `all`, `follow`, hoặc `like` |
| `adb_serial` | `auto` hoặc serial/IP cụ thể (không tự chuyển sang thiết bị khác nếu chỉ định) |
| `tiktok_package`, `instagram_package` | `auto` để tự nhận diện package đã cài |
| `max_jobs_per_session` | Số job tối đa trong 1 phiên chạy |
| `delay_min`, `delay_max` | Nghỉ ngẫu nhiên tối thiểu/tối đa (giây) |
| `profile_load_timeout` | Thời gian chờ tải trang cá nhân/video |
| `verify_timeout` | Thời gian xác thực trạng thái sau khi click |
| `human_behavior` | Bật/tắt mô phỏng lướt feed chống ban |
| `human_behavior_every_n_jobs` | Cỡ giãn cách kích hoạt anti-ban — vòng thực tế ngẫu nhiên trong `[n-2, n+2]` |
| `human_behavior_scroll_times` | Cỡ số video mỗi lần lướt — thực tế ngẫu nhiên trong `[n-1, n+1]` |
| `auto_clean_logs_days` | Tự xóa file log cũ hơn N ngày (`0` = tắt) |
