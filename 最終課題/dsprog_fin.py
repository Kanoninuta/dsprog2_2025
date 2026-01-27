import re
import time
import sqlite3
from datetime import datetime
from io import BytesIO

import requests
import pandas as pd

XLSX_URL = "https://www.tourism.jp/wp/wp-content/uploads/2026/01/JTM_inbound_20260105.xlsx"
DB_PATH = "dsprog_fin.db"
SLEEP_SEC = 1.0

SHEETS = [
    "国別・目的別（アジア）",
    "国別・目的別（欧州）",
    "国別・目的別（その他国、総計）",
]

def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def get_xlsx_bytes(url: str) -> bytes:
    time.sleep(SLEEP_SEC)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

#日付を揃える
def parse_year_month(text, prev_year):
    if pd.isna(text):
        return None, None, prev_year
    s = str(text).strip()

    m = re.search(r"(\d{4})\s*年.*?(\d{1,2})\s*月", s)
    if m:
        y = int(m.group(1))
        mo = int(m.group(2))
        return y, mo, y

    m2 = re.search(r"(\d{1,2})\s*月", s)
    if m2 and prev_year is not None:
        mo = int(m2.group(1))
        return prev_year, mo, prev_year

    return None, None, prev_year

def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inbound_country (
          year INTEGER NOT NULL,
          month INTEGER NOT NULL,
          country TEXT NOT NULL,
          visitors INTEGER,
          source_sheet TEXT NOT NULL,
          fetched_at TEXT NOT NULL,
          PRIMARY KEY (year, month, country)
        );
    """)
    conn.commit()

def extract_country_rows_from_sheet(xlsx_bytes: bytes, sheet_name: str, fetched_at: str):
    
    df = pd.read_excel(BytesIO(xlsx_bytes), sheet_name=sheet_name, header=None)


    header_country_row = 1
    header_metric_row = 2
    data_start_row = 3

    # 列ごとの (country, metric)
    countries = df.iloc[header_country_row].tolist()
    metrics = df.iloc[header_metric_row].tolist()

    # 「入国総数」列だけ
    target_cols = []
    for col_idx, (c, m) in enumerate(zip(countries, metrics)):
        if pd.isna(c) or pd.isna(m):
            continue
        if str(m).strip() == "入国総数":
            country = str(c).strip()
    #　集まりは除外
            if country.endswith("計") or "総計" in country:
                continue
            target_cols.append((col_idx, country))

    if not target_cols:
        raise RuntimeError(f"{sheet_name}: 入国総数の国別列が見つかりませんでした")

    rows = []
    prev_year = None

    for r in range(data_start_row, len(df)):
        ym_cell = df.iat[r, 1]  # 列1が月
        year, month, prev_year = parse_year_month(ym_cell, prev_year)
        if year is None:
            continue

        for col_idx, country in target_cols:
            v = df.iat[r, col_idx]
            if pd.isna(v):
                continue
            try:
                visitors = int(float(v))
            except Exception:
                continue

            rows.append((year, month, country, visitors, sheet_name, fetched_at))

    return rows

def upsert_rows(conn: sqlite3.Connection, rows):
    conn.executemany("""
        INSERT OR REPLACE INTO inbound_country
        (year, month, country, visitors, source_sheet, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?);
    """, rows)
    conn.commit()

def main():
    fetched_at = now_iso()
    xlsx_bytes = get_xlsx_bytes(XLSX_URL)

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    total = 0
    for sheet in SHEETS:
        rows = extract_country_rows_from_sheet(xlsx_bytes, sheet, fetched_at)
        upsert_rows(conn, rows)
        print(sheet, "rows:", len(rows))
        total += len(rows)




    conn.close()
    print("inserted_total_rows:", total)
 

if __name__ == "__main__":
    main()
