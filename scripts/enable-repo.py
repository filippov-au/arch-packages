#!/usr/bin/env python3
"""Add this repository ahead of Arch's repositories, preserving existing config."""
import datetime
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

CONFIG = pathlib.Path('/etc/pacman.conf')
STANZA = '''[arch-packages]
SigLevel = Optional TrustAll
Server = https://github.com/filippov-au/arch-packages/releases/download/packages

'''


def configure(text):
    # Remove only our previous stanza, then insert ahead of the first repository.
    text = re.sub(r'^\[arch-packages\]\s*\n.*?(?=^\[|\Z)', '', text, flags=re.M | re.S)
    sections = list(re.finditer(r'^\[([^]\n]+)\]\s*$', text, re.M))
    if not sections or sections[0][1] != 'options':
        raise RuntimeError('Expected [options] as the first pacman.conf section')
    first_repo = next((match.start() for match in sections if match[1] != 'options'), len(text))
    return text[:first_repo].rstrip() + '\n\n' + STANZA + text[first_repo:]


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo: sudo python scripts/enable-repo.py')
    original = CONFIG.read_text()
    changed = configure(original)
    if original != changed:
        with tempfile.NamedTemporaryFile(mode='w', dir='/etc', prefix='.pacman.conf.', delete=False) as temp:
            temp.write(changed)
            filename = temp.name
        try:
            subprocess.run(['pacman-conf', '--config', filename, '--repo-list'], check=True)
            backup = CONFIG.with_name('pacman.conf.backup-' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
            shutil.copy2(CONFIG, backup)
            shutil.copymode(CONFIG, filename)
            os.replace(filename, CONFIG)
            print(f'Configured repository. Backup: {backup}')
        finally:
            pathlib.Path(filename).unlink(missing_ok=True)
    else:
        print('Repository already configured first.')
    print('Refresh and upgrade with: sudo pacman -Syu')
