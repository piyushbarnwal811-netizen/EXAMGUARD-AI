import sqlite3
from pathlib import Path


def check_db(path: str) -> None:
    print(f"\nChecking DB: {path}")
    if not Path(path).exists():
        print("  (file not found)")
        return
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute('PRAGMA table_info("students")')
    rows = c.fetchall()
    if not rows:
        print("  (no students table or empty)")
    for r in rows:
        print("  ", r)
    conn.close()


def main():
    check_db('examguard.db')
    check_db('examguard_prod.db')


if __name__ == '__main__':
    main()
