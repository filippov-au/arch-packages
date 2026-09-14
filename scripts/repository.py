#!/usr/bin/env python3
"""Assemble or publish the rolling pacman repository hosted by GitHub Releases."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGES = ('orca', 'proton_pass', 'proton_mail', 'proton_drive', 'proton_vpn')
NAME = 'arch-packages'
TAG = 'packages'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def recipe_hash(package):
    digest = hashlib.sha256()
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', package], cwd=ROOT)
    for name in sorted(set(filter(None, paths.split(b'\0')))):
        path = ROOT / name.decode()
        if path.name in ('.upstream.json', '.aur-url', '.nvchecker.toml', '.gitignore'):
            continue
        digest.update(name + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def get_json(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def download(url, path):
    with urllib.request.urlopen(url, timeout=120) as response, path.open('wb') as output:
        shutil.copyfileobj(response, output)


def build(repo, output):
    output.mkdir(parents=True, exist_ok=True)
    if list(output.glob('*.pkg.tar.zst')):
        raise RuntimeError('Use an empty output directory to avoid publishing stale packages')
    base = f'https://github.com/{repo}/releases/download/{TAG}'
    previous = get_json(base + '/manifest.json') or {'packages': {}}
    manifest = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'packages': {}}
    for package in PACKAGES:
        fingerprint = recipe_hash(package)
        old = previous['packages'].get(package)
        if old and old['recipe_sha256'] == fingerprint:
            filename = old['filename']
            if pathlib.Path(filename).name != filename or not filename.endswith('.pkg.tar.zst'):
                raise RuntimeError('Invalid filename in remote manifest')
            target = output / filename
            download(base + '/' + filename, target)
            if sha(target) != old['sha256']:
                raise RuntimeError(f'{package}: downloaded package checksum mismatch')
            manifest['packages'][package] = old
            print(f'{package}: reused published build', flush=True)
            continue
        work = output / package
        if work.exists():
            shutil.rmtree(work)
        subprocess.run(['bash', 'scripts/build.sh', package, str(work)], cwd=ROOT, check=True)
        archives = list(work.glob('*.pkg.tar.zst'))
        if len(archives) != 1:
            raise RuntimeError(f'{package}: expected one package archive')
        artifact = archives[0]
        if old and old['filename'] == artifact.name:
            raise RuntimeError(f'{package}: recipe changed without a version/pkgrel bump; bump pkgrel before publishing')
        target = output / artifact.name
        shutil.move(artifact, target)
        work.rmdir()
        manifest['packages'][package] = {'filename': target.name, 'sha256': sha(target), 'recipe_sha256': fingerprint}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    # repo-add runs in the same neutral environment as package builds.
    subprocess.run(['docker', 'run', '--rm', '--platform', 'linux/amd64',
                    '--mount', f'type=bind,source={output.resolve()},target=/repository',
                    '-w', '/repository', 'archlinux:base-devel', 'bash', '-c',
                    'repo-add arch-packages.db.tar.gz ./*.pkg.tar.zst && '
                    'cp --remove-destination arch-packages.db.tar.gz arch-packages.db && '
                    'cp --remove-destination arch-packages.files.tar.gz arch-packages.files && '
                    'chmod a+r arch-packages.*'], check=True)
    print(f'Repository ready: {output}')


def publish(repo, output):
    manifest = json.loads((output / 'manifest.json').read_text())
    expected = set(PACKAGES)
    if set(manifest['packages']) != expected:
        raise RuntimeError('Manifest does not contain all five packages')
    for entry in manifest['packages'].values():
        filename = entry['filename']
        if pathlib.Path(filename).name != filename or sha(output / filename) != entry['sha256']:
            raise RuntimeError('Artifact checksum or filename validation failed')
    # Authenticated lookup also finds a draft left by an interrupted first upload.
    lookup = subprocess.run(['gh', 'api', f'repos/{repo}/releases/tags/{TAG}'], capture_output=True, text=True)
    release = json.loads(lookup.stdout)
    if lookup.returncode:
        if str(release.get('status')) == '404':
            release = None
        else:
            raise RuntimeError('Cannot read GitHub release metadata')
    if release is None:
        subprocess.run(['gh', 'release', 'create', TAG, '--repo', repo, '--draft',
                        '--target', manifest['source_commit'], '--title', 'Arch package repository',
                        '--notes', 'Rolling pacman repository. Package files are immutable; the database advances after all packages upload.'], check=True)
        assets = {}
    else:
        assets = {asset['name']: asset for asset in release['assets']}
    for entry in manifest['packages'].values():
        filename = entry['filename']
        if filename in assets:
            # Never overwrite an existing package filename with different bytes.
            digest = assets[filename].get('digest')
            if digest != 'sha256:' + entry['sha256']:
                raise RuntimeError(f'{filename}: existing release asset differs or lacks a verifiable digest')
            continue
        subprocess.run(['gh', 'release', 'upload', TAG, str(output / filename), '--repo', repo], check=True)
    # Retain old package archives for clients holding an older database.
    for filename in ('arch-packages.files.tar.gz', 'arch-packages.files',
                     'arch-packages.db.tar.gz', 'arch-packages.db', 'manifest.json'):
        subprocess.run(['gh', 'release', 'upload', TAG, str(output / filename), '--repo', repo, '--clobber'], check=True)
    subprocess.run(['gh', 'release', 'edit', TAG, '--repo', repo, '--draft=false'], check=True)
    print(f'Published https://github.com/{repo}/releases/tag/{TAG}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'publish'))
    parser.add_argument('--repo', required=True, help='GitHub OWNER/REPOSITORY')
    parser.add_argument('--output', default='dist', type=pathlib.Path)
    args = parser.parse_args()
    if len(args.repo.split('/')) != 2 or any(not part.replace('-', '').replace('_', '').replace('.', '').isalnum() for part in args.repo.split('/')):
        parser.error('invalid repository name')
    (build if args.command == 'build' else publish)(args.repo, args.output.resolve())
