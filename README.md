# YouTube Music Taskbar
##This was made using ChatGPT##

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

## License

GPL-3.0-or-later
