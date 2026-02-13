#!/usr/bin/env python
# License: GPL v3 Copyright: 2024, kitty-meow contributors

import sys
from typing import List, Optional

from kitty.typing_compat import BossType

from ..tui.handler import result_handler


def option_text() -> str:
    return '''\
--title -t
default=Menu
The title to display above the menu.


--item -i
type=list
dest=items
A menu item. Can be specified multiple times. Format: ``key:Text``
where key is a single character shortcut and Text is the display text.
For example: ``c:Copy`` or ``p:Paste``


--default -d
The default selected item (by key). If unspecified, first item is selected.


--x
type=int
default=-1
X position (in cells) for the menu. -1 means center horizontally.


--y
type=int
default=-1
Y position (in cells) for the menu. -1 means center vertically.
'''


help_text = '''\
Display a popup menu and return the selected item.

Example usage::

    kitten menu -i "c:Copy" -i "p:Paste" -i "a:Select All"
'''
usage = 'ITEMS...'


def main(args: List[str]) -> Optional[str]:
    raise SystemExit('This kitten must be run from within kitty')


@result_handler()
def handle_result(args: List[str], data: dict, target_window_id: int, boss: BossType) -> None:
    response = data.get('response', '')
    if response:
        w = boss.window_id_map.get(target_window_id)
        if response == 'c':
            boss.copy_to_clipboard()
        elif response == 'p':
            boss.paste_from_clipboard()
        elif response == 'y':
            boss.copy_to_clipboard_as_html()
        elif response == 'a':
            if w is not None:
                w.screen.select_all()
        elif response == 'l':
            if w is not None:
                w.clear_selection()


if __name__ == '__main__':
    main(sys.argv)
elif __name__ == '__doc__':
    cd = sys.cli_docs  # type: ignore
    cd['usage'] = '[options]'
    cd['options'] = option_text
    cd['help_text'] = help_text
    cd['short_desc'] = 'Display a popup menu'
