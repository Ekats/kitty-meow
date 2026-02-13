// License: GPLv3 Copyright: 2024, kitty-meow contributors

package menu

import (
	"fmt"
	"strings"

	"github.com/kovidgoyal/kitty/tools/cli"
	"github.com/kovidgoyal/kitty/tools/tui"
	"github.com/kovidgoyal/kitty/tools/tui/loop"
	"github.com/kovidgoyal/kitty/tools/utils/style"
	"github.com/kovidgoyal/kitty/tools/wcswidth"
)

var _ = fmt.Print

type MenuItem struct {
	Key   string
	Text  string
	Index int
}

type Response struct {
	Response string `json:"response"`
}

func showMenu(o *Options) (response string, err error) {
	response = ""
	lp, err := loop.New()
	if err != nil {
		return "", err
	}
	lp.MouseTrackingMode(loop.FULL_MOUSE_TRACKING)

	// Parse menu items
	items := make([]MenuItem, 0, len(o.Items))
	for i, item := range o.Items {
		key, text, found := strings.Cut(item, ":")
		if !found {
			text = item
			key = string([]rune(strings.ToLower(item))[0])
		}
		items = append(items, MenuItem{Key: strings.ToLower(key), Text: text, Index: i})
	}

	if len(items) == 0 {
		return "", fmt.Errorf("No menu items specified")
	}

	selectedIndex := 0
	// Find default selection
	for i, item := range items {
		if item.Key == o.Default {
			selectedIndex = i
			break
		}
	}

	ctx := style.Context{AllowEscapeCodes: true}
	menuWidth := 0

	// Calculate menu width
	for _, item := range items {
		w := wcswidth.Stringwidth(item.Text) + 6
		if w > menuWidth {
			menuWidth = w
		}
	}
	titleW := wcswidth.Stringwidth(o.Title) + 4
	if titleW > menuWidth {
		menuWidth = titleW
	}

	// Track Y positions for mouse clicks
	itemYPositions := make([]int, len(items))
	menuStartY := 0
	menuStartX := 0

	draw_screen := func() error {
		lp.StartAtomicUpdate()
		defer lp.EndAtomicUpdate()
		lp.ClearScreen()

		sz, err := lp.ScreenSize()
		if err != nil {
			return err
		}
		screenWidth := int(sz.WidthCells)
		screenHeight := int(sz.HeightCells)

		menuHeight := len(items) + 4 // title + separator + items + borders
		menuStartY = (screenHeight - menuHeight) / 2
		if menuStartY < 0 {
			menuStartY = 0
		}
		menuStartX = (screenWidth - menuWidth) / 2
		if menuStartX < 0 {
			menuStartX = 0
		}

		// Move to starting position
		lp.QueueWriteString(strings.Repeat("\r\n", menuStartY))

		pad := strings.Repeat(" ", menuStartX)

		// Draw top border
		lp.Println(pad + ctx.SprintFunc("fg=gray")("┌"+strings.Repeat("─", menuWidth-2)+"┐"))

		// Draw title
		title := o.Title
		titlePad := (menuWidth - 2 - wcswidth.Stringwidth(title)) / 2
		titleLine := pad + ctx.SprintFunc("fg=gray")("│") +
			strings.Repeat(" ", titlePad) +
			ctx.SprintFunc("bold fg=white")(title) +
			strings.Repeat(" ", menuWidth-2-titlePad-wcswidth.Stringwidth(title)) +
			ctx.SprintFunc("fg=gray")("│")
		lp.Println(titleLine)

		// Draw separator
		lp.Println(pad + ctx.SprintFunc("fg=gray")("├"+strings.Repeat("─", menuWidth-2)+"┤"))

		// Draw menu items
		currentY := menuStartY + 3
		for i, item := range items {
			itemYPositions[i] = currentY

			text := " " + item.Text
			textWidth := wcswidth.Stringwidth(text)
			itemPad := menuWidth - 3 - textWidth
			if itemPad < 0 {
				itemPad = 0
			}

			var itemContent string
			if i == selectedIndex {
				itemContent = ctx.SprintFunc("bg=blue fg=white bold")(text + strings.Repeat(" ", itemPad))
			} else {
				// Highlight the shortcut key
				keyIdx := strings.Index(strings.ToLower(item.Text), item.Key)
				if keyIdx >= 0 {
					runes := []rune(item.Text)
					runeIdx := len([]rune(item.Text[:keyIdx]))
					prefix := " " + string(runes[:runeIdx])
					key := string(runes[runeIdx])
					suffix := string(runes[runeIdx+1:])
					itemContent = prefix + ctx.SprintFunc("fg=green bold")(key) + suffix + strings.Repeat(" ", itemPad)
				} else {
					itemContent = text + strings.Repeat(" ", itemPad)
				}
			}

			lp.Println(pad + ctx.SprintFunc("fg=gray")("│") + itemContent + ctx.SprintFunc("fg=gray")("│"))
			currentY++
		}

		// Draw bottom border
		lp.QueueWriteString(pad + ctx.SprintFunc("fg=gray")("└"+strings.Repeat("─", menuWidth-2)+"┘"))

		return nil
	}

	lp.OnInitialize = func() (string, error) {
		lp.SetCursorVisible(false)
		return "", draw_screen()
	}

	lp.OnFinalize = func() string {
		lp.SetCursorVisible(true)
		return ""
	}

	lp.OnResize = func(old_size loop.ScreenSize, new_size loop.ScreenSize) error {
		return draw_screen()
	}

	lp.OnKeyEvent = func(event *loop.KeyEvent) error {
		if event.MatchesPressOrRepeat("escape") || event.MatchesPressOrRepeat("q") {
			event.Handled = true
			lp.Quit(0)
			return nil
		}
		if event.MatchesPressOrRepeat("enter") || event.MatchesPressOrRepeat("space") {
			event.Handled = true
			response = items[selectedIndex].Key
			lp.Quit(0)
			return nil
		}
		if event.MatchesPressOrRepeat("up") || event.MatchesPressOrRepeat("k") {
			event.Handled = true
			if selectedIndex > 0 {
				selectedIndex--
				draw_screen()
			}
			return nil
		}
		if event.MatchesPressOrRepeat("down") || event.MatchesPressOrRepeat("j") {
			event.Handled = true
			if selectedIndex < len(items)-1 {
				selectedIndex++
				draw_screen()
			}
			return nil
		}
		// Check for shortcut keys
		if event.Type == loop.PRESS || event.Type == loop.REPEAT {
			key := strings.ToLower(event.Text)
			for _, item := range items {
				if item.Key == key {
					event.Handled = true
					response = item.Key
					lp.Quit(0)
					return nil
				}
			}
		}
		return nil
	}

	lp.OnMouseEvent = func(event *loop.MouseEvent) error {
		if event.Event_type == loop.MOUSE_CLICK {
			for i, item := range items {
				y := itemYPositions[i]
				if int(event.Cell.Y) == y && int(event.Cell.X) >= menuStartX+1 && int(event.Cell.X) < menuStartX+menuWidth-1 {
					response = item.Key
					lp.Quit(0)
					return nil
				}
			}
			// Click outside menu - close it
			lp.Quit(0)
			return nil
		}
		if event.Event_type == loop.MOUSE_MOVE {
			for i := range items {
				y := itemYPositions[i]
				if int(event.Cell.Y) == y && int(event.Cell.X) >= menuStartX+1 && int(event.Cell.X) < menuStartX+menuWidth-1 {
					if selectedIndex != i {
						selectedIndex = i
						draw_screen()
					}
					break
				}
			}
		}
		return nil
	}

	err = lp.Run()
	if err != nil {
		return "", err
	}
	ds := lp.DeathSignalName()
	if ds != "" {
		return "", fmt.Errorf("Killed by signal: %s", ds)
	}
	return response, nil
}

func main(_ *cli.Command, o *Options, args []string) (rc int, err error) {
	output := tui.KittenOutputSerializer()
	result := &Response{}

	result.Response, err = showMenu(o)
	if err != nil {
		return 1, err
	}

	s, err := output(result)
	if err != nil {
		return 1, err
	}
	_, err = fmt.Println(s)
	if err != nil {
		return 1, err
	}
	return 0, nil
}

func EntryPoint(parent *cli.Command) {
	create_cmd(parent, main)
}
