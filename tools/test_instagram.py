"""
tools/test_instagram.py — Test nhanh 1 job Instagram để kiểm tra luồng Follow
"""
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from config.settings import load_config
from services.instagram_service import InstagramJobRunner

if __name__ == "__main__":
    cfg = load_config()
    runner = InstagramJobRunner(config=cfg)
    runner.setup()

    data = runner.api.get_job_ig(runner.username, type_job="follow")
    jobs = data.get("data", {}).get("jobs", [])
    print(f"\nCó {len(jobs)} job Instagram khả dụng")

    if jobs:
        test_job = jobs[0]
        print(f"Chạy thử job #{test_job['id']} — Follow @{test_job.get('object_id')}")
        result = runner.process_job(test_job)
        print(f"\nKết quả: {result}")
        print(f"Thống kê: {runner.stats}")
    else:
        print("Không có job nào!")
