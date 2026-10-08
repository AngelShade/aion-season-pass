"""Check source installation/upgrade/restore on copies of the supported source."""
import argparse
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inventory_tool as tool

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', type=Path, required=True,
                    help='Unpatched matching server source root at manifest referenceCommit')
args, remaining = parser.parse_known_args()
BASELINE = {name: (args.source_root / name).read_bytes() for name in tool.SOURCE_FILES + [tool.CONFIG]}
PACKAGE = tool.KIT


class StoragePackage(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='storage-source-check-')
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.root = base / 'source'
        self.kit = base / 'kit'
        (self.kit / 'server').mkdir(parents=True)
        for name in ['inventory-only.patch', 'warehouse-expansion.patch']:
            shutil.copyfile(PACKAGE / 'server' / name, self.kit / 'server' / name)
        for name, data in BASELINE.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (self.root / 'pom.xml').write_bytes(b'<project/>')
        self.addCleanup(patch.stopall)
        patch.object(tool, 'KIT', self.kit).start()

    def contents(self):
        return {name: (self.root / name).read_bytes() for name in BASELINE}

    def latest_backup(self):
        return sorted((self.kit / 'server' / 'backups').iterdir())[-1]

    def test_fresh_and_repeat_restore(self):
        before = self.contents()
        tool.apply_server(self.root)
        installed = self.contents()
        self.assertNotEqual(installed, before)
        tool.apply_server(self.root)
        self.assertEqual(self.contents(), installed)
        self.assertEqual(len(list((self.kit / 'server/backups').iterdir())), 1)
        tool.restore(self.latest_backup(), 'server')
        self.assertEqual(self.contents(), before)

    def test_upgrade_inventory_only(self):
        result = tool.git_apply(self.root, self.kit / 'server/inventory-only.patch')
        self.assertEqual(result.returncode, 0, result.stderr)
        before = self.contents()
        tool.apply_server(self.root)
        self.assertIn(b'EXPANDED_WAREHOUSES', (self.root / tool.SOURCE_FILES[-1]).read_bytes())
        self.assertIn(b'gameserver.warehouse.expanded = true', (self.root / tool.CONFIG).read_bytes())
        tool.restore(self.latest_backup(), 'server')
        self.assertEqual(self.contents(), before)

    def test_crlf_bom_unrelated_settings_preserved(self):
        for name in tool.SOURCE_FILES:
            (self.root / name).write_bytes(BASELINE[name].replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        config = b'\xef\xbb\xbfother.setting = keep\r\n'
        (self.root / tool.CONFIG).write_bytes(config)
        before = self.contents()
        tool.apply_server(self.root)
        updated = (self.root / tool.CONFIG).read_bytes()
        self.assertTrue(updated.startswith(config))
        self.assertNotIn(b'\n', updated.replace(b'\r\n', b''))
        for name in tool.SOURCE_FILES:
            self.assertNotIn(b'\n', (self.root / name).read_bytes().replace(b'\r\n', b''))
        tool.restore(self.latest_backup(), 'server')
        self.assertEqual(self.contents(), before)

    def test_conflict_and_duplicate_setting_do_not_write(self):
        name = 'game-server/src/com/aionemu/gameserver/services/AccountService.java'
        path = self.root / name
        path.write_bytes(path.read_bytes().replace(b'Storage wh = new PlayerStorage', b'Storage different = new PlayerStorage'))
        before = self.contents()
        with self.assertRaisesRegex(ValueError, 'No files changed'):
            tool.apply_server(self.root)
        self.assertEqual(self.contents(), before)
        path.write_bytes(BASELINE[name])
        (self.root / tool.CONFIG).write_bytes(b'gameserver.warehouse.expanded = false\ngameserver.warehouse.expanded = true\n')
        before = self.contents()
        with self.assertRaisesRegex(ValueError, 'Duplicate server setting'):
            tool.apply_server(self.root)
        self.assertEqual(self.contents(), before)

    def test_legacy_inventory_backup_still_restores(self):
        names = tool.INVENTORY_SOURCE_FILES + [tool.CONFIG]
        before = {name: (self.root / name).read_bytes() for name in names}
        result = tool.git_apply(self.root, self.kit / 'server/inventory-only.patch')
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {name: (self.root / name).read_bytes() for name in names}
        backup = tool.backup_files(self.root, before, after, 'server')
        tool.restore(backup, 'server')
        self.assertEqual(self.contents(), BASELINE)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + remaining)
