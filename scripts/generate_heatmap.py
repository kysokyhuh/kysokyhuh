
#!/usr/bin/env python3
"""Generate a moving constellation from GitHub contributions."""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen

USERNAME = "kysokyhuh"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets"
API = f"https://github-contributions-api.jogruber.de/v4/{USERNAME}?y=last"

# Animation duration in seconds.
DURATION = 18

PALETTES = {
    "light": {
        "text": "#626974",
        "muted": "#87919D",
        "empty": "#D1D5DB",
        "low": "#AAB3BF",
        "mid": "#6F7B89",
        "high": "#333D49",
        "route": "#8EA7BB",
        "blue": "#5D91B3",
        "halo": "#A9CEE5",
    },
    "dark": {
        "text": "#CED5DE",
        "muted": "#929EAD",
        "empty": "#57606D",
        "low": "#7D8998",
        "mid": "#A7B3C2",
        "high": "#E4EAF2",
        "route": "#7F99B0",
        "blue": "#BFD7EA",
        "halo": "#BFD7EA",
    },
}


def fetch_days() -> list[dict]:
    request = Request(
        API,
        headers={"User-Agent": "constellation-365/3.0"},
    )

    with urlopen(request, timeout=30) as response:
        data = json.load(response)

    days = data.get("contributions", [])

    if len(days) < 300:
        raise ValueError(
            "Contribution API returned less than a year of data"
        )

    return days


def layout(days: list[dict]):
    daily = {}

    for item in days:
        current = date.fromisoformat(item["date"])
        daily[current] = max(0, int(item["count"]))

    start_date = min(daily)
    start = start_date - timedelta(
        days=(start_date.weekday() + 1) % 7
    )

    end = max(daily)
    weeks = ((end - start).days // 7) + 1

    points = []

    for current, count in sorted(daily.items()):
        offset = (current - start).days
        week, weekday = divmod(offset, 7)

        points.append({
            "date": current,
            "count": count,
            "week": week,
            "x": 38 + week * 13,
            "y": 72 + weekday * 13,
        })

    return points, 38 + weeks * 13 + 20


def choose_anchors(points: list[dict]) -> list[dict]:
    """Choose real activity peaks across the year."""

    active = [
        p for p in points
        if p["count"] > 0
    ]

    if not active:
        return []

    first_week = points[0]["week"]
    last_week = points[-1]["week"]

    span = max(
        1,
        last_week - first_week + 1,
    )

    bucket_count = 12
    selected = []

    for segment in range(bucket_count):
        matches = [
            p for p in active
            if min(
                bucket_count - 1,
                (p["week"] - first_week)
                * bucket_count // span,
            ) == segment
        ]

        if matches:
            selected.append(
                max(
                    matches,
                    key=lambda p: (
                        p["count"],
                        -p["date"].toordinal(),
                    ),
                )
            )

    return sorted(
        selected,
        key=lambda p: p["date"],
    )


def route_path(anchors: list[dict]) -> str:
    if not anchors:
        return ""

    x0 = anchors[0]["x"]
    y0 = anchors[0]["y"]

    return f"M {x0:.1f},{y0:.1f} " + " ".join(
        f"L {p['x']:.1f},{p['y']:.1f}"
        for p in anchors[1:]
    )


def fractional_arrival(
    anchors: list[dict],
) -> list[float]:

    if len(anchors) < 2:
        return [0.0] * len(anchors)

    distances = [0.0]

    for a, b in zip(anchors, anchors[1:]):
        distance = math.hypot(
            b["x"] - a["x"],
            b["y"] - a["y"],
        )

        distances.append(
            distances[-1] + distance
        )

    total = max(distances[-1], 1.0)

    return [
        distance / total
        for distance in distances
    ]


def render(days: list[dict], mode: str) -> str:
    palette = PALETTES[mode]
    points, width = layout(days)

    active = [
        p for p in points
        if p["count"] > 0
    ]

    anchors = choose_anchors(points)

    max_count = max(
        (p["count"] for p in active),
        default=1,
    )

    # Highlight the six busiest contribution days.
    highlighted = {
        p["date"]
        for p in sorted(
            active,
            key=lambda p: (
                -p["count"],
                p["date"],
            ),
        )[:6]
    }

    total = sum(
        p["count"] for p in points
    )

    height = 195

    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" '
            f'role="img" '
            f'aria-label="Animated GitHub contribution constellation">'
        ),
        (
            f'<title>{total} GitHub contributions '
            f'mapped into a moving constellation</title>'
        ),
        (
            f'<text x="38" y="20" '
            f'fill="{palette["text"]}" '
            f'font-family="Arial,sans-serif" '
            f'font-size="12" font-weight="700">'
            f'CONSTELLATION / 365</text>'
        ),
        (
            f'<text x="38" y="37" '
            f'fill="{palette["muted"]}" '
            f'font-family="Arial,sans-serif" '
            f'font-size="10">'
            f'A year of building, in motion.</text>'
        ),
    ]

    # Month labels.
    month_seen = set()

    for p in points:
        marker = (
            p["date"].year,
            p["date"].month,
        )

        if marker in month_seen:
            continue

        month_seen.add(marker)

        if p["x"] >= 65:
            month = escape(
                p["date"].strftime("%b")
            )

            parts.append(
                f'<text x="{p["x"]}" y="59" '
                f'fill="{palette["muted"]}" '
                f'font-family="Arial,sans-serif" '
                f'font-size="9">{month}</text>'
            )

    # Draw the contribution stars.
    for p in points:
        x = p["x"]
        y = p["y"]
        count = p["count"]

        if count == 0:
            parts.append(
                f'<circle cx="{x}" cy="{y}" '
                f'r="0.65" '
                f'fill="{palette["empty"]}" '
                f'opacity="0.22"/>'
            )
            continue

        strength = count / max_count

        radius = 1.4 + 1.9 * math.sqrt(strength)

        if strength > 0.5:
            color = palette["high"]
        elif strength > 0.2:
            color = palette["mid"]
        else:
            color = palette["low"]

        if p["date"] in highlighted:
            color = palette["blue"]
            radius = 3.5

        parts.append(
            f'<circle cx="{x}" cy="{y}" '
            f'r="{radius:.2f}" fill="{color}">'
            f'<title>{p["date"].isoformat()}: '
            f'{count} contributions</title>'
            f'</circle>'
        )

    # Animate a Glacier Blue signal along real activity peaks.
    if len(anchors) >= 2:
        motion = route_path(anchors)

        # Faint permanent connection path.
        parts.append(
            f'<path d="{motion}" fill="none" '
            f'stroke="{palette["route"]}" '
            f'stroke-width="0.9" '
            f'opacity="0.32" '
            f'stroke-linejoin="round"/>'
        )

        # Short illuminated trail traveling along the path.
        parts.append(
            f'<path d="{motion}" fill="none" '
            f'pathLength="100" '
            f'stroke="{palette["blue"]}" '
            f'stroke-width="2.1" '
            f'stroke-linecap="round" '
            f'stroke-dasharray="5 95" opacity="0.9">'
            f'<animate '
            f'attributeName="stroke-dashoffset" '
            f'from="0" to="-100" '
            f'dur="{DURATION}s" '
            f'repeatCount="indefinite"/>'
            f'</path>'
        )

        # The moving signal and its soft halo.
        for radius, opacity in (
            (7, 0.15),
            (3.3, 1.0),
        ):
            if radius == 7:
                fill = palette["halo"]
            else:
                fill = palette["blue"]

            parts.append(
                f'<circle r="{radius}" '
                f'fill="{fill}" opacity="{opacity}">'
                f'<animateMotion '
                f'path="{motion}" '
                f'dur="{DURATION}s" '
                f'calcMode="paced" '
                f'repeatCount="indefinite"/>'
                f'</circle>'
            )

        # Light up selected stars as the signal arrives.
        arrivals = fractional_arrival(anchors)

        for point, frac in zip(anchors, arrivals):
            if frac >= 0.98:
                frac = 0.97

            before = max(
                0.0,
                frac - 0.012,
            )

            peak = min(
                0.98,
                max(before + 0.002, frac),
            )

            after = min(
                0.995,
                peak + 0.025,
            )

            if before == 0.0:
                key_times = (
                    f"0;{peak:.4f};"
                    f"{after:.4f};1"
                )
                values = "0.8;0.85;0;0"
            else:
                key_times = (
                    f"0;{before:.4f};"
                    f"{peak:.4f};"
                    f"{after:.4f};1"
                )
                values = "0;0;0.85;0;0"

            parts.append(
                f'<circle '
                f'cx="{point["x"]}" '
                f'cy="{point["y"]}" '
                f'r="7" '
                f'fill="{palette["halo"]}" '
                f'opacity="0">'
                f'<animate '
                f'attributeName="opacity" '
                f'values="{values}" '
                f'keyTimes="{key_times}" '
                f'dur="{DURATION}s" '
                f'repeatCount="indefinite"/>'
                f'</circle>'
            )

    # Footer.
    parts.extend([
        (
            f'<text x="38" y="179" '
            f'fill="{palette["text"]}" '
            f'font-family="Arial,sans-serif" '
            f'font-size="10">'
            f'{total} contributions / last year</text>'
        ),
        (
            f'<text x="{width - 175}" y="179" '
            f'fill="{palette["muted"]}" '
            f'font-family="Arial,sans-serif" '
            f'font-size="10">'
            f'GLACIER BLUE / LIVE SIGNAL</text>'
        ),
        '</svg>',
    ])

    return "\n".join(parts) + "\n"


def main() -> None:
    days = fetch_days()

    OUTPUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    for mode in PALETTES:
        output_file = (
            OUTPUT / f"contributions-{mode}.svg"
        )

        output_file.write_text(
            render(days, mode),
            encoding="utf-8",
        )

        print("Updated", output_file)


if __name__ == "__main__":
    main()
