"""Quick test — chạy 1 job để kiểm tra flow."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from main import JobRunner, CONFIG

runner = JobRunner()
runner.setup()

# Lấy 1 job test
data = runner.api.get_job(runner.account_name)
jobs = data["data"]["jobs"]
print(f"\nCó {len(jobs)} job(s) available")

if jobs:
    job = jobs[0]
    print(f"Test job #{job['id']} — @{job['object_id']}")
    result = runner.process_job(job)
    print(f"\nKết quả: {result}")
    print(f"Stats: {runner.stats}")
else:
    print("Không có job nào!")
