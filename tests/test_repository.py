import hashlib
import json
import pathlib
import subprocess
import sys
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

    def test_resumes_draft_and_uploads_packages_before_database(self):
        commands = []

        def run(args, **kwargs):
            commands.append(args)
            return subprocess.CompletedProcess(args, 0, json.dumps({'assets': [], 'draft': True}))

        with patch.object(repository.subprocess, 'run', run):
            repository.publish('example/packages', self.output)
        uploads = [args for args in commands if args[:3] == ['gh', 'release', 'upload']]
        self.assertEqual(len(uploads), 10)
        self.assertTrue(all(args[4].endswith('.pkg.tar.zst') for args in uploads[:5]))
        self.assertTrue(all('--clobber' not in args for args in uploads[:5]))
        self.assertTrue(uploads[-2][4].endswith('arch-packages.db'))
        self.assertEqual(commands[-1][-1], '--draft=false')
        self.assertFalse(any(args[:3] == ['gh', 'release', 'create'] for args in commands))
