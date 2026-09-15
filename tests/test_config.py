import importlib.util
import pathlib
import sys
import unittest

path = pathlib.Path(__file__).resolve().parents[1] / 'scripts' / 'enable-repo.py'
sys.path.insert(0, str(path.parent))
spec = importlib.util.spec_from_file_location('enable_repo', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ConfigTests(unittest.TestCase):
    def test_priority_preservation_and_idempotence(self):
        original = '[options]\nArchitecture = auto\n\n[core]\nInclude = /etc/pacman.d/mirrorlist\n\n[extra]\nInclude = /etc/pacman.d/mirrorlist\n'
        configured = module.configure(original)
        self.assertLess(configured.index('[arch-packages]'), configured.index('[core]'))
        self.assertIn('[extra]\nInclude = /etc/pacman.d/mirrorlist', configured)
        self.assertEqual(configured, module.configure(configured))

    def test_moves_existing_repository_to_first_position(self):
        original = '[options]\nColor\n[core]\nServer = https://example.invalid\n' + module.STANZA
        result = module.configure(original)
        self.assertEqual(result.count('[arch-packages]'), 1)
        self.assertLess(result.index('[arch-packages]'), result.index('[core]'))
