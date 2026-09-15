#!/usr/bin/env python3
"""Select the system update entrypoint for Arch and Omarchy installations."""
import pathlib
import shlex
import shutil


def update_backend(os_release=pathlib.Path('/etc/os-release'), which=shutil.which):
    values = {}
    for line in os_release.read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator and key in ('ID', 'ID_LIKE'):
            values[key] = ' '.join(shlex.split(value))
    # Older Omarchy installations identify as Arch in os-release.
    if values.get('ID') == 'omarchy' or which('omarchy'):
        if not which('omarchy'):
            raise RuntimeError('Omarchy detected, but the omarchy command is missing')
        return 'omarchy'
    if values.get('ID') == 'arch' or 'arch' in values.get('ID_LIKE', '').split():
        if not which('pacman'):
            raise RuntimeError('Arch detected, but the pacman command is missing')
        return 'pacman'
    raise RuntimeError('This installer supports Arch Linux and Omarchy')


if __name__ == '__main__':
    try:
        print(update_backend())
    except (OSError, RuntimeError) as error:
        raise SystemExit(str(error))
