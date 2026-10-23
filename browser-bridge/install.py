#!/usr/bin/env python3
"""Install the native host for a standard Linux Firefox installation."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import venv
import zipfile


def install(data_dir, manifest_dir):
    source = Path(__file__).resolve().parent
    data_dir.mkdir(parents=True, exist_ok=True)
    environment = data_dir / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / "bin/python"
    subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                    "dbus-next==0.2.3"], check=True)
    shutil.copy2(source / "native_host.py", data_dir / "native_host.py")
    launcher = data_dir / "host"
    launcher.write_text("#!/bin/sh\nexec " + shlex.quote(str(python)) + " "
                        + shlex.quote(str(data_dir / "native_host.py")) + ' "$@"\n')
    launcher.chmod(0o700)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "com.gibi.youtube_music.json").write_text(json.dumps({
        "name": "com.gibi.youtube_music",
        "description": "YouTube Music taskbar tab bridge",
        "path": str(launcher),
        "type": "stdio",
        "allowed_extensions": ["youtube-music-taskbar@gibi260306"]
    }, indent=2) + "\n")
    extension = data_dir / "youtube-music-taskbar-companion.xpi"
    with zipfile.ZipFile(extension, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((source / "extension").iterdir()):
            if path.is_file():
                archive.write(path, path.name)
    print("Native bridge installed. Unsigned Firefox add-on:")
    print(extension)
    print("For testing: about:debugging#/runtime/this-firefox -> Load Temporary Add-on")
    print("Temporary add-ons disappear on Firefox restart. See browser-bridge/README.md for signing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get(
        "XDG_DATA_HOME", Path.home() / ".local/share")) / "youtube-music-taskbar")
    parser.add_argument("--manifest-dir", type=Path, default=Path.home() / ".mozilla/native-messaging-hosts")
    parser.add_argument("--uninstall", action="store_true", help="Remove the native host and its private environment")
    args = parser.parse_args()
    data_dir = args.data_dir.expanduser().resolve()
    manifest_dir = args.manifest_dir.expanduser().resolve()
    if args.uninstall:
        # Do not recursively remove a user-supplied directory: delete only the
        # paths this installer owns, including its private virtual environment.
        for name in ("host", "native_host.py", "youtube-music-taskbar-companion.xpi"):
            (data_dir / name).unlink(missing_ok=True)
        shutil.rmtree(data_dir / "venv", ignore_errors=True)
        (manifest_dir / "com.gibi.youtube_music.json").unlink(missing_ok=True)
        print("Native bridge removed. Remove the companion from Firefox as well.")
    else:
        try:
            install(data_dir, manifest_dir)
        except (OSError, subprocess.CalledProcessError) as error:
            print("Installation failed: " + str(error), file=sys.stderr)
            sys.exit(1)
