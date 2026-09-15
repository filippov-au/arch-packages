import hashlib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import update
import vendor

DATA = b'verified vendor download'
HASHES = {name: hashlib.new(name, DATA).hexdigest() for name in vendor.ALGORITHMS.values()}


class VendorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)

    def fixture(self, package='proton_pass'):
        directory = self.root / package
        directory.mkdir()
        for name in ('PKGBUILD', '.SRCINFO', '.upstream.json'):
            shutil.copy2(ROOT / package / name, directory / name)
        config = json.loads((directory / '.upstream.json').read_text())
        current = vendor.scalar((directory / 'PKGBUILD').read_text(), 'pkgver')
        version = '9.10.0'
        metadata = (directory / '.SRCINFO').read_text()
        assets = []
        for spec in config['assets']:
            url = vendor.metadata_values(metadata, spec['source'])[0].split('::')[-1].replace(current, version)
            algorithm = 'sha256' if config['provider'] == 'github' else 'sha512'
            assets.append(dict(spec, url=url, algorithm=algorithm, digest=HASHES[algorithm]))
        return directory, config, version, assets

    def test_all_recipes_preserve_packaging_and_local_checksums(self):
        for package in update.PACKAGES:
            with self.subTest(package=package):
                directory, config, version, assets = self.fixture(package)
                before = (directory / 'PKGBUILD').read_text()
                old_metadata = (directory / '.SRCINFO').read_text()
                with patch.object(vendor, 'download_hashes', return_value=HASHES):
                    changes = vendor.prepare(directory, config, version, assets)
                recipe = changes['PKGBUILD'].decode()
                metadata = changes['.SRCINFO'].decode()
                self.assertEqual(vendor.scalar(recipe, 'pkgver'), version)
                self.assertEqual(vendor.scalar(recipe, 'pkgrel'), '1')
                self.assertEqual(recipe.split('package()')[1], before.split('package()')[1])
                self.assertEqual(vendor.metadata_values(metadata, 'depends'), vendor.metadata_values(old_metadata, 'depends'))
                for asset in assets:
                    for checksum in asset['checksums']:
                        key = checksum + asset['source'].removeprefix('source')
                        old_values = vendor.array(before, key)[1]
                        new_values = vendor.array(recipe, key)[1]
                        self.assertEqual(new_values, [HASHES[vendor.ALGORITHMS[checksum]], *old_values[1:]])
                        self.assertEqual(vendor.metadata_values(metadata, key), new_values)
                self.assertEqual((directory / 'PKGBUILD').read_text(), before)

    def test_download_verifies_vendor_checksum(self):
        asset = {'url': 'https://proton.me/example', 'algorithm': 'sha512', 'digest': HASHES['sha512']}
        with patch.object(vendor.urllib.request, 'urlopen', return_value=io.BytesIO(DATA)):
            self.assertEqual(vendor.download_hashes(asset), HASHES)
        with patch.object(vendor.urllib.request, 'urlopen', return_value=io.BytesIO(b'corrupt')):
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                vendor.download_hashes(asset)

    def test_stable_selection_ignores_beta_and_feed_order(self):
        _, config, _, _ = self.fixture()
        def release(version, category='Stable'):
            return {'Version': version, 'CategoryName': category, 'File': [{
                'Identifier': '.deb (Ubuntu/Debian)', 'Url': 'https://proton.me/example',
                'Sha512CheckSum': HASHES['sha512']}]}
        data = {'Releases': [release('10.0.0', 'Beta'), release('1.9.0'), release('1.10.0')]}
        with patch.object(vendor, 'get_json', return_value=data):
            self.assertEqual(vendor.latest(config)[0], '1.10.0')
        data['Releases'][2]['File'][0]['Sha512CheckSum'] = 'invalid'
        with patch.object(vendor, 'get_json', return_value=data), self.assertRaisesRegex(RuntimeError, 'checksum'):
            vendor.latest(config)

    def test_github_requires_stable_release_and_asset_digest(self):
        _, config, _, _ = self.fixture('orca')
        data = {'tag_name': 'v1.2.3', 'draft': False, 'prerelease': False, 'assets': [{
            'name': 'orca-linux.AppImage', 'browser_download_url': 'https://github.com/example',
            'digest': 'sha256:' + HASHES['sha256']}]}
        with patch.object(vendor, 'get_json', return_value=data):
            self.assertEqual(vendor.latest(config)[0], '1.2.3')
            data['prerelease'] = True
            with self.assertRaisesRegex(RuntimeError, 'stable'):
                vendor.latest(config)
            data['prerelease'] = False
            data['assets'][0]['digest'] = None
            with self.assertRaisesRegex(RuntimeError, 'digest'):
                vendor.latest(config)

    def test_changed_vendor_url_rejected_before_download(self):
        directory, config, version, assets = self.fixture()
        assets[0]['url'] = 'https://example.invalid/unreviewed.deb'
        with patch.object(vendor, 'download_hashes') as download:
            with self.assertRaisesRegex(RuntimeError, 'URL differs'):
                vendor.prepare(directory, config, version, assets)
        download.assert_not_called()

    def test_metadata_mismatch_rejected(self):
        directory, config, version, assets = self.fixture()
        (directory / '.SRCINFO').write_text('\tpkgver = 0.0.0\n')
        with self.assertRaisesRegex(RuntimeError, 'version does not match'):
            vendor.prepare(directory, config, version, assets)

    def test_second_architecture_failure_does_not_write_any_files(self):
        directory, _, version, assets = self.fixture('proton_drive')
        before = {p.name: p.read_bytes() for p in directory.iterdir()}
        with patch.object(update, 'ROOT', self.root), patch.object(vendor, 'latest', return_value=(version, assets)):
            with patch.object(vendor, 'download_hashes', side_effect=[HASHES, RuntimeError('checksum mismatch')]):
                with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                    update.update('proton_drive')
        self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})

    def test_noop_and_downgrade_do_not_download(self):
        directory, _, _, assets = self.fixture()
        current = vendor.scalar((directory / 'PKGBUILD').read_text(), 'pkgver')
        for version in (current, '0.0.1'):
            with patch.object(update, 'ROOT', self.root), patch.object(vendor, 'latest', return_value=(version, assets)):
                with patch.object(vendor, 'download_hashes') as download:
                    self.assertFalse(update.update('proton_pass'))
                download.assert_not_called()

    def test_update_writes_verified_version(self):
        directory, _, version, assets = self.fixture()
        with patch.object(update, 'ROOT', self.root), patch.object(vendor, 'latest', return_value=(version, assets)):
            with patch.object(vendor, 'download_hashes', return_value=HASHES):
                self.assertTrue(update.update('proton_pass'))
        self.assertEqual(vendor.scalar((directory / 'PKGBUILD').read_text(), 'pkgver'), version)

    def test_pr_mode_opens_one_pr_per_version(self):
        _, _, version, assets = self.fixture()
        for args in [('init', '-q'), ('config', 'user.name', 'Test Builder'),
                     ('config', 'user.email', 'builder@example.invalid'), ('add', '.'),
                     ('commit', '-qm', 'Initial fixture')]:
            subprocess.run(['git', '-C', str(self.root), *args], check=True)
        original_branch = subprocess.check_output(['git', '-C', str(self.root), 'branch', '--show-current'], text=True).strip()
        real_run = update.run
        created = []
        def run(*args, **kwargs):
            if args[:3] == ('gh', 'pr', 'list'):
                return json.dumps(created).encode()
            if args[:3] == ('gh', 'pr', 'create'):
                body = pathlib.Path(args[args.index('--body-file') + 1]).read_text()
                self.assertIn('vendor-published checksums', body)
                created.append({'url': 'https://example.invalid/pull/1'})
                return b'https://example.invalid/pull/1'
            if args[:2] == ('git', 'push'):
                return b''
            return real_run(*args, **kwargs)
        with patch.object(update, 'ROOT', self.root), patch.object(update, 'run', run):
            with patch.object(vendor, 'latest', return_value=(version, assets)), patch.object(vendor, 'download_hashes', return_value=HASHES):
                self.assertTrue(update.update('proton_pass', pr=True, repo='example/packages'))
                subprocess.run(['git', '-C', str(self.root), 'switch', '-q', original_branch], check=True)
                self.assertFalse(update.update('proton_pass', pr=True, repo='example/packages'))
        self.assertEqual(len(created), 1)


if __name__ == '__main__':
    unittest.main()
