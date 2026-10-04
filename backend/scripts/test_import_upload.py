import os
from pathlib import Path

import httpx
import pandas as pd


def main() -> None:
    xlsx = Path("tmp_students_upload.xlsx")
    df = pd.DataFrame([{"name": "Upload Test", "email": "upload.test@example.com"}])
    df.to_excel(xlsx, index=False)

    try:
        with httpx.Client(timeout=30.0) as client:
            login = client.post(
                "http://127.0.0.1:8000/api/auth/admin-login",
                json={"username": "admin", "password": "admin123"},
            )
            print("admin-login", login.status_code, login.text)
            token = login.json().get("access_token") if login.status_code == 200 else None
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            with xlsx.open("rb") as student_file:
                files = {
                    "file": (
                        xlsx.name,
                        student_file,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                }
                response = client.post(
                    "http://127.0.0.1:8000/api/admin/import-students",
                    headers=headers,
                    files=files,
                    data={"send_invites": "false"},
                )
                print("import-students", response.status_code)
                print(response.text)
    finally:
        xlsx.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
