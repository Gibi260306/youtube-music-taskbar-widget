# YouTube Music tab volume (Firefox)

The companion connects the widget to **YouTube Music's own player and volume
sliders**. It does not send volume commands to Firefox's application mixer.
It grants website access only to `https://music.youtube.com/*`.

**This is an experimental, unsigned add-on.** A temporary installation lasts
until Firefox restarts. For everyday use it needs Mozilla signing as an unlisted
add-on. The code has automated browser/protocol tests; a live Firefox + Plasma
test is still required before treating the change as verified on your desktop.

## Install and try it

These steps target standard Linux Firefox (including the Arch package), with
Python 3.10+, `venv`, and `pip`. Sandboxed Firefox installations may need different
native-host integration and are not covered by this installer.

1. From the repository directory, install the local bridge:

   ```bash
   python3 browser-bridge/install.py
   ```

   This creates a private Python environment with `dbus-next==0.2.3`, registers
   `com.gibi.youtube_music` in `~/.mozilla/native-messaging-hosts/`, and builds an
   unsigned `.xpi`. It does not need root privileges or open a network listener.
   The installer prints the exact `.xpi` path.

2. Open `about:debugging#/runtime/this-firefox`, choose **Load Temporary Add-on**,
   and select that `.xpi` (or `browser-bridge/extension/manifest.json`). If the
   companion displays `!`, click its toolbar icon to reconnect after installation.

3. Open YouTube Music and load a song. Install the updated widget:

   ```bash
   kpackagetool6 --type Plasma/Applet --upgrade package
   ```

   Remove and re-add the widget if Plasma still shows the old version. A working
   connection displays **YouTube Music tab (Firefox)** in the popup.

4. Start at a comfortable listening level and verify:

   - Move the widget to 50%: YouTube Music's own slider should show 50%.
   - Move the site slider to 25%: the widget should follow within about a second.
   - Set the widget to zero and raise it again: the site should mute and unmute.
   - Play a video in another tab: its volume must remain unchanged.
   - Close the Music tab: the dedicated player should disappear. Generic browser
     volume is disabled so the widget cannot silently switch to the wrong control.

The connection pins one Music tab. When first connecting, it prefers an audible
Music tab, then the most recently accessed one. It stays pinned until that tab
closes or navigates away; another playing tab does not steal the controls. Commands
already queued for a closed tab are discarded. Other native MPRIS players remain
usable when there is no Music connection.

## Keep the add-on installed after a restart

Use Mozilla's [Extension Workshop signing guide](https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/)
to submit the generated `.xpi` for **unlisted distribution**, keeping the add-on
ID `youtube-music-taskbar@gibi260306`. Install the signed file through Firefox's
**Add-ons and themes → gear menu → Install Add-on From File**. A temporary build
is sufficient for testing; the generated file is not already signed or published.

## How volume works

The extension uses Firefox's native messaging API. Its local host exposes
`org.mpris.MediaPlayer2.gibi_youtube_music.instance<PID>` on your session D-Bus.
The widget prefers that player to the general browser media controller.

Volume reads the visible site slider and writes through the Music player bar's
`updateVolume()` method, keeping both directions on the site's displayed scale.
The underlying `getVolume()` API can report a different, transformed gain (for
example, a 75% site slider and an internal value near 43%). Both site slider
variants are kept in sync, and the visible one takes precedence when the hidden
one is stale. If the site sliders are unavailable, both reads and writes fall
back to the player API's scale. No gain curve is guessed or hard-coded.

The bridge does not calculate a percentage of the Firefox mixer volume, write
`HTMLMediaElement.volume`, or use `pactl`. YouTube may round slider values to its
own step size. Its page API/selectors are not a stable public contract; site
changes can require an update to `player.js`.

When the companion is absent, a browser player shows a connection hint and its
volume slider/wheel are disabled. This is intentional: a general browser MPRIS
volume cannot promise to control the Music site's own slider. Native players
such as Pear retain their ordinary volume control.

## Tests

The browser tests use separate simulated tabs and serialize the injected page
function as Firefox does. They check direct player/slider updates, reverse sync
with different internal/displayed scales, hidden sliders, live dragging and
rounding, mute/unmute, bounds, rapid dragging, navigation, and stale-tab commands.

```bash
node --test tests/browser-bridge.test.cjs
```

Python tests require `dbus-next`. Use the private environment installed above
(replace the path if `XDG_DATA_HOME` differs):

```bash
~/.local/share/youtube-music-taskbar/venv/bin/python -m unittest discover -s tests -v
dbus-run-session -- ~/.local/share/youtube-music-taskbar/venv/bin/python -m unittest discover -s tests -v
```

The second command also runs a real session D-Bus test of the host subprocess,
native message framing, property writes, reverse sync, and disconnect cleanup.
It requires permission to create a local Unix socket. Neither these tests nor
the simulated tabs substitute for the live checks above.

## Remove the bridge

```bash
python3 browser-bridge/install.py --uninstall
```

Remove the companion from Firefox as well. No background service is installed:
Firefox owns the native host process and closes it when the extension disconnects.
