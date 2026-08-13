import os
from pathlib import Path
from typing import Iterable

from app.config import get_settings

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")


def generate_excel_report(
    rows: Iterable[dict[str, object]],
    filename: str = "exam_report.xlsx",
) -> Path:
    import pandas as pd

    settings = get_settings()
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = settings.REPORTS_DIR / filename

    dataframe = pd.DataFrame(list(rows))
    dataframe.to_excel(report_path, index=False)
    return report_path
