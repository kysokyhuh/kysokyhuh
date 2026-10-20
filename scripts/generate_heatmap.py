#!/usr/bin/env python3
"""Generate a constellation-style GitHub activity graphic."""

from __future__ import annotations

import hashlib
import json
import math
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
        "text": "#6B7280",
        "inactive": "#E5E7EB",
        "line": "#D1D5DB",
        "line_highlight": "#BFD7EA",
        "levels": {
            0: "#E5E7EB",
            1: "#CFCFD6",
            2: "#A7AFBA",
            3: "#6B7280",
            4: "#BFD7EA",
        },
        "twinkle_opacity": ("0.55", "1.0"),
        "subtitle": "#9CA3AF",
    },
    "dark": {
        "text": "#D1D5DB",
        "inactive": "#2A2F36",
        "line": "#4B5563",
        "line_highlight": "#BFD7EA",
        "levels": {
            0: "#2A2F36",
            1: "#525B67",
            2: "#7C8794",
            3: "#D1D5DB",
            4: "#BFD7EA",
        },
        "twinkle_opacity": ("0.45", "1.0"),
        "subtitle": "#9CA3AF",
    },
}


def stable_noise(key: str, low: float, high: float) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return low + (high - low) * value


def download() -> list[dict]:
    request = Request(
        API,
        headers={"User-Agent": "constellation-github-profile/1.0"},
    )

    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    days = payload.get("contributions")

    if not isinstance(days, list) or len(days) < 300:
        raise ValueError("Contribution API did not return a complete year")

    return days


def build_points(days: list[dict]):
    daily = {}

    for item in days:
        day = date.fromisoformat(item["date"])
        count = max(0, int(item["count"]))
        level = max(0, min(4, int(item["level"])))
        daily[day] = {"count": count, "level": level}

    first = min(daily)
    last = max(daily)

    start = first - timedelta(days=(first.weekday() + 1) % 7)

    return daily, start, first, last


def make_connections(points: list[dict]) -> list[tuple[int, int]]:
    if not points:
        return []

    index_of = {point["day"]: i for i, point in enumerate(points)}
    edges = set()

    # Connect nearby points across adjacent weeks
    for i, point in enumerate(points):
        best_j = None
        best_distance = 999999.0

        for other in points[i + 1 :]:
            day_diff = (other["day"] - point["day"]).days
            if day_diff > 18:
                break

            week_diff = abs(other["week"] - point["week"])
            row_diff = abs(other["row"] - point["row"])

            if week_diff <= 2 and row_diff <= 3:
                distance = math.hypot(other["x"] - point["x"], other["y"] - point["y"])
                if distance < best_distance:
                    best_distance = distance
                    best_j = index_of[other["day"]]

        if best_j is not None:
            edge = tuple(sorted((i, best_j)))
            edges.add(edge)

    # Add some vertical / in-week structure
    by_week = {}
    for i, point in enumerate(points):
        by_week.setdefault(point["week"], []).append((i, point))

    for _, items in by_week.items():
        items.sort(key=lambda pair: pair[1]["row"])
        for a, b in zip(items, items[1:]):
            i, pa = a
            j, pb = b
            if abs(pa["row"] - pb["row"]) <= 2:
                edge = tuple(sorted((i, j)))
                edges.add(edge)

    return sorted(edges)


def render(days: list[dict], theme: str) -> str:
    colors = THEMES[theme]
    daily, start, first, last = build_points(days)

    pitch_x = 13
    pitch_y = 13
    left = 42
    top = 40
    weeks = ((last - start).days // 7) + 1

    width = left + weeks * pitch_x + 18
    height = 185

    total_contributions = sum(entry["count"] for entry in daily.values())

    pieces = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" '
            f'role="img" aria-label="Constellation view of GitHub activity">'
        ),
        f'<title>{total_contributions} GitHub contributions during the past year</title>',
    ]

    pieces.append(
        f'<text x="{left}" y="18" fill="{colors["text"]}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700">'
        f'CONSTELLATION / 365</text>'
    )
    pieces.append(
        f'<text x="{left}" y="32" fill="{colors["subtitle"]}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="10">'
        f'A year of building, mapped in stars.</text>'
    )

    # Month labels
    months_seen = set()
    for day in sorted(daily):
        marker = (day.year, day.month)
        if marker not in months_seen:
            months_seen.add(marker)
            col = (day - start).days // 7
            x = left + col * pitch_x
            if x >= left + 10:
                pieces.append(
                    f'<text x="{x}" y="52" fill="{colors["text"]}" '
                    f'font-family="Arial, Helvetica, sans-serif" font-size="9">'
                    f'{escape(day.strftime("%b"))}</text>'
                )

    star_points = []
    all_days = sorted(daily)

    for day in all_days:
        entry = daily[day]
        count = entry["count"]
        level = entry["level"]

        number = (day - start).days
        week = number // 7
        row = number % 7

        base_x = left + week * pitch_x
        base_y = top + 22 + row * pitch_y

        jitter_x = stable_noise(f"{day.isoformat()}-x", -1.8, 1.8)
        jitter_y = stable_noise(f"{day.isoformat()}-y", -1.8, 1.8)

        x = base_x + jitter_x
        y = base_y + jitter_y

        if level == 0:
            radius = 1.15
        elif level == 1:
            radius = 1.55
        elif level == 2:
            radius = 1.95
        elif level == 3:
            radius = 2.35
        else:
            radius = 2.75

        star_points.append(
            {
                "day": day,
                "count": count,
                "level": level,
                "week": week,
                "row": row,
                "x": x,
                "y": y,
                "r": radius,
            }
        )

    active_points = [point for point in star_points if point["level"] > 0]
    edges = make_connections(active_points)

    # Connection lines first
    for edge_index, (i, j) in enumerate(edges):
        a = active_points[i]
        b = active_points[j]

        highlight = a["level"] == 4 or b["level"] == 4
        stroke = colors["line_highlight"] if highlight else colors["line"]
        opacity_low = "0.18" if not highlight else "0.32"
        opacity_high = "0.34" if not highlight else "0.56"
        begin = stable_noise(f"line-{edge_index}", 0.0, 4.0)

        pieces.append(
            f'<line x1="{a["x"]:.2f}" y1="{a["y"]:.2f}" '
            f'x2="{b["x"]:.2f}" y2="{b["y"]:.2f}" '
            f'stroke="{stroke}" stroke-width="0.9" '
            f'stroke-linecap="round" opacity="{opacity_low}">'
            f'<animate attributeName="opacity" '
            f'values="{opacity_low};{opacity_high};{opacity_low}" '
            f'dur="8s" begin="{begin:.2f}s" repeatCount="indefinite" />'
            f'</line>'
        )

    # Stars
    low_opacity, high_opacity = colors["twinkle_opacity"]

    for index, point in enumerate(star_points):
        color = colors["levels"][point["level"]]
        begin = stable_noise(f"star-{point['day'].isoformat()}", 0.0, 6.0)

        # soft glow for peak stars
        if point["level"] == 4:
            pieces.append(
                f'<circle cx="{point["x"]:.2f}" cy="{point["y"]:.2f}" '
                f'r="{point["r"] + 2.3:.2f}" fill="{color}" opacity="0.10">'
                f'<animate attributeName="opacity" values="0.06;0.18;0.06" '
                f'dur="6s" begin="{begin:.2f}s" repeatCount="indefinite" />'
                f'</circle>'
            )

        pieces.append(
            f'<circle cx="{point["x"]:.2f}" cy="{point["y"]:.2f}" '
            f'r="{point["r"]:.2f}" fill="{color}" opacity="{low_opacity}">'
            f'<title>{point["day"].isoformat()}: {point["count"]} contributions</title>'
            f'<animate attributeName="opacity" values="{low_opacity};{high_opacity};{low_opacity}" '
            f'dur="5.5s" begin="{begin:.2f}s" repeatCount="indefinite" />'
            f'</circle>'
        )

    # Footer
    legend_y = height - 12
    legend_x = left

    pieces.append(
        f'<text x="{legend_x}" y="{legend_y}" fill="{colors["text"]}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="10">'
        f'{total_contributions} contributions / last year</text>'
    )

    quiet_x = width - 135
    pieces.append(
        f'<text x="{quiet_x}" y="{legend_y}" fill="{colors["text"]}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="10">Quiet</text>'
    )

    for idx, level in enumerate([0, 1, 2, 3, 4]):
        cx = quiet_x + 34 + idx * 14
        cy = legend_y - 4
        r = 1.3 + idx * 0.3
        pieces.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="{colors["levels"][level]}" />'
        )

    pieces.append(
        f'<text x="{quiet_x + 110}" y="{legend_y}" fill="{colors["text"]}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="10">Active</text>'
    )

    pieces.append("</svg>")

    return "\n".join(pieces) + "\n"


def main() -> None:
    days = download()

    OUTPUT.mkdir(parents=True, exist_ok=True)

    for theme in THEMES:
        file = OUTPUT / f"contributions-{theme}.svg"
        file.write_text(render(days, theme), encoding="utf-8")
        print(f"Updated {file}")


if __name__ == "__main__":
    main()
