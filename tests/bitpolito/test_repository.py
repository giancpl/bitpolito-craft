import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('configure_repository', ROOT / 'scripts/bitpolito/configure-repository.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class RepositorySetupTests(unittest.TestCase):
    def test_origin_urls_resolve_fork(self):
        for url in ('git@github.com:giancpl/bitpolito-craft.git', 'https://github.com/giancpl/bitpolito-craft.git',
                    'ssh://git@github.com/giancpl/bitpolito-craft.git', 'https://github.com/giancpl/bitpolito-craft/'):
            self.assertEqual(setup.origin_repository(url), 'giancpl/bitpolito-craft')
        for url in ('https://example.com/a/b', 'git@github.com:invalid', 'https://github.com/a/b/extra'):
            with self.assertRaises(ValueError): setup.origin_repository(url)

    def test_uses_origin_without_consulting_gh_default(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(setup.subprocess, 'check_output', return_value='git@github.com:giancpl/bitpolito-craft.git\n'):
            self.assertEqual(setup.repository(), 'giancpl/bitpolito-craft')
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'BitPolito/bitpolito-craft'}):
            self.assertEqual(setup.repository(), 'BitPolito/bitpolito-craft')

    def test_upstream_is_refused_before_any_mutation(self):
        with patch.object(setup, 'repository', return_value='storytold/deckcraft'), patch.object(setup, 'gh', return_value={'full_name': 'storytold/deckcraft'}) as api:
            with self.assertRaisesRegex(ValueError, 'original upstream'):
                setup.configure()
            api.assert_called_once_with('repos/storytold/deckcraft')

    def test_stale_validation_is_refused_before_any_mutation(self):
        responses = [{'full_name': 'giancpl/bitpolito-craft'}, {'workflow_runs': [{'head_sha': 'old'}]}, {'sha': 'new'}]
        with patch.object(setup, 'repository', return_value='giancpl/bitpolito-craft'), patch.object(setup, 'gh', side_effect=responses) as api:
            with self.assertRaisesRegex(ValueError, 'current main'):
                setup.configure()
            self.assertTrue(all(len(call.args) == 1 for call in api.call_args_list))


if __name__ == '__main__': unittest.main()
