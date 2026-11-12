"""The exporter must reject inconsistent evidence before merging or publishing it."""
import copy
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
report = importlib.import_module('report_dv')


class MergeReached(Exception):
    """Stop a valid export before invoking a simulator coverage tool."""


class ExportEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runs = json.loads((ROOT / 'dv/results/target_v1/uvm_runs.json').read_text())
        self.supp = json.loads((ROOT / 'dv/results/target_v1/supplemental_runs.json').read_text())
        for name in ['docs/dv/coverage_model.json', 'docs/dv/testcases.json', 'tools/run_dv.py']:
            self.copy(name)
        for r in self.runs:
            for name in r['source_hashes']:
                self.copy(name)
            self.copy(r['exported_log'], r['log'])
            if r['coverage_file']:
                target = self.root / r['coverage_file']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()
        for name, r in self.supp.items():
            for source in r['sources']:
                self.copy(source)
            self.copy(r['exported_log'], f'build/{name}/run.log')
            (self.root / f'build/{name}/coverage.dat').touch()
        self.current = self.runs[0]['source_hashes']

    def copy(self, source, destination=None):
        dest = self.root / (destination or source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, dest)

    def export(self):
        path = self.root / 'build/target/regression.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.runs))
        for name, r in self.supp.items():
            (self.root / f'build/{name}/result.json').write_text(json.dumps(r))
        with patch.object(report, 'ROOT', self.root), \
             patch.object(report, 'inputs', return_value=self.current), \
             patch.object(report.subprocess, 'check_output', return_value='{}'), \
             patch.object(report.subprocess, 'run', side_effect=MergeReached):
            report.main()

    def reject(self):
        with self.assertRaisesRegex(ValueError, 'Evidence'):
            self.export()

    def test_valid_recorded_evidence_reaches_merge(self):
        with self.assertRaises(MergeReached):
            self.export()

    def test_missing_uvm_completion_rejected(self):
        p = self.root / self.runs[0]['log']
        p.write_text(p.read_text().replace('TEST_COMPLETED|', 'REMOVED_COMPLETION|'))
        self.reject()

    def test_error_log_with_stale_pass_json_rejected(self):
        p = self.root / self.runs[0]['log']
        p.write_text(p.read_text().replace('UVM_ERROR :    0', 'UVM_ERROR :    1'))
        # Match any whitespace formatting used by the pinned UVM report server.
        import re
        p.write_text(re.sub(r'UVM_ERROR\s*:\s*0', 'UVM_ERROR : 1', p.read_text()))
        self.reject()

    def test_missing_assertion_activation_rejected(self):
        p = self.root / self.runs[0]['log']
        p.write_text(p.read_text().replace('ASSERTIONS_ACTIVE|', 'REMOVED_ASSERTIONS|'))
        self.reject()

    def test_json_coverage_disagrees_with_log_rejected(self):
        bins = self.runs[0]['functional_bins']
        bins[next(iter(bins))] += 1
        self.reject()

    def test_duplicate_test_replacing_required_test_rejected(self):
        self.runs[2] = copy.deepcopy(self.runs[1])
        self.reject()

    def test_negative_control_with_unstable_source_rejected(self):
        self.runs[-1]['source_stable'] = False
        self.reject()

    def test_negative_control_timeout_rejected(self):
        self.runs[-1]['timed_out'] = True
        self.reject()

    def test_supplemental_stale_pass_nonzero_exit_rejected(self):
        self.supp['system']['returncode'] = 1
        self.reject()

    def test_supplemental_missing_completion_rejected(self):
        p = self.root / 'build/system/run.log'
        p.write_text(p.read_text().replace('SYS_TEST_COMPLETED|', 'REMOVED_COMPLETION|'))
        self.reject()


if __name__ == '__main__':
    unittest.main()
