# Kitty Selection Fix - Implementation Session

I'm forking Kitty terminal to fix a 7-year-old issue: **selection gets cleared when new terminal output arrives**.

## The Problem
When you select text in Kitty and new output appears (like from `tail -f` or a build), the selection disappears. VSCode/VSCodium terminal (xterm.js) doesn't have this problem.

## The Fix
See `PLAN.md` in this directory for the full plan. TL;DR:

**Phase 1 (start here):** Modify `clear_intersecting_selections()` in `kitty/screen.c` to preserve selection when user has scrolled back into history. The key insight: if `start_scrolled_by > 0` or `end_scrolled_by > 0`, the selection is in scrollback and shouldn't be cleared by new output.

**Phase 2 (if needed):** Implement absolute buffer coordinates like xterm.js does.

## First Steps
1. Clone: `git clone https://github.com/kovidgoyal/kitty.git .`
2. Build: `./dev.sh build`
3. Find `clear_intersecting_selections()` in `kitty/screen.c` (~line 716)
4. Implement the fix
5. Test: run `while true; do date; sleep 0.1; done`, select text, verify it persists

## Key References
- `kitty/screen.c` - main selection logic
- `kitty/screen.h` - SelectionBoundary and Selection structs
- xterm.js SelectionModel.ts - reference implementation that works

Let's fix this properly.
