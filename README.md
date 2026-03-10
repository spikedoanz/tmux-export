# tmux-export

Capture tmux pane content and export as txt, tty (ANSI), or html. Works locally and over SSH. Built for sharing LLM agent terminal sessions.

## Install

```
uvx tmux-export
```

## Usage

```bash
# Interactive — pick session/window/pane
tmux-export
tmux-export user@remote-host

# Direct
tmux-export -s my-session -w 0 -p 0
tmux-export user@host -s my-session -w 0 -p 0

# URI style
tmux-export host:/tmux/my-session/0/0

# Export only specific formats
tmux-export -s my-session -w 0 -p 0 -f txt,tty

# Limit scrollback
tmux-export -s my-session -w 0 -p 0 --scrollback 500

# Share via GitHub Gist (requires gh CLI)
tmux-export -s my-session -w 0 -p 0 --host

# Load an export into a local tmux window
tmux-export --load ~/.cache/tmux-export/local/my-session/w0p0/20260310-120000.tty
```

## Output

Exports are cached at `~/.cache/tmux-export/<host>/<session>/w<N>p<N>/`:

- `.txt` — plain text
- `.tty` — with ANSI escape codes (colors, attributes)
- `.html` — rendered terminal view
- `.toml` — metadata (hostname, dimensions, timestamp, command)

## Requirements

- Python 3.10+
- `tmux` on the target machine
- `gh` CLI (optional, for `--host`)
- `ssh` (optional, for remote capture)
