import flet as ft
import requests


# 地域リスト取得
def get_area_list():
    area_url = "https://www.jma.go.jp/bosai/common/const/area.json"
    data_json = requests.get(area_url).json()
    offices = data_json["offices"]
    return [(offices[key]["name"], key) for key in offices]


# 天気予報取得
def get_weather_forecast(area_code):
    forecast_url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json"
    try:
        data_json = requests.get(forecast_url).json()
        forecast = data_json[0]["timeSeries"][0]["areas"][0]
        area_name = forecast["area"]["name"]
        weather_list = forecast["weathers"]
        return area_name, weather_list
    except Exception as e:
        return None, [f"エラー: {e}"]


# メイン処理
def main(page: ft.Page):
    page.title = "気象庁 天気予報アプリ"
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH

    areas = get_area_list()

    forecast_column = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

    # 天気表示
    def show_forecast(index):
        name, code = areas[index]
        area_name, forecast_list = get_weather_forecast(code)

        forecast_column.controls.clear()
        forecast_column.controls.append(
            ft.Text(f"{area_name}の天気予報", size=20, weight=ft.FontWeight.BOLD)
        )
        for w in forecast_list:
            forecast_column.controls.append(ft.Text(w))

        page.update()

    # 左メニュー（スクロール可）
    menu = ft.ListView(
        width=260,
        expand=True,
        spacing=4,
        padding=10,
        auto_scroll=False,
    )

    for i, (name, code) in enumerate(areas):
        menu.controls.append(
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOCATION_ON),
                title=ft.Text(name),
                on_click=lambda e, idx=i: show_forecast(idx),
            )
        )

    # UI構築
    page.add(
        ft.Row(
            [
                menu,
                ft.VerticalDivider(width=1),
                forecast_column,
            ],
            expand=True,
        )
    )

    show_forecast(0)


ft.run(main)
