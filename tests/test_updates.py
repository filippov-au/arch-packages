import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import update


class MergeTests(unittest.TestCase):
    def test_adjacent_checksums_preserve_custom_launcher(self):
        old, new, wrapper, customized = (value * 64 for value in (b'a', b'b', b'c', b'd'))
        base = b"pkgver=1\nsha256sums=('" + old + b"'\n'" + wrapper + b"')\n"
        local = base.replace(wrapper, customized)
        upstream = base.replace(b'pkgver=1', b'pkgver=2').replace(old, new)
        result = update.merge_recipe(local, base, upstream)
        self.assertIn(b'pkgver=2', result)
        self.assertIn(new, result)
        self.assertIn(customized, result)
        self.assertNotIn(wrapper, result)

    def test_same_checksum_changed_both_sides_requires_review(self):
        with self.assertRaises(RuntimeError):
            update.merge_recipe(b'a' * 64, b'b' * 64, b'c' * 64)

    def test_upstream_delete_keeps_conflicting_local_file(self):
        with self.assertRaises(RuntimeError):
            update.merge(b'custom', b'original', None)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = pathlib.Path(self.temp.name)
        self.remote = base / 'upstream'
        self.remote.mkdir()
        self.root = base / 'checkout'
        self.package = self.root / 'orca'
        self.package.mkdir(parents=True)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test Builder')
        self.git('config', 'user.email', 'builder@example.invalid')
        (self.remote / 'PKGBUILD').write_text('pkgname=example\npkgver=1\npkgrel=1\n')
        (self.remote / 'wrapper.sh').write_text('original\n')
        self.commit()
        head = self.git('rev-parse', 'HEAD').strip()
        for name in ('PKGBUILD', 'wrapper.sh'):
            (self.package / name).write_bytes((self.remote / name).read_bytes())
        (self.package / '.upstream.json').write_text(json.dumps({
            'url': str(self.remote), 'commit': head, 'files': ['PKGBUILD', 'wrapper.sh']}))

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.remote), *args], text=True)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'Fixture')

    def test_update_then_noop_preserves_local_change(self):
        (self.package / 'wrapper.sh').write_text('custom wayland launcher\n')
        (self.remote / 'PKGBUILD').write_text('pkgname=example\npkgver=2\npkgrel=1\n')
        self.commit()
        with patch.object(update, 'ROOT', self.root):
            self.assertTrue(update.update('orca'))
            self.assertFalse(update.update('orca'))
        self.assertIn('pkgver=2', (self.package / 'PKGBUILD').read_text())
        self.assertEqual((self.package / 'wrapper.sh').read_text(), 'custom wayland launcher\n')

    def test_conflict_does_not_partially_update_files(self):
        (self.package / 'wrapper.sh').write_text('local\n')
        (self.remote / 'wrapper.sh').write_text('upstream\n')
        (self.remote / 'PKGBUILD').write_text('pkgname=example\npkgver=2\npkgrel=1\n')
        self.commit()
        before = {p.name: p.read_bytes() for p in self.package.iterdir()}
        with patch.object(update, 'ROOT', self.root), self.assertRaises(RuntimeError):
            update.update('orca')
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.package.iterdir()})

    def test_symlink_cannot_escape_package_directory(self):
        (self.remote / 'escape').symlink_to('../../outside')
        self.commit()
        with patch.object(update, 'ROOT', self.root), self.assertRaisesRegex(RuntimeError, 'symlink escapes'):
            update.update('orca')
        self.assertFalse((self.package / 'escape').exists())

    def test_pr_mode_opens_one_pr_and_skips_existing_revision(self):
        for args in [('init', '-q'), ('config', 'user.name', 'Test Builder'),
                     ('config', 'user.email', 'builder@example.invalid'), ('add', '.'),
                     ('commit', '-qm', 'Initial fixture')]:
            subprocess.run(['git', '-C', str(self.root), *args], check=True)
        original_branch = subprocess.check_output(['git', '-C', str(self.root), 'branch', '--show-current'], text=True).strip()
        (self.remote / 'PKGBUILD').write_text('pkgname=example\npkgver=2\npkgrel=1\n')
        self.commit()
        real_run = update.run
        calls = []
        existing = []

        def mocked_run(*args, **kwargs):
            if args[:3] == ('gh', 'pr', 'list'):
                return json.dumps(existing).encode()
            if args[:3] == ('gh', 'pr', 'create'):
                calls.append(args)
                body = pathlib.Path(args[args.index('--body-file') + 1]).read_text()
                self.assertIn('Local customizations', body)
                existing.append({'url': 'https://example.invalid/pull/1'})
                return b'https://example.invalid/pull/1'
            if args[:2] == ('git', 'push'):
                return b''
            return real_run(*args, **kwargs)

        with patch.object(update, 'ROOT', self.root), patch.object(update, 'run', mocked_run):
            self.assertTrue(update.update('orca', pr=True, repo='example/packages'))
            subprocess.run(['git', '-C', str(self.root), 'switch', '-q', original_branch], check=True)
            self.assertFalse(update.update('orca', pr=True, repo='example/packages'))
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
