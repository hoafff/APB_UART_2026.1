"""Fail-closed validation of the DE2-115 Quartus release evidence (stdlib only)."""
from collections import Counter, defaultdict
import hashlib
import math
from pathlib import Path, PurePosixPath
import re

CORNERS = {'7_slow_1200mv_85c', '7_slow_1200mv_0c', 'MIN_fast_1200mv_0c'}
METRICS = {'setup', 'hold', 'recovery', 'removal', 'min_pulse_width',
           'reset_recovery', 'reset_removal'}
SW_BITS = (*range(8), 14, 15, 16, 17)
EDGES = {
    ('reset_sync[0]', 'reset_sync[1]'), ('key_sync[0]', 'key_sync[1]'),
    ('rx_sync[0]', 'rx_sync[1]'),
    ('rx_sync[1]', 'apb_uart_sv:uart|uart_rx:rx|sync_q[0]'),
    ('apb_uart_sv:uart|uart_rx:rx|sync_q[0]', 'apb_uart_sv:uart|uart_rx:rx|sync_q[1]'),
    ('apb_uart_sv:uart|uart_rx:rx|sync_q[1]', 'apb_uart_sv:uart|uart_rx:rx|sync_q[2]'),
    *((f'sw_meta[{i}]', f'sw_sync[{i}]') for i in SW_BITS),
}
INPUTS = {'GPIO_UART_RX', 'KEY[0]', 'KEY[1]', *(f'SW[{i}]' for i in SW_BITS)}
OUTPUTS = {'GPIO_UART_TX', *(f'{bus}[{i}]' for bus, width in
    [('LEDR', 5), ('LEDG', 9), ('HEX0', 7), ('HEX1', 7), ('HEX4', 7), ('HEX5', 7)]
    for i in range(width))}
CHECKS = dict.fromkeys(('no_clock', 'multiple_clock', 'generated_clock', 'loops',
    'latches', 'partial_input_delay', 'partial_output_delay',
    'io_min_max_delay_consistency'), '0') | {'no_input_delay': '15', 'no_output_delay': '43'}
UCP = {'Illegal Clocks', 'Unconstrained Clocks', 'Unconstrained Input Ports',
       'Unconstrained Input Port Paths', 'Unconstrained Output Ports',
       'Unconstrained Output Port Paths'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonnegative(value):
    number = float(value)
    require(math.isfinite(number) and number >= 0, f'Invalid/negative slack: {value}')
    return number


def unique_rows(rows, keys, label):
    result = {}
    for row in rows:
        require(len(row) > keys, f'Malformed {label}: {row}')
        key = tuple(row[:keys])
        require(key not in result, f'Duplicate {label}: {key}')
        result[key] = tuple(row[keys:])
    return result


def validate_timing(text):
    rows = defaultdict(list)
    for line in text.splitlines():
        if line.strip():
            kind, *values = line.split('\t')
            rows[kind].append(values)
    expected_kinds = {'CLOCK', 'COUNT', 'CHAIN_EDGE', 'CHAIN_TIMING', 'METRIC',
                      'CHECK', 'INPUT_WAIVER', 'OUTPUT_WAIVER', 'UCP', 'STATUS'}
    require(set(rows) == expected_kinds, 'Missing or unknown timing report sections')
    require(rows['STATUS'] == [['POST_FIT_AUDIT_PASS']], 'Incomplete post-fit audit')
    require(rows['CLOCK'] == [['CLOCK_50', '20.000']], 'Expected one 50 MHz clock')
    counts = unique_rows(rows['COUNT'], 1, 'count')
    require(counts == {(k,): (v,) for k, v in {
        'chain_registers': '33', 'chain_edges': '18', 'corners': '3', 'ignored_sdc': '0'
    }.items()}, 'Incomplete counts or ignored SDC constraints')
    require(Counter(map(tuple, rows['CHAIN_EDGE'])) == Counter(EDGES), 'Wrong chain topology')
    metrics = unique_rows(rows['METRIC'], 2, 'metric')
    require(set(metrics) == {(c, m) for c in CORNERS for m in METRICS},
            'Missing/unknown corner or timing category')
    worst = {}
    for (_, kind), values in metrics.items():
        require(len(values) == 2 and int(values[0]) > 0, 'No timed paths')
        slack = nonnegative(values[1])
        worst[kind] = min(worst.get(kind, slack), slack)
    chains = unique_rows(rows['CHAIN_TIMING'], 4, 'chain timing')
    require(set(chains) == {(c, t, a, b) for c in CORNERS for t in ('setup', 'hold')
                           for a, b in EDGES}, 'Missing timed synchronizer edge')
    for values in chains.values():
        require(len(values) == 1, 'Malformed chain slack')
        nonnegative(values[0])
    require(unique_rows(rows['CHECK'], 1, 'check') ==
            {(k,): (v,) for k, v in CHECKS.items()}, 'Unexpected check_timing issue')
    for kind, expected in [('INPUT_WAIVER', INPUTS), ('OUTPUT_WAIVER', OUTPUTS)]:
        require(Counter(map(tuple, rows[kind])) == Counter((p,) for p in expected),
                f'Wrong or missing exact port waivers: {kind}')
    require(unique_rows(rows['UCP'], 1, 'UCP') == {(k,): ('0', '0') for k in UCP},
            'Missing UCP data or unconstrained paths')
    return {'corners': 3, 'worst_slack_ns': dict(sorted(worst.items())),
            'chain_registers': 33, 'chain_edges': 18, 'unconstrained_paths': 0,
            'ignored_sdc': 0}


def validate_pins(text, profile):
    require(len(profile) == len({p['port'] for p in profile}) ==
            len({p['pin'] for p in profile}) == 65, 'Invalid pin profile')
    fitted = {}
    for line in text.splitlines():
        cols = [c.strip() for c in line.split(':')]
        if len(cols) == 7 and cols[2] in ('input', 'output', 'bidir') and cols[6] == 'Y':
            require(cols[0] not in fitted, f'Duplicate fitted port {cols[0]}')
            fitted[cols[0]] = (f'PIN_{cols[1]}', cols[2], cols[3])
    expected = {p['port']: (p['pin'], p['direction'], p['io_standard']) for p in profile}
    require(fitted == expected, 'Fitted locations/directions/I/O standards differ from 65-port profile')
    return {'pin_bits': 65, 'inputs': 22, 'outputs': 43}


def review_warnings(log):
    require(not re.search(r'^\s*(Critical Warning|Error)(?:\s|\()', log, re.M),
            'Quartus error or critical warning')
    warnings = re.findall(r'^\s*Warning \((\d+)\): (.*)$', log, re.M)
    expected = {'10335': 3, '13024': 1, '13410': 6, '21074': 1, '15610': 6,
                '292013': 1, '15714': 1, '169177': 1}
    require(dict(Counter(code for code, _ in warnings)) == expected,
            'Warning inventory changed; human engineering review required')
    for code, message in warnings:
        if code == '10335':
            require('Unrecognized synthesis attribute "async_reg"' in message,
                    'Unexpected synthesis attribute warning')
        elif code == '13410':
            require(re.match(r'Pin "LEDG\[[2-7]\]" is stuck at GND(?: |$)', message),
                    'Unexpected constant output')
        elif code == '15610':
            require(re.match(r'No output dependent on input pin "SW\[(8|9|1[0-3])\]"', message),
                    'Unexpected unused input')
        elif code == '169177':
            require(message.startswith('2 pins must meet Intel FPGA requirements'),
                    'Changed electrical warning')
    require('Quartus Prime Full Compilation was successful. 0 errors' in log,
            'Full compilation did not complete successfully')
    return expected


def validate_simulation(log):
    counts = re.findall(r'SYS_TEST_COMPLETED\|checks=(\d+)', log)
    require(counts == ['4027274', '46', '2361'], f'Incomplete simulation: {counts}')
    require(not re.search(r'\*\* (?:Error|Fatal)|^# Errors: [1-9]', log, re.M),
            'Simulation errors')
    require('SYS_TEST_COMPLETED|checks=2361|frames=192' in log,
            'Missing onehot frame completion')
    require(re.findall(r'^# Errors: (\d+), Warnings: (\d+)', log, re.M) == [('0', '0')] * 4,
            'Missing compiler/simulator summaries or unexpected diagnostics')
    return {'status': 'PASS', 'system_checks': 4027274, 'controller_checks': 46,
            'onehot_checks': 2361, 'onehot_frames': 192, 'uvm_windows': 'NOT_RUN'}


def safe_path(root, name):
    require(isinstance(name, str) and '\\' not in name and ':' not in name,
            f'Invalid relative manifest path: {name}')
    part = PurePosixPath(name)
    require(name and not part.is_absolute() and '..' not in part.parts,
            f'Unsafe manifest path: {name}')
    path = (Path(root) / name).resolve()
    require(path.is_relative_to(Path(root).resolve()), f'Escaping manifest path: {name}')
    return path


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot(root, paths):
    return {name: sha256(safe_path(root, name)) for name in sorted(set(paths))}


def verify_hashes(root, files):
    require(isinstance(files, dict) and bool(files), 'Missing/empty hash manifest')
    for name, expected in files.items():
        path = safe_path(root, name)
        require(isinstance(expected, str) and re.fullmatch('[a-f0-9]{64}', expected),
                f'Invalid SHA-256 for {name}')
        require(path.is_file(), f'Missing sealed file: {name}')
        require(sha256(path) == expected, f'SHA-256 mismatch: {name}')
    return len(files)
