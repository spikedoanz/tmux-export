"""Color themes for tmux-export HTML output.

Each theme has:
  fg: foreground color
  bg: background color
  cursor: cursor color
  colors: list of 16 ANSI colors (0-15)
    0-7:  normal (black, red, green, yellow, blue, magenta, cyan, white)
    8-15: bright variants
"""

import json
import sys
import urllib.request

BUILTIN_THEMES = {
    "nvim_dark": {
        "fg": "#e0e2ea", "bg": "#14161b", "cursor": "#9b9ea4",
        "colors": [
            "#07080d", "#ffc0b9", "#b3f6c0", "#fce094",
            "#a6dbff", "#ffcaff", "#8cf8f7", "#eef1f8",
            "#4f5258", "#ffc0b9", "#b3f6c0", "#fce094",
            "#a6dbff", "#ffcaff", "#8cf8f7", "#eef1f8",
        ],
    },
    "catppuccin_mocha": {
        "fg": "#cdd6f4", "bg": "#1e1e2e", "cursor": "#f5e0dc",
        "colors": [
            "#45475a", "#f38ba8", "#a6e3a1", "#f9e2af",
            "#89b4fa", "#f5c2e7", "#94e2d5", "#a6adc8",
            "#585b70", "#f37799", "#89d88b", "#ebd391",
            "#74a8fc", "#f2aede", "#6bd7ca", "#bac2de",
        ],
    },
    "dracula": {
        "fg": "#f8f8f2", "bg": "#282a36", "cursor": "#f8f8f2",
        "colors": [
            "#21222c", "#ff5555", "#50fa7b", "#f1fa8c",
            "#bd93f9", "#ff79c6", "#8be9fd", "#f8f8f2",
            "#6272a4", "#ff6e6e", "#69ff94", "#ffffa5",
            "#d6acff", "#ff92df", "#a4ffff", "#ffffff",
        ],
    },
    "gruvbox_dark": {
        "fg": "#ebdbb2", "bg": "#282828", "cursor": "#ebdbb2",
        "colors": [
            "#282828", "#cc241d", "#98971a", "#d79921",
            "#458588", "#b16286", "#689d6a", "#a89984",
            "#928374", "#fb4934", "#b8bb26", "#fabd2f",
            "#83a598", "#d3869b", "#8ec07c", "#ebdbb2",
        ],
    },
    "nord": {
        "fg": "#d8dee9", "bg": "#2e3440", "cursor": "#eceff4",
        "colors": [
            "#3b4252", "#bf616a", "#a3be8c", "#ebcb8b",
            "#81a1c1", "#b48ead", "#88c0d0", "#e5e9f0",
            "#596377", "#bf616a", "#a3be8c", "#ebcb8b",
            "#81a1c1", "#b48ead", "#8fbcbb", "#eceff4",
        ],
    },
    "solarized_dark": {
        "fg": "#9cc2c3", "bg": "#001e27", "cursor": "#f34b00",
        "colors": [
            "#002831", "#d11c24", "#6cbe6c", "#a57706",
            "#2176c7", "#c61c6f", "#259286", "#eae3cb",
            "#006488", "#f5163b", "#51ef84", "#b27e28",
            "#178ec8", "#e24d8e", "#00b39e", "#fcf4dc",
        ],
    },
}

DEFAULT_THEME = "nvim_dark"

GOGH_URL = "https://raw.githubusercontent.com/Gogh-Co/Gogh/master/data/themes.json"


def gogh_to_theme(g):
    """Convert a Gogh JSON theme dict to our format."""
    return {
        "fg": g["foreground"], "bg": g["background"], "cursor": g["cursor"],
        "colors": [g[f"color_{i:02d}"] for i in range(1, 17)],
    }


def fetch_gogh_theme(name):
    """Fetch a theme by name from the Gogh repository."""
    try:
        with urllib.request.urlopen(GOGH_URL, timeout=10) as resp:
            themes = json.loads(resp.read())
    except Exception as e:
        print(f"error fetching Gogh themes: {e}", file=sys.stderr)
        sys.exit(1)
    for t in themes:
        if t["name"].lower() == name.lower():
            return gogh_to_theme(t)
    matches = [t for t in themes if name.lower() in t["name"].lower()]
    if len(matches) == 1:
        return gogh_to_theme(matches[0])
    if matches:
        print(f"ambiguous Gogh theme '{name}', matches:", file=sys.stderr)
        for m in matches[:10]:
            print(f"  {m['name']}", file=sys.stderr)
        sys.exit(1)
    print(f"error: Gogh theme '{name}' not found", file=sys.stderr)
    sys.exit(1)


def resolve_theme(name):
    """Resolve a theme name to a theme dict."""
    if name is None:
        name = DEFAULT_THEME
    if name.startswith("gogh:"):
        return fetch_gogh_theme(name[5:])
    if name in BUILTIN_THEMES:
        return BUILTIN_THEMES[name]
    for k, v in BUILTIN_THEMES.items():
        if k.lower() == name.lower().replace("-", "_").replace(" ", "_"):
            return v
    print(f"error: unknown theme '{name}'", file=sys.stderr)
    print(f"  builtin: {', '.join(BUILTIN_THEMES.keys())}", file=sys.stderr)
    print(f"  or use gogh:<name> for Gogh themes", file=sys.stderr)
    sys.exit(1)


def theme_css(theme):
    """Generate CSS overrides for a color theme."""
    colors = theme["colors"]
    fg, bg = theme["fg"], theme["bg"]
    lines = []
    lines.append(f".body_foreground {{ color: {fg}; }}")
    lines.append(f".body_background {{ background-color: {bg}; }}")
    lines.append(f".inv_foreground {{ color: {bg}; }}")
    lines.append(f".inv_background {{ background-color: {fg}; }}")
    for i in range(8):
        c = colors[i]
        lines.append(f".ansi3{i} {{ color: {c}; }}")
        lines.append(f".inv3{i} {{ background-color: {c}; }}")
        lines.append(f".ansi4{i} {{ background-color: {c}; }}")
        lines.append(f".inv4{i} {{ color: {c}; }}")
    for i in range(8):
        c = colors[8 + i]
        lines.append(f".ansi9{i} {{ color: {c}; }}")
        lines.append(f".inv9{i} {{ background-color: {c}; }}")
        lines.append(f".ansi10{i} {{ background-color: {c}; }}")
        lines.append(f".inv10{i} {{ color: {c}; }}")
    return "\n".join(lines)
