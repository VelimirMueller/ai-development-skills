"""Generate the tool-guide SVG illustrations from small specs (one style for every guide)."""
import json, sys, html, pathlib

W = 720
STYLE = """<style>
.bg{fill:#ffffff}.card{fill:#f6f3fb;stroke:#d9d3e6}.hub{fill:#fbe9fd;stroke:#c64fd6}
.t{font:600 15px system-ui,-apple-system,Segoe UI,sans-serif;fill:#1d1b29}
.s{font:13px system-ui,-apple-system,Segoe UI,sans-serif;fill:#5c5870}
.h{font:700 17px system-ui,-apple-system,Segoe UI,sans-serif;fill:#1d1b29}
.e{font:26px system-ui,'Apple Color Emoji','Segoe UI Emoji',sans-serif}
.ln{stroke:#a59fb8;stroke-width:2;fill:none}.ar{fill:#a59fb8}
.bad{fill:#fdeeee;stroke:#e3a5a5}.ok{fill:#eaf7f0;stroke:#9fd3b7}
.bt{font:700 14px system-ui,sans-serif;fill:#b23a3a}.ot{font:700 14px system-ui,sans-serif;fill:#1c7a52}
@media (prefers-color-scheme:dark){.bg{fill:#17151f}.card{fill:#221f2e;stroke:#3a3550}.hub{fill:#3a1f40;stroke:#c64fd6}
.t,.h{fill:#f1eef8}.s{fill:#b3adc6}.ln{stroke:#6f6888}.ar{fill:#6f6888}
.bad{fill:#3a2124;stroke:#7a3d42}.ok{fill:#1c3329;stroke:#3d7a5c}.bt{fill:#f08c8c}.ot{fill:#7fd6a8}}
</style>
<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="ar" d="M0 0L10 5L0 10z"/></marker></defs>"""

esc = lambda s: html.escape(s, quote=True)


def svg(h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img" '
            f'aria-label="{esc(title)}"><title>{esc(title)}</title>{STYLE}'
            f'<rect class="bg" width="{W}" height="{h}" rx="14"/>{body}</svg>\n')


def text_lines(x, y, lines, cls="s", gap=17, anchor="middle"):
    return "".join(f'<text class="{cls}" x="{x}" y="{y + i * gap}" text-anchor="{anchor}">{esc(l)}</text>'
                   for i, l in enumerate(lines))


def card(x, y, w, h, emoji, label, sub, cls="card"):
    out = f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="12"/>'
    cx = x + w / 2
    out += f'<text class="e" x="{cx}" y="{y + 34}" text-anchor="middle">{emoji}</text>'
    out += f'<text class="t" x="{cx}" y="{y + 58}" text-anchor="middle">{esc(label)}</text>'
    out += text_lines(cx, y + 78, sub if isinstance(sub, list) else [sub])
    return out


def hub(spec):
    """A tool in the middle, its parts around it."""
    parts = spec["parts"]
    cols, cw, ch, gx = 4, 160, 112, 16
    rows = (len(parts) + cols - 1) // cols
    top = 54
    body = f'<text class="h" x="24" y="34">{esc(spec["title"])}</text>'
    hub_y = top + ch + 20 if rows > 1 else top
    split = cols if rows > 1 else 0
    ys = []
    for i, p in enumerate(parts):
        r = 0 if i < split else 1
        idx = i if r == 0 else i - split
        n = split if r == 0 else len(parts) - split
        x0 = (W - (n * cw + (n - 1) * gx)) / 2
        y = top if r == 0 else hub_y + 80
        ys.append((x0 + idx * (cw + gx) + cw / 2, y, r))
        body += card(x0 + idx * (cw + gx), y, cw, ch, *p)
    hx, hw = W / 2 - 110, 220
    for cx, y, r in ys:
        y1 = y + ch if r == 0 else y
        y2 = hub_y + 20 if r == 0 else hub_y + 60
        body += f'<line class="ln" x1="{cx}" y1="{y1}" x2="{W / 2}" y2="{y2}"/>'
    body += f'<rect class="hub" x="{hx}" y="{hub_y + 20}" width="{hw}" height="40" rx="20"/>'
    body += f'<text class="h" x="{W / 2}" y="{hub_y + 46}" text-anchor="middle">{esc(spec["center"])}</text>'
    h = hub_y + 80 + ch + 24 if rows > 1 else hub_y + 84
    return svg(h, body, spec["title"])


def flow(spec):
    """Steps left to right (wraps to a second row), arrows labelled."""
    steps, per = spec["steps"], 4
    cw, ch, gx = 150, 120, 30
    body = f'<text class="h" x="24" y="34">{esc(spec["title"])}</text>'
    y, rows = 56, [steps[i:i + per] for i in range(0, len(steps), per)]
    for r, row in enumerate(rows):
        x0 = (W - (len(row) * cw + (len(row) - 1) * gx)) / 2
        for i, s in enumerate(row):
            x = x0 + i * (cw + gx)
            body += card(x, y, cw, ch, s[0], s[1], s[2])
            if i < len(row) - 1:
                body += f'<line class="ln" x1="{x + cw + 2}" y1="{y + ch / 2}" x2="{x + cw + gx - 2}" y2="{y + ch / 2}" marker-end="url(#a)"/>'
        if r < len(rows) - 1:
            lx = x0 + (len(row) - 1) * (cw + gx) + cw / 2
            nx = (W - (len(rows[r + 1]) * cw + (len(rows[r + 1]) - 1) * gx)) / 2 + cw / 2
            body += (f'<path class="ln" d="M{lx} {y + ch + 2} V{y + ch + 18} H{nx} V{y + ch + 36}" marker-end="url(#a)"/>')
        y += ch + 40
    y -= 22
    if spec.get("note"):
        body += text_lines(W / 2, y + 10, [spec["note"]])
        y += 24
    return svg(y + 4, body, spec["title"])


def before_after(spec):
    """Two panels: life without the tool, life with it."""
    b, a = spec["before"], spec["after"]
    n = max(len(b), len(a))
    h = 90 + n * 30 + 24
    pw = (W - 72) / 2
    body = f'<text class="h" x="24" y="34">{esc(spec["title"])}</text>'
    for i, (cls, tcls, head, items, mark) in enumerate(
            [("bad", "bt", "😩  Before", b, "✗"), ("ok", "ot", "😌  After", a, "✓")]):
        x = 24 + i * (pw + 24)
        body += f'<rect class="{cls}" x="{x}" y="50" width="{pw}" height="{h - 74}" rx="12"/>'
        body += f'<text class="{tcls}" x="{x + 16}" y="76">{esc(head)}</text>'
        for j, it in enumerate(items):
            body += f'<text class="{tcls}" x="{x + 16}" y="{106 + j * 30}">{mark}</text>'
            body += f'<text class="s" x="{x + 36}" y="{106 + j * 30}">{esc(it)}</text>'
    body += f'<text class="e" x="{W / 2}" y="{50 + (h - 74) / 2 + 9}" text-anchor="middle">➜</text>'
    return svg(h, body, spec["title"])


KINDS = {"hub": hub, "flow": flow, "before_after": before_after}

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python3 gen_svg.py <specs.json> <output-dir>")
    specs = json.loads(pathlib.Path(sys.argv[1]).read_text())
    out = pathlib.Path(sys.argv[2])
    for name, spec in specs.items():
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(KINDS[spec["kind"]](spec))
        print("wrote", p)
