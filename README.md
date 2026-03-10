# tmux-export

Capture tmux panes as txt, tty, or html. Works over SSH. Built for sharing LLM agent sessions.

## Quick start

```bash
# Interactive — pick session/window/pane
uvx tmux-export

# Direct
uvx tmux-export -s my-session -w 0 -p 0

# Remote
uvx tmux-export user@host -s my-session -w 0 -p 0

# Share via GitHub Gist (requires gh)
uvx tmux-export -s my-session -w 0 -p 0 --host

# Load export into local tmux window
uvx tmux-export --load path/to/export.tty
```

## Options

```
-s, --session NAME    tmux session name
-w, --window N        window index
-p, --pane N          pane index (default 0)
-f, --format FMT      txt,tty,html,all (default: all)
--theme THEME         nvim_dark (default), catppuccin_mocha, dracula,
                      gruvbox_dark, nord, solarized_dark, or gogh:<name>
--scrollback N        lines of scrollback (default: all)
--host [PATH]         upload html to GitHub Gist
--load PATH           replay export in a tmux window
```

## Output

Cached at `~/.cache/tmux-export/<host>/<session>/w<N>p<N>/`:

```
20260310-120000.txt   # plain text
20260310-120000.tty   # ANSI escape codes
20260310-120000.html  # rendered terminal
20260310-120000.toml  # metadata
```
