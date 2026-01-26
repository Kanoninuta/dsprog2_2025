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

# orgの検索結果（repoリンクを集める用）
SEARCH_URL = "https://github.com/search?q=org:google&type=repositories"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

SLEEP_SEC = 1  # ★必須：各リクエストの間に sleep(1)


# =========================
# 文字列 → int（例: '2.2k' → 2200）
# =========================
def to_int_stars(text: str) -> int:
    t = (text or "").strip().lower().replace(",", "")
    if not t:
        return 0
    m = re.match(r"^(\d+(\.\d+)?)(k)?$", t)
    if m:
        num = float(m.group(1))
        if m.group(3) == "k":
            num *= 1000
        return int(num)
    digits = re.sub(r"[^\d]", "", t)
    return int(digits) if digits else 0


# =========================
# DB初期化
# =========================
def init_db(conn: sqlite3.Connection) -> None:
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


def save_repo(conn: sqlite3.Connection, repo_name: str, lang: str | None, stars: int, scraped_at: str) -> None:
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
# HTTP GET（429対策リトライつき） + 必ずsleep
# =========================
def get_html(session: requests.Session, url: str, max_retries: int = 3) -> str:
    last_err = None
    for i in range(max_retries):
        try:
            resp = session.get(url, headers=HEADERS, timeout=25)
            # 429/503 などはリトライ
            if resp.status_code in (429, 503):
                time.sleep(SLEEP_SEC * (i + 2))  # 1秒以上（要件は満たす）
                continue
            resp.raise_for_status()
            html = resp.text
            time.sleep(SLEEP_SEC)  # ★必須：各リクエストの間
            return html
        except Exception as e:
            last_err = e
            time.sleep(SLEEP_SEC * (i + 2))
    raise RuntimeError(f"Failed to fetch: {url} ({last_err})")


# =========================
# 検索ページから repoリンクを正規表現で拾う（壊れにくい）
# =========================
def extract_repo_names_from_search_html(html: str) -> list[str]:
    # /google/<repo> のリンクだけ拾う（/issues などを除外）
    names = re.findall(r'href="/google/([^"/]+)"', html)
    # 変なもの除外 & 重複除去
    seen = set()
    cleaned = []
    for n in names:
        n = n.strip()
        if not n or n.lower() in ("google", "orgs", "search"):
            continue
        if n in seen:
            continue
        seen.add(n)
        cleaned.append(n)
    return cleaned


# =========================
# repo個別ページから「主要言語」「スター数」を取る
# =========================
def scrape_repo_detail(session: requests.Session, repo_name: str) -> tuple[str | None, int]:
    url = f"https://github.com/{ORG}/{repo_name}"
    html = get_html(session, url)

    # Bot対策ページなどを検知
    if "Verify you are human" in html or "captcha" in html.lower():
        # 取得不能のときは None/0 で返す（DBには入る）
        return None, 0

    soup = BeautifulSoup(html, "html.parser")

    lang_el = soup.select_one('[itemprop="programmingLanguage"]')
    lang = lang_el.get_text(strip=True) if lang_el else None

    stars = 0
    star_el = soup.select_one(f'a[href="/{ORG}/{repo_name}/stargazers"]')
    if star_el:
        stars = to_int_stars(star_el.get_text(" ", strip=True))
    else:
        # フォールバック：stargazers を含むリンクの中で最大の数値
        candidates = []
        for a in soup.select('a[href*="stargazers"]'):
            candidates.append(to_int_stars(a.get_text(" ", strip=True)))
        stars = max(candidates) if candidates else 0

    return lang, stars


def main(search_pages: int = 3, max_repos: int = 30) -> None:
    jst = timezone(timedelta(hours=9))
    scraped_at = datetime.now(jst).isoformat(timespec="seconds")

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    session = requests.Session()

    # 1) 検索ページを回して repo名を集める
    repo_names: list[str] = []
    for p in range(1, search_pages + 1):
        url = f"{SEARCH_URL}&p={p}"
        print(f"[SEARCH {p}] GET {url}")
        html = get_html(session, url)
        names = extract_repo_names_from_search_html(html)
        repo_names.extend(names)

    # 重複除去して上限を適用
    unique = []
    seen = set()
    for n in repo_names:
        if n in seen:
            continue
        seen.add(n)
        unique.append(n)
    unique = unique[:max_repos]

    if not unique:
        print("Done. saved/updated: 0 repos")
        print("NOTE: GitHubがBot対策ページを返している可能性があります。")
        conn.close()
        return

    # 2) 各repoの個別ページに行って言語・スター取得 → DB保存
    saved = 0
    for i, repo in enumerate(unique, start=1):
        print(f"[REPO {i}/{len(unique)}] GET https://github.com/{ORG}/{repo}")
        lang, stars = scrape_repo_detail(session, repo)
        save_repo(conn, repo, lang, stars, scraped_at)
        saved += 1

    conn.close()
    print(f"Done. saved/updated: {saved} repos")


if __name__ == "__main__":
    main(search_pages=3, max_repos=30)
