#!/usr/bin/env python3
"""Check vendor releases; optionally open one update PR per package version."""
import argparse
import json
import pathlib
import subprocess
import tempfile
import vendor

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGES = ('orca', 'proton_pass', 'proton_mail', 'proton_drive', 'stremio')


def run(*args, cwd=None, **kwargs):
    return subprocess.run(args, cwd=cwd or ROOT, check=True, capture_output=True, **kwargs).stdout


def update(package, pr=False, repo=None):
    state = json.loads((ROOT / package / '.upstream.json').read_text())
    return update_vendor(package, state, pr, repo)


def update_vendor(package, config, pr=False, repo=None):
    if pr and run('git', 'status', '--porcelain').strip():
        raise RuntimeError('PR mode requires a clean checkout')
    directory = ROOT / package
    current = vendor.scalar((directory / 'PKGBUILD').read_text(), 'pkgver')
    latest, assets = vendor.latest(config)
    if vendor.version_key(latest) <= vendor.version_key(current):
        print(f'{package}: packaged {current}; latest stable vendor release {latest}')
        return False
    branch = f'updates/{package}/{latest}'
    if pr:
        existing = json.loads(run('gh', 'pr', 'list', '--repo', repo, '--head', branch,
                                  '--state', 'all', '--json', 'url'))
        if existing:
            print(existing[0]['url'])
            return False
    changes = vendor.prepare(directory, config, latest, assets)
    if pr:
        run('git', 'switch', '-c', branch)
    for name, content in changes.items():
        (directory / name).write_bytes(content)
    print(f'{package}: {current} -> {latest} (pinned vendor release)')
    if pr:
        title = f'Update {package}: {latest}'
        run('git', 'add', '--', package)
        run('git', 'commit', '-m', title)
        run('git', 'push', '--set-upstream', 'origin', branch)
        with tempfile.TemporaryDirectory() as tmp:
            body = pathlib.Path(tmp) / 'pr.md'
            verification = (
                'Official source archive downloaded over HTTPS and its SHA-256 pinned. '
                'Upstream does not publish an independent checksum for this source archive. '
                if config['provider'] == 'github-source' else
                'Downloads were verified against vendor-published checksums. ')
            body.write_text(f'Update `{package}` from `{current}` to `{latest}`.\n\n'
                            f'Vendor release feed: {config["url"]}\n\n'
                            f'{verification}'
                            'Local packaging and launcher customizations were preserved. '
                            'No PKGBUILD was executed by the update checker. '
                            'Review dependencies and approve the package build checks before merging.\n')
            print(run('gh', 'pr', 'create', '--repo', repo, '--title', title,
                      '--body-file', str(body), '--head', branch).decode().strip())
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', choices=PACKAGES)
    parser.add_argument('--pr', action='store_true')
    parser.add_argument('--repo', help='GitHub OWNER/REPOSITORY (required with --pr)')
    args = parser.parse_args()
    if args.pr and not args.repo:
        parser.error('--pr requires --repo')
    update(args.package, args.pr, args.repo)
