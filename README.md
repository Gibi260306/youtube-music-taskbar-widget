# YouTube Music Taskbar
Made with help from ChatGPT.

A compact KDE Plasma 6 media widget for YouTube Music and other MPRIS-compatible players.

It shows the current track and album artwork in the panel, with a popup for playback, seeking, volume, and opening the active player.

## Install

```bash
git clone https://github.com/Gibi260306/youtube-music-taskbar-widget.git
cd youtube-music-taskbar-widget
kpackagetool6 --type Plasma/Applet --install package
```

Then right-click the Plasma panel, choose **Add Widgets**, and add **YouTube Music Taskbar**.

To update an existing installation:

```bash
git pull
kpackagetool6 --type Plasma/Applet --upgrade package
```

## Requirements

- KDE Plasma 6
- An MPRIS-compatible player, such as Firefox playing YouTube Music

## Firefox companion: YouTube Music tab volume

The Firefox companion lets the widget control **YouTube Music's own volume
slider**, independently of other tabs. Volume stays synchronized in both
directions: changing either slider updates the other. Firefox's application
mixer volume remains a separate control.

This needs both the Firefox add-on and a local Python bridge. The bridge exposes
the Music tab to Plasma through MPRIS. The add-on has website access only to
`https://music.youtube.com/*`.

### Set up the companion

Use standard Linux Firefox 128 or newer, Python 3.10 or newer, `venv`, and `pip`.
The installer does not require root privileges. Sandboxed Firefox installations
may need different native-host integration.

1. From the cloned repository directory, install the local bridge:

   ```bash
   python3 browser-bridge/install.py
   ```

   This creates a private Python environment, registers the Firefox native host,
   and prints the path to the generated unsigned `.xpi` add-on.

2. In Firefox, open `about:debugging#/runtime/this-firefox`, click **Load Temporary
   Add-on**, and select that `.xpi`. You can also select
   `browser-bridge/extension/manifest.json` from the repository.

3. Open YouTube Music and load a song. The widget popup should show
   **YouTube Music tab (Firefox)**. If the companion shows `!`, click its toolbar
   icon to reconnect.

4. Move the widget slider to 50% and check that the site shows 50%. Then change
   the site slider: the widget should follow within about a second.

**The companion is unsigned. Firefox removes a temporary add-on when it
restarts, so you must load it again.** Keeping it installed permanently requires
Mozilla signing; see the [full companion guide](browser-bridge/README.md) for
signing, troubleshooting, tests, and removal instructions.

The widget prefers the dedicated Music tab connection when available. Without
the companion, browser volume controls are disabled and show a setup hint.
Native MPRIS players retain their usual volume controls.

## License

GPL-3.0-or-later
