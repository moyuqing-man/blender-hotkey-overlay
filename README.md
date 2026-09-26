# Hotkey Overlay

Real-time keyboard & mouse overlay add-on for Blender (v1.12.1).

## Features
- **Glassmorphism UI (v1.12.0)**: rounded corners everywhere, frosted semi-transparent card with top highlight, 3-layer floating shadow, rounded border, minimal title bar; one-click "Minimal Glass" preset in the panel
- **Screencast-Keys style** big center card for key/mouse display: large text, semi-transparent dark background, gold border, fade in/out + rise animation
- **Persistent hotkey hint card** (top-left of viewport, always visible): Object / Edit / Pose / Sculpt modes, 13+ hotkeys each
- **Draggable hint card**: drag by title bar OR body; Ctrl+drag for 1/4-speed fine adjustment; X/Y numeric fields + reset button in the panel
- **Click title bar to collapse/expand**: card shrinks to title + last-key status row
- **Custom colors + card opacity**: 6 colors (background / title bar / title text / key text / description text / border) plus a card opacity slider applied live to the WHOLE card (body, title bar, border, shadow and text)
- **No box-select interference while dragging**: card drag/collapse consumes mouse events, so Blender's box select never triggers while moving the card
- **Key history teaching fade**: status row shows the last 3 keys (newest left, fading by age) for teaching/demo
- **Held modifier keys row (Screencast-Keys style)**: while holding Ctrl/Shift/Alt, a persistent gold key block shows the held modifier(s); disappears on release
- **Mode following**: after Tab switching to Edit/Pose/Sculpt, the hint card switches to that mode's hints automatically
- **Auto-save all appearance settings**: color / opacity / position / collapse state auto-save to config 0.8s after change and restore on restart
- One-click auto-generate hints from your custom user keymap (shows your real bindings)
- Fully customizable hint text with one-click restore defaults
- Auto-save config, import/export json backup
- Auto-start capture on loading a blend file (persistent timer + temp_override works on Blender 5.2)
- Clean unregister: draw handler, handlers, modal instance all removed, no background residue

## Compatibility
- Legacy add-on: Blender 3.6 ~ 4.1 (install the py file directly)
- New extension: Blender 4.2 ~ 5.x (extension zip; auto-adapts to 5.x keymap renames)

## Install
### Blender 3.6-4.1
1. Download `hotkey_overlay_legacy.zip` (contains `hotkey_overlay.py`).
2. Edit → Preferences → Add-ons → Install, choose the zip, enable.

### Blender 4.2+
1. Download `hotkey_overlay_v1.9.4.zip` (contains `hotkey_overlay/` with `hotkey_overlay.py` + `__init__.py` + `blender_manifest.toml`).
2. Edit → Preferences → Extensions → Install, choose the zip, enable.

> Before upgrading, remove the old Hotkey Overlay first to avoid class conflicts.

## Usage
1. Press N in the 3D viewport to open the sidebar → HotkeyOverlay panel.
2. Capture starts automatically when loading a blend file.
3. Use the panel buttons to start/stop capture manually.
4. Auto-generate hints from your custom keymap via the mode dropdown + generate button.
5. Drag the hint card anywhere; click its title bar to collapse; tune colors/opacity under Appearance; fine-tune X/Y or reset under Position.
6. Customize hint text and display duration, then save config.

## Blender 5.2 notes
- If the card is not visible on first start, re-open the 3D viewport once (or press N) to trigger redraw.
- A Chinese IME may intercept letter keys; use English input or function keys for clean capture.

## License
GPL-3.0-only