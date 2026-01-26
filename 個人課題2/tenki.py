import flet as ft
import requests
from datetime import datetime


# 地域リスト取得
def get_area_list():
    area_url = "https://www.jma.go.jp/bosai/common/const/area.json"
    data_json = requests.get(area_url).json()
    offices = data_json["offices"]
    return [(offices[key]["name"], key) for key in offices]


# 天気予報取得（weatherCodes + 日付）
def get_weather_forecast(area_code):
    forecast_url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json"
    data_json = requests.get(forecast_url).json()

    ts = data_json[0]["timeSeries"][0]  # 天気(文字列/コード)が入ってる系列
    area = ts["areas"][0]

    area_name = area["area"]["name"]
    weathers = area["weathers"]
    weather_codes = area["weatherCodes"]
    time_defines = ts["timeDefines"]  # ISO日時文字列

    return area_name, weathers, weather_codes, time_defines


# 天気コード→アイコン（ざっくり分類）
def icon_from_weather_code(code: str) -> str:
    # 100台:晴 / 200台:曇 / 300台:雨 / 400台:雪 の“大まかな傾向”で割り当て
    if code.startswith("1"):
        return ft.Icons.WB_SUNNY
    if code.startswith("2"):
        return ft.Icons.CLOUD
    if code.startswith("3"):
        return ft.Icons.UMBRELLA
    if code.startswith("4"):
        return ft.Icons.AC_UNIT
    return ft.Icons.WB_CLOUDY


# ISO日時→日付文字列
def to_date_str(iso_dt: str) -> str:
    # 例: "2026-01-26T00:00:00+09:00"
    try:
        dt = datetime.fromisoformat(iso_dt.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return iso_dt[:10]


# メイン処理
def main(page: ft.Page):
    page.title = "気象庁 天気予報アプリ"
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH

    areas = get_area_list()

    title = ft.Text("", size=22, weight=ft.FontWeight.BOLD)
    cards = ft.GridView(
        expand=True,
        runs_count=4,        # 横に並ぶ目安（ウィンドウ幅で変わる）
        max_extent=220,      # カード幅の目安
        spacing=12,
        run_spacing=12,
        padding=16,
    )

    right = ft.Column([title, cards], expand=True)

    # 天気表示
    def show_forecast(index: int):
        name, code = areas[index]

        try:
            area_name, weathers, weather_codes, time_defines = get_weather_forecast(code)
        except Exception as e:
            title.value = f"{name}（取得失敗）"
            cards.controls = [ft.Text(f"エラー: {e}")]
            page.update()
            return

        title.value = f"{area_name}の天気予報"

        cards.controls.clear()
        for w, c, t in zip(weathers, weather_codes, time_defines):
            date_str = to_date_str(t)
            cards.controls.append(
                ft.Card(
                    content=ft.Container(
                        padding=14,
                        content=ft.Column(
                            [
                                ft.Text(date_str, weight=ft.FontWeight.BOLD),
                                ft.Icon(icon_from_weather_code(c), size=54),
                                ft.Text(w, size=14, text_align=ft.TextAlign.CENTER),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                    )
                )
            )

        page.update()

    # 左メニュー（スクロール可）
    menu = ft.ListView(
        width=260,
        expand=True,
        spacing=4,
        padding=10,
    )

    for i, (name, code) in enumerate(areas):
        menu.controls.append(
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOCATION_ON),
                title=ft.Text(name),
                subtitle=ft.Text(code),
                on_click=lambda e, idx=i: show_forecast(idx),
            )
        )

    # UI構築
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

    show_forecast(0)


ft.run(main)
