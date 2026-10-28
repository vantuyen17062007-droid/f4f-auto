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
│   └── helpers.py               # Tiện ích chung: Phân giải video ID, URL, thiết bị ADB, mã màu
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
└── README.md                    # Tài liệu hướng dẫn sử dụng
```

---

## 🌟 Tính Năng Nổi Bật

1. **Hỗ Trợ Đa Nền Tảng (TikTok & Instagram):**
   - **TikTok**: Tự động làm job **Follow** trang cá nhân và job **Like video** (hoặc chạy kết hợp cả hai).
   - **Instagram**: Tự động làm job **Follow** trang cá nhân kiếm **+35 xu/job**.
2. **Hợp Nhất API Toàn Diện (`api/f4f_client.py`):**
   - Tích hợp chuẩn API của **TikTok**, **Instagram**, và **Facebook**.
   - Tự động sinh chữ ký bảo mật **HMAC SHA256** và quản lý token phiên.
   - Hỗ trợ lấy nick, lấy job, báo cáo hoàn thành job (`complete-job`) và tự động bỏ qua job lỗi (`skip-job`).
3. **Cơ Chế Điều Khiển ADB & UI Thông Minh (`core/adb.py`):**
   - Mở thẳng trang cá nhân / video qua Android Intent / DeepLinkActivity.
   - Nhận diện chính xác nút Follow (`profile_header_follow_button` trên Instagram, anchor `Nhắn tin` trên TikTok).
   - Tự động kiểm tra trạng thái trước và sau khi tương tác để tránh bị click trùng lặp.
   - Tự động đóng các popup phiền toái (đồng bộ danh bạ, bật thông báo...).
4. **Cấu Hình Tương Tác Trực Tiếp Qua Terminal:**
   - Không cần mở file `config.json` ra sửa thủ công.
   - Khi khởi động `main.py`, tool hiện bảng tóm tắt:
     - Nhấn **Enter (hoặc 1)**: Chạy ngay với cấu hình trước đó.
     - Nhấn **2 (hoặc `c`)**: Trình wizard hỏi trực tiếp từng thông số (tài khoản, số job, delay, anti-ban).
5. **Mô Phỏng Người Thật (Anti-Ban / Checkpoint):**
   - Tùy chỉnh tần suất lướt feed (`human_behavior_every_n_jobs`: sau bao nhiêu job thì lướt feed 1 lần).
   - Tùy chỉnh số video lướt mỗi lần (`human_behavior_scroll_times`).
6. **Đa Nền Tảng Chạy Được Trên PC Lẫn Điện Thoại:**
   - Hỗ trợ Windows, Linux, macOS.
   - Hỗ trợ chạy trực tiếp trong ứng dụng **Termux** trên điện thoại Android qua Local ADB.

---

## 🖥️ Hướng Dẫn Chạy Trên MÁY TÍNH (PC)

### 1. Cài Đặt Thư Viện Cần Thiết:
```bash
pip install requests uiautomator2 lxml
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
pip install requests uiautomator2 lxml
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
  "f4f_user": "your_f4f_username",        // Tài khoản follow4follow.net
  "f4f_pass": "your_f4f_password",        // Mật khẩu follow4follow.net
  "platform": "tiktok",                  // "tiktok" hoặc "instagram"
  "tiktok_uid": "",                      // Để trống để tự động chọn nick qua API
  "instagram_username": "",              // Để trống để tự động chọn nick qua API
  "job_type": "all",                     // TikTok: "all", "follow", hoặc "like"
  "adb_serial": "auto",                  // "auto" hoặc serial/IP cụ thể
  "tiktok_package": "auto",              // "auto" (tự nhận diện com.ss.android.ugc.trill...)
  "instagram_package": "auto",           // "auto" (tự nhận diện com.instagram.android...)
  "max_jobs_per_session": 50,            // Số job tối đa trong 1 phiên chạy
  "delay_min": 8,                        // Nghỉ ngẫu nhiên tối thiểu (giây)
  "delay_max": 18,                       // Nghỉ ngẫu nhiên tối đa (giây)
  "profile_load_timeout": 8,             // Thời gian chờ tải trang cá nhân
  "verify_timeout": 3,                   // Thời gian xác thực nút sau khi click
  "human_behavior": true,                // Bật chế độ lướt feed chống ban
  "human_behavior_every_n_jobs": 5,      // Sau bao nhiêu job thì lướt feed 1 lần
  "human_behavior_scroll_times": 2,      // Mỗi lần lướt bao nhiêu video
  "auto_clean_logs_days": 7              // Tự xóa file log cũ hơn N ngày
}
```
