import pandas as pd
import httpx
import os

xlsx = 'tmp_students_upload.xlsx'
df = pd.DataFrame([{'name': 'Upload Test', 'email': 'upload.test@example.com'}])
df.to_excel(xlsx, index=False)

with httpx.Client(timeout=30.0) as client:
    login = client.post('http://127.0.0.1:8000/api/auth/admin-login', json={'username': 'admin', 'password': 'admin123'})
    print('admin-login', login.status_code, login.text)
    token = None
    if login.status_code == 200:
        token = login.json().get('access_token')
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    with open(xlsx, 'rb') as f:
        files = {'file': ('tmp_students_upload.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {'send_invites': 'false'}
        resp = client.post('http://127.0.0.1:8000/api/admin/import-students', headers=headers, files=files, data=data)
        print('import-students', resp.status_code)
        try:
            print(resp.json())
        except Exception:
            print(resp.text)

os.remove(xlsx)
