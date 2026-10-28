"""
f4f_instagram.py — Module tương thích ngược.
Toàn bộ API đã được hợp nhất vào api_f4f.py hỗ trợ TikTok, Instagram, Facebook.
"""

from api_f4f import ApiF4F as F4FInstagram, ApiF4F as f4f_ig, ApiF4F as f4f, ApiF4F

__all__ = ["F4FInstagram", "f4f_ig", "f4f", "ApiF4F"]

if __name__ == "__main__":
    client = F4FInstagram()
    # Test lấy danh sách tài khoản Instagram
