"""Build, verify and package the DE2-115 SRAM release. Never programs hardware."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

from fpga_checks import (CORNERS, METRICS, require, review_warnings, safe_path,
                         sha256, snapshot, validate_pins, validate_simulation,
                         validate_timing, verify_hashes)

ROOT = Path(__file__).resolve().parents[1]
BUILD = 'build/fpga'
REV = 'de2_115_apb_uart'
MANIFEST = f'{BUILD}/release_manifest.json'
SOURCES = [f'rtl/modified/pulp_apb_uart_sv/{name}.sv'
           for name in ('uart_fifo', 'uart_tx', 'uart_rx', 'apb_uart_sv')] + [
    'rtl/fpga/de2_uart_controller.sv', 'rtl/fpga/de2_115_apb_uart_bringup.sv']
INPUTS = SOURCES + [f'dv/system/{name}.sv' for name in
    ('tb_system', 'tb_controller', 'tb_tx_onehot')] + [f'fpga/de2_115/{name}' for name in (
    f'{REV}.qpf', f'{REV}.qsf', f'{REV}.sdc', 'pins.qsf', 'synchronizers.qsf')] + [
    'fpga/scripts/check_project.tcl', 'fpga/scripts/audit_timing.tcl',
    'fpga/scripts/simulate.do', 'tools/build_fpga.py', 'tools/fpga_checks.py',
    'tools/tests/test_fpga_release.py', 'tools/tests/fixtures/fpga_timing.tsv',
    'tools/tests/fixtures/fpga_pins.pin', 'tools/tests/fixtures/fpga_compile.txt',
    'tools/tests/fixtures/fpga_simulation.txt',
    'docs/spec/pins.json', 'reference/DE2_115_pin_assignments.csv']
REPORTS = [f'{BUILD}/output_files/{REV}.{ext}' for ext in
    ('sof', 'pin', 'fit.rpt', 'fit.summary', 'map.rpt', 'map.summary',
     'sta.rpt', 'sta.summary', 'asm.rpt', 'flow.rpt')] + [
    f'{BUILD}/reports/{name}' for name in ('timing.tsv', 'check_timing.rpt',
    'unconstrained.rpt', 'ignored_sdc.rpt', 'exceptions.rpt', 'clocks.rpt')] + [
    f'{BUILD}/reports/{corner}_{metric}.rpt'
    for corner in sorted(CORNERS) for metric in sorted(METRICS | {'fmax', 'metastability'})]
HARDWARE = dict.fromkeys(('jumpers_and_voltage', 'jtag_programming', 'uart_board_tests'), 'NOT_RUN')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read(path):
    return path.read_text(encoding='utf-8', errors='replace')


def run(argv, cwd, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    print('RUN:', subprocess.list2cmdline([str(x) for x in argv]), flush=True)
    with log.open('w', encoding='utf-8') as stream:
        stream.write('COMMAND: ' + subprocess.list2cmdline([str(x) for x in argv]) + '\n')
        stream.flush()
        result = subprocess.run([str(x) for x in argv], cwd=cwd, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f'Command failed ({result.returncode}); see {log}')


def tool(bin_dir, name):
    result = Path(bin_dir) / (name + ('.exe' if os.name == 'nt' else ''))
    require(result.is_file(), f'Tool not found: {result}')
    return result


def git_info(root):
    if not shutil.which('git'):
        return {'commit': None, 'dirty': None}
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True)
    if head.returncode:
        return {'commit': None, 'dirty': None}
    status = subprocess.run(['git', 'status', '--porcelain'], cwd=root,
                            capture_output=True, text=True, check=True)
    return {'commit': head.stdout.strip(), 'dirty': bool(status.stdout.strip())}


def check_reports(root):
    for name in REPORTS:
        path = safe_path(root, name)
        require(path.is_file() and path.stat().st_size > 0, f'Missing/empty artifact: {name}')
    result = validate_timing(read(root / BUILD / 'reports/timing.tsv'))
    result.update(validate_pins(read(root / BUILD / f'output_files/{REV}.pin'),
                               json.loads(read(root / 'docs/spec/pins.json'))))
    result['warnings'] = review_warnings(read(root / BUILD / 'logs/compile.log'))
    fitted = read(root / BUILD / f'output_files/{REV}.fit.summary')
    require(re.search(r'^Fitter Status : Successful', fitted, re.M), 'Fitter not successful')
    require(re.search(r'^Device : EP4CE115F29C7\s*$', fitted, re.M), 'Wrong fitted device')
    for corner in CORNERS:
        meta = read(root / BUILD / f'reports/{corner}_metastability.rpt')
        require('Number of Synchronizer Chains Found: 15' in meta and
                'Fraction of Chains for which MTBFs Could Not be Calculated: 0.000' in meta,
                f'Incomplete metastability report: {corner}')
    return result


def verify_release(root):
    data = json.loads(read(root / MANIFEST))
    require(data.get('schema') == 1 and data.get('status') == 'SOFTWARE_READY / HARDWARE_PENDING',
            'Unsupported/incomplete release manifest')
    require(data.get('hardware') == HARDWARE, 'Hardware status must remain NOT_RUN')
    require(set(data.get('inputs', {})) == set(INPUTS), 'Missing/extra sealed build inputs')
    required = set(REPORTS) | {f'{BUILD}/logs/{name}.log' for name in
                             ('preflight', 'compile', 'audit', 'check_spec', 'check_dv', 'release_tests')}
    simulation = data.get('simulation')
    require(isinstance(simulation, dict), 'Missing simulation status')
    sim_log = f'{BUILD}/logs/simulation.log'
    if simulation.get('status') == 'PASS':
        required.add(sim_log)
    else:
        require(simulation.get('status') == 'NOT_RUN' and
                set(simulation) == {'status', 'reason'} and
                isinstance(simulation['reason'], str) and bool(simulation['reason'].strip()),
                'Invalid NOT_RUN simulation record')
        require(sim_log not in data.get('artifacts', {}), 'NOT_RUN must not seal a stale simulation log')
    require(required <= set(data.get('artifacts', {})), 'Missing sealed release artifacts')
    count = verify_hashes(root, data['inputs']) + verify_hashes(root, data['artifacts'])
    require(check_reports(root) == data.get('verification'), 'Recorded verification differs from evidence')
    if simulation['status'] == 'PASS':
        require(validate_simulation(read(root / sim_log)) == simulation,
                'Simulation verdict/counts differ from the sealed log')
    print(f'RELEASE_VERIFY_PASS: {count} hashes; 65 fitted pins; 3 timing corners; BOARD_NOT_TESTED')
    return data


def build(root, quartus_bin, questa_bin=None):
    # Invalidate the old verdict first. An interrupted/failed build cannot keep a green seal.
    (root / MANIFEST).unlink(missing_ok=True)
    (root / BUILD / f'output_files/{REV}.sof').unlink(missing_ok=True)
    (root / BUILD / 'reports/timing.tsv').unlink(missing_ok=True)
    before = snapshot(root, INPUTS)
    logs = root / BUILD / 'logs'
    qsh = tool(quartus_bin, 'quartus_sh')
    qsta = tool(quartus_bin, 'quartus_sta')
    version = subprocess.run([str(qsh), '--version'], capture_output=True, text=True, check=True).stdout.strip()
    require('25.1std.0' in version and 'Lite Edition' in version,
            'This warning/timing profile is reviewed for Quartus Lite 25.1std.0 only')
    for name in ('check_spec', 'check_dv'):
        run([sys.executable, '-X', 'utf8', f'tools/{name}.py'], root, logs / f'{name}.log')
    run([sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tools/tests',
         '-p', 'test_fpga_release.py'], root, logs / 'release_tests.log')
    run([qsh, '-t', 'fpga/scripts/check_project.tcl'], root, logs / 'preflight.log')
    run([qsh, '--flow', 'compile', REV], root / 'fpga/de2_115', logs / 'compile.log')
    run([qsta, '-t', 'fpga/scripts/audit_timing.tcl'], root, logs / 'audit.log')
    result = check_reports(root)
    artifacts = REPORTS + [f'{BUILD}/logs/{name}.log' for name in
        ('preflight', 'compile', 'audit', 'check_spec', 'check_dv', 'release_tests')]
    simulation = {'status': 'NOT_RUN', 'reason': 'Use --questa-bin to run the three existing benches'}
    if questa_bin:
        sim_dir = root / BUILD / 'questa'
        sim_dir.mkdir(parents=True, exist_ok=True)
        script = (root / 'fpga/scripts/simulate.do').as_posix()
        run([tool(questa_bin, 'vsim'), '-c', '-do', f'do {{{script}}}'],
            sim_dir, logs / 'simulation.log')
        simulation = validate_simulation(read(logs / 'simulation.log'))
        artifacts.append(f'{BUILD}/logs/simulation.log')
    verify_hashes(root, before)
    manifest = {'schema': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'status': 'SOFTWARE_READY / HARDWARE_PENDING', 'git': git_info(root),
                'quartus_version': version, 'python_version': sys.version,
                'inputs': before, 'artifacts': snapshot(root, artifacts),
                'verification': result, 'simulation': simulation, 'hardware': HARDWARE}
    write_json(root / MANIFEST, manifest)
    verify_release(root)


def package(root, output):
    data = verify_release(root)
    # Package the actual checkout (tracked and untracked source), never Quartus DBs/installers.
    listing = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                             cwd=root, capture_output=True, check=True).stdout.decode('utf-8')
    sources = {p for p in listing.split('\0') if p and (root / p).is_file()}
    names = sources | set(data['inputs']) | set(data['artifacts']) | {MANIFEST}
    output = output.resolve()
    require(output.suffix.lower() == '.zip', 'Package output must end in .zip')
    require(not output.is_relative_to(root), 'Write delivery archives outside the repository')
    require(not output.exists(), f'Refusing to overwrite existing archive: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    hashes = snapshot(root, names)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(names):
            archive.write(safe_path(root, name), name)
        archive.writestr('PACKAGE_SHA256.json', json.dumps(hashes, indent=2) + '\n')
    with zipfile.ZipFile(output) as archive:
        for name, digest in hashes.items():
            import hashlib
            require(hashlib.sha256(archive.read(name)).hexdigest() == digest, f'Archive hash: {name}')
        require(archive.testzip() is None, 'ZIP CRC failure')
    output.with_suffix('.zip.sha256').write_text(f'{sha256(output)}  {output.name}\n', encoding='ascii')
    print(f'PACKAGE_PASS: {output}; {len(names)} files; {output.stat().st_size} bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'verify', 'package'))
    parser.add_argument('--quartus-bin', default=os.environ.get('QUARTUS_BIN', r'D:\uart\25.1std\quartus\bin64'))
    parser.add_argument('--questa-bin', help='Optional Questa bin directory; runs existing non-UVM benches')
    parser.add_argument('--output', type=Path, help='New archive path outside the repository')
    args = parser.parse_args()
    try:
        if args.action == 'build':
            build(ROOT, args.quartus_bin, args.questa_bin)
        elif args.action == 'verify':
            verify_release(ROOT)
        else:
            require(args.output is not None, '--output is required for package')
            package(ROOT, args.output)
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f'FPGA_RELEASE_FAIL: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
