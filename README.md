# Follow4Follow Multi-Platform Auto Tool 2.0 (TikTok & Instagram)
*(Tối ưu hóa chạy đa nền tảng: Máy tính Windows/Linux & Điện thoại Android Termux)*

---

## 🌟 Tính năng nổi bật đã tối ưu
1. **Hỗ trợ đa nền tảng (TikTok & Instagram):**
   - Hỗ trợ chạy tự động cả **TikTok** (Follow & Like video) lẫn **Instagram** (Follow kiếm +35 xu/job).
   - Menu chọn nền tảng trực quan ngay khi khởi động `main.py` hoặc chạy riêng file `instagram_runner.py`.
2. **Hợp nhất API toàn diện (`api_f4f.py`):**
   - Một file API duy nhất tích hợp cả 3 nền tảng: **TikTok**, **Instagram**, và **Facebook**.
   - Hỗ trợ đầy đủ: lấy danh sách nick, lấy job kiếm coin, báo cáo hoàn thành job, và skip job lỗi.
3. **Cơ chế Like video & Follow thông minh:**
   - Mở thẳng trang cá nhân / video bằng Intent / Deeplink Activity chuẩn.
   - Tự động nhận diện chính xác nút Follow (`profile_header_follow_button` trên Instagram, anchor `Nhắn tin` trên TikTok).
   - Tự động kiểm tra trạng thái: nếu đã follow / liked từ trước sẽ không thao tác lại.
4. **Tự động nhận diện tài khoản (`get_acc`):**
   - Không cần nhập thủ công UID hay username!
   - Tool tự động gọi API F4F lấy danh sách tài khoản liên kết (TikTok/Instagram).
   - Tự động chọn nếu có 1 tài khoản, hoặc hiển thị menu chọn nhanh bằng số nếu có nhiều tài khoản.
5. **Cấu hình trực tiếp trên Terminal khi khởi động:**
   - Khi chạy `python main.py`, tool hiển thị cấu hình hiện tại và cho phép bấm Enter chạy ngay hoặc gõ `2` để tùy chỉnh thông số.
6. **Mô phỏng người thật linh hoạt (Anti-Ban / Checkpoint):**
   - Tùy chỉnh tần suất lướt feed (`human_behavior_every_n_jobs`: sau bao nhiêu job thì lướt feed 1 lần).
   - Tùy chỉnh số lần lướt feed (`human_behavior_scroll_times`).
7. **Auto-Detect Thiết bị & Package:**
   - Tự động tìm thiết bị ADB đang kết nối (USB hoặc Wifi ADB).
   - Tự động nhận diện bản TikTok (`com.ss.android.ugc.trill`, `com.zhiliaoapp.musically`, ...) và Instagram (`com.instagram.android`, `com.instagram.lite`).
8. **Tự động tắt Popup & Dọn dẹp Log:**
   - Bấm bỏ qua popup phiền toái và tự động dọn log cũ hơn 7 ngày.

---

## 🖥️ Hướng dẫn chạy trên MÁY TÍNH (PC)

### 1. Cài đặt thư viện:
```bash
pip install requests uiautomator2 lxml
```

### 2. Chỉnh sửa cấu hình (Tùy chọn):
- Mở file `config.json` và điền tài khoản, mật khẩu f4f của bạn.
- Bạn có thể chỉnh `human_behavior_every_n_jobs` (ví dụ cứ 5 job lướt 1 lần) và `human_behavior_scroll_times` (lướt 2 video).

### 3. Kết nối điện thoại & Khởi chạy:
- Bật **Gỡ lỗi USB (USB Debugging)** trên điện thoại và cắm cáp vào máy tính (hoặc kết nối qua Wifi ADB).
- Chạy lệnh:
  ```bash
  python main.py
  ```
- Tool sẽ tự động đọc `config.json`, tự đăng nhập, kết nối ADB và chạy tự động hoàn toàn!

---

## 📱 Hướng dẫn chạy TRỰC TIẾP TRÊN ĐIỆN THOẠI (Termux)

Bạn có thể chạy tool độc lập ngay trên chính chiếc điện thoại Android bằng ứng dụng **Termux** mà không cần bật máy tính.

### 1. Cài đặt môi trường trên Termux:
Mở Termux và chạy các lệnh sau:
```bash
pkg update && pkg upgrade -y
pkg install python android-tools git libxml2 libxslt -y
pip install requests uiautomator2 lxml
```

### 2. Kích hoạt kết nối ADB cục bộ (Local ADB):
Trên Android 11 trở lên:
1. Vào **Cài đặt cho nhà phát triển** -> Bật **Gỡ lỗi không dây (Wireless debugging)**.
2. Bấm vào mục Gỡ lỗi không dây -> Chọn **Ghép nối thiết bị bằng mã ghép nối (Pair with pairing code)**.
3. Mở Termux và gõ:
   ```bash
   adb pair 127.0.0.1:<PORT_GHÉP_NỐI>
   ```
   (Nhập mã PIN hiển thị trên màn hình).
4. Sau khi ghép nối thành công, kết nối ADB:
   ```bash
   adb connect 127.0.0.1:<PORT_KẾT_NỐI>
   ```

### 3. Chạy tool trên Termux:
Chuyển vào thư mục chứa code và chạy:
```bash
python main.py
```
*(Tool sẽ tự động nhận diện kết nối `127.0.0.1` và chạy hoàn toàn tự động)*.

---

## ⚙️ Cấu trúc file `config.json`

```json
{
  "f4f_user": "your_f4f_username",        // Tài khoản follow4follow.net
  "f4f_pass": "your_f4f_password",        // Mật khẩu follow4follow
  "tiktok_uid": "",                      // Để trống để tự chọn nick TikTok qua get_acc_tik
  "job_type": "all",                     // "all" (cả hai), "follow" (chỉ follow), hoặc "like" (chỉ like)
  "adb_serial": "auto",                  // "auto" hoặc IP cụ thể
  "tiktok_package": "auto",              // "auto" (tự chọn TikTok phù hợp)
  "max_jobs_per_session": 50,            // Số job tối đa trong 1 lần chạy
  "delay_min": 8,                        // Nghỉ tối thiểu giữa các job (giây)
  "delay_max": 18,                       // Nghỉ tối đa giữa các job (giây)
  "profile_load_timeout": 8,             // Thời gian chờ load profile
  "verify_timeout": 3,                   // Thời gian xác thực trạng thái follow
  "human_behavior": true,                // Bật mô phỏng lướt feed chống ban
  "human_behavior_every_n_jobs": 5,      // Chạy sau bao nhiêu job thì lướt video
  "human_behavior_scroll_times": 2,      // Mỗi lần lướt bao nhiêu video
  "auto_clean_logs_days": 7              // Tự xóa file log cũ hơn 7 ngày
}
```
