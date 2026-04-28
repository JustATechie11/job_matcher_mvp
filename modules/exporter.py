import json
import os
from datetime import datetime

import pandas as pd


def export_jobs_to_excel(jobs: list[dict], export_dir: str = "exports") -> str:
    os.makedirs(export_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(export_dir, f"verified_jobs_{timestamp}.xlsx")

    df = pd.DataFrame(jobs)
    df.to_excel(file_path, index=False)

    return file_path


def export_jobs_to_json(jobs: list[dict], export_dir: str = "exports") -> str:
    os.makedirs(export_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(export_dir, f"verified_jobs_{timestamp}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

    return file_path