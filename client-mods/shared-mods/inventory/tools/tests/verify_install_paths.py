"""Check destination selection without touching an installed client or server."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inventory_tool as tool


class InstallationPaths(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='inventory-paths-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def files(self, root, names):
        for name in names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'path-check fixture')

    def test_blank_input_does_not_choose_current_directory(self):
        with patch('builtins.input', return_value='   '):
            with self.assertRaisesRegex(ValueError, 'No folder entered'):
                tool.ask_path(None, 'Folder:')

    def test_spaces_and_quotes(self):
        root = self.root / 'Aion 4.8 NA'
        root.mkdir()
        with patch('builtins.input', return_value='  "' + str(root) + '"  '):
            self.assertEqual(tool.ask_path(None, 'Folder:'), root.resolve())

    def test_client_root_accepted_subfolders_refused_without_writes(self):
        root = self.root / 'Aion 4.8 NA'
        self.files(root, tool.CLIENT_FILES)
        tool.require_install_root(root, 'client')
        before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
        with patch.object(tool, 'require_client_closed') as closed:
            for name in ['bin64', 'Data', 'L10N']:
                with self.assertRaisesRegex(ValueError, 'Aion GAME folder') as error:
                    tool.install_client(root / name)
                self.assertIn('Missing required files:', str(error.exception))
                self.assertIn('No files changed.', str(error.exception))
            closed.assert_not_called()
        self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_source_root_accepted_module_and_deployment_refused(self):
        root = self.root / 'AionSource'
        self.files(root, ['pom.xml'] + tool.SOURCE_FILES + [tool.CONFIG])
        tool.require_install_root(root, 'server')
        # The module has its own pom.xml: it is still the wrong root.
        self.files(root / 'game-server', ['pom.xml'])
        deployed = self.root / 'Live' / 'game-server'
        self.files(deployed, ['libs/game-server-4.8-SNAPSHOT.jar', 'config/main/custom.properties'])
        with patch.object(tool, 'git_apply') as apply:
            for selected in [root / 'game-server', root / 'game-server' / 'src', deployed]:
                with self.assertRaisesRegex(ValueError, 'top-level SOURCE folder'):
                    tool.apply_server(selected)
            apply.assert_not_called()

    def test_package_and_incomplete_root_refused(self):
        for kind in ['client', 'server']:
            with self.assertRaisesRegex(ValueError, 'Inventory-Only'):
                tool.require_install_root(tool.KIT, kind)
        self.files(self.root, ['pom.xml'])
        with self.assertRaisesRegex(ValueError, 'game-server/src'):
            tool.require_install_root(self.root, 'server')


if __name__ == '__main__':
    unittest.main()
