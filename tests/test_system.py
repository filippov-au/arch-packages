import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from system import update_backend


class DetectionTests(unittest.TestCase):
    def detect(self, release, commands):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / 'os-release'
            path.write_text(release)
            return update_backend(path, lambda command: '/usr/bin/' + command if command in commands else None)

    def test_omarchy(self):
        self.assertEqual(self.detect('ID=omarchy\nID_LIKE=arch\n', {'omarchy', 'pacman'}), 'omarchy')

    def test_legacy_omarchy(self):
        self.assertEqual(self.detect('ID=arch\n', {'omarchy', 'pacman'}), 'omarchy')

    def test_arch(self):
        self.assertEqual(self.detect('ID=arch\n', {'pacman'}), 'pacman')

    def test_arch_derivative(self):
        self.assertEqual(self.detect('ID=derivative\nID_LIKE="arch linux"\n', {'pacman'}), 'pacman')

    def test_missing_omarchy_command_must_not_bypass_guard(self):
        with self.assertRaisesRegex(RuntimeError, 'omarchy command is missing'):
            self.detect('ID=omarchy\nID_LIKE=arch\n', {'pacman'})

    def test_unsupported_distribution(self):
        with self.assertRaisesRegex(RuntimeError, 'supports Arch'):
            self.detect('ID=ubuntu\nID_LIKE=debian\n', {'pacman'})


class InstallerTests(unittest.TestCase):
    def run_installer(self, backend, update_status=0):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            shutil.copy2(ROOT / 'install.sh', root / 'install.sh')
            binaries = root / 'bin'
            binaries.mkdir()
            scripts = {
                'python': '[[ "$1" == scripts/system.py ]] || exit 99\nprintf "%s\\n" "$TEST_BACKEND"\n',
                'sudo': 'printf "sudo %s\\n" "$*" >> "$TEST_LOG"\n',
                'omarchy': 'printf "omarchy %s\\n" "$*" >> "$TEST_LOG"\nexit "$TEST_UPDATE_STATUS"\n',
            }
            for name, body in scripts.items():
                path = binaries / name
                path.write_text('#!/bin/bash\n' + body)
                path.chmod(0o755)
            log = root / 'commands.log'
            env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'],
                       TEST_BACKEND=backend, TEST_LOG=str(log), TEST_UPDATE_STATUS=str(update_status))
            result = subprocess.run(['/bin/bash', str(root / 'install.sh'), 'orca'], env=env, capture_output=True, text=True)
            return result, log.read_text().splitlines()

    def test_omarchy_updates_before_explicit_install(self):
        result, commands = self.run_installer('omarchy')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands, ['sudo python scripts/enable-repo.py', 'omarchy update -y',
                                    'sudo pacman -S arch-packages/stably-orca-bin'])

    def test_arch_uses_pacman_system_upgrade(self):
        result, commands = self.run_installer('pacman')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands, ['sudo python scripts/enable-repo.py',
                                    'sudo pacman -Syu arch-packages/stably-orca-bin'])

    def test_failed_omarchy_update_stops_installation(self):
        result, commands = self.run_installer('omarchy', update_status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('pacman' in command for command in commands))
