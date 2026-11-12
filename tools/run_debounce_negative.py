#!/usr/bin/env python3
"""Mutation control: tb_system must reject an immediate debounce release.

Only the scratch wrapper is mutated; this run is never merged into coverage.
"""
import datetime
import json
from pathlib import Path
import resource
import subprocess
from run_dv import ROOT,command
from evidence import sha


def main():
    out=ROOT/'build/negative_debounce'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    out.mkdir(parents=True)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    original=ROOT/'rtl/fpga/de2_115_apb_uart_bringup.sv'
    before='else if(debounce_q==DEBOUNCE_CYCLES-1)'
    text=original.read_text()
    assert text.count(before)==1
    mutant=out/'de2_release_mutant.sv'
    mutant.write_text(text.replace(before,'else if(!key_sync[1] || debounce_q==DEBOUNCE_CYCLES-1)'))
    files=[ROOT/p for p in (ROOT/'rtl/modified/pulp_apb_uart_sv/files.f').read_text().splitlines()]
    files += [ROOT/'rtl/fpga/de2_uart_controller.sv',mutant,ROOT/'dv/system/tb_system.sv']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files+[original,Path(__file__).resolve()]}
    cmd=command('verilator')+['--binary','--timing','--assert','-Wno-fatal','--top-module','tb_system','--Mdir',str(out/'obj'),'-j','1']+list(map(str,files))
    with (out/'build.log').open('w') as f:
        proc=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    if proc.returncode: raise SystemExit(proc.returncode)
    binary=out/'obj/Vtb_system'
    run_cmd=command('verilator')[:-1]+[str(binary)]
    timed_out=False
    with (out/'run.log').open('w') as f:
        try: rc=subprocess.run(run_cmd,cwd=out,stdout=f,stderr=subprocess.STDOUT,timeout=180).returncode
        except subprocess.TimeoutExpired: rc=124;timed_out=True
    text=(out/'run.log').read_text()
    stable=all(sha(ROOT/p)==h for p,h in hashes.items())
    detected=stable and rc!=0 and not timed_out and 'SYSTEM_CHECK exact 500000 synchronized samples release' in text
    result={'status':'DETECTED' if detected else 'NOT_DETECTED','sources':hashes,'source_stable':stable,
            'build_command':cmd,'run_command':run_cmd,'returncode':rc,'timed_out':timed_out,
            'binary_sha256':sha(binary),'log':str((out/'run.log').relative_to(ROOT)),
            'log_sha256':sha(out/'run.log'),'coverage_policy':'EXCLUDED: deliberate incorrect wrapper'}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/'build/negative_debounce/latest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],result['log'])
    raise SystemExit(0 if detected else 1)


if __name__=='__main__': main()
