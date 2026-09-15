"""Prepare binary package updates from vendor feeds without executing recipes."""
import hashlib
import json
import pathlib
import re
import shlex
import urllib.request

ALGORITHMS = {'sha256sums': 'sha256', 'sha512sums': 'sha512', 'b2sums': 'blake2b'}


def version_key(value):
    # These vendors use three numeric components for stable releases.
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', value):
        raise RuntimeError('Unsupported vendor version; review the release manually')
    return tuple(map(int, value.split('.')))


def get_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'arch-packages-update-checker'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def latest(config):
    data = get_json(config['url'])
    if config['provider'] == 'github':
        if data.get('draft') or data.get('prerelease'):
            raise RuntimeError('Expected a stable GitHub release')
        version = data['tag_name'].removeprefix('v')
        version_key(version)
        assets = []
        for spec in config['assets']:
            matches = [asset for asset in data['assets'] if asset['name'] == spec['name']]
            if len(matches) != 1:
                raise RuntimeError('Missing or ambiguous GitHub release asset')
            asset = matches[0]
            digest = asset.get('digest') or ''
            if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
                raise RuntimeError('GitHub asset has no verifiable SHA-256 digest')
            assets.append(dict(spec, url=asset['browser_download_url'], algorithm='sha256', digest=digest[7:]))
        return version, assets
    if config['provider'] != 'proton':
        raise RuntimeError('Unknown vendor provider')
    stable = [release for release in data['Releases'] if release['CategoryName'] == 'Stable']
    if not stable:
        raise RuntimeError('Vendor feed contains no stable releases')
    release = max(stable, key=lambda item: version_key(item['Version']))
    assets = []
    for spec in config['assets']:
        matches = [asset for asset in release[config.get('files_key', 'File')]
                   if all(asset.get(key) == value for key, value in spec['match'].items())]
        if len(matches) != 1:
            raise RuntimeError('Missing or ambiguous Proton release asset')
        asset = matches[0]
        digest = asset.get('Sha512CheckSum') or ''
        if not re.fullmatch(r'[0-9a-f]{128}', digest):
            raise RuntimeError('Proton asset has no verifiable SHA-512 checksum')
        assets.append(dict(spec, url=asset['Url'], algorithm='sha512', digest=digest))
    return release['Version'], assets


def download_hashes(asset):
    print(f"Verifying vendor download: {asset['url']}", flush=True)
    hashes = {name: hashlib.new(name) for name in ALGORITHMS.values()}
    with urllib.request.urlopen(asset['url'], timeout=120) as response:
        while block := response.read(1024 * 1024):
            for digest in hashes.values():
                digest.update(block)
    result = {name: digest.hexdigest() for name, digest in hashes.items()}
    if result[asset['algorithm']] != asset['digest']:
        raise RuntimeError('Vendor download checksum mismatch; package files were not changed')
    return result


def scalar(recipe, key):
    matches = re.findall(r'^' + re.escape(key) + r'=(.*)$', recipe, re.M)
    if len(matches) != 1:
        raise RuntimeError(f'Expected one {key} assignment')
    values = shlex.split(matches[0], comments=True)
    if len(values) != 1:
        raise RuntimeError(f'Unsupported {key} assignment')
    return values[0]


def array(recipe, key):
    matches = list(re.finditer(r'^' + re.escape(key) + r'=\(([^)]*)\)', recipe, re.M))
    if len(matches) != 1:
        raise RuntimeError(f'Expected one simple {key} array')
    return matches[0], shlex.split(matches[0][1], comments=True)


def metadata_values(metadata, key):
    return re.findall(r'^\t' + re.escape(key) + r' = (.*)$', metadata, re.M)


def replace_metadata(metadata, key, values):
    if len(metadata_values(metadata, key)) != len(values):
        raise RuntimeError(f'.SRCINFO {key} does not match recipe; regenerate it first')
    replacements = iter(values)
    return re.sub(r'^(\t' + re.escape(key) + r' = ).*$',
                  lambda match: match[1] + next(replacements), metadata, flags=re.M)


def prepare(directory, config, new_version, assets):
    recipe = (directory / 'PKGBUILD').read_text()
    metadata = (directory / '.SRCINFO').read_text()
    old_version = scalar(recipe, 'pkgver')
    if metadata_values(metadata, 'pkgver') != [old_version]:
        raise RuntimeError('.SRCINFO version does not match recipe')
    variables = {key: scalar(recipe, key) for key in ('pkgname', 'pkgver', 'url')}
    variables['_name'] = variables['pkgname'].removesuffix('-bin')

    def expand(value, version):
        values = dict(variables, pkgver=version)
        def substitute(match):
            key = match[1] or match[2]
            if key not in values:
                raise RuntimeError(f'Unsupported source variable: {key}')
            return values[key]
        result = re.sub(r'\$\{(\w+)\}|\$(\w+)', substitute, value)
        if '$' in result or '`' in result:
            raise RuntimeError('Source requires shell evaluation; review manually')
        return result

    for asset in assets:
        source_key = asset['source']
        _, sources = array(recipe, source_key)
        if not sources or metadata_values(metadata, source_key) != [expand(item, old_version) for item in sources]:
            raise RuntimeError(f'.SRCINFO {source_key} does not match recipe')
        new_sources = [expand(item, new_version) for item in sources]
        # Feed data cannot redirect the updater to a different host or asset.
        if not asset['url'].startswith('https://') or new_sources[0].split('::')[-1] != asset['url']:
            raise RuntimeError('Vendor URL differs from the reviewed recipe; update the source manually')
        hashes = download_hashes(asset)
        metadata = replace_metadata(metadata, source_key, new_sources)
        suffix = source_key.removeprefix('source')
        for checksum in asset['checksums']:
            key = checksum + suffix
            match, values = array(recipe, key)
            if len(values) != len(sources) or metadata_values(metadata, key) != values:
                raise RuntimeError(f'.SRCINFO {key} does not match recipe')
            algorithm = ALGORITHMS[checksum]
            if not re.fullmatch(r'[0-9a-f]+', values[0]):
                raise RuntimeError('Expected a pinned source checksum')
            # Replace only the first checksum; preserve local launcher hashes.
            body = match[1].replace(values[0], hashes[algorithm], 1)
            recipe = recipe[:match.start(1)] + body + recipe[match.end(1):]
            metadata = replace_metadata(metadata, key, [hashes[algorithm], *values[1:]])
    recipe = re.sub(r'^pkgver=.*$', 'pkgver=' + new_version, recipe, flags=re.M)
    recipe = re.sub(r'^pkgrel=.*$', 'pkgrel=1', recipe, flags=re.M)
    metadata = replace_metadata(metadata, 'pkgver', [new_version])
    metadata = replace_metadata(metadata, 'pkgrel', ['1'])
    # Versioned local source filenames and provides also follow pkgver.
    for key in ('noextract', 'provides'):
        values = metadata_values(metadata, key)
        metadata = replace_metadata(metadata, key, [value.replace(old_version, new_version) for value in values])
    return {'PKGBUILD': recipe.encode(), '.SRCINFO': metadata.encode()}
