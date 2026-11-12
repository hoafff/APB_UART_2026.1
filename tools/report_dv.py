#!/usr/bin/env python3
"""Export only reviewed, matching-source runs; keep physical sign-off separate."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,hashlib,json,re,shutil,subprocess,zipfile
from run_dv import ROOT,command,inputs

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

def main():
    current=inputs()
    runs=json.loads((ROOT/'build/target/regression.json').read_text())
    normal=[r for r in runs if not r['negative_control']]
    negatives=[r for r in runs if r['negative_control']]
    assert len(normal)==15 and len(negatives)==2
    assert all(r['status']=='PASS' and r.get('source_stable') and r['source_hashes']==current for r in normal)
    assert all(r['status']=='DETECTED' and r['source_hashes']==current for r in negatives)
    assert {r['seed'] for r in normal if r['test']=='target_random_test'}=={17,29,101}
    supplemental={name:json.loads((ROOT/f'build/{name}/result.json').read_text()) for name in ['system','controller','onehot']}
    for name,r in supplemental.items():
        assert r['status']=='PASS',name
        assert all(sha(ROOT/p)==h for p,h in r['sources'].items()),name
    spec_check=subprocess.check_output(['python','tools/check_spec.py'],cwd=ROOT,text=True)
    dv_check=subprocess.check_output(['python','tools/check_dv.py'],cwd=ROOT,text=True)
    ledger=Counter()
    for r in normal: ledger.update(r['functional_bins'])
    for name in supplemental:
        log=(ROOT/f'build/{name}/run.log').read_text()
        for pattern in [r'^COV\|([^|]+)\|(\d+)$',r'^SYS_COV\|([^|]+)\|(\d+)$']:
            ledger.update({k:int(v) for k,v in re.findall(pattern,log,re.M)})
    model=json.loads((ROOT/'docs/dv/coverage_model.json').read_text())
    groups={name:{'hit':sum(ledger[b]>0 for b in bins),'total':len(bins),'missing':[b for b in bins if not ledger[b]]} for name,bins in model['groups'].items()}
    missing=[b for g in groups.values() for b in g['missing']]
    if missing: raise SystemExit('Mandatory functional bins still OPEN: '+', '.join(missing))
    out=ROOT/'dv/results/target_v1'; out.mkdir(parents=True,exist_ok=True)
    logs=out/'logs'; logs.mkdir(exist_ok=True)
    for r in runs:
        source=ROOT/r['log']; dest=logs/(source.parent.name+'.log'); shutil.copy2(source,dest)
        r['exported_log']=str(dest.relative_to(ROOT))
    for name,r in supplemental.items():
        dest=logs/(name+'.log'); shutil.copy2(ROOT/f'build/{name}/run.log',dest)
        r['exported_log']=str(dest.relative_to(ROOT))
    cov_paths=[ROOT/r['coverage_file'] for r in normal if r['coverage_file']]
    cov_paths += [ROOT/f'build/{name}/coverage.dat' for name in supplemental]
    assert len(cov_paths)==18 and all(p.is_file() for p in cov_paths)
    merged=ROOT/'build/target/coverage_merged.dat'
    merge_cmd=command('verilator_coverage')+['--write',str(merged)]+list(map(str,cov_paths))
    subprocess.run(merge_cmd,check=True,cwd=ROOT,stdout=subprocess.DEVNULL)
    with (out/'coverage_merged.dat.gz').open('wb') as f:
        with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z: z.write(merged.read_bytes())
    # Distinguish RTL instrumentation from UVM library; normalize absolute/relative source paths.
    native_points={}
    for line in merged.read_text().splitlines():
        match=re.match(r"C '(.*)' (\d+)$",line)
        if not match: continue
        fields={part.split('\x02',1)[0]:part.split('\x02',1)[1] for part in match[1].split('\x01') if '\x02' in part}
        file=fields.get('f','')
        if 'rtl/modified/' not in file and 'rtl/fpga/' not in file: continue
        file=file[file.index('rtl/'):]
        key=tuple([file]+[fields.get(k,'') for k in ['l','n','t','page','o']])
        native_points[key]=native_points.get(key,0)+int(match[2])
    native=defaultdict(lambda:{'hit':0,'total':0})
    for key,count in native_points.items():
        native[key[3]]['total']+=1; native[key[3]]['hit']+=int(count>0)
    unhit=[{'file':k[0],'line':k[1],'kind':k[3],'point':k[5]} for k,c in native_points.items() if not c]
    write_json(out/'native_unhit_points.json',unhit)
    waves=[]
    with zipfile.ZipFile(out/'waveforms.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for r in normal:
            wave=(ROOT/r['log']).parent/'wave.fst'
            if wave.exists():
                name=r['test']+'_seed'+str(r['seed'])+'.fst'; z.write(wave,name); waves.append({'name':name,'sha256':sha(wave)})
    assert len(waves)>=2
    write_json(out/'waveform_manifest.json',waves)
    write_json(out/'uvm_runs.json',runs); write_json(out/'supplemental_runs.json',supplemental)
    write_json(out/'source_manifest.json',{'uvm_build_inputs':current,'supplemental_inputs':{n:r['sources'] for n,r in supplemental.items()},'spec_sha256':sha(ROOT/'docs/01_System_Specification.md'),'tool':normal[0]['tool'],'solver':normal[0]['solver'],'uvm_commit':normal[0]['uvm_commit'],'code_git_head':normal[0]['git_head']})
    write_json(out/'functional_coverage.json',{'groups':groups,'observed_counts':dict(ledger),'total_required':sum(g['total'] for g in groups.values()),'hit_required':sum(g['hit'] for g in groups.values()),'excluded_negative_runs':len(negatives),'hardware':'NOT_RUN'})
    write_json(out/'native_coverage.json',{'merge_command':merge_cmd,'rtl_points_by_kind':dict(native),'note':'Instrumentation points, normalized across hierarchy/paths; not a claim of full line/toggle or functional sign-off','unhit_count':len(unhit)})
    write_json(out/'document_checks.json',{'spec':json.loads(spec_check),'dv':json.loads(dv_check)})
    trace=json.loads((ROOT/'docs/dv/traceability.json').read_text()); cases=json.loads((ROOT/'docs/dv/testcases.json').read_text())
    for c in cases: c['evidence_status']='HW_NOT_RUN' if c['kind']=='HARDWARE' else 'PASS_DOCUMENT_CHECK' if c['kind']=='DOC' else 'PASS_SIMULATION'
    for row in trace:
        row['status']='HW_PENDING' if row['scope']=='HARDWARE_PENDING' else 'PASS_DOCUMENT_CHECK' if row['scope']=='DOC' else 'MAPPED_SIM_TESTS_PASS'
        row['evidence']='dv/results/target_v1/'
    write_json(ROOT/'docs/dv/testcases.json',cases); write_json(ROOT/'docs/dv/traceability.json',trace)
    summary={'normal_uvm_runs_pass':len(normal),'negative_controls_detected':len(negatives),'supplemental_runs_pass':len(supplemental),'functional_bins_hit':sum(g['hit'] for g in groups.values()),'functional_bins_required':sum(g['total'] for g in groups.values()),'requirements_mapped':len(trace),'physical_requirements_pending':sum(t['scope']=='HARDWARE_PENDING' for t in trace),'quartus_run':False,'hardware_run':False,'questa_run':False,'native_unhit_points':len(unhit)}
    write_json(out/'summary.json',summary)
    md=['# Kết quả kiểm chứng TARGET-v1.0','',
        '**15/15 run UVM chức năng PASS; 3/3 simulation bổ sung PASS; 2/2 negative controls DETECTED.**',
        f"Functional coverage: **{summary['functional_bins_hit']}/{summary['functional_bins_required']} bin đã công khai** trong coverage_model.json. Đây là coverage của tập nghĩa vụ mô phỏng đã định nghĩa, không phải mọi chuỗi đầu vào hoặc bằng chứng formal/hardware.",
        '',f"Code revision của các run UVM: `{normal[0]['git_head']}`; SHA-256 nguồn/công cụ/solver nằm trong [source_manifest](../../dv/results/target_v1/source_manifest.json). Nếu Git dirty do tài liệu, từng run vẫn bắt buộc hash RTL/TB/runner đúng executable.",
        '', '## UVM runs','', '| Test | Seed | Kết quả | SB checks | TX / RX | Thời gian wall-clock |', '|---|---:|---|---:|---|---:|']
    for r in normal: md.append(f"| `{r['test']}` | {r['seed']} | PASS | {r['scoreboard']['checks']} | {r['scoreboard']['tx']} / {r['scoreboard']['rx']} | {r['seconds']:.2f} s |")
    md += ['', '## Bổ sung và negative controls','',
        '- `tb_system`: profile 50 MHz/D27, default debounce 500000 cycles, reset sync, N/O/E, send/RX/echo/hold/errors, finite burst 32; chỉ simulation.',
        '- `tb_controller`: injected slave faults (init/runtime), manual overflow, same-edge consume/new, echo reservation/fairness và poll interval khi hold IRQ.',
        '- `tb_tx_onehot`: 192 N/parity/stop/one-hot cases; kiểm cả bit dữ liệu nằm ngoài WLS.',
        '- Negative TX-data và ACCESS thiếu SETUP đều bị checker đúng phát hiện. Các run này không được cộng vào PASS/coverage target.',
        '', '## Functional coverage theo nhóm','', '| Nhóm | Hit / bắt buộc |', '|---|---|']
    for name,g in groups.items(): md.append(f"| {name} | {g['hit']} / {g['total']} |")
    md += ['', '## Native RTL coverage','', '| Loại điểm instrument | Hit / tổng |', '|---|---|']
    for name,g in sorted(native.items()): md.append(f"| {name} | {g['hit']} / {g['total']} |")
    md += ['',f"Còn **{len(unhit)} điểm instrument chưa hit**; danh sách lưu trong native_unhit_points.json để review. Chưa tuyên bố code/toggle coverage closure. Không tự loại unreachable bins để nâng tỷ lệ.",
        '', '## Bằng chứng và giới hạn','',
        '- [Evidence index](../../dv/results/target_v1/summary.json), [logs](../../dv/results/target_v1/logs), [functional ledger](../../dv/results/target_v1/functional_coverage.json), [native merge](../../dv/results/target_v1/coverage_merged.dat.gz), [waveforms](../../dv/results/target_v1/waveforms.zip).',
        '- 80 requirement có testcase/observer mapping; các row MAPPED_SIM_TESTS_PASS xác nhận ca liên kết đã chạy đạt, không thay một review sign-off toàn bộ không gian trạng thái. 5 requirement FPGA vẫn HW_PENDING.',
        '- Chưa chạy Quartus/fitter/STA, chưa có bitstream hay thử DE2-115 + CP2102 thật. Chưa chạy Questa, formal hoặc X-propagation/analog metastability.',
        '- Thư viện/công cụ có sẵn được tái sử dụng; đã tải UVM pin vào .tools/uvm. Các failure ban đầu (syntax/task direction, hết disk, runtime thiếu PATH Z3) được giữ trong build history và issue ledger.',
        '', '## Chạy lại','', '```bash','bash dv/sim/run_smoke.sh','```','', 'Hoặc chạy từng lệnh trong dv/README.md. Exporter sẽ từ chối source mismatch, run FAIL, thiếu ba random seeds, negative control không phát hiện hoặc thiếu mandatory functional bin.']
    (ROOT/'docs/dv/RESULTS.md').write_text('\n'.join(md)+'\n')
    shutil.copy2(ROOT/'build/spec/validation.json',ROOT/'docs/spec/validation.json')
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
