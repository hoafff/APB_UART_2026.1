#!/usr/bin/env python3
"""Reproducible UVM build/run. Zero exit alone is never a PASS."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,re,shutil,subprocess,sys,time,resource
from evidence import sources,uvm_identity,seal_build,validate_build,bind_run,require
ROOT=Path(__file__).resolve().parents[1]
UVM_COMMIT='656f20d087370a7c742e00188d20bbf30fa95339'
TESTS=['target_apb_test','target_tx_modes_test','target_rx_modes_test','target_tolerance_test',
       'target_errors_test','target_fifo_test','target_irq_test','target_reset_test',
       'target_snapshot_test','target_baud_test','target_false_start_test','target_concurrency_test']
def command(tool):
    suite=os.environ.get('OSS_CAD_SUITE')
    if suite:
        return [str(Path(suite)/'bin'/tool)]
    if shutil.which(tool): return [tool]
    wrapper=Path.home()/'.local/bin/ic-eda'
    if wrapper.exists(): return [str(wrapper),tool]
    raise SystemExit(f'Missing {tool}. Set OSS_CAD_SUITE or install OSS CAD Suite; see dv/README.md')
def dependency():
    uvm=Path(os.environ.get('UVM_HOME',str(ROOT/'.tools/uvm'))).resolve()
    if not (uvm/'src/uvm_pkg.sv').exists():
        if 'UVM_HOME' in os.environ: raise SystemExit('UVM_HOME lacks src/uvm_pkg.sv')
        uvm.mkdir(parents=True,exist_ok=True)
        for args in [['git','init',str(uvm)],['git','-C',str(uvm),'remote','add','origin','https://github.com/verilator/uvm.git'],
                     ['git','-C',str(uvm),'fetch','--depth','1','origin',UVM_COMMIT],['git','-C',str(uvm),'checkout','--detach','FETCH_HEAD']]:
            subprocess.run(args,check=True,stdout=subprocess.DEVNULL)
    revision=subprocess.check_output(['git','-C',str(uvm),'rev-parse','HEAD'],text=True).strip()
    if revision!=UVM_COMMIT: raise SystemExit(f'Expected pinned UVM {UVM_COMMIT}, got {revision}')
    return uvm

def inputs():
    return sources(ROOT,'target')
def build():
    uvm=dependency(); out=ROOT/'build/target'; out.mkdir(parents=True,exist_ok=True)
    if (out/'build.log').exists():
        history=out/'build_history'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        history.mkdir(parents=True)
        for name in ['build.log','build.json']:
            if (out/name).exists(): shutil.copy2(out/name,history/name)
    cmd=command('verilator')+['--binary','--timing','--assert','--coverage','--trace-fst','-Wno-fatal',
        '--top-module','tb_top','+define+UVM_NO_DPI',f'+incdir+{uvm}/src',f'+incdir+{ROOT}/dv/uvm/include',
        str(uvm/'src/uvm_pkg.sv'),'-f','rtl/modified/pulp_apb_uart_sv/files.f',
        'dv/uvm/uart_apb_if.sv','dv/assertions/apb_uart_assertions.sv','dv/uvm/apb_uart_uvm_pkg.sv','dv/uvm/tb_top.sv',
        '--Mdir',str(out/'obj'),'--output-groups','64','--output-split','10000','-CFLAGS','-O0','-j','1']
    before=inputs(); dep_before=uvm_identity(uvm); start=time.monotonic()
    (out/'build.json').unlink(missing_ok=True)
    print('Building; log:',out/'build.log',flush=True)
    with (out/'build.log').open('w') as log:
        p=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    meta={'command':cmd,'returncode':p.returncode,'seconds':time.monotonic()-start,'sources':before,
          'source_stable':before==inputs(),'uvm_commit':UVM_COMMIT,
          'tool':subprocess.check_output(command('verilator')+['--version'],text=True).strip()}
    if p.returncode==0 and meta['source_stable']:
        require(dep_before==uvm_identity(uvm),'UVM changed during build')
        meta=seal_build(ROOT,'target',cmd,out/'obj/Vtb_top',before,meta['tool'],dep_before)
    (out/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    if p.returncode or not meta['source_stable']:
        print((out/'build.log').read_text()[-12000:]); raise SystemExit(1)
    print('Build complete',flush=True)
def run(test,seed,negative=None,trace=False,timeout=900):
    out=ROOT/'build/target'; binary=out/'obj/Vtb_top'
    if not binary.exists(): raise SystemExit('Run build first')
    meta=json.loads((out/'build.json').read_text())
    validate_build(ROOT,meta,'target')
    dep_before=uvm_identity(dependency())
    require(dep_before==meta['dependency'],'UVM differs from build')
    require(subprocess.check_output(command('verilator')+['--version'],text=True).strip()==meta['tool'],'simulator tool differs from build')
    suffix=f'{test}_seed{seed}'+(f'_{negative}' if negative else '')
    run_dir=out/'runs'/suffix
    if run_dir.exists():
        # Keep every previous run, including failures.
        run_dir=run_dir.with_name(suffix+'_'+datetime.datetime.now().strftime('%H%M%S_%f'))
    run_dir.mkdir(parents=True)
    cmd=command('verilator')[:-1]+[str(binary),f'+UVM_TESTNAME={test}',f'+verilator+seed+{seed}',
         f'+verilator+coverage+file+{run_dir}/coverage.dat']
    if trace: cmd+=['+TRACE']
    if negative: cmd+=['+'+negative]
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    run_env=os.environ.copy()
    if run_env.get('OSS_CAD_SUITE'):
        run_env['PATH']=str(Path(run_env['OSS_CAD_SUITE'])/'bin')+os.pathsep+run_env.get('PATH','')
    start=time.monotonic(); timed_out=False
    with (run_dir/'run.log').open('w') as log:
        log.write('EVIDENCE_RUN|'+str(run_dir.relative_to(ROOT))+'|'+meta['build_id']+'\n');log.flush()
        try: p=subprocess.run(cmd,cwd=run_dir,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,env=run_env); rc=p.returncode
        except subprocess.TimeoutExpired: rc=124; timed_out=True
    log=(run_dir/'run.log').read_text(errors='replace')
    errors=re.findall(r'UVM_ERROR\s*:\s*(\d+)',log); fatals=re.findall(r'UVM_FATAL\s*:\s*(\d+)',log)
    sb=re.search(r'SB_RESULT\|checks=(\d+)\|tx=(\d+)\|rx=(\d+)\|dropped=(\d+)',log)
    completed=f'TEST_COMPLETED|{test}|' in log
    checks=int(sb[1]) if sb else 0
    stable=meta['sources']==inputs()
    try:
        validate_build(ROOT,meta,'target')
        require(dep_before==uvm_identity(dependency()),'UVM changed during run')
    except ValueError: stable=False
    good=stable and rc==0 and errors and errors[-1]=='0' and fatals and fatals[-1]=='0' and completed and checks>0
    rejected=(stable and not good and not timed_out and
        (('TX decoded data' in log and 'UVM_ERROR' in log) if negative=='NEGATIVE_TX_DATA' else 'ASSERT_APB_SETUP_STABILITY' in log))
    status=('DETECTED' if rejected else 'NOT_DETECTED') if negative else ('PASS' if good else 'FAIL')
    cov={m[0]:int(m[1]) for m in re.findall(r'^COV\|([^|]+)\|(\d+)$',log,re.M)}
    result={'test':test,'seed':seed,'negative_control':negative,'status':status,'returncode':rc,
            'seconds':time.monotonic()-start,'completed':completed,'uvm_errors':int(errors[-1]) if errors else None,
            'uvm_fatals':int(fatals[-1]) if fatals else None,'scoreboard':dict(zip(['checks','tx','rx','dropped'],map(int,sb.groups()))) if sb else {},
            'functional_bins':cov,'command':cmd,'log':str((run_dir/'run.log').relative_to(ROOT)),
            'coverage_file':str((run_dir/'coverage.dat').relative_to(ROOT)) if (run_dir/'coverage.dat').exists() else None,
            'source_hashes':inputs(),'source_stable':stable,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'working_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
            'solver':subprocess.check_output(command('z3')+['--version'],env=run_env,text=True).strip(),'tool':meta['tool'],'uvm_commit':UVM_COMMIT,'assertions_enabled':True,'timed_out':timed_out}
    result.update(bind_run(ROOT,meta,run_dir,negative))
    result['binary_stable']=stable
    if result['coverage_file'] is None and not negative:
        result['status']='FAIL';status='FAIL'
    (run_dir/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'{status}: {test} seed={seed} checks={checks} time={result["seconds"]:.2f}s log={result["log"]}',flush=True)
    if status not in ['PASS','DETECTED']: print('\n'.join(line for line in log.splitlines() if 'ERROR' in line or 'FATAL' in line or 'Error' in line)[-5000:])
    return result

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['build','run','regress'])
    parser.add_argument('--test',default='target_apb_test'); parser.add_argument('--seed',type=int,default=17)
    parser.add_argument('--negative',choices=['NEGATIVE_TX_DATA','NEGATIVE_APB_PROTOCOL']); parser.add_argument('--trace',action='store_true')
    args=parser.parse_args()
    if args.action=='build': build(); return
    if args.action=='run': results=[run(args.test,args.seed,args.negative,args.trace)]
    else:
        results=[run(t,17,trace=t in ['target_errors_test','target_snapshot_test']) for t in TESTS]
        results += [run('target_random_test',s) for s in [17,29,101]]
        results += [run('target_tx_modes_test',17,'NEGATIVE_TX_DATA'),run('target_apb_test',17,'NEGATIVE_APB_PROTOCOL')]
        (ROOT/'build/target/regression.json').write_text(json.dumps(results,indent=2)+'\n')
    raise SystemExit(0 if all(r['status'] in ['PASS','DETECTED'] for r in results) else 1)
if __name__=='__main__': main()
