import os
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'install.sh'
STANZA = ('[arch-packages]\nSigLevel = Optional TrustAll\n'
          'Server = https://github.com/filippov-au/arch-packages/releases/download/packages\n\n')


class ConfigTests(unittest.TestCase):
    def configure(self, original):
        result = subprocess.run(['/bin/bash', '-c', 'source "$1"; configure_repo', 'bash', str(SCRIPT)],
                                input=original, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        return result.stdout

    def test_priority_preservation_and_idempotence(self):
        original = '[options]\nArchitecture = auto\n\n[core]\nInclude = /etc/pacman.d/mirrorlist\n\n[extra]\nInclude = /etc/pacman.d/mirrorlist\n'
        configured = self.configure(original)
        self.assertLess(configured.index('[arch-packages]'), configured.index('[core]'))
        self.assertIn('[extra]\nInclude = /etc/pacman.d/mirrorlist', configured)
        self.assertEqual(configured, self.configure(configured))

    def test_moves_existing_repository_to_first_position(self):
        original = '[options]\nColor\n[core]\nServer = https://example.invalid\n' + STANZA
        result = self.configure(original)
        self.assertEqual(result.count('[arch-packages]'), 1)
        self.assertLess(result.index('[arch-packages]'), result.index('[core]'))

    def test_options_only(self):
        configured = self.configure('[options]\nColor\n')
        self.assertEqual(configured, '[options]\nColor\n\n' + STANZA)
        self.assertEqual(configured, self.configure(configured))

    def test_removes_duplicate_stanzas_and_preserves_other_repositories(self):
        original = ('[options]\nColor\n' + STANZA +
                    '[core]\nServer = https://example.invalid/core\n' + STANZA +
                    '[extra]\nServer = https://example.invalid/extra\n')
        result = self.configure(original)
        self.assertEqual(result.count('[arch-packages]'), 1)
        self.assertIn('[core]\nServer = https://example.invalid/core', result)
        self.assertIn('[extra]\nServer = https://example.invalid/extra', result)
        self.assertEqual(result, self.configure(result))

    def test_invalid_first_section(self):
        for original in ('', '# comment\n', '[core]\nServer = https://example.invalid\n'):
            with self.subTest(original=original):
                with self.assertRaisesRegex(RuntimeError, 'Expected \\[options\\]'):
                    self.configure(original)

    def test_config_validation_backup_and_idempotent_write(self):
        for validation_status in (0, 1):
            with self.subTest(validation_status=validation_status), tempfile.TemporaryDirectory() as temp:
                root = pathlib.Path(temp)
                config = root / 'pacman.conf'
                original = '[options]\nColor\n[core]\nServer = https://example.invalid\n'
                config.write_text(original)
                config.chmod(0o640)
                binaries = root / 'bin'
                binaries.mkdir()
                validator = binaries / 'pacman-conf'
                validator.write_text('#!/bin/bash\n[[ "$1" == --config && -s "$2" && "$3" == --repo-list ]] || exit 99\n'
                                     f'exit {validation_status}\n')
                validator.chmod(0o755)
                command = ['/bin/bash', '-c', 'source "$1"; enable_repo "$2"', 'bash', str(SCRIPT), str(config)]
                env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'])
                result = subprocess.run(command, env=env, capture_output=True, text=True)
                self.assertEqual(list(root.glob('.pacman.conf.*')), [])
                backups = list(root.glob('pacman.conf.backup-*'))
                if validation_status:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(config.read_text(), original)
                    self.assertEqual(backups, [])
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(config.read_text(), self.configure(original))
                    self.assertEqual(config.stat().st_mode & 0o777, 0o640)
                    self.assertEqual(len(backups), 1)
                    self.assertEqual(backups[0].read_text(), original)
                    before = config.stat().st_mtime_ns
                    repeated = subprocess.run(command, env=env, capture_output=True, text=True)
                    self.assertEqual(repeated.returncode, 0, repeated.stderr)
                    self.assertEqual(config.stat().st_mtime_ns, before)
                    self.assertEqual(list(root.glob('pacman.conf.backup-*')), backups)
