# Hướng Dẫn Build APK và Chạy F4F Auto Runner (Native Android)

Dự án này là phiên bản **Android Native hoàn chỉnh** (viết bằng **Kotlin**), sử dụng **AccessibilityService (Trợ Năng)** để tự động hóa tương tác TikTok & Instagram mà **không cần ADB, không cần máy tính, không cần Root**.

---

## 📁 Cấu Trúc Dự Án Android

```text
android_app/
├── app/
│   ├── src/main/
│   │   ├── AndroidManifest.xml                        # Khai báo quyền, Accessibility & Service
│   │   ├── res/
│   │   │   ├── xml/accessibility_service_config.xml   # Cấu hình gói app mục tiêu (TikTok, IG)
│   │   │   ├── layout/activity_main.xml               # Giao diện chính cấu hình
│   │   │   └── layout/layout_floating_widget.xml      # Bong bóng nổi điều khiển trên màn hình
│   │   └── java/com/f4f/autorunner/
│   │       ├── MainActivity.kt                        # Màn hình đăng nhập & điều khiển
│   │       ├── api/
│   │       │   ├── Models.kt                          # Data class response từ F4F
│   │       │   └── F4FApiClient.kt                    # Client HMAC-SHA256 & OkHttp
│   │       ├── service/
│   │       │   ├── F4FAccessibilityService.kt         # Lõi đọc UI, click Follow/Like, lướt feed
│   │       │   └── FloatingWidgetService.kt           # Bong bóng nổi đếm xu & nút dừng
│   │       └── engine/
│   │           └── AutoJobEngine.kt                   # Vòng lặp lấy job, mở Intent, nhận xu
│   └── build.gradle.kts
├── build.gradle.kts
└── settings.gradle.kts
```

---

## 🛠️ Cách Build Thành File APK Độc Lập

### Cách 1: Sử dụng Android Studio (Dễ nhất - Khuyên dùng)
1. Tải và cài đặt **[Android Studio](https://developer.android.com/studio)** trên máy tính.
2. Mở Android Studio -> Chọn **Open** -> Điều hướng đến thư mục:
   `D:\agl\TIKTOK\android_app`
3. Đợi Android Studio đồng bộ Gradle xong (khoảng 1-2 phút).
4. Trên thanh menu, chọn:
   **Build** -> **Build Bundle(s) / APK(s)** -> **Build APK(s)**.
5. Khi build xong, Android Studio sẽ hiện thông báo ở góc dưới bên phải:
   `APK(s) generated successfully: locate` -> Bấm **locate** để lấy file `app-debug.apk`.
6. Bạn chép file `.apk` này sang điện thoại Android bất kỳ để cài đặt.

### Cách 2: Build trực tiếp bằng dòng lệnh (Nếu có Gradle Wrapper)
```bash
cd android_app
./gradlew assembleDebug
```
File APK sẽ xuất hiện tại:
`android_app/app/build/outputs/apk/debug/app-debug.apk`

---

## 📱 Hướng Dẫn Sử Dụng Trên Điện Thoại

1. **Cài đặt APK**:
   - Mở file `.apk` vừa build trên điện thoại và chọn Cài đặt (Cho phép cài từ nguồn không xác định nếu được hỏi).
2. **Cấp 2 quyền cần thiết**:
   - Mở ứng dụng **F4F Auto Runner**.
   - Bấm nút **1. Bật Dịch vụ Trợ Năng** -> Máy sẽ chuyển sang phần *Cài đặt Trợ năng* -> Tìm tên **F4F Auto Runner** và gạt công tắc **Bật**.
   - Bấm nút **2. Cấp quyền cửa sổ nổi** -> Cho phép ứng dụng vẽ lên trên các ứng dụng khác (để hiển thị bong bóng nổi).
3. **Đăng nhập & Bắt đầu**:
   - Nhập tài khoản, mật khẩu Follow4Follow rồi bấm **Đăng nhập**.
   - Chọn nền tảng muốn chạy (**TikTok** hoặc **Instagram**).
   - Chọn tài khoản mạng xã hội muốn kiếm xu trong danh sách dropdown.
   - Bấm **BẮT ĐẦU CHẠY AUTO**.
4. **Theo dõi**:
   - App sẽ tự động mở trang cá nhân / video và tự bấm Follow / Like.
   - Bong bóng nổi trên màn hình sẽ liên tục cập nhật số xu kiếm được trong thời gian thực.
   - Bấm vào bong bóng nổi hoặc quay lại app bấm **DỪNG LẠI** bất kỳ lúc nào để kết thúc phiên.

## Giao diện (thiết kế lại)
- Nền xanh lục đậm, điểm nhấn vàng đồng xu; màu khai báo tập trung trong `res/values/colors.xml`, kiểu chữ/nút trong `res/values/themes.xml`.
- Font: **Be Vietnam Pro** (SIL OFL 1.1, giấy phép ở `licenses/BeVietnamPro-OFL.txt`), đặt trong `res/font/`.
- Trạng thái chọn (nền tảng, bộ lọc nhật ký) dùng `isSelected` + selector, không đổi background bằng code.
