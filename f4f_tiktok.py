"""
f4f_tiktok.py — Module tương thích ngược.
Toàn bộ API đã được hợp nhất vào api_f4f.py hỗ trợ TikTok, Instagram, Facebook.
"""

from api_f4f import ApiF4F as f4f, ApiF4F, F4F

__all__ = ["f4f", "ApiF4F", "F4F"]

if __name__ == "__main__":
    a = f4f()
    # a.login('your_username', 'your_password')
    # print(a.get_acc_tik())
