"""Exercise the document checker CLIs with real inputs and both Python optimization switches."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODES = ('standard', '-O', 'PYTHONOPTIMIZE')


class DocumentChecks(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for folder in ('docs', 'reference', 'rtl', 'dv/uvm', 'dv/system'):
            shutil.copytree(ROOT / folder, self.root / folder)
        (self.root / 'tools').mkdir()
        for script in ('check_spec.py', 'check_dv.py'):
            shutil.copy2(ROOT / 'tools' / script, self.root / 'tools' / script)

    def run_checker(self, script, mode):
        env = os.environ.copy()
        env.pop('PYTHONOPTIMIZE', None)
        cmd = [sys.executable, '-B', '-X', 'utf8']
        if mode == '-O':
            cmd.append('-O')
        elif mode == 'PYTHONOPTIMIZE':
            env['PYTHONOPTIMIZE'] = '1'
        cmd.append(str(self.root / 'tools' / script))
        return subprocess.run(cmd, cwd=self.root, env=env, capture_output=True,
                              encoding='utf-8', timeout=30)

    def assert_rejected(self, script, diagnostic):
        for mode in MODES:
            with self.subTest(script=script, mode=mode):
                result = self.run_checker(script, mode)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(diagnostic, result.stderr)
                self.assertEqual(result.stdout, '')

    def test_valid_inputs_report_the_same_results_in_all_modes(self):
        for script, field, expected in [('check_spec.py', 'passed_checks', 10),
                                        ('check_dv.py', 'actual_top_ports_match_pin_map', 65)]:
            reports = []
            for mode in MODES:
                with self.subTest(script=script, mode=mode):
                    result = self.run_checker(script, mode)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    report = json.loads(result.stdout)
                    self.assertEqual(report[field], expected)
                    self.assertEqual(report['requirements'], 80)
                    reports.append(report)
            for report in reports[1:]:
                self.assertEqual(report, reports[0])

    def test_reversed_clock_pin_direction(self):
        path = self.root / 'docs/spec/pins.json'
        pins = json.loads(path.read_bytes())
        clock = next(p for p in pins if p['port'] == 'CLOCK_50')
        self.assertEqual(clock['direction'], 'input')
        clock['direction'] = 'output'
        path.write_text(json.dumps(pins), encoding='utf-8')
        self.assert_rejected('check_dv.py', 'CLOCK_50')
        self.assert_rejected('check_spec.py', 'CLOCK_50')

    def test_missing_spec_requirement_definition(self):
        path = self.root / 'docs/01_System_Specification.md'
        text = path.read_text(encoding='utf-8')
        definition = '\n| `TGT-APB-01` |'
        self.assertEqual(text.count(definition), 1)
        path.write_text(text.replace(definition, '\n| `BROKEN-APB-01` |'), encoding='utf-8')
        self.assert_rejected('check_spec.py', '80 unique TARGET requirement definitions')


if __name__ == '__main__':
    unittest.main()
