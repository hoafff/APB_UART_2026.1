"""Build/run the non-UVM benches with the same provenance contract as UVM."""
import datetime
import json
import re
import shutil
import subprocess
import time
from run_dv import ROOT,command
from evidence import sources,seal_build,validate_build,bind_run


def run(kind):
    top={'system':'tb_system','controller':'tb_controller','onehot':'tb_tx_onehot'}[kind]
    out=ROOT/'build'/kind
    out.mkdir(parents=True,exist_ok=True)
    run_id=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    run_dir=out/'runs'/run_id
    run_dir.mkdir(parents=True)
    before=sources(ROOT,kind)
    files=[str(ROOT/p) for p in before if p.endswith('.sv')]
    cmd=command('verilator')+['--binary','--timing','--assert','--coverage','-Wno-fatal','--top-module',top,'--Mdir',str(out/'obj'),'-j','1']+files
    binary=out/'obj'/('V'+top)
    started=time.monotonic()
    with (run_dir/'build.log').open('w') as log:
        proc=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    if proc.returncode:
        print((run_dir/'build.log').read_text()[-6000:])
        raise SystemExit(proc.returncode)
    tool=subprocess.check_output(command('verilator')+['--version'],text=True).strip()
    build=seal_build(ROOT,kind,cmd,binary,before,tool)
    (run_dir/'build.json').write_text(json.dumps(build,indent=2)+'\n')
    validate_build(ROOT,build,kind)
    run_cmd=command('verilator')[:-1]+[str(binary),f'+verilator+coverage+file+{run_dir}/coverage.dat']
    timed_out=False
    with (run_dir/'run.log').open('w') as log:
        log.write('EVIDENCE_RUN|'+str(run_dir.relative_to(ROOT))+'|'+build['build_id']+'\n');log.flush()
        try:
            proc=subprocess.run(run_cmd,cwd=run_dir,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            rc=proc.returncode
        except subprocess.TimeoutExpired:
            rc=124;timed_out=True
    text=(run_dir/'run.log').read_text()
    stable=sources(ROOT,kind)==before
    try: validate_build(ROOT,build,kind)
    except ValueError: stable=False
    good=stable and rc==0 and not timed_out and bool(re.search(r'^SYS_TEST_COMPLETED\|checks=[1-9]\d*',text,re.M)) and not any(s in text for s in ['%Error','%Fatal','WATCHDOG'])
    result={'status':'PASS' if good else 'FAIL','returncode':rc,'seconds':time.monotonic()-started,
            'sources':before,'source_stable':stable,'tool':tool,'build_command':cmd,'run_command':run_cmd,
            'scope':'Supplemental RTL simulation; not FPGA hardware','log':str((run_dir/'run.log').relative_to(ROOT)),
            'timed_out':timed_out,'negative_control':None}
    result.update(bind_run(ROOT,build,run_dir))
    result['binary_stable']=stable
    (run_dir/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    # Compatibility pointers; these are not used as artifact identities.
    for name in ['build.json','build.log','run.log','result.json']:
        shutil.copy2(run_dir/name,out/name)
    print(result['status'],kind,'log='+result['log'])
    print(text[-2000:])
    raise SystemExit(0 if good else 1)
