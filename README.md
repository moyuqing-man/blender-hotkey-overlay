# Hotkey Overlay

Real-time keyboard & mouse overlay add-on for Blender (v1.12.3).

## Features
- **Black minimal floating UI (v1.12.1 default)**: near-black card, Blender-orange key accents, thin mid-gray border, matching Blender's dark UI; rounded corners via custom SDF shader (auto-falls-back to plain rect on shader failure)
- **Independent recent-key chip color (v1.12.2)**: separate color picker for the recent-key chip background, decoupled from the key-text color
- **Screencast-Keys style** key/mouse capture shown in the persistent hint card's status row: last 3 keys with age-based fade
- **Held modifier keys row**: holding Ctrl/Shift/Alt shows a persistent block that disappears on release
- **Persistent hotkey hint card** (top-left of viewport, always visible): Object / Edit / Pose / Sculpt modes, 13+ hotkeys each
- **Draggable / collapsible hint card**: drag anywhere to move; click title bar to collapse to title + status row; X/Y numeric fields + reset in the panel
- **Custom colors + opacity**: card bg / title bg / title / key / description / border colors, plus recent-key text and recent-key chip colors (8 pickers); background opacity controls the whole card, chip opacity controls recent-key/held blocks
- **Auto-generate hints from your custom user keymap** (shows your real bindings; click button to refresh)
- Fully customizable hint text with one-click restore defaults
- Auto-save appearance (0.8s debounce), import/export json backup
- Auto-start capture on loading a blend file; clean unregister with no background residue

## Compatibility
- **Blender 4.2 ~ 5.x only (extension format)**; tested on Blender 5.2.2 LTS (Steam).
- **No longer supports Blender 3.6 ~ 4.1 legacy add-on format.** The rounded SDF shader depends on `GPUShaderCreateInfo` (4.0+ API), and the extension manifest pins `blender_version_min = "4.2.0"`.

## Install
1. Download `hotkey_overlay_v1.12.3.zip` (contains `hotkey_overlay/` with `hotkey_overlay.py` + `__init__.py` + `blender_manifest.toml`).
2. Edit → Preferences → Extensions → Install, choose the zip, enable.

> Before upgrading, remove the old Hotkey Overlay first to avoid class conflicts.

## Usage
1. Press N in the 3D viewport to open the sidebar → HotkeyOverlay panel.
2. Capture starts automatically when loading a blend file.
3. Drag the hint card anywhere; click its title bar to collapse; tune colors/opacity under Appearance; fine-tune X/Y or reset under Position.
4. Auto-generate hints from your custom keymap via the mode dropdown + generate button.

## License
GPL-3.0-only