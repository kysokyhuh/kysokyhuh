#!/usr/bin/env python3
"""Generate a cleaner constellation-style GitHub activity graphic."""

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
        "subtitle": "#9CA3AF",
        "faint": "#E5E7EB",
        "line": "#D1D5DB",
        "line_highlight": "#BFD7EA",
        "glow": "#DCEAF5",
        "levels": {
            0: "#E5E7EB",
            1: "#CFCFD6",
            2: "#9AA4B2",
            3: "#6B7280",
            4: "#BFD7EA",
        },
    },
    "dark": {
        "text": "#D1D5DB",
        "subtitle": "#9CA3AF",
        "faint": "#2A2F36",
        "line": "#4B5563",
        "line_highlight": "#BFD7EA",
        "glow": "#BFD7EA",
        "levels": {
            0: "#2A2F36",
            1: "#59616D",
            2: "#8A95A3",
            3: "#D1D5DB",
            4: "#BFD7EA",
        },
    },
}


def stable_noise(key: str, low: float, high: float) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return low + (high - low) * value


def download() -> list[dict]:
    request = Request(
        API,
        headers={"User-Agent": "constellation-github-profile/2.0"},
    )

    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    days = payload.get("contributions")

    if not isinstance(days, list) or len(days) < 300:
        raise ValueError("Contribution API did not return a complete year")

    return days


def build_daily(days: list[dict]):
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


def build_points(daily: dict, start: date, left: int, top: int, pitch_x: int, pitch_y: int):
    points = []

    for day in sorted(daily):
        entry = daily[day]
        count = entry["count"]
        level = entry["level"]

        number = (day - start).days
        week = number // 7
        row = number % 7

        base_x = left + week * pitch_x
        base_y = top + row * pitch_y

        if level == 0:
            jitter = 0.25
            radius = 0.8
            opacity = 0.23
        elif level == 1:
            jitter = 0.60
            radius = 1.50
            opacity = 0.70
        elif level == 2:
            jitter = 0.75
            radius = 2.10
            opacity = 0.82
        elif level == 3:
            jitter = 0.90
            radius = 2.80
            opacity = 0.94
        else:
            jitter = 1.00
            radius = 3.60
            opacity = 1.00

        x = base_x + stable_noise(f"{day.isoformat()}-x", -jitter, jitter)
        y = base_y + stable_noise(f"{day.isoformat()}-y", -jitter, jitter)

        points.append(
            {
                "day": day,
                "count": count,
                "level": level,
                "week": week,
                "row": row,
                "x": x,
                "y": y,
                "r": radius,
                "opacity": opacity,
            }
        )

    return points


def make_connections(points: list[dict]) -> list[tuple[int, int]]:
    """Create sparse, meaningful connections only between stronger activity days."""
    anchors = [(i, p) for i, p in enumerate(points) if p["level"] >= 2]
    edges: set[tuple[int, int]] = set()

    degrees = {i: 0 for i, _ in anchors}

    for idx, (i, point) in enumerate(anchors):
        candidates = []

        for j, other in anchors[idx + 1 :]:
            day_diff = (other["day"] - point["day"]).days
            if day_diff > 18:
                break

            week_diff = abs(other["week"] - point["week"])
            row_diff = abs(other["row"] - point["row"])

            if week_diff <= 2 and row_diff <= 2:
                distance = math.hypot(other["x"] - point["x"], other["y"] - point["y"])
                score = distance + row_diff * 3 + week_diff * 2
                candidates.append((score, j))

        candidates.sort(key=lambda item: item[0])

        max_links = 2 if point["level"] == 4 else 1

        for _, j in candidates:
            if degrees[i] >= max_links:
                break
            if degrees[j] >= 2:
                continue

            edge = tuple(sorted((i, j)))
            if edge in edges:
                continue

            edges.add(edge)
            degrees[i] += 1
            degrees[j] += 1

    return sorted(edges)


def render(days: list[dict], theme: str) -> str:
    colors = THEMES[theme]
    daily, start, first, last = build_daily(days)

    pitch_x = 13
    pitch_y = 13
    left = 44
    top = 74

    weeks = ((last - start).days // 7) + 1
    width = left + weeks * pitch_x + 18
    height = 185

    total_contributions = sum(item["count"] for item in daily.values())

    points = build_points(daily, start, left, top, pitch_x, pitch_y)
    edges = make_connections(points)

    pieces = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" '
            f'role="img" aria-label="Constellation view of GitHub activity">'
        ),
        f'<title>{total_contributions} GitHub contributions during the past year</title>',
    ]

    # Header
    pieces.append(
        f'<text x="{left}" y="20" fill="{colors["text"]}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="12" font-weight="700">'
        f'CONSTELLATION / 365</text>'
    )
    pieces.append(
        f'<text x="{left}" y="34" fill="{colors["subtitle"]}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="10">'
        f'Active days become stars.</text>'
    )

    # Month labels
    months_seen = set()
    for day in sorted(daily):
        label = (day.year, day.month)
        if label not in months_seen:
            months_seen.add(label)
            column = (day - start).days // 7
            x = left + column * pitch_x
            if x >= left + 10:
                pieces.append(
                    f'<text x="{x}" y="56" fill="{colors["text"]}" '
                    f'font-family="Arial, Helvetica, sans-serif" font-size="9">'
                    f'{escape(day.strftime("%b"))}</text>'
                )

    # Draw faint background stars first
    for point in points:
        if point["level"] != 0:
            continue

        pieces.append(
            f'<circle cx="{point["x"]:.2f}" cy="{point["y"]:.2f}" '
            f'r="{point["r"]:.2f}" fill="{colors["faint"]}" opacity="{point["opacity"]:.2f}" />'
        )

    # Draw sparse constellation lines
    for index, (i, j) in enumerate(edges):
        a = points[i]
        b = points[j]

        highlight = a["level"] == 4 or b["level"] == 4
        stroke = colors["line_highlight"] if highlight else colors["line"]
        opacity = "0.54" if highlight else "0.28"

        pieces.append(
            f'<line x1="{a["x"]:.2f}" y1="{a["y"]:.2f}" '
            f'x2="{b["x"]:.2f}" y2="{b["y"]:.2f}" '
            f'stroke="{stroke}" stroke-width="1" stroke-linecap="round" opacity="{opacity}" />'
        )

    # Draw active stars
    for point in points:
        if point["level"] == 0:
            continue

        color = colors["levels"][point["level"]]

        # Peak days get a soft glow and subtle pulse
        if point["level"] == 4:
            begin = stable_noise(f"peak-{point['day'].isoformat()}", 0.0, 4.0)

            pieces.append(
                f'<circle cx="{point["x"]:.2f}" cy="{point["y"]:.2f}" '
                f'r="{point["r"] + 2.6:.2f}" fill="{colors["glow"]}" opacity="0.12">'
                f'<animate attributeName="opacity" values="0.08;0.22;0.08" '
                f'dur="6s" begin="{begin:.2f}s" repeatCount="indefinite" />'
                f'</circle>'
            )

            pieces.append(
                f'<circle cx="{point["x"]:.2f}" cy="{point["y"]:.2f}" '
                f'r="{point["r"]:.2f}" fill="{color}" opacity="1">'
                f'<title>{point["day"].isoformat()}: {point["count"]} contributions</title>'
                f'<animate attributeName="opacity" values="0.86;1;0.86" '
                f'dur="4.5s" begin="{begin:.2f}s" repeatCount="indefinite" />'
                f'</circle>'
            )
        else:
            pieces.append(
                f'<circle cx="{point["x"]:.2f}" cy="{point["y"]:.2f}" '
                f'r="{point["r"]:.2f}" fill="{color}" opacity="{point["opacity"]:.2f}">'
                f'<title>{point["day"].isoformat()}: {point["count"]} contributions</title>'
                f'</circle>'
            )

    # Footer
    footer_y = height - 12
    pieces.append(
        f'<text x="{left}" y="{footer_y}" fill="{colors["text"]}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="10">'
        f'{total_contributions} contributions / last year</text>'
    )

    legend_x = width - 126
    pieces.append(
        f'<text x="{legend_x}" y="{footer_y}" fill="{colors["text"]}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="10">Quiet</text>'
    )

    legend_levels = [1, 2, 3, 4]
    for idx, level in enumerate(legend_levels):
        cx = legend_x + 33 + idx * 16
        cy = footer_y - 4
        r = 1.4 + idx * 0.45
        pieces.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="{colors["levels"][level]}" />'
        )

    pieces.append(
        f'<text x="{legend_x + 100}" y="{footer_y}" fill="{colors["text"]}" '
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
