#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,os,subprocess,time,datetime,shutil
from run_dv import ROOT,command
out=ROOT/'build/onehot'; out.mkdir(parents=True,exist_ok=True)
if (out/'build.log').exists():
 history=out/'history'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'); history.mkdir(parents=True)
 for name in ['build.log','run.log','result.json']:
  if (out/name).exists(): shutil.copy2(out/name,history/name)
files=[ROOT/p for p in (ROOT/'rtl/modified/pulp_apb_uart_sv/files.f').read_text().splitlines()]
files += [ROOT/'dv/system/tb_tx_onehot.sv']
sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
cmd=command('verilator')+['--binary','--timing','--assert','--coverage','-Wno-fatal','--top-module','tb_tx_onehot','--Mdir',str(out/'obj'),'-j','1']+[str(p) for p in files]
start=time.monotonic()
with (out/'build.log').open('w') as log: p=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
if p.returncode:
 print((out/'build.log').read_text()[-6000:]); raise SystemExit(p.returncode)
run_cmd=[str(out/'obj/Vtb_tx_onehot'),f'+verilator+coverage+file+{out}/coverage.dat']
with (out/'run.log').open('w') as log: p=subprocess.run(run_cmd,cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=180)
log=(out/'run.log').read_text(); good=p.returncode==0 and 'SYS_TEST_COMPLETED|' in log
result={'status':'PASS' if good else 'FAIL','returncode':p.returncode,'seconds':time.monotonic()-start,'sources':sources,'build_command':cmd,'run_command':run_cmd,'scope':'Supplemental UART RTL simulation: 192 one-hot/mode combinations','log':str((out/'run.log').relative_to(ROOT))}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2)); print(log[-3000:]); raise SystemExit(0 if good else 1)
