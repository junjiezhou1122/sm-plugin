import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sm_plugin import Error, Preset, Skill, bundle, compose_presets, load_preset, load_presets, main, save_preset


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

    def test_composition_order_and_canonical_path_deduplication(self):
        alias = self.base / 'alias'
        alias.symlink_to(self.source, target_is_directory=True)
        other_source = self.base / 'other'
        other_source.mkdir()
        (other_source / 'SKILL.md').write_text('Other skill')
        other = Preset('other', 'Other', (Skill('example', alias), Skill('other', other_source)))
        first = compose_presets([self.preset, other])
        second = compose_presets([other, self.preset, other])
        self.assertEqual(first, second)
        self.assertEqual(first.skills, (Skill('example', self.source.resolve()), Skill('other', other_source.resolve())))
        path = bundle(first, self.root)
        self.assertEqual(path, bundle(second, self.root))
        manifest = json.loads((path / 'manifest.json').read_text())
        self.assertEqual(manifest['presets'], [{'id': 'id', 'name': 'Example'},
                                              {'id': 'other', 'name': 'Other'}])
        self.assertEqual(len(list((path / 'skills').iterdir())), 2)
        (path / 'skills/other').unlink()
        with self.assertRaisesRegex(Error, 'skill folders differ'):
            bundle(second, self.root)

    def test_composition_rejects_distinct_paths_with_case_insensitive_name(self):
        other_source = self.base / 'other'
        other_source.mkdir()
        other = Preset('other', 'Other', (Skill('EXAMPLE', other_source),))
        for presets in ([self.preset, other], [other, self.preset]):
            with self.assertRaisesRegex(Error, 'Skill name collision') as caught:
                compose_presets(presets)
            self.assertIn(str(self.source.resolve()), str(caught.exception))
            self.assertIn(str(other_source.resolve()), str(caught.exception))
        self.assertFalse(self.root.exists())

    def test_single_selection_preserves_original_bundle_manifest(self):
        self.assertEqual(compose_presets([self.preset, self.preset]), self.preset)
        path = bundle(compose_presets([self.preset]), self.root)
        manifest = json.loads((path / 'manifest.json').read_text())
        self.assertEqual(manifest, {'format': 1, 'preset_id': 'id', 'preset_name': 'Example',
                                   'mode': 'additive', 'skills': [{'name': 'example', 'path': str(self.source)}]})
        self.assertEqual(path, bundle(self.preset, self.root))

    def test_multiple_selectors_sync_launch_and_verify(self):
        other = Preset('other', 'Other preset', ())
        for command in ('sync', 'launch', 'verify'):
            with self.subTest(command=command):
                argv = ['--root', str(self.root), command]
                if command != 'sync':
                    argv += ['claude', '--cwd', str(self.base)]
                argv += ['Example', 'Other preset']
                if command != 'sync':
                    argv += ['--executable', 'fixture-claude']
                if command == 'launch':
                    argv += ['--', '--model', 'example']
                with patch('sm_plugin.load_preset', side_effect=[self.preset, other]) as load:
                    with patch('sm_plugin.subprocess.call', return_value=0) as call:
                        with patch('builtins.print'):
                            self.assertEqual(main(argv), 0)
                    self.assertEqual([c.args[1] for c in load.call_args_list], ['Example', 'Other preset'])
                if command == 'launch':
                    self.assertEqual(call.call_args.args[0][-2:], ['--model', 'example'])
                elif command == 'verify':
                    self.assertEqual(call.call_args.args[0][1:4], ['plugin', 'validate', '--json'])

    def test_composed_dry_run_reports_contributors_and_preserves_forwarding(self):
        other = Preset('other', 'Other preset', ())
        with patch('sm_plugin.load_preset', side_effect=[self.preset, other]):
            with patch('builtins.print') as output:
                self.assertEqual(main(['--root', str(self.root), 'launch', 'claude',
                                      'Example', 'Other preset', '--cwd', str(self.base),
                                      '--executable', 'fixture-claude', '--dry-run',
                                      '--', '--model', 'example']), 0)
        result = json.loads(output.call_args.args[0])
        self.assertEqual(result['presets'], [{'id': 'id', 'name': 'Example'},
                                            {'id': 'other', 'name': 'Other preset'}])
        self.assertEqual(result['skill_count'], 1)
        self.assertEqual(result['extra_args'], ['--model', 'example'])

    def record(self, skill_id='skill-id', name='example', tags=()):
        return {'id': skill_id, 'name': name, 'path': str(self.source), 'tags': list(tags)}

    def test_tags_exact_match_and_archived_filter(self):
        records = [self.record(tags=['deli']),
                   self.record('archived-id', 'archived', ['deli', 'archived']),
                   self.record('wrong-id', 'wrong', ['Deli'])]
        with patch('sm_plugin.read_cli', side_effect=[['deli', 'archived'], records]):
            selected = load_presets('fixture', [], ['deli'])
        self.assertEqual(selected.skills, (Skill('example', self.source.resolve(), 'skill-id'),))
        self.assertEqual(selected.tags, ('deli',))
        path = bundle(selected, self.root)
        self.assertEqual(json.loads((path / 'manifest.json').read_text())['tags'], ['deli'])
        with patch('sm_plugin.read_cli', side_effect=[['archived'], [records[1]]]):
            self.assertEqual(load_presets('fixture', [], ['archived']).skills, ())

    def test_preset_tag_union_deduplicates_ids_and_is_order_independent(self):
        preset = Preset('id', 'Example', (Skill('example', self.source.resolve(), 'skill-id'),))
        def read(cli, *args):
            if args == ('skills', 'tag', 'list'):
                return ['deli', 'research']
            return [self.record(tags=['deli', 'research'])]
        with patch('sm_plugin.load_preset', return_value=preset), patch('sm_plugin.read_cli', side_effect=read):
            first = load_presets('fixture', ['Example'], ['research', 'deli'])
            second = load_presets('fixture', ['Example', 'Example'], ['deli', 'research', 'deli'])
        self.assertEqual(first, second)
        self.assertEqual(first.skills, preset.skills)
        self.assertEqual(first.presets, (('id', 'Example'),))
        self.assertEqual(first.tags, ('deli', 'research'))

    def test_unknown_tag_and_no_selectors_fail_before_writes(self):
        with patch('sm_plugin.read_cli', return_value=['deli']) as read:
            with self.assertRaisesRegex(Error, 'Unknown tag'):
                load_presets('fixture', [], ['Deli'])
            self.assertEqual(read.call_count, 1)
        for argv in (['sync'], ['launch', 'codex'], ['verify', 'codex'], ['save', 'New']):
            with patch('sm_plugin.read_cli', return_value=[]) as read:
                with self.assertRaisesRegex(Error, 'at least one'):
                    main(['--root', str(self.root), *argv])
                self.assertTrue(all('create' not in call.args for call in read.call_args_list))
        self.assertFalse(self.root.exists())

    def test_tag_only_sync_launch_and_verify(self):
        selected = Preset('composition:tags', 'tag:deli', self.preset.skills, tags=('deli',))
        for command in ('sync', 'launch', 'verify'):
            argv = ['--root', str(self.root), command]
            if command != 'sync':
                argv += ['claude', '--executable', 'fixture-claude', '--cwd', str(self.base)]
            argv += ['--tag', 'deli', '--tag', 'research']
            if command == 'launch':
                argv += ['--dry-run']
            with patch('sm_plugin.load_presets', return_value=selected) as load, \
                    patch('sm_plugin.subprocess.call', return_value=0), patch('builtins.print') as output:
                self.assertEqual(main(argv), 0)
                self.assertEqual(load.call_args.args[1:], ([], ['deli', 'research']))
                if command == 'launch':
                    result = json.loads(output.call_args.args[0])
                    self.assertEqual(result['tags'], ['deli'])
                    self.assertEqual(result['presets'], [])

    def test_save_writes_exact_ids_and_description_without_bundle(self):
        selected = Preset('id', 'Example', (Skill('example', self.source.resolve(), 'skill-id'),))
        with patch('sm_plugin.load_presets', return_value=selected), \
                patch('sm_plugin.read_cli', side_effect=[[], [self.record()], {'id': 'new-id'}, {}]) as read, \
                patch('builtins.print'):
            self.assertEqual(main(['--root', str(self.root), 'save', 'New', 'Example',
                                   '--tag', 'deli', '--description', 'Snapshot']), 0)
        self.assertEqual([call.args[1:] for call in read.call_args_list], [
            ('presets', 'list'), ('skills', 'list'),
            ('presets', 'create', 'New', '--description', 'Snapshot'),
            ('presets', 'add-skill', 'new-id', 'skill-id')])
        self.assertFalse(self.root.exists())

    def test_save_dry_run_is_read_only_and_reports_ids_names(self):
        selected = Preset('composition:tags', 'tag:deli',
                          (Skill('example', self.source.resolve(), 'skill-id'),), tags=('deli',))
        with patch('sm_plugin.load_presets', return_value=selected), \
                patch('sm_plugin.read_cli', side_effect=[[], [self.record()]]) as read, \
                patch('builtins.print') as output:
            self.assertEqual(save_preset('fixture', 'New', [], ['deli'], dry_run=True), 0)
        self.assertEqual([call.args[1:] for call in read.call_args_list], [('presets', 'list'), ('skills', 'list')])
        result = json.loads(output.call_args.args[0])
        self.assertEqual(result['skills'], [{'id': 'skill-id', 'name': 'example'}])
        self.assertEqual(result['tags'], ['deli'])
        self.assertTrue(result['dry_run'])
        self.assertFalse(self.root.exists())

    def test_save_existing_name_refused_before_selection_or_mutation(self):
        with patch('sm_plugin.read_cli', return_value=[{'id': 'existing', 'name': 'New'}]) as read, \
                patch('sm_plugin.load_presets') as load:
            with self.assertRaisesRegex(Error, 'already exists'):
                save_preset('fixture', 'New', ['Example'])
            read.assert_called_once_with('fixture', 'presets', 'list')
            load.assert_not_called()

    def test_save_empty_missing_id_and_changed_id_refused(self):
        for skills, records, message in [
                ((), [], 'empty selection'),
                (self.preset.skills, [self.record()], 'missing or changed'),
                ((Skill('example', self.source.resolve(), 'skill-id'),), [], 'missing or changed')]:
            with patch('sm_plugin.load_presets', return_value=Preset('id', 'Example', skills)), \
                    patch('sm_plugin.read_cli', side_effect=[[], records]) as read:
                with self.assertRaisesRegex(Error, message):
                    save_preset('fixture', 'New', ['Example'])
                self.assertTrue(all('create' not in call.args for call in read.call_args_list))

    def test_save_collision_refused_before_create(self):
        other = self.base / 'other'
        other.mkdir()
        (other / 'SKILL.md').write_text('Other')
        records = [self.record(), {'id': 'other-id', 'name': 'EXAMPLE', 'path': str(other)}]
        with patch('sm_plugin.read_cli', side_effect=[[], [{'id': 'id', 'name': 'Example'}], records]) as read:
            with self.assertRaisesRegex(Error, 'Duplicate skill folder'):
                save_preset('fixture', 'New', ['Example'])
            self.assertTrue(all('create' not in call.args for call in read.call_args_list))

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
