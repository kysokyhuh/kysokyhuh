
#!/usr/bin/env python3
"""Generate monochrome GitHub contribution heatmaps."""

from __future__ import annotations

import json
from datetime import date, timedelta
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen

USER = "kysokyhuh"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets"
API = f"https://github-contributions-api.jogruber.de/v4/{USER}?y=last"

THEMES = {
    "light": {
        "text": "#52525B",
        "cells": [
            "#F4F4F5",
            "#D4D4D8",
            "#A1A1AA",
            "#71717A",
            "#18181B",
        ],
    },
    "dark": {
        "text": "#D4D4D8",
        "cells": [
            "#27272A",
            "#52525B",
            "#71717A",
            "#A1A1AA",
            "#FAFAFA",
        ],
    },
}


def download() -> list[dict]:
    request = Request(
        API,
        headers={"User-Agent": "minimal-github-profile/1.0"},
    )

    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    days = payload.get("contributions")

    if not isinstance(days, list) or len(days) < 300:
        raise ValueError(
            "Contribution API did not return a complete year"
        )

    return days


def render(days: list[dict], theme: str) -> str:
    colors = THEMES[theme]
    daily = {}

    for item in days:
        day = date.fromisoformat(item["date"])
        daily[day] = (
            max(0, int(item["count"])),
            max(0, min(4, int(item["level"]))),
        )

    first, last = min(daily), max(daily)

    start = first - timedelta(
        days=(first.weekday() + 1) % 7
    )

    weeks = ((last - start).days // 7) + 1

    size, pitch = 10, 13
    left, top = 44, 32

    width = left + weeks * pitch + 14
    height = 154

    count = sum(total for total, _ in daily.values())

    pieces = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" '
            f'role="img" aria-label="Contribution heatmap">'
        ),
        f'<title>{count} GitHub contributions during the past year</title>',
    ]

    months_seen = set()

    for d in sorted(daily):
        label = (d.year, d.month)

        if label not in months_seen:
            months_seen.add(label)

            column = (d - start).days // 7
            x = left + column * pitch

            if x >= left + 14:
                pieces.append(
                    f'<text x="{x}" y="18" '
                    f'fill="{colors["text"]}" '
                    f'font-family="Arial,sans-serif" '
                    f'font-size="10">'
                    f'{escape(d.strftime("%b"))}</text>'
                )

    for day, (total, level) in sorted(daily.items()):
        number = (day - start).days
        column, row = divmod(number, 7)

        x = left + column * pitch
        y = top + row * pitch

        pieces.append(
            f'<rect x="{x}" y="{y}" '
            f'width="{size}" height="{size}" '
            f'rx="2" fill="{colors["cells"][level]}">'
            f'<title>{day.isoformat()}: '
            f'{total} contributions</title></rect>'
        )

    pieces.append(
        f'<text x="{left}" y="148" '
        f'fill="{colors["text"]}" '
        f'font-family="Arial,sans-serif" '
        f'font-size="11">'
        f'{count} contributions / last year</text>'
    )

    legend_x = width - 5 * 13 - 45

    pieces.append(
        f'<text x="{legend_x - 29}" y="148" '
        f'fill="{colors["text"]}" '
        f'font-family="Arial,sans-serif" '
        f'font-size="10">Less</text>'
    )

    for index, color in enumerate(colors["cells"]):
        pieces.append(
            f'<rect x="{legend_x + index * 13}" '
            f'y="137" width="10" height="10" '
            f'rx="2" fill="{color}" />'
        )

    pieces.append(
        f'<text x="{legend_x + 5 * 13}" y="148" '
        f'fill="{colors["text"]}" '
        f'font-family="Arial,sans-serif" '
        f'font-size="10">More</text>'
    )

    pieces.append("</svg>")

    return "\n".join(pieces) + "\n"


def main() -> None:
    days = download()

    OUTPUT.mkdir(parents=True, exist_ok=True)

    for theme in THEMES:
        file = OUTPUT / f"contributions-{theme}.svg"

        file.write_text(
            render(days, theme),
            encoding="utf-8",
        )

        print(f"Updated {file}")


if __name__ == "__main__":
    main()
