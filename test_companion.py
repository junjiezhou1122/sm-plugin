import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sm_plugin import Error, Preset, Skill, bundle, load_preset, main


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        (self.source / 'SKILL.md').write_text('---\nname: example\ndescription: Test fixture.\n---\nTest.\n')
        self.preset = Preset('id', 'Example', (Skill('example', self.source),))
        self.root = self.base / 'bundles'

    def test_sync_idempotent_and_live_source_updates(self):
        first = bundle(self.preset, self.root)
        second = bundle(self.preset, self.root)
        self.assertEqual(first, second)
        (self.source / 'SKILL.md').write_text('Updated upstream')
        self.assertEqual((first / 'skills/example/SKILL.md').read_text(), 'Updated upstream')
        self.assertEqual({p.name for p in self.root.iterdir()}, {first.name, '.sm-plugin-owned'})

    def test_membership_changes_keep_previous_launch_snapshot(self):
        old = bundle(self.preset, self.root)
        new = bundle(Preset('id', 'Example', ()), self.root)
        self.assertNotEqual(old, new)
        self.assertTrue((old / 'skills/example').is_symlink())
        self.assertEqual(list((new / 'skills').iterdir()), [])

    def test_unmanaged_data_is_never_deleted(self):
        self.root.mkdir()
        sentinel = self.root / 'precious.txt'
        sentinel.write_text('keep')
        with self.assertRaises(Error):
            bundle(self.preset, self.root)
        self.assertEqual(sentinel.read_text(), 'keep')
        self.assertEqual(list(self.root.iterdir()), [sentinel])

    def test_changed_bundle_is_refused_without_repair(self):
        path = bundle(self.preset, self.root)
        unmanaged = path / 'skills/keep.txt'
        unmanaged.write_text('keep')
        with self.assertRaises(Error):
            bundle(self.preset, self.root)
        self.assertEqual(unmanaged.read_text(), 'keep')

    def test_concurrent_sync_same_and_distinct_profiles(self):
        bundle(self.preset, self.root)
        presets = [self.preset, Preset('other', 'Other', ())] * 10
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            paths = list(pool.map(lambda p: bundle(p, self.root), presets))
        self.assertEqual(len(set(paths)), 2)
        self.assertTrue((paths[0] / 'skills/example').is_symlink())
        self.assertEqual(list((paths[1] / 'skills').iterdir()), [])

    def test_concurrent_first_sync(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            paths = list(pool.map(lambda _: bundle(self.preset, self.root), range(20)))
        self.assertEqual(len(set(paths)), 1)
        self.assertTrue((paths[0] / 'skills/example').is_symlink())

    def test_malformed_records_fail_cleanly(self):
        for records in [[None], [{'id': 1, 'name': 'Example'}]]:
            with patch('sm_plugin.read_cli', return_value=records):
                with self.assertRaises(Error):
                    load_preset('fixture', 'Example')
        with patch('sm_plugin.read_cli', side_effect=[[{'id': 'id', 'name': 'Example'}], [None]]):
            with self.assertRaises(Error):
                load_preset('fixture', 'Example')

    def test_codex_arguments_are_not_silently_ignored(self):
        with patch('sm_plugin.load_preset', return_value=self.preset):
            with self.assertRaisesRegex(Error, 'no forwarded arguments'):
                main(['--root', str(self.root), 'launch', 'codex', 'Example',
                      '--executable', 'codex', '--dry-run', '--', '--model', 'example'])

    def test_unsafe_skill_names_rejected_before_write(self):
        for name in ['../escape', '/absolute', '.', '..', 'a/b', 'a\\b', '']:
            with self.subTest(name=name):
                with patch('sm_plugin.read_cli', side_effect=[[{'id': 'id', 'name': 'Example'}],
                        [{'name': name, 'path': str(self.source)}]]):
                    with self.assertRaises(Error):
                        load_preset('fixture', 'Example')
        self.assertFalse(self.root.exists())

    def test_preset_names_never_become_paths(self):
        path = bundle(Preset('../escape', '../../name', ()), self.root)
        self.assertEqual(path.parent, self.root)
        self.assertFalse((self.base / 'escape').exists())

    def test_exclusive_refused_before_cli_access(self):
        with patch('sm_plugin.read_cli') as read:
            with self.assertRaisesRegex(Error, 'Exclusive'):
                main(['launch', 'claude', 'Example', '--mode', 'exclusive'])
            read.assert_not_called()

    def test_global_directory_write_refused(self):
        with self.assertRaises(Error):
            bundle(self.preset, Path.home() / '.claude/companion')

    def test_symlink_root_refused(self):
        target = self.base / 'unmanaged'
        target.mkdir()
        self.root.symlink_to(target, target_is_directory=True)
        with self.assertRaises(Error):
            bundle(self.preset, self.root)
        self.assertEqual(list(target.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
