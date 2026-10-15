"""SVG rendering of actual finite geometry; no scripts or model-generated HTML."""

from worldguard.contracts import scene_from, task_from


def scene_svg(before, after, task, original, recovery=None, audit=None):
    before, after, task = scene_from(before), scene_from(after), task_from(task)
    scale = 75
    ox, oy = after.origin_xy_m
    width, height = after.width * after.resolution_m * scale, after.height * after.resolution_m * scale

    def xy(p):
        return ((p[0] - ox) * scale, height - (p[1] - oy) * scale)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-20 -20 {width + 40} {height + 40}" role="img" aria-label="Navigation geometry">',
        f'<rect width="{width}" height="{height}" fill="#f5f7fa" stroke="#738095"/>',
    ]
    old = set(before.occupied)
    res = after.resolution_m * scale
    for row, col in after.occupied:
        color = "#29374b" if (row, col) in old else "#d94c4c"
        parts.append(
            f'<rect x="{col * res}" y="{height - (row + 1) * res}" width="{res}" height="{res}" fill="{color}"/>'
        )
    for plan, color, dash in ((original, "#c36a00", 'stroke-dasharray="7 4"'), (recovery, "#007c83", "")):
        if plan and plan["path"]:
            points = " ".join(f"{x},{y}" for x, y in map(xy, plan["path"]))
            parts.append(
                f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3" {dash}/>'
            )
    if audit:
        for violation in audit["violations"]:
            if "segment_xy_m" in violation:
                points = " ".join(f"{x},{y}" for x, y in map(xy, violation["segment_xy_m"]))
                parts.append(f'<polyline points="{points}" fill="none" stroke="#bc1682" stroke-width="5"/>')
    for label, p in (("S", task.start_xy_m), ("G", task.goal_xy_m)):
        x, y = xy(p)
        parts.extend(
            [
                f'<circle cx="{x}" cy="{y}" r="{task.robot.effective_radius * scale}" fill="none" stroke="#263852" stroke-dasharray="2 2"/>',
                f'<circle cx="{x}" cy="{y}" r="5" fill="#263852"/>',
                f'<text x="{x + 8}" y="{y - 10}" font-size="15" fill="#263852">{label}</text>',
            ]
        )
    parts.append("</svg>")
    return "".join(parts)
