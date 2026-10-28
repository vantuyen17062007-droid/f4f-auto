"""
tools/test_tiktok.py — Test nhanh 1 job TikTok để kiểm tra kết nối & luồng xử lý
"""
import sys
import os

# Thêm thư mục gốc vào sys.path để import dễ dàng
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from config.settings import load_config
from services.tiktok_service import TikTokJobRunner

if __name__ == "__main__":
    cfg = load_config()
    runner = TikTokJobRunner(config=cfg, job_type="follow")
    runner.setup()

    data = runner.api.get_job_tiktok(runner.account_name, type_job="follow")
    jobs = data.get("data", {}).get("jobs", [])
    print(f"\nCó {len(jobs)} job TikTok khả dụng")

    if jobs:
        test_job = jobs[0]
        test_job["type_job"] = "follow"
        print(f"Chạy thử job #{test_job['id']} — @{test_job.get('object_id')}")
        result = runner.process_job(test_job)
        print(f"\nKết quả: {result}")
        print(f"Thống kê: {runner.stats}")
    else:
        print("Không có job nào!")
