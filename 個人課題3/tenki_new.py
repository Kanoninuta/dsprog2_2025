import flet as ft
import requests
import sqlite3
from datetime import datetime, timezone


DB_PATH = "weather.db"


# DB初期化
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_code TEXT NOT NULL,
        area_name TEXT NOT NULL,
        fetched_at TEXT NOT NULL,
        date TEXT NOT NULL,
        weather_code TEXT,
        weather_text TEXT,
        UNIQUE(area_code, fetched_at, date)
    );
    """)
    conn.commit()
    conn.close()


# 地域リスト取得
def get_area_list():
    area_url = "https://www.jma.go.jp/bosai/common/const/area.json"
    data_json = requests.get(area_url).json()
    offices = data_json["offices"]
    return [(offices[key]["name"], key) for key in offices]



def fetch_forecast_from_api(area_code):
    forecast_url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json"
    data_json = requests.get(forecast_url).json()

    ts = data_json[0]["timeSeries"][0]
    area = ts["areas"][0]

    area_name = area["area"]["name"]
    weathers = area["weathers"]
    weather_codes = area["weatherCodes"]
    time_defines = ts["timeDefines"]

    rows = []
    for w, c, t in zip(weathers, weather_codes, time_defines):
        date_str = t[:10]  
        rows.append((date_str, c, w))

    return area_name, rows


# DBに保存
def save_forecast_to_db(area_code, area_name, rows):
    fetched_at = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executemany("""
    INSERT OR REPLACE INTO forecasts
    (area_code, area_name, fetched_at, date, weather_code, weather_text)
    VALUES (?, ?, ?, ?, ?, ?);
    """, [
        (area_code, area_name, fetched_at, date_str, code, text)
        for (date_str, code, text) in rows
    ])

    conn.commit()
    conn.close()
    return fetched_at



def load_latest_forecast_from_db(area_code):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    SELECT fetched_at, area_name
    FROM forecasts
    WHERE area_code = ?
    ORDER BY fetched_at DESC
    LIMIT 1;
    """, (area_code,))
    head = cur.fetchone()

    if head is None:
        conn.close()
        return None, None, []

    fetched_at, area_name = head

    cur.execute("""
    SELECT date, weather_code, weather_text
    FROM forecasts
    WHERE area_code = ? AND fetched_at = ?
    ORDER BY date ASC;
    """, (area_code, fetched_at))
    rows = cur.fetchall()

    conn.close()
    return fetched_at, area_name, rows


# 表示
def icon_from_weather_code(code: str) -> str:
    if code is None:
        return ft.Icons.WB_CLOUDY
    code = str(code)
    if code.startswith("1"):
        return ft.Icons.WB_SUNNY
    if code.startswith("2"):
        return ft.Icons.CLOUD
    if code.startswith("3"):
        return ft.Icons.UMBRELLA
    if code.startswith("4"):
        return ft.Icons.AC_UNIT
    return ft.Icons.WB_CLOUDY


# メイン処理
def main(page: ft.Page):
    page.title = "気象庁 天気予報アプリ_new"
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH

    init_db()
    areas = get_area_list()

    title = ft.Text("", size=22, weight=ft.FontWeight.BOLD)
    subtitle = ft.Text("", size=12)

    cards = ft.GridView(
        expand=True,
        runs_count=4,
        max_extent=220,
        spacing=12,
        run_spacing=12,
        padding=16,
    )

    right = ft.Column([title, subtitle, cards], expand=True)

    # DBの内容で画面更新
    def show_from_db(area_code):
        fetched_at, area_name, rows = load_latest_forecast_from_db(area_code)

        if not rows:
            title.value = "DBにデータがありません"
            subtitle.value = "左の地域をクリックして取得してください"
            cards.controls.clear()
            page.update()
            return

        title.value = f"{area_name}の天気予報"
        subtitle.value = f"DB取得時刻: {fetched_at}"

        cards.controls.clear()
        for date_str, code, text in rows:
            cards.controls.append(
                ft.Card(
                    content=ft.Container(
                        padding=14,
                        content=ft.Column(
                            [
                                ft.Text(date_str, weight=ft.FontWeight.BOLD),
                                ft.Icon(icon_from_weather_code(code), size=54),
                                ft.Text(text, size=14, text_align=ft.TextAlign.CENTER),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                    )
                )
            )
        page.update()

    # 取得→DB保存→DB表示（JSON表示はしない）
    def fetch_save_show(area_code):
        try:
            area_name, rows = fetch_forecast_from_api(area_code)
            save_forecast_to_db(area_code, area_name, rows)
            show_from_db(area_code)
        except Exception as e:
            title.value = "取得失敗"
            subtitle.value = ""
            cards.controls = [ft.Text(f"エラー: {e}")]
            page.update()

    # 左メニュー（クリックで取得＆保存＆表示）
    menu = ft.ListView(width=260, expand=True, spacing=4, padding=10)
    for name, code in areas:
        menu.controls.append(
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOCATION_ON),
                title=ft.Text(name),
                subtitle=ft.Text(code),
                on_click=lambda e, c=code: fetch_save_show(c),
            )
        )

    page.add(
        ft.Row(
            [
                menu,
                ft.VerticalDivider(width=1),
                right,
            ],
            expand=True,
        )
    )

    # 初期表示（DBに無ければ案内が出る）
    show_from_db(areas[0][1])


ft.run(main)
