-- テーブル作成
CREATE TABLE IF NOT EXISTS google_repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_name TEXT NOT NULL UNIQUE,
    primary_language TEXT,
    stars INTEGER NOT NULL DEFAULT 0,
    scraped_at TEXT NOT NULL
);

-- データ確認
SELECT repo_name, primary_language, stars, scraped_at
FROM google_repos
ORDER BY stars DESC
LIMIT 20;
