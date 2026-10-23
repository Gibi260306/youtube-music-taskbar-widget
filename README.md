# YouTube Music Taskbar
This was made with the help of Chatgbt

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

## YouTube Music tab volume in Firefox

To control the Music website's own volume slider independently of other tabs,
install the [Firefox companion and local bridge](browser-bridge/README.md).
The widget prefers this dedicated Music tab connection when it is available.
Without it, generic browser volume is disabled and the widget shows a setup hint;
native MPRIS players keep their usual volume control.

The companion is currently an unsigned test build. Temporary installation ends
when Firefox restarts; the setup guide explains permanent signing and live tests.

## License

GPL-3.0-or-later
