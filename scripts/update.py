#!/usr/bin/env python3
"""Merge upstream packaging changes; optionally open one PR for this package."""
import argparse
import json
import pathlib
import os
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGES = ('orca', 'proton_pass', 'proton_mail', 'proton_drive', 'proton_vpn')


def run(*args, cwd=None, **kwargs):
    return subprocess.run(args, cwd=cwd or ROOT, check=True, capture_output=True, **kwargs).stdout


def version(data):
    values = {}
    for key in ('epoch', 'pkgver', 'pkgrel'):
        match = re.search(r'^' + key + r'=[\'\"]?([\w.+:-]+)', data.decode(), re.M)
        if match:
            values[key] = match[1]
    return (values.get('epoch', '0') + ':' + values['pkgver'] + '-' + values['pkgrel'])


def merge(local, base, remote):
    if local == base:
        return remote
    if remote == base or local == remote:
        return local
    if None in (local, base, remote):
        raise RuntimeError('upstream deletion/addition conflicts with a local change')
    with tempfile.TemporaryDirectory() as tmp:
        paths = [pathlib.Path(tmp) / name for name in ('local', 'base', 'upstream')]
        for path, data in zip(paths, (local, base, remote)):
            path.write_bytes(data)
        result = subprocess.run(['git', 'merge-file', '-p', *map(str, paths)], capture_output=True)
        if result.returncode:
            raise RuntimeError('upstream conflicts with a local customization; merge manually')
        return result.stdout


def merge_recipe(local, base, remote):
    # Adjacent source checksums often change on different sides. Merge each
    # checksum independently, while still failing if BOTH sides changed it.
    if None in (local, base, remote):
        return merge(local, base, remote)
    pattern = rb'\b[a-f0-9]{64,128}\b'
    hashes = [re.findall(pattern, value) for value in (local, base, remote)]
    if len(set(map(len, hashes))) != 1:
        return merge(local, base, remote)
    merged = [merge(*triple) for triple in zip(*hashes)]
    normalized = []
    for value in (local, base, remote):
        counter = iter(range(len(merged)))
        normalized.append(re.sub(pattern, lambda _: f'CHECKSUM_PLACEHOLDER_{next(counter)}_END'.encode(), value))
    result = merge(*normalized)
    for index, value in enumerate(merged):
        result = result.replace(f'CHECKSUM_PLACEHOLDER_{index}_END'.encode(), value)
    return result


def update(package, pr=False, repo=None):
    directory = ROOT / package
    statefile = directory / '.upstream.json'
    state = json.loads(statefile.read_text())
    with tempfile.TemporaryDirectory() as tmp:
        run('git', 'clone', '--quiet', state['url'], tmp)
        head = run('git', 'rev-parse', 'HEAD', cwd=tmp).decode().strip()
        if head == state['commit']:
            print(f'{package}: up to date')
            return False
        # Validate tree paths and modes before writing anything to the workspace.
        entries = run('git', 'ls-tree', '-rz', head, cwd=tmp).split(b'\0')
        files = []
        modes = {}
        for entry in filter(None, entries):
            metadata, rawpath = entry.split(b'\t', 1)
            path = rawpath.decode()
            mode, kind, _ = metadata.decode().split()
            if mode not in ('100644', '100755', '120000') or kind != 'blob':
                raise RuntimeError(f'Unsupported upstream file: {path}')
            if any(part in ('.git', '..') for part in pathlib.PurePosixPath(path).parts) or path.startswith('/'):
                raise RuntimeError('Unsafe upstream path')
            if path in ('.upstream.json', '.aur-url') or path.startswith('.github/'):
                raise RuntimeError(f'Reserved upstream path: {path}')
            files.append(path)
            modes[path] = mode

        def blob(commit, path, available):
            return run('git', 'show', f'{commit}:{path}', cwd=tmp) if path in available else None

        changes = {}
        for path in sorted(set(state['files']) | set(files)):
            target = directory / path
            if not target.parent.resolve().is_relative_to(directory.resolve()):
                raise RuntimeError('Local parent directory escapes the package directory')
            local = os.readlink(target).encode() if target.is_symlink() else (target.read_bytes() if target.is_file() else None)
            try:
                merger = merge_recipe if path in ('PKGBUILD', '.SRCINFO') else merge
                changes[path] = merger(local, blob(state['commit'], path, state['files']), blob(head, path, files))
                if modes.get(path) == '120000' and changes[path] is not None:
                    destination = (target.parent / changes[path].decode()).resolve()
                    if not destination.is_relative_to(directory.resolve()):
                        raise RuntimeError('symlink escapes the package directory')
            except RuntimeError as error:
                raise RuntimeError(f'{package}/{path}: {error}') from error
        oldversion = version((directory / 'PKGBUILD').read_bytes())
        newversion = version(changes['PKGBUILD'])
        branch = f'updates/{package}/{head[:12]}'
        if pr:
            if run('git', 'status', '--porcelain').strip():
                raise RuntimeError('PR mode requires a clean checkout')
            existing = json.loads(run('gh', 'pr', 'list', '--repo', repo, '--head', branch,
                                      '--state', 'all', '--json', 'url'))
            if existing:
                print(existing[0]['url'])
                return False
            run('git', 'switch', '-c', branch)
        for path, content in changes.items():
            target = directory / path
            if content is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.unlink(missing_ok=True)
                if modes.get(path) == '120000':
                    target.symlink_to(content.decode())
                else:
                    target.write_bytes(content)
                    target.chmod(int(modes.get(path, '100644'), 8) & 0o777)
        state.update(commit=head, files=files)
        statefile.write_text(json.dumps(state, indent=2) + '\n')
        print(f'{package}: {oldversion} -> {newversion} ({head[:12]})')
        if pr:
            title = f'Update {package}: {newversion}'
            run('git', 'add', '--', package)
            run('git', 'commit', '-m', title)
            run('git', 'push', '--set-upstream', 'origin', branch)
            body = pathlib.Path(tmp) / 'pr.md'
            body.write_text(f'Update `{package}` from `{oldversion}` to `{newversion}`.\n\n'
                            f'Upstream packaging: {state["url"]}\n\nCommit: `{head}`\n\n'
                            'Local customizations were preserved with a three-way merge. '
                            'No PKGBUILD was executed by the update checker. Review the recipe, '
                            'checksums, dependencies, and build results before merging.\n')
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
