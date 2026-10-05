"""Write the README's SVG art: feature icons and the animated how-it-works
diagram (SMIL, so it animates inside GitHub's <img> rendering).

Run:  python tools/readme_svgs.py
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "readme"

# Feather-style glyphs (MIT), drawn on a 24px grid
GLYPHS = {
    "host": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
            '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "cloud": '<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/>',
    "backup": '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>'
              '<polyline points="12 7 12 12 15 14"/>',
    "invite": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
              '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "live": '<circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 0 1 0 8.49"/>'
            '<path d="M7.76 16.24a6 6 0 0 1 0-8.49"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>'
            '<path d="M4.93 19.07a10 10 0 0 1 0-14.14"/>',
    "update": '<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>',
    "palette": '<circle cx="13.5" cy="6.5" r="1.5"/><circle cx="17.5" cy="10.5" r="1.5"/>'
               '<circle cx="8.5" cy="7.5" r="1.5"/><circle cx="6.5" cy="12.5" r="1.5"/>'
               '<path d="M12 2a10 10 0 0 0 0 20c1.1 0 2-.9 2-2 0-.5-.2-1-.5-1.3-.3-.4-.5-.8-.5-1.3 '
               '0-1.1.9-2 2-2h2.4A5.6 5.6 0 0 0 22 10c0-4.4-4.5-8-10-8z"/>',
    "open": '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78'
            'l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>',
}
COLORS = {
    "host": ("#7A9BFF", "#5CD6C9"), "cloud": ("#5CD6C9", "#7A9BFF"), "shield": ("#55D6B4", "#3ECF8E"),
    "backup": ("#F2B66B", "#E8A23D"), "invite": ("#B88CFF", "#7A9BFF"), "live": ("#E33A55", "#FF8466"),
    "update": ("#4DBBFF", "#5CD6C9"), "palette": ("#FFD447", "#FF8F4A"), "open": ("#FF6B8A", "#B88CFF"),
}


def icon(name: str) -> str:
    a, b = COLORS[name]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="0 0 72 72">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{a}" stop-opacity="0.28"/>
      <stop offset="1" stop-color="{b}" stop-opacity="0.10"/>
    </linearGradient>
    <linearGradient id="st" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/>
    </linearGradient>
  </defs>
  <rect x="1" y="1" width="70" height="70" rx="20" fill="#0B0F1E"/>
  <rect x="1" y="1" width="70" height="70" rx="20" fill="url(#bg)" stroke="{a}" stroke-opacity="0.45" stroke-width="1.5"/>
  <g transform="translate(18 18) scale(1.5)" fill="none" stroke="url(#st)" stroke-width="1.9"
     stroke-linecap="round" stroke-linejoin="round">{GLYPHS[name]}</g>
</svg>
'''


FRIENDS = [("You", "#7A9BFF", 120, 70), ("Bram", "#F2B66B", 780, 70),
           ("Kim", "#B78AF7", 780, 290), ("Elise", "#5CD6C9", 120, 290)]


def diagram() -> str:
    cx, cy = 450, 180
    dur = 8  # seconds for the full loop
    # orb route: You -> cloud -> Bram -> cloud -> Kim -> cloud -> Elise -> cloud -> You
    pts = []
    for _, _, x, y in FRIENDS:
        pts += [(x, y), (cx, cy)]
    path = "M " + " L ".join(f"{x} {y}" for x, y in pts) + f" L {FRIENDS[0][2]} {FRIENDS[0][3]}"
    nodes = []
    for i, (name, color, x, y) in enumerate(FRIENDS):
        # each friend glows during their quarter of the loop
        k0, k1 = i / 4, (i + 1) / 4
        keys = "0;" + ";".join(f"{v:.3f}" for v in (k0, min(k0 + 0.02, 1), max(k1 - 0.02, 0), k1)) + ";1"
        vals = "0.25;0.25;1;1;0.25;0.25" if i else "1;1;1;1;0.25;1"
        if i:
            keys = f"0;{k0:.3f};{k0 + 0.02:.3f};{k1 - 0.02:.3f};{k1:.3f};1"
        else:
            keys = f"0;{k1 - 0.02:.3f};{k1:.3f};0.98;1"
            vals = "1;1;0.25;0.25;1"
        day = ["Mon", "Tue", "Thu", "Sat"][i]
        nodes.append(f'''
  <g>
    <circle cx="{x}" cy="{y}" r="44" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="3">
      <animate attributeName="fill-opacity" values="{vals.replace('1', '0.35').replace('0.25', '0.08')}" keyTimes="{keys}" dur="{dur}s" repeatCount="indefinite"/>
    </circle>
    <circle cx="{x}" cy="{y}" r="58" fill="none" stroke="{color}" stroke-width="2" opacity="0">
      <animate attributeName="opacity" values="{vals.replace('0.25', '0')}" keyTimes="{keys}" dur="{dur}s" repeatCount="indefinite"/>
    </circle>
    <text x="{x}" y="{y + 8}" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="22" font-weight="700" fill="#FFFFFF">{name}</text>
    <text x="{x}" y="{y + 82}" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="17" fill="{color}">{day}: hosts
      <animate attributeName="opacity" values="{vals.replace('0.25', '0.2')}" keyTimes="{keys}" dur="{dur}s" repeatCount="indefinite"/>
    </text>
  </g>''')
    lines = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{x}" y2="{y}" stroke="#7A9BFF" stroke-opacity="0.35" stroke-width="2.5" stroke-dasharray="8 10">'
        f'<animate attributeName="stroke-dashoffset" from="0" to="-36" dur="1.2s" repeatCount="indefinite"/></line>'
        for _, _, x, y in FRIENDS)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="400" viewBox="0 0 900 400">
  <defs>
    <radialGradient id="bg" cx="50%" cy="50%" r="70%">
      <stop offset="0" stop-color="#18204A"/><stop offset="1" stop-color="#0A0C16"/>
    </radialGradient>
    <radialGradient id="orb" cx="35%" cy="30%" r="70%">
      <stop offset="0" stop-color="#E8FFF4"/><stop offset="0.4" stop-color="#55D6B4"/><stop offset="1" stop-color="#1E6B5A"/>
    </radialGradient>
    <filter id="glow" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect width="900" height="400" rx="24" fill="url(#bg)"/>
  {lines}
  <g transform="translate({cx - 70} {cy - 60})">
    <svg width="140" height="100" viewBox="0 0 24 24" fill="rgba(122,155,255,0.22)" stroke="#CFE0FF" stroke-width="1.1">
      <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>
    </svg>
  </g>
  <text x="{cx}" y="{cy + 66}" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="17" fill="#AFC0D6">your shared cloud folder</text>
  {"".join(nodes)}
  <circle r="17" fill="url(#orb)" filter="url(#glow)">
    <animateMotion dur="{dur}s" repeatCount="indefinite" path="{path}" keyPoints="0;1" keyTimes="0;1" calcMode="linear"/>
  </circle>
  <text x="450" y="40" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="22" font-weight="700" fill="#FFFFFF">One world. Whoever's online hosts.</text>
</svg>
'''


def main():
    (OUT / "icons").mkdir(parents=True, exist_ok=True)
    for name in GLYPHS:
        (OUT / "icons" / f"{name}.svg").write_text(icon(name), encoding="utf-8")
    (OUT / "how-it-works.svg").write_text(diagram(), encoding="utf-8")
    print("wrote", len(GLYPHS), "icons + diagram")


if __name__ == "__main__":
    main()
