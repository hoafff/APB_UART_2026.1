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
        from evidence import source_paths,sources,seal_build,bind_run,digest
        for name in ['docs/dv/coverage_model.json','docs/dv/testcases.json']:
            self.copy(name)
        for kind in ['target','system','controller','onehot']:
            for path in source_paths(ROOT,kind): self.copy(str(path.relative_to(ROOT)))
        self.current=sources(self.root,'target')
        builds={}
        for kind in ['target','system','controller','onehot']:
            binary=self.root/f'build/{kind}/obj/synthetic_binary'
            binary.parent.mkdir(parents=True,exist_ok=True);binary.write_bytes(b'unit-test executable identity')
            dep_sources={'src/fixture.sv':'a'*64}
            dep={'revision':self.runs[0]['uvm_commit'],'sources':dep_sources,'digest':digest(dep_sources)} if kind=='target' else None
            builds[kind]=seal_build(self.root,kind,['verilator','--timing','--assert','--coverage'],binary,
                                   sources(self.root,kind),self.runs[0]['tool'],dep)
        for kind,r in [('target',r) for r in self.runs]+list(self.supp.items()):
            self.copy(r['exported_log'],r['log'])
            run_dir=(self.root/r['log']).parent
            # Deliberately tiny synthetic native artifacts; this suite tests integrity,
            # while the integration regression exercises the actual Verilator merge.
            if r.get('negative_control')!='NEGATIVE_APB_PROTOCOL':
                (run_dir/'coverage.dat').write_text("# SystemC::Coverage-3\nC 'unit fixture' 1\n")
            build=builds[kind]
            log=run_dir/'run.log'
            log.write_text('EVIDENCE_RUN|'+str(run_dir.relative_to(self.root))+'|'+build['build_id']+'\n'+log.read_text())
            r.update(bind_run(self.root,build,run_dir,r.get('negative_control')))
            r['tool']=build['tool'];r['source_stable']=True
            if kind=='target':r['source_hashes']=self.current
            else:r['sources']=sources(self.root,kind)

    def copy(self, source, destination=None):
        dest = self.root / (destination or source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, dest)

    def export(self):
        with patch.object(report,'ROOT',self.root):
            return report.validate_evidence(self.runs,self.supp,self.current)

    def reject(self):
        with self.assertRaisesRegex(ValueError, 'Evidence'):
            self.export()

    def test_valid_evidence_accepted(self):
        self.assertEqual(self.export()['result'],'PASS_EVIDENCE_CHECK')

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

    def test_binary_identity_mismatch_rejected(self):
        self.runs[0]['binary_sha256']='0'*64
        self.reject()

    def test_uvm_tool_identity_mismatch_rejected(self):
        self.runs[0]['uvm_commit']='0'*40
        self.runs[0]['tool']='unrelated simulator'
        self.reject()

    def test_empty_supplemental_sources_rejected(self):
        self.supp['system']['sources']={}
        self.reject()

    def test_negative_coverage_substitution_rejected(self):
        self.runs[0]['coverage_file']=self.runs[-2]['coverage_file']
        self.reject()

    def test_duplicate_coverage_substitution_rejected(self):
        self.runs[1]['coverage_file']=self.runs[0]['coverage_file']
        self.reject()

    def test_binary_replaced_after_build_rejected(self):
        p=self.root/self.runs[0]['build']['binary']['path']
        p.write_bytes(b'stale executable')
        self.reject()

    def test_coverage_modified_rejected(self):
        (self.root/self.runs[0]['coverage_file']).write_text('stale native coverage')
        self.reject()

    def test_foreign_coverage_rehashed_rejected(self):
        from evidence import artifact
        p=self.root/self.runs[0]['coverage_file']
        p.write_bytes((self.root/self.runs[-2]['coverage_file']).read_bytes())
        self.runs[0]['coverage_artifact']=artifact(self.root,p)
        self.reject()

    def test_empty_coverage_rejected(self):
        (self.root/self.runs[0]['coverage_file']).write_bytes(b'')
        self.reject()

    def test_incomplete_supplemental_sources_rejected(self):
        self.supp['system']['sources'].pop(next(iter(self.supp['system']['sources'])))
        self.reject()

    def test_edited_build_manifest_rejected(self):
        self.runs[0]['build']['flags']['assert']=False
        self.reject()

    def test_no_assert_flag_even_with_new_digest_rejected(self):
        from evidence import digest
        build=self.runs[0]['build']
        build['command'].remove('--assert')
        build['build_id']=digest({k:v for k,v in build.items() if k!='build_id'})
        self.runs[0]['build_id']=build['build_id']
        self.reject()

    def test_missing_native_payload_even_rehashed_rejected(self):
        from evidence import artifact
        p=self.root/self.runs[0]['coverage_file']
        p.write_text('\n'.join(line for line in p.read_text().splitlines() if not line.startswith("C '")))
        self.runs[0]['coverage_artifact']=artifact(self.root,p)
        self.reject()

    def test_log_run_binding_even_rehashed_rejected(self):
        from evidence import artifact
        p=self.root/self.runs[0]['log']
        p.write_text(p.read_text().replace('EVIDENCE_RUN|','FOREIGN_RUN|'))
        self.runs[0]['log_artifact']=artifact(self.root,p)
        self.reject()


if __name__ == '__main__':
    unittest.main()
