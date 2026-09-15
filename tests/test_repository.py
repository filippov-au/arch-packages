import hashlib
import io
import json
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import repository


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = pathlib.Path(self.temp.name)
        self.manifest = {'source_commit': 'a' * 40, 'packages': {}}
        for package in repository.PACKAGES:
            data = package.encode()
            name = package + '-1-1-any.pkg.tar.zst'
            (self.output / name).write_bytes(data)
            self.manifest['packages'][package] = {
                'filename': name, 'sha256': hashlib.sha256(data).hexdigest(), 'recipe_sha256': 'b' * 64}
        (self.output / 'manifest.json').write_text(json.dumps(self.manifest))
        self.write_databases()

    def write_databases(self, entries=None, suffixes=('db', 'files')):
        entries = entries if entries is not None else list(self.manifest['packages'].values())
        for suffix in suffixes:
            path = self.output / f'arch-packages.{suffix}.tar.gz'
            with tarfile.open(path, 'w:gz') as archive:
                for index, entry in enumerate(entries):
                    size = entry.get('size', (self.output / entry['filename']).stat().st_size)
                    data = (f"%FILENAME%\n{entry['filename']}\n\n"
                            f"%SHA256SUM%\n{entry['sha256']}\n\n"
                            f"%CSIZE%\n{size}\n\n"
                            f"%DESC%\n{entry.get('description', 'Example package')}\n\n").encode()
                    member = tarfile.TarInfo(f'package-{index}/desc')
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            (self.output / f'arch-packages.{suffix}').write_bytes(path.read_bytes())

    def assert_rejected_before_network(self, message):
        with patch.object(repository.subprocess, 'run') as command:
            with self.assertRaisesRegex(RuntimeError, message):
                repository.publish('example/packages', self.output)
        command.assert_not_called()

    def test_validates_complete_repository(self):
        self.assertEqual(repository.validate(self.output), self.manifest)

    def test_refuses_missing_database_before_network_calls(self):
        (self.output / 'arch-packages.db').unlink()
        self.assert_rejected_before_network('missing database')

    def test_refuses_stale_database_before_network_calls(self):
        self.write_databases(list(self.manifest['packages'].values())[1:])
        self.assert_rejected_before_network('package list differs')

    def test_refuses_stale_database_checksum_before_network_calls(self):
        entries = [dict(entry, sha256='0' * 64) for entry in self.manifest['packages'].values()]
        self.write_databases(entries)
        self.assert_rejected_before_network('checksum or size mismatch')

    def test_refuses_stale_database_size_before_network_calls(self):
        entries = [dict(entry, size=0) for entry in self.manifest['packages'].values()]
        self.write_databases(entries)
        self.assert_rejected_before_network('checksum or size mismatch')

    def test_refuses_mismatched_database_alias_before_network_calls(self):
        (self.output / 'arch-packages.files').write_bytes(b'stale database')
        self.assert_rejected_before_network('alias mismatch')

    def test_refuses_inconsistent_package_descriptions_before_network_calls(self):
        entries = [dict(entry, description='Different description') for entry in self.manifest['packages'].values()]
        self.write_databases(entries, suffixes=('files',))
        self.assert_rejected_before_network('descriptions differ')

    def test_refuses_corrupt_database_before_network_calls(self):
        for name in ('arch-packages.db', 'arch-packages.db.tar.gz'):
            (self.output / name).write_bytes(b'not a tar archive')
        self.assert_rejected_before_network('invalid repository database')

    def test_refuses_duplicate_database_entry_before_network_calls(self):
        entries = list(self.manifest['packages'].values())
        self.write_databases(entries + entries[:1])
        self.assert_rejected_before_network('invalid repository database')

    def test_refuses_duplicate_manifest_filename_before_network_calls(self):
        self.manifest['packages']['proton_pass'] = self.manifest['packages']['orca']
        (self.output / 'manifest.json').write_text(json.dumps(self.manifest))
        self.assert_rejected_before_network('filename validation')

    def test_refuses_artifact_tampering_before_network_calls(self):
        (self.output / self.manifest['packages']['orca']['filename']).write_bytes(b'changed')
        with patch.object(repository.subprocess, 'run') as command:
            with self.assertRaisesRegex(RuntimeError, 'checksum'):
                repository.publish('example/packages', self.output)
        command.assert_not_called()

    def test_refuses_overwriting_existing_package_name(self):
        release = {'assets': [{'name': self.manifest['packages']['orca']['filename'], 'digest': 'sha256:' + '0' * 64}]}
        with patch.object(repository.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(release))) as command:
            with self.assertRaisesRegex(RuntimeError, 'differs'):
                repository.publish('example/packages', self.output)
        self.assertEqual(command.call_count, 1)

    def test_github_cli_failure_has_actionable_error(self):
        with patch.object(repository.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '')) as command:
            with self.assertRaisesRegex(RuntimeError, 'authentication and connectivity'):
                repository.publish('example/packages', self.output)
        self.assertEqual(command.call_count, 1)

    def test_resumes_draft_and_uploads_packages_before_database(self):
        commands = []

        def run(args, **kwargs):
            commands.append(args)
            return subprocess.CompletedProcess(args, 0, json.dumps({'assets': [], 'draft': True}))

        with patch.object(repository.subprocess, 'run', run):
            repository.publish('example/packages', self.output)
        uploads = [args for args in commands if args[:3] == ['gh', 'release', 'upload']]
        self.assertEqual(len(uploads), len(repository.PACKAGES) + 5)
        self.assertTrue(all(args[4].endswith('.pkg.tar.zst') for args in uploads[:len(repository.PACKAGES)]))
        self.assertTrue(all('--clobber' not in args for args in uploads[:len(repository.PACKAGES)]))
        self.assertTrue(uploads[-2][4].endswith('arch-packages.db'))
        self.assertEqual(commands[-1][-1], '--draft=false')
        self.assertFalse(any(args[:3] == ['gh', 'release', 'create'] for args in commands))
