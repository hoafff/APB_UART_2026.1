"""Check which checkout files reach a submission ZIP."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_fpga


class PackageSourcesTest(unittest.TestCase):
    def test_package_only_tracked_sources_and_sealed_build_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            root.mkdir()
            subprocess.run(['git', 'init', '--quiet'], cwd=root, check=True)
            (root / 'README.md').write_text('UART project')
            subprocess.run(['git', 'add', 'README.md'], cwd=root, check=True)
            (root / 'operator-notes.txt').write_text('local lab notes')
            artifact = 'build/fpga/output_files/test.sof'
            (root / artifact).parent.mkdir(parents=True)
            (root / artifact).write_bytes(b'fixture')
            (root / build_fpga.MANIFEST).write_text('{}')
            manifest = {'inputs': {}, 'artifacts': {artifact: build_fpga.sha256(root / artifact)}}
            archive = Path(tmp) / 'submission.zip'
            with patch.object(build_fpga, 'verify_release', return_value=manifest):
                build_fpga.package(root, archive)
            with ZipFile(archive) as files:
                self.assertEqual(set(files.namelist()),
                                 {'README.md', artifact, build_fpga.MANIFEST, 'PACKAGE_SHA256.json'})
