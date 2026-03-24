from kitty.fast_data_types import Screen, add_timer, get_options, GLFW_MOUSE_BUTTON_LEFT, GLFW_RELEASE, set_tab_bar_extra_line
from kitty.tab_bar import DrawData, ExtraData, TabBarData, as_rgb, draw_title
from kitty.utils import color_as_int

# Hardcoded Breath theme colors (hex to RGB int)
BG_COLOR = as_rgb(0x222222)  # dark gray
ACTIVE_BG = as_rgb(0x17a88b)  # #17a88b teal
ACTIVE_FG = as_rgb(0x1e2229)  # #1e2229
INACTIVE_BG = as_rgb(0x2e3440)  # #2e3440
INACTIVE_FG = as_rgb(0x7f8c8d)  # #7f8c8d
PLUS_BG = as_rgb(0x2e3440)  # same as inactive
PLUS_FG = as_rgb(0x7f8c8d)  # light gray
BORDER_COLOR = as_rgb(0x7f8c8d)  # light gray border
CLOSE_BG_ACTIVE = as_rgb(0x0d7a64)  # darker manjaro green
CLOSE_BG_INACTIVE = as_rgb(0x151515)  # near black
CLOSE_FG = as_rgb(0xffffff)  # white x
SPLIT_BG = as_rgb(0x1a1a2e)  # dark blue-ish
SPLIT_FG = as_rgb(0x4fc3f7)  # light blue for split icons

# Layout constants
MIN_TAB_WIDTH = 10
MAX_TAB_WIDTH = 25
BUTTONS_WIDTH = 9  # + button (3) + split buttons (6)

# Track button positions (cell coordinates)
plus_button_start = 0
plus_button_end = 0
hsplit_button_start = 0
hsplit_button_end = 0
vsplit_button_start = 0
vsplit_button_end = 0
close_buttons = {}  # tab_id -> (start, end)

# Row 2 overflow tracking
_overflow_tabs = []  # list of (tab_id, is_active, title) for tabs on row 2
_overflow_buttons = {}  # tab_id -> (start, end) whole tab area on row 2
_overflow_close_buttons = {}  # tab_id -> (start, end) close button on row 2
_main_tab_count = 0
_last_num_tabs = 1
_has_overflow = False  # tracks if 2nd row is active
_current_os_window_id = 0  # set by patched TabBar.update
_current_tab_manager = None  # set by patched TabBar.update


def _compute_main_tab_count(num_tabs, columns):
    """Compute how many tabs fit as full-width main tabs on row 1."""
    available = columns - BUTTONS_WIDTH
    # Estimate per-tab width: MIN_TAB_WIDTH + close button (3) + separator (1)
    avg_tab_width = MIN_TAB_WIDTH + 4
    return max(1, available // avg_tab_width)


def draw_tab(
    draw_data: DrawData,
    screen: Screen,
    tab: TabBarData,
    before: int,
    max_tab_length: int,
    index: int,
    is_last: bool,
    extra_data: ExtraData,
) -> int:
    global _main_tab_count, _last_num_tabs
    global close_buttons, _overflow_tabs, _overflow_buttons, _overflow_close_buttons
    global plus_button_start, plus_button_end
    global hsplit_button_start, hsplit_button_end, vsplit_button_start, vsplit_button_end

    # === Layout pass ===
    if extra_data.for_layout:
        if is_last:
            _last_num_tabs = index
        num_tabs_estimate = max(_last_num_tabs, index)
        main_count = _compute_main_tab_count(num_tabs_estimate, screen.columns)
        if is_last:
            _main_tab_count = main_count
        # Overflow tabs report minimal width (kitty skips them on row 1)
        if index > main_count:
            screen.cursor.x = 1
        else:
            screen.cursor.x = min(len(tab.title) + 5, MAX_TAB_WIDTH)
        return screen.cursor.x

    # === Draw pass ===
    if index == 1:
        close_buttons = {}
        _overflow_tabs = []
        _overflow_buttons = {}
        _overflow_close_buttons = {}
        # Clear row 2 if it exists
        if screen.lines > 1:
            screen.cursor.y = 1
            screen.cursor.x = 0
            screen.cursor.bg = BG_COLOR
            screen.cursor.fg = 0
            screen.draw(' ' * screen.columns)
        # Back to row 1
        screen.cursor.y = 0
        screen.cursor.x = 0

    # Overflow tab — collect for row 2, don't draw on row 1
    if index > _main_tab_count:
        _overflow_tabs.append((tab.tab_id, tab.is_active, tab.title))
        if is_last:
            return _draw_end_section(screen)
        return before

    # === Draw main tab on row 1 ===

    # Fill background before first tab
    if index == 1 and before > 0:
        screen.cursor.bg = BG_COLOR
        screen.draw(' ' * before)

    # Separator
    if index > 1:
        screen.cursor.bg = BG_COLOR
        screen.cursor.fg = BORDER_COLOR
        screen.draw('|')

    # Tab colors
    if tab.is_active:
        screen.cursor.bg = ACTIVE_BG
        screen.cursor.fg = ACTIVE_FG
    else:
        screen.cursor.bg = INACTIVE_BG
        screen.cursor.fg = INACTIVE_FG

    # Tab title with min/max width and centering
    title = tab.title
    max_title = MAX_TAB_WIDTH - 5  # space for ' title ' + ' x '
    if len(title) > max_title:
        title = title[:max_title - 1] + '\u2026'

    tab_text = f' {title} '
    if len(tab_text) < MIN_TAB_WIDTH:
        pad = MIN_TAB_WIDTH - len(tab_text)
        left_pad = pad // 2
        right_pad = pad - left_pad
        tab_text = ' ' * left_pad + tab_text + ' ' * right_pad
    screen.draw(tab_text)

    # Close button
    close_start = screen.cursor.x
    screen.cursor.bg = CLOSE_BG_ACTIVE if tab.is_active else CLOSE_BG_INACTIVE
    screen.cursor.fg = CLOSE_FG
    screen.draw(' \u00d7 ')
    close_buttons[tab.tab_id] = (close_start, screen.cursor.x)

    end = screen.cursor.x

    if is_last:
        end = _draw_end_section(screen)

    return end


def _draw_end_section(screen):
    global plus_button_start, plus_button_end
    global hsplit_button_start, hsplit_button_end, vsplit_button_start, vsplit_button_end
    global _overflow_buttons, _overflow_close_buttons, _has_overflow

    # === Row 1: + button, fill, split buttons ===
    plus_button_start = screen.cursor.x
    screen.cursor.bg = PLUS_BG
    screen.cursor.fg = PLUS_FG
    screen.draw(' + ')
    plus_button_end = screen.cursor.x

    # Fill to split buttons
    split_buttons_width = 6
    split_buttons_start = screen.columns - split_buttons_width

    screen.cursor.bg = BG_COLOR
    screen.cursor.fg = 0
    fill_width = split_buttons_start - screen.cursor.x
    if fill_width > 0:
        screen.draw(' ' * fill_width)

    # Split buttons
    hsplit_button_start = screen.cursor.x
    screen.cursor.bg = SPLIT_BG
    screen.cursor.fg = SPLIT_FG
    screen.draw(' \u25a4 ')
    hsplit_button_end = screen.cursor.x

    vsplit_button_start = screen.cursor.x
    screen.cursor.bg = SPLIT_BG
    screen.cursor.fg = SPLIT_FG
    screen.draw(' \U000f0bcc ')
    vsplit_button_end = screen.cursor.x

    # === Dynamic row 2: toggle based on overflow ===
    needs_overflow = len(_overflow_tabs) > 0
    if needs_overflow != _has_overflow:
        _has_overflow = needs_overflow
        if _current_os_window_id:
            set_tab_bar_extra_line(_current_os_window_id, needs_overflow)
            # Schedule resize like a real window resize does — this calls
            # layout_tab_bar() which re-reads geometry and resizes the screen
            if _current_tab_manager is not None:
                add_timer(lambda timer_id: _current_tab_manager.resize(), 0.0, False)

    # Draw row 2 overflow tabs if screen has 2 lines
    if _overflow_tabs and screen.lines > 1:
        screen.cursor.y = 1
        screen.cursor.x = 0

        for i, (tab_id, is_active, title) in enumerate(_overflow_tabs):
            if screen.cursor.x >= screen.columns - 2:
                break

            # Separator between overflow tabs
            if i > 0:
                screen.cursor.bg = BG_COLOR
                screen.cursor.fg = BORDER_COLOR
                screen.draw('|')

            # Same colors as row 1 tabs
            if is_active:
                screen.cursor.bg = ACTIVE_BG
                screen.cursor.fg = ACTIVE_FG
            else:
                screen.cursor.bg = INACTIVE_BG
                screen.cursor.fg = INACTIVE_FG

            # Same title rendering as row 1
            max_title = MAX_TAB_WIDTH - 5
            if len(title) > max_title:
                title = title[:max_title - 1] + '\u2026'

            tab_text = f' {title} '
            if len(tab_text) < MIN_TAB_WIDTH:
                pad = MIN_TAB_WIDTH - len(tab_text)
                left_pad = pad // 2
                right_pad = pad - left_pad
                tab_text = ' ' * left_pad + tab_text + ' ' * right_pad

            if screen.cursor.x + len(tab_text) + 3 > screen.columns:
                break

            start = screen.cursor.x
            screen.draw(tab_text)

            # Close button
            close_start = screen.cursor.x
            close_bg = CLOSE_BG_ACTIVE if is_active else CLOSE_BG_INACTIVE
            screen.cursor.bg = close_bg
            screen.cursor.fg = CLOSE_FG
            screen.draw(' \u00d7 ')
            _overflow_buttons[tab_id] = (start, screen.cursor.x)
            _overflow_close_buttons[tab_id] = (close_start, screen.cursor.x)

        # Fill rest of row 2
        screen.cursor.bg = BG_COLOR
        screen.cursor.fg = 0
        remaining = screen.columns - screen.cursor.x
        if remaining > 0:
            screen.draw(' ' * remaining)

        # Move cursor back to row 1 end
        screen.cursor.y = 0
        screen.cursor.x = screen.columns

    return screen.columns


# Monkey patch TabManager and TabBar to handle button clicks and track os_window_id
def _patch_tab_manager():
    from kitty.tabs import TabManager
    from kitty.tab_bar import TabBar
    from kitty.boss import get_boss

    # Patch TabBar.update to store os_window_id and TabManager ref
    original_update = TabBar.update

    def patched_update(self, data):
        global _current_os_window_id, _current_tab_manager
        _current_os_window_id = self.os_window_id
        # Find the TabManager that owns this TabBar
        boss = get_boss()
        if boss:
            _current_tab_manager = boss.os_window_map.get(self.os_window_id)
        return original_update(self, data)

    TabBar.update = patched_update

    # Patch TabManager.handle_click_on_tab for button click handling
    original_handle_click = TabManager.handle_click_on_tab

    def patched_handle_click(self, x: int, y: int = 0, button: int = 0, modifiers: int = 0, action: int = 0) -> None:
        if self.tab_bar.laid_out_once:
            cell_x = (x - self.tab_bar.window_geometry.left) // self.tab_bar.cell_width
            # Determine which row was clicked using actual screen line count
            tab_bar_top = self.tab_bar.window_geometry.top
            tab_bar_bottom = self.tab_bar.window_geometry.bottom
            num_lines = self.tab_bar.screen.lines
            cell_height = (tab_bar_bottom - tab_bar_top) // num_lines if num_lines > 0 else (tab_bar_bottom - tab_bar_top)
            row = 0
            if num_lines > 1 and cell_height > 0:
                row = min(num_lines - 1, (y - tab_bar_top) // cell_height)

            # Row 2 is entirely custom — swallow ALL events to prevent
            # original handler from interpreting them as row 1 clicks
            if row == 1:
                if button == GLFW_MOUSE_BUTTON_LEFT and action == GLFW_RELEASE:
                    # Check close buttons first, then tab body
                    for tab_id, (start, end) in _overflow_close_buttons.items():
                        if start <= cell_x < end:
                            tab = self.tab_for_id(tab_id)
                            if tab is not None:
                                self.remove(tab)
                            return

                    for tab_id, (start, end) in _overflow_buttons.items():
                        if start <= cell_x < end:
                            tab = self.tab_for_id(tab_id)
                            if tab is not None:
                                self.set_active_tab(tab)
                            return
                return  # Swallow press/drag/etc on row 2

            if button == GLFW_MOUSE_BUTTON_LEFT and action == GLFW_RELEASE:
                # Row 1: + button, split buttons, close buttons
                if plus_button_start <= cell_x < plus_button_end:
                    self.new_tab()
                    return

                if hsplit_button_start <= cell_x < hsplit_button_end:
                    boss = get_boss()
                    if boss and boss.active_window:
                        boss.call_remote_control(boss.active_window, ('goto-layout', 'splits'))
                        boss.call_remote_control(
                            boss.active_window,
                            ('launch', '--location=hsplit', '--cwd=current')
                        )
                    return

                if vsplit_button_start <= cell_x < vsplit_button_end:
                    boss = get_boss()
                    if boss and boss.active_window:
                        boss.call_remote_control(boss.active_window, ('goto-layout', 'splits'))
                        boss.call_remote_control(
                            boss.active_window,
                            ('launch', '--location=vsplit', '--cwd=current')
                        )
                    return

                # Close buttons (row 1)
                for tab_id, (start, end) in close_buttons.items():
                    if start <= cell_x < end:
                        tab = self.tab_for_id(tab_id)
                        if tab is not None:
                            self.remove(tab)
                        return

        original_handle_click(self, x, y, button, modifiers, action)

    TabManager.handle_click_on_tab = patched_handle_click


_patch_tab_manager()
