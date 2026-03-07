import calendar
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

BASE_DIR = Path("/home/agent/autofinisher-factory/digital_product_factory")
OUTPUTS_DIR = BASE_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_adhd_planner_csv() -> None:
    themes = ["Dark Rainbow", "Pastel Calm", "Bright ADHD", "Monochrome", "Custom"]
    rows = []

    start_date = datetime(2026, 1, 1)
    for day in range(365):
        date = start_date + timedelta(days=day)
        date_str = date.strftime("%d %b %Y")
        month_name = calendar.month_name[date.month]

        for theme in themes:
            rows.append(
                {
                    "Theme": theme,
                    "Page_Title": f"Daily – {date_str}",
                    "Text_Main": "Morning Surge • Dopamine Menu • Focus Timer • Brain Breaks",
                    "Link_Target_LogicalID": f"monthly_{month_name.lower()}",
                    "Sticker_Pack": "50 ADHD stickers pack",
                }
            )

    for month in range(1, 13):
        month_name = calendar.month_name[month]
        for theme in themes:
            rows.append(
                {
                    "Theme": theme,
                    "Page_Title": f"Month Overview – {month_name} 2026",
                    "Text_Main": "Hyperlinked overview + progress bars + habit review",
                    "Link_Target_LogicalID": "yearly_overview",
                    "Sticker_Pack": "50 ADHD stickers pack",
                }
            )

    df = pd.DataFrame(rows)
    path = OUTPUTS_DIR / "2026_ADHD_DIGITAL_PLANNER_FULL.csv"
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"ADHD Planner CSV ready: {len(df)} rows -> {path}")


def generate_cleaning_checklist_csv() -> None:
    themes = ["Dark Rainbow", "Pastel Calm", "Bright ADHD", "Monochrome", "Custom"]
    rooms = ["Kitchen", "Living Room", "Bathroom", "Bedroom", "Home Office", "Entryway", "Dining Room"]
    rows = []

    for theme in themes:
        for room in rooms:
            for week in range(1, 5):
                rows.append(
                    {
                        "Theme": theme,
                        "Page_Title": f"Week {week} – {room} Cleaning Checklist",
                        "Text_Main": "Dopamine Hit: Watch favorite show after completion • Reward: Reduce clutter",
                        "Link_Target_LogicalID": "weekly_overview",
                        "Sticker_Pack": "30 cleaning + ADHD icons",
                    }
                )

    df = pd.DataFrame(rows)
    path = OUTPUTS_DIR / "ADHD_CLEANING_CHECKLIST_FULL.csv"
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"Cleaning Checklist CSV ready: {len(df)} rows -> {path}")


if __name__ == "__main__":
    generate_adhd_planner_csv()
    generate_cleaning_checklist_csv()
    print("All CSV files generated.")
