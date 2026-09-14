#!/usr/bin/env python3
"""Check source/history and package archives without printing matched values."""
import argparse
import os
import pathlib
import re
import socket
import subprocess
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATTERNS = {
    'private key': rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'GitHub credential': rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
    'AWS access key': rb'AKIA[A-Z0-9]{16}',
    'Slack credential': rb'xox[baprs]-[A-Za-z0-9-]{20,}',
    'credential in URL': rb'https?://[^\s/@:]+:[^\s/@]+@',
    'personal home path': rb'/(?:home/(?!builder(?:/|\b)|builduser(?:/|\b)|runner(?:/|\b))[^/\s\x00]+|Users/[^/\s\x00]+)/',
}


def check(data, label):
    for name, pattern in PATTERNS.items():
        if re.search(pattern, data):
            raise RuntimeError(f'{label}: possible {name} (value redacted)')


def source(history=False):
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT)
    for name in filter(None, names.split(b'\0')):
        path = ROOT / os.fsdecode(name)
        if path.is_file():
            check(path.read_bytes(), os.fsdecode(name))
    if history:
        objects = subprocess.check_output(['git', 'rev-list', '--objects', '--all'], cwd=ROOT)
        for line in objects.splitlines():
            oid = line.split(b' ', 1)[0].decode()
            kind = subprocess.check_output(['git', 'cat-file', '-t', oid], cwd=ROOT).strip()
            if kind in (b'blob', b'commit', b'tag'):
                check(subprocess.check_output(['git', 'cat-file', kind.decode(), oid], cwd=ROOT), f'git object {oid}')
    print('Source privacy checks passed' + (' (including Git history)' if history else ''))


def package(path):
    # Stream decompressed members so large Electron binaries do not fill RAM.
    process = subprocess.Popen(['zstd', '-dc', str(path)], stdout=subprocess.PIPE)
    metadata = set()
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
            for member in archive:
                check(member.name.encode(), path.name + ': member name')
                check(member.linkname.encode(), path.name + ': link target')
                if member.uid != 0 or member.gid != 0 or member.uname not in ('', 'root') or member.gname not in ('', 'root'):
                    raise RuntimeError(f'{path.name}: archive contains non-root ownership')
                if not member.isfile():
                    continue
                stream = archive.extractfile(member)
                if member.name in ('.BUILDINFO', '.PKGINFO'):
                    data = stream.read()
                    check(data, path.name + ':' + member.name)
                    metadata.add(member.name)
                    if member.name == '.BUILDINFO':
                        for key in ('builddir', 'startdir'):
                            if not re.search(rb'^' + key.encode() + rb' = /build(?:/[^\n]*)?$', data, re.M):
                                raise RuntimeError(f'{path.name}: non-isolated build metadata')
                else:
                    # Detect host-specific paths in payloads. Generic upstream build
                    # paths and public application identifiers are not user secrets.
                    tail = b''
                    while block := stream.read(1024 * 1024):
                        combined = tail + block
                        home = str(pathlib.Path.home()).encode() + b'/'
                        hostname = socket.gethostname().encode()
                        if (home not in (b'/root/', b'/home/runner/') and home in combined) or (len(hostname) > 5 and hostname in combined):
                            raise RuntimeError(f'{path.name}: host information in payload (value redacted)')
                        tail = combined[-4096:]
        if metadata != {'.BUILDINFO', '.PKGINFO'}:
            raise RuntimeError(f'{path.name}: missing package metadata')
    finally:
        process.stdout.close()
        code = process.wait()
    if code:
        raise RuntimeError(f'{path.name}: decompression failed')
    print(f'{path.name}: package privacy checks passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--packages', type=pathlib.Path)
    args = parser.parse_args()
    if args.packages:
        paths = sorted(args.packages.glob('*.pkg.tar.zst'))
        if not paths:
            parser.error('no packages to audit')
        for path in paths:
            package(path)
    else:
        source(args.history)
