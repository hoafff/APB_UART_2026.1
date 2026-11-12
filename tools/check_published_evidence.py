#!/usr/bin/env python3
"""Verify archived logs/native artifacts after checkout, without running a model.

Executable bytes are not distributed: this validates recorded build bindings and
source/artifact content, not the existence/execution of a binary on this host.
"""
import json
from pathlib import Path
import shutil
import tempfile
import zipfile
from collections import Counter
from unittest.mock import patch
import report_dv
from evidence import sources,source_paths,require,sha


def main():
    root=Path(__file__).resolve().parents[1]
    out=root/'dv/results/target_v2'
    hashes=json.loads((out/'artifact_sha256.json').read_text())
    require(all((out/name).is_file() and sha(out/name)==value for name,value in hashes.items()),'archived artifact hash mismatch')
    runs=json.loads((out/'uvm_runs.json').read_text())
    supp=json.loads((out/'supplemental_runs.json').read_text())
    with tempfile.TemporaryDirectory(prefix='uart-evidence-') as temp:
        scratch=Path(temp)
        names={'docs/dv/testcases.json','docs/dv/coverage_model.json'}
        for kind in ['target','system','controller','onehot']:
            names.update(str(p.relative_to(root)) for p in source_paths(root,kind))
        for name in names:
            p=scratch/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,p)
        with zipfile.ZipFile(out/'run_artifacts.zip') as z:
            require(z.testzip() is None,'archive CRC')
            require(len(z.namelist())==len(set(z.namelist())),'duplicate archive member')
            for info in z.infolist():
                p=(scratch/info.filename).resolve()
                require(p.is_relative_to(scratch) and not info.is_dir(),'invalid archive member')
                p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(info))
        with patch.object(report_dv,'ROOT',scratch):
            validation=report_dv.validate_evidence(runs,supp,sources(scratch,'target'),check_binary=False)
        ledger=Counter()
        for r in runs:
            if not r['negative_control']:ledger.update(r['functional_bins'])
        import re
        for r in supp.values():
            text=(scratch/r['log']).read_text()
            for pattern in [r'^COV\|([^|]+)\|(\d+)$',r'^SYS_COV\|([^|]+)\|(\d+)$']:
                ledger.update({k:int(v) for k,v in re.findall(pattern,text,re.M)})
        published=json.loads((out/'functional_coverage.json').read_text())
        require(dict(ledger)==published['observed_counts'],'published functional ledger mismatch')
        model=json.loads((root/'docs/dv/coverage_model.json').read_text())
        bins=[b for group in model['groups'].values() for b in group]
        require(all(ledger[b]>0 for b in bins),'missing mandatory functional bin')
        validation.update(scope='Archived evidence integrity only; no simulation or binary replay',functional_bins=len(bins))
        print(json.dumps(validation,indent=2))


if __name__=='__main__': main()
