"""Content-bound build/run records shared by all simulation runners.

These guards detect stale or accidentally mixed artifacts, not a malicious author
who can rewrite both the artifacts and their manifests. No simulator is mocked.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess


def require(ok, message):
    if not ok:
        raise ValueError('Evidence rejected: '+message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(root, path):
    path=Path(path).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), 'artifact outside root or missing')
    require(path.stat().st_size>0, 'empty artifact: '+str(path))
    return {'path':str(path.relative_to(root.resolve())), 'sha256':sha(path), 'bytes':path.stat().st_size}


def source_paths(root, kind):
    if kind=='target':
        paths=[p for folder in ['rtl/modified','dv/uvm','dv/assertions'] for p in (root/folder).rglob('*') if p.is_file()]
        paths += [root/'tools/run_dv.py']
    else:
        configs={'system':('tb_system',True),'controller':('tb_controller',False),'onehot':('tb_tx_onehot',True)}
        require(kind in configs,'unknown build kind')
        top,core=configs[kind]
        paths=[root/'dv/system'/f'{top}.sv',root/'tools'/f'run_{kind}.py',root/'tools/run_supplemental.py',root/'tools/run_dv.py']
        if core:
            filelist=root/'rtl/modified/pulp_apb_uart_sv/files.f'
            paths += [filelist]+[root/p for p in filelist.read_text().splitlines() if p.strip()]
        if kind!='onehot': paths += [root/'rtl/fpga/de2_uart_controller.sv']
        if kind=='system': paths += [root/'rtl/fpga/de2_115_apb_uart_bringup.sv']
    return sorted(set(paths+[root/'tools/evidence.py']))


def sources(root,kind):
    return {str(p.relative_to(root)):sha(p) for p in source_paths(root,kind)}


def uvm_identity(path):
    head=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
    dirty=subprocess.check_output(['git','-C',str(path),'status','--porcelain','--untracked-files=all'],text=True).strip()
    require(not dirty,'UVM working tree is dirty')
    files={str(p.relative_to(path)):sha(p) for p in sorted((path/'src').rglob('*')) if p.is_file()}
    require(bool(files),'empty UVM dependency manifest')
    return {'revision':head,'sources':files,'digest':digest(files)}


def seal_build(root,kind,command,binary,before,tool,dependency=None):
    require(before==sources(root,kind),'sources changed during build')
    flags={name:('--'+name in command) for name in ['timing','assert','coverage']}
    require(all(flags.values()),'required instrumentation disabled')
    record={'schema':2,'kind':kind,'command':command,'sources':before,'source_stable':True,
            'tool':tool,'dependency':dependency,'flags':flags,'binary':artifact(root,binary),'returncode':0}
    record['build_id']=digest(record)
    return record


def validate_build(root,build,kind,check_binary=True):
    require(build.get('schema')==2 and build.get('kind')==kind,'build schema/kind')
    require(build.get('build_id')==digest({k:v for k,v in build.items() if k!='build_id'}),'build manifest digest')
    require(build.get('returncode')==0 and build.get('source_stable') is True,'failed/unstable build')
    require(build.get('sources')==sources(root,kind),'incomplete or changed build sources')
    require(build.get('flags')=={'timing':True,'assert':True,'coverage':True},'build flags')
    require(all('--'+f in build['command'] for f in build['flags']),'command/flags mismatch')
    dep=build.get('dependency')
    if kind=='target':
        require(isinstance(dep,dict) and bool(dep.get('sources')),'missing UVM dependency identity')
        require(dep['digest']==digest(dep['sources']),'UVM manifest digest')
    else: require(dep is None,'unexpected supplemental dependency')
    if check_binary: require(build['binary']==artifact(root,root/build['binary']['path']),'binary differs from build')


def stamp_coverage(path,run_id,build_id,negative):
    if path.is_file():
        with path.open('a') as f:
            f.write('\n# RUN_ID='+run_id+' BUILD_ID='+build_id+' NEGATIVE='+str(negative or 'NONE')+'\n')


def bind_run(root,build,run_dir,negative=None):
    coverage=run_dir/'coverage.dat'
    run_id=str(run_dir.relative_to(root))
    stamp_coverage(coverage,run_id,build['build_id'],negative)
    return {'schema':2,'run_id':run_id,'build_id':build['build_id'],'build':build,
            'binary_sha256':build['binary']['sha256'],'binary_stable':True,
            'log_artifact':artifact(root,run_dir/'run.log'),
            'coverage_artifact':artifact(root,coverage) if coverage.is_file() else None,
            'coverage_file':str(coverage.relative_to(root)) if coverage.is_file() else None,
            'assertions_enabled':build['flags']['assert']}


def validate_run(root,run,kind,seen,check_binary=True):
    require(run.get('schema')==2 and run.get('binary_stable') is True,'run schema/binary stability')
    build=run.get('build',{})
    validate_build(root,build,kind,check_binary)
    require(run.get('build_id')==build['build_id'],'run/build mismatch')
    require(run.get('binary_sha256')==build['binary']['sha256'],'run binary mismatch')
    require(run.get('tool')==build['tool'],'run tool mismatch')
    if kind=='target': require(run.get('uvm_commit')==build['dependency']['revision'],'run UVM mismatch')
    require(run.get('source_stable') is True,'unstable run sources')
    require(run.get('source_hashes',run.get('sources'))==build['sources'],'run source mismatch')
    require(run.get('assertions_enabled') is True,'assertions not bound to build')
    run_dir=(root/run['run_id']).resolve()
    require(run_dir.is_relative_to(root.resolve()/'build'/kind),'run directory outside expected tree')
    require((root/run['log']).resolve()==run_dir/'run.log','log outside run')
    require(run.get('log_artifact')==artifact(root,run_dir/'run.log'),'log hash/size mismatch')
    header='EVIDENCE_RUN|'+run['run_id']+'|'+build['build_id']
    require((run_dir/'run.log').read_text().splitlines().count(header)==1,'log run/build binding')
    cov=run.get('coverage_artifact')
    if cov is None:
        require(run.get('negative_control')=='NEGATIVE_APB_PROTOCOL' and run.get('coverage_file') is None,'missing native coverage')
        return
    path=(root/run['coverage_file']).resolve()
    require(path==run_dir/'coverage.dat','coverage belongs to another run')
    require(cov==artifact(root,path),'coverage hash/size mismatch')
    identity=(path.stat().st_dev,path.stat().st_ino)
    require(identity not in seen,'duplicate/aliased native coverage')
    seen.add(identity)
    lines=path.read_text().splitlines()
    require(lines and lines[0]=='# SystemC::Coverage-3' and any(re.fullmatch(r"C '.*' [0-9]+",line) for line in lines),'empty/invalid native coverage payload')
    token='# RUN_ID='+run['run_id']+' BUILD_ID='+build['build_id']+' NEGATIVE='+str(run.get('negative_control') or 'NONE')
    require(lines.count(token)==1,'native coverage run binding')
