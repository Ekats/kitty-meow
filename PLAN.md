# Kitty Fork: Persistent Selection Fix

> **Chosen Approach:** Incremental implementation - Start with Phase 1 minimal fix, add Phase 2 if needed.

---

## Problem Statement

Kitty clears text selection whenever new terminal output arrives on any line that intersects the selection. This makes it impossible to copy text from log tails, build output, or any continuously updating terminal.

**xterm.js (VSCode/VSCodium terminal) solved this in 2017.** Kitty maintainer rejected the fix in [issue #148](https://github.com/kovidgoyal/kitty/issues/148) citing "performance" concerns, but xterm.js proves it's viable.

---

## Root Cause Analysis

### Current Kitty Behavior

**File:** `kitty/screen.c`

The problem is in `init_text_loop_line()` (line ~748):

```c
static void
init_text_loop_line(Screen *self, text_loop_state *s) {
    linebuf_init_cells(self->linebuf, self->cursor->y, &s->cp, &s->gp);
    clear_intersecting_selections(self, self->cursor->y);  // <-- THE PROBLEM
    linebuf_mark_line_dirty(self->linebuf, self->cursor->y);
    // ...
}
```

This is called **every time** new text is written. It checks if the cursor's current line intersects any selection and clears the ENTIRE selection if it does.

### Current Selection Coordinate System

```c
typedef struct {
    unsigned int x, y;
    bool in_left_half_of_cell;
} SelectionBoundary;

typedef struct {
    SelectionBoundary start, end;
    unsigned int start_scrolled_by, end_scrolled_by;  // Scroll offsets
    // ...
} Selection;
```

Kitty already has `scrolled_by` offsets, but the clearing logic ignores context - it clears on ANY intersection.

---

## Solution: xterm.js Approach

### How xterm.js Does It

1. **Absolute Buffer Coordinates**: Selection stored as absolute buffer positions, not viewport-relative
2. **Trim Handler**: When circular buffer wraps, adjust selection coords by trim amount
3. **Deferred Rendering**: Queue selection refresh on animation frame
4. **Smart Clearing**: Only clear if the selected TEXT ITSELF is modified, not just the line

### Key xterm.js Code

```typescript
// SelectionModel.ts - Trim handling
public handleTrim(amount: number): boolean {
    if (this.selectionStart) {
        this.selectionStart[1] -= amount;  // Adjust Y coordinate
    }
    if (this.selectionEnd) {
        this.selectionEnd[1] -= amount;
    }
    // Only clear if selection scrolled completely out
    if (this.selectionEnd && this.selectionEnd[1] < 0) {
        this.clearSelection();
        return true;
    }
    return false;
}
```

---

## Implementation Plan

### Phase 1: Minimal Fix (Low Risk)

**Goal:** Stop clearing selection when output arrives OUTSIDE the selected region.

**File:** `kitty/screen.c`

**Change:** Modify `clear_intersecting_selections()` to be smarter:

```c
static void
clear_intersecting_selections(Screen *self, index_type y) {
    // NEW: Only clear if the line being modified is WITHIN the selection
    // AND the selection is in the visible viewport (not scrolled back)

    for (size_t i = 0; i < self->selections.count; i++) {
        Selection *s = &self->selections.items[i];

        // Calculate if user has scrolled back
        bool selection_in_scrollback = (s->start_scrolled_by > 0 || s->end_scrolled_by > 0);

        // If selection is in scrollback (user scrolled up), preserve it
        if (selection_in_scrollback) {
            continue;  // Don't clear - selection is in history
        }

        // Only clear if line y is actually within the selection bounds
        if (selection_has_screen_line(&self->selections, y)) {
            clear_selection(&self->selections);
        }
    }
    // Same logic for url_ranges...
}
```

**Risk:** Low - only changes clearing behavior, not coordinate system.

### Phase 2: Absolute Coordinates (Medium Risk)

**Goal:** Store selection in absolute buffer space like xterm.js.

**Changes:**

1. **Modify SelectionBoundary** to use absolute buffer Y:
```c
typedef struct {
    unsigned int x;
    int y_absolute;  // Absolute position in buffer (can be negative for trimmed)
    bool in_left_half_of_cell;
} SelectionBoundary;
```

2. **Add trim handler** called when historybuf wraps:
```c
static void
selection_handle_trim(Selections *selections, unsigned int amount) {
    for (size_t i = 0; i < selections->count; i++) {
        Selection *s = &selections->items[i];
        s->start.y_absolute -= amount;
        s->end.y_absolute -= amount;

        // Clear if completely trimmed
        if (s->end.y_absolute < 0) {
            // Remove this selection
        }
    }
}
```

3. **Hook into INDEX_UP macro** to call trim handler.

4. **Update rendering** to convert absolute coords to viewport coords.

### Phase 3: Testing & Edge Cases

1. **Test scrollback selection**: Select text, scroll down, new output arrives - selection should persist
2. **Test buffer wrap**: Fill scrollback completely, selection should adjust or clear gracefully
3. **Test selection across scroll boundary**: Selection spanning history and visible area
4. **Test rapid output**: `yes | head -1000` while selecting shouldn't crash
5. **Test multi-selection**: Multiple selections shouldn't interfere

---

## Files to Modify

| File | Changes |
|------|---------|
| `kitty/screen.c` | Main selection logic, clearing behavior, trim handler |
| `kitty/screen.h` | SelectionBoundary struct if using absolute coords |
| `kitty/window.py` | May need updates for Python bindings |
| `kitty_tests/` | Add tests for persistent selection |

---

## Build & Test Workflow

```bash
# Clone fork
cd ~/Repos/kitty-selection-fix
git clone https://github.com/kovidgoyal/kitty.git .
git remote add upstream https://github.com/kovidgoyal/kitty.git

# Build
./dev.sh build

# Test
./test.py

# Run development version
./kitty/launcher/kitty

# Test selection persistence
# Terminal 1: ./kitty/launcher/kitty
# Run: while true; do date; sleep 0.1; done
# Select some text, watch if it persists
```

---

## Milestones

### Milestone 1: Proof of Concept
- [ ] Fork and build Kitty successfully
- [ ] Locate exact code paths (verified by agents above)
- [ ] Implement Phase 1 minimal fix
- [ ] Manual testing passes

### Milestone 2: Robust Implementation
- [ ] Implement Phase 2 absolute coordinates (if Phase 1 insufficient)
- [ ] Add trim handler for buffer wrap
- [ ] Write unit tests
- [ ] Test edge cases

### Milestone 3: Release
- [ ] Clean up code, add comments
- [ ] Update documentation
- [ ] Create GitHub release
- [ ] Optionally submit PR upstream (likely rejected, but worth trying)

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Phase 1 breaks edge cases | Medium | Extensive manual testing |
| Phase 2 coordinate changes cascade | High | Incremental changes, git bisect |
| Upstream rejects PR | Very High | Maintain fork independently |
| Performance regression | Low | xterm.js proves it's viable |
| Merge conflicts with upstream | Medium | Regular rebasing |

---

## Success Criteria

1. Select text in terminal
2. Run `while true; do echo "new output"; sleep 0.1; done`
3. Selection persists until user explicitly clears it
4. No crashes or visual glitches
5. Performance comparable to upstream

---

## References

- [Kitty Issue #148](https://github.com/kovidgoyal/kitty/issues/148) - Original feature request (rejected)
- [xterm.js PR #670](https://github.com/xtermjs/xterm.js/pull/670) - Successful implementation
- [Windows Terminal PR #6062](https://github.com/microsoft/terminal/pull/6062) - Another successful implementation
- [xterm.js SelectionModel.ts](https://github.com/xtermjs/xterm.js/blob/master/src/browser/selection/SelectionModel.ts) - Reference implementation
