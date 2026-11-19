"""Replay the archived Linux simulation on a host with Windows-style path keys."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PublishedEvidenceTest(unittest.TestCase):
    def test_archive_replay_with_windows_paths_without_resource(self):
        script = """
from pathlib import PureWindowsPath
import sys
sys.modules['resource'] = None
sys.path.insert(0, 'tools')
import check_published_evidence as reader
native_sources = reader.sources
native_artifact = reader.artifact
def win_sources(root, kind):
    return {str(PureWindowsPath(k)): v for k, v in native_sources(root, kind).items()}
def win_artifact(root, path):
    result = native_artifact(root, path)
    result['path'] = str(PureWindowsPath(result['path']))
    return result
reader.sources, reader.artifact = win_sources, win_artifact
reader.main()
"""
        result = subprocess.run([sys.executable, '-X', 'utf8', '-c', script], cwd=ROOT,
                                capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"functional_bins": 833', result.stdout)
