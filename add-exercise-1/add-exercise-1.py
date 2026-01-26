import re
import time
import sqlite3
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# =========================
# 設定
# =========================
DB_PATH = "add-exercise-1.db"
ORG = "google"
BASE_URL = f"https://github.com/orgs/{ORG}/repositories"
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SLEEP_SEC = 1  # 必須


# =========================
# スター数変換（52.8k → 52800）
# =========================
def to_int_stars(text: str) -> int:
    t = (text or "").strip().lower().replace(",", "")
    if not t:
        return 0

    if t.endswith("k"):
        return int(float(t[:-1]) * 1000)

    if t.isdigit():
        return int(t)

    digits = re.sub(r"[^\d]", "", t)
    return int(digits) if digits else 0


# =========================
# DB初期化
# =========================
def init_db(conn):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS google_repos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_name TEXT NOT NULL UNIQUE,
        primary_language TEXT,
        stars INTEGER NOT NULL DEFAULT 0,
        scraped_at TEXT NOT NULL
    );
    """)
    conn.commit()


# =========================
# 保存
# =========================
def save_repo(conn, repo_name, lang, stars, scraped_at):
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO google_repos (repo_name, primary_language, stars, scraped_at)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(repo_name) DO UPDATE SET
        primary_language=excluded.primary_language,
        stars=excluded.stars,
        scraped_at=excluded.scraped_at;
    """, (repo_name, lang, stars, scraped_at))
    conn.commit()


# =========================
# 1ページ取得
# =========================
def scrape_page(session, url):
    resp = session.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    repos = []

    for row in soup.select("li.Box-row"):

        # リポジトリ名
        name_a = row.select_one('a[itemprop="name codeRepository"]')
        if not name_a:
            continue

        href = name_a.get("href", "")
        m = re.match(r"^/google/([^/]+)$", href)
        if not m:
            continue

        repo_name = m.group(1)

        # 言語
        lang_el = row.select_one('[itemprop="programmingLanguage"]')
        lang = lang_el.get_text(strip=True) if lang_el else None

        # スター
        star_el = row.select_one('a[href$="/stargazers"]')
        stars = to_int_stars(star_el.get_text(strip=True)) if star_el else 0

        repos.append((repo_name, lang, stars))

    # 次ページ
    next_url = None
    next_link = soup.select_one('a[rel="next"]')
    if next_link and next_link.get("href"):
        next_url = urljoin("https://github.com", next_link["href"])

    return repos, next_url


# =========================
# メイン
# =========================
def main(max_pages=3):

    jst = timezone(timedelta(hours=9))
    scraped_at = datetime.now(jst).isoformat(timespec="seconds")

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    session = requests.Session()

    url = BASE_URL
    page = 0
    total = 0

    while url and page < max_pages:
        page += 1
        print(f"[PAGE {page}] GET {url}")

        repos, next_url = scrape_page(session, url)

        for repo_name, lang, stars in repos:
            save_repo(conn, repo_name, lang, stars, scraped_at)
            total += 1

        time.sleep(SLEEP_SEC)  # ← 必須

        url = next_url

    conn.close()
    print(f"Done. saved/updated: {total} repos")


if __name__ == "__main__":
    main(max_pages=3)
