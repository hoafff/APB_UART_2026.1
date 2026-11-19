from pathlib import Path
from itertools import product
import csv
import hashlib
import json
import re
import subprocess

workspace = Path(__file__).resolve().parents[1]
root = workspace / 'docs/spec'
spec_path = workspace / 'docs/01_System_Specification.md'
spec = spec_path.read_text()
requirements = json.loads((root / 'requirements.json').read_text())
legacy = json.loads((root / 'legacy_mapping.json').read_text())
pins = json.loads((root / 'pins.json').read_text())
results = []

def require(condition, message):
    if not condition:
        raise SystemExit(f'SPEC check failed: {message}')

def passed(name, evidence):
    results.append({'check': name, 'result': 'PASS_DOCUMENT_CHECK', 'evidence': evidence})

definitions = re.findall(r'^\| `(TGT-[A-Z]+-\d{2})` \|', spec, re.M)
require(len(definitions) == 80 and len(set(definitions)) == 80,
        'expected 80 unique TARGET requirement definitions in the specification')
require(set(definitions) == {r['id'] for r in requirements},
        'specification requirement IDs differ from requirements.json')
references = set(re.findall(r'\bTGT-[A-Z]+-\d{2}\b', spec))
require(references <= set(definitions), f'undefined requirement IDs: {sorted(references - set(definitions))}')
sections = set(re.findall(r'^#{2,3} (\d+(?:\.\d+)?)\.', spec, re.M))
for row in requirements:
    for section in row['sections'].split(','):
        require(section in sections, f"{row['id']} references missing section {section}")
    require(set(row['acceptance']) <= {'DOC', *('AT%02d' % i for i in range(1, 9))},
            f"{row['id']} references an unknown acceptance group")
    require(row['target_execution_status'] == 'NOT_RUN', f"{row['id']} initial status must be NOT_RUN")
passed('Requirement index and cross-references', '80 unique target IDs; section/group references resolve; initial catalogue statuses remain NOT_RUN; current run results are separate')

old_spec = workspace / 'docs/history/01_System_Specification_v0.3.md'
old_ids = set(re.findall(r'\| `(REQ_[A-Z]+_\d{3})` \|', old_spec.read_text()))
require(len(legacy) == 36 and {row[0] for row in legacy} == old_ids,
        'legacy_mapping.json must cover the 36 original requirement IDs')
for legacy_id, ids, _ in legacy:
    require(set(ids.split(',')) <= set(definitions), f'{legacy_id} maps to an unknown TARGET requirement')
passed('Legacy traceability', 'All 36 legacy requirement IDs have explicit target mappings without overwriting the old SPEC')

pin_source = workspace / 'reference/DE2_115_pin_assignments.csv'
source_hash = hashlib.sha256(pin_source.read_bytes()).hexdigest()
require(source_hash == 'b3bedb3419d6ed39db5bc913e0910ec6dc4cb990e93b347cdfe765308ca0ba17',
        f'SHA-256 mismatch for {pin_source.name}')
lines = pin_source.read_text().splitlines()
start = next(i for i, line in enumerate(lines) if line.startswith('To,'))
source_rows = {row['To']: row for row in csv.DictReader(lines[start:])}
require(len(pins) == len({p['port'] for p in pins}) == len({p['pin'] for p in pins}) == 65,
        'pins.json must list 65 unique ports and physical pins')
for p in pins:
    source = source_rows[p['board_signal']]
    require(p['pin'] == source['Location'] and p['io_standard'] == source['I/O Standard'],
            f"{p['port']} location or I/O standard differs from the board CSV")
    table_row = f"| `{p['port']}` | {p['direction']} | `{p['board_signal']}` | `{p['pin']}` | {p['io_standard']} |"
    require(table_row in spec, f"{p['port']} pin row in the specification differs from pins.json")
require(sum(p['direction'] == 'input' for p in pins) == 22, 'expected 22 input pins')
passed('Board pin map', '65/65 names, locations and I/O standards match CSV; 22 inputs, 43 outputs; no duplicate pin; physical voltage not checked')

baud_rows = []
for baud, expected in [(9600, 326), (19200, 163), (38400, 81), (57600, 54), (115200, 27)]:
    divisor = round(50_000_000 / (16 * baud))
    require(divisor == expected, f'{baud} baud: expected divisor {expected}, got {divisor}')
    baud_rows.append({'target': baud, 'divisor': divisor, 'actual_calculated': 50_000_000/(16*divisor),
                      'error_percent': (50_000_000/(16*divisor)/baud-1)*100})
require(16 * 27 == 432 and 432 * 20 == 8640, 'default bit period must be 432 clocks / 8640 ns')
require((1+8+0+1) * 432 == 4320, 'default 8N1 frame must take 4320 clocks')
require(500_000 * 20 == 10_000_000 and 5000 * 20 == 100_000, 'debounce or polling interval mismatch')
require(16 * 65535 * 12 < 2**24, 'maximum frame duration exceeds the 24-bit counter')
passed('Timing arithmetic', {'baud_rows': baud_rows, 'default_bit_ns': 8640,
                             'default_8n1_frame_ns': 86400, 'debounce_ns': 10000000,
                             'poll_ns': 100000, 'maximum_12bit_frame_ns': 16*65535*12*20})

cases = 0
for n, parity, stops, divisor, rate, phase in product(range(5,9), [0,1], [1,2], [1,27,326,65535], [.98,1,1.02], [0,.25,.5,.75,1]):
    # Pure ideal timing consistency check, not a model of analog metastability or RTL.
    frame_bits = 1+n+parity+stops
    last_stop = frame_bits-1
    for bit_index in range(frame_bits):
        remote_start = bit_index*16*divisor/rate
        remote_end = (bit_index+1)*16*divisor/rate
        samples = [(16*bit_index + tick)*divisor + phase for tick in [7,8,9]]
        require(sum(remote_start <= t < remote_end for t in samples) >= 2,
                f'RX majority outside bit {bit_index} at divisor {divisor}, rate {rate}, phase {phase}')
    decision = (16*last_stop+9)*divisor+phase
    earliest_next_start = frame_bits*16*divisor/rate
    require(decision+1 < earliest_next_start,
            f'RX stop decision overlaps next start at divisor {divisor}, rate {rate}, phase {phase}')
    cases += 1
passed('RX sample-window arithmetic', f'{cases} ideal cases: majority lies inside its intended peer bit; clean-stop decision plus one clock precedes next peer start at ±2%; not an RTL/tolerance pass')

fifo_cases = 0
for cap in [1,16]:
    for count, push, pop in product(range(cap+1), [0,1], [0,1]):
        pop_ok = bool(pop and count)
        push_ok = bool(push and (count<cap or pop_ok))
        after = count + int(push_ok) - int(pop_ok)
        require(0 <= after <= cap, f'FIFO occupancy {after} outside 0..{cap}')
        if count == 0 and push and pop:
            require(after == 1 and not pop_ok, 'empty FIFO must accept only the simultaneous push')
        if count == cap and push and pop:
            require(after == cap and push_ok, 'full FIFO must replace the popped entry on simultaneous push')
        if count == cap and push and not pop:
            require(not push_ok and after == cap, 'full FIFO must reject a push without a pop')
        fifo_cases += 1
passed('FIFO transition rules', f'{fifo_cases} occupancy/push/pop combinations respect bounds and specified full/empty behavior; formula check only')

irq_cases = 0
for fifo_on, ier, rx_count, threshold, error, tx_pending in product([0,1],range(8),range(17),[1,4,8,14],[0,1],[0,1]):
    if not fifo_on and rx_count>1: continue
    threshold_eff = threshold if fifo_on else 1
    code = 6 if (ier&4 and error) else 4 if (ier&1 and rx_count>=threshold_eff) else 2 if (ier&2 and tx_pending) else 1
    iir = (0xC0 if fifo_on else 0) | code
    event = code != 1
    require((iir & 1) == (0 if event else 1), 'IIR pending bit disagrees with IRQ event')
    require(iir not in [0,0xC0], f'unexpected IIR value {iir:#04x}')
    if ier == 0:
        require(not event, 'IRQ event while all interrupts are disabled')
    if ier == 1 and rx_count == 0:
        require(not event, 'RX-only IRQ event with an empty RX FIFO')
    irq_cases += 1
passed('IIR truth-table consistency', f'{irq_cases} modeled combinations; no-source returns bit0=1; RDA independent of TX-empty; not implementation verification')

digits = ['abcdef','bc','abdeg','abcdg','bcfg','acdfg','acdefg','abc','abcdefg','abcdfg','abcefg','cdefg','adef','bcdeg','adefg','aefg']
patterns = ['1000000','1111001','0100100','0110000','0011001','0010010','0000010','1111000','0000000','0010000','0001000','0000011','1000110','0100001','0000110','0001110']
for on, pattern in zip(digits, patterns, strict=True):
    derived = ''.join('0' if s in on else '1' for s in 'gfedcba')
    require(derived == pattern and pattern in spec, f'HEX pattern {pattern} invalid or missing from specification')
passed('HEX decoder table', 'All 16 patterns agree with {g,f,e,d,c,b,a} active-low convention')

require(spec.count('```') % 2 == 0, 'unbalanced Markdown code fences')
require(not re.search(r'@[A-Z_]+@', spec), 'unresolved template placeholder in specification')
require(all(('**AT%02d —' % i) in spec for i in range(1,9)), 'expected acceptance headings AT01 through AT08')
require(all(('## %d.' % i) in spec for i in range(1,18)), 'expected specification sections 1 through 17')
table_len = None
for number, line in enumerate(spec.splitlines(),1):
    if line.startswith('|'):
        columns = len(line.split('|'))
        if table_len is not None:
            require(columns == table_len, f'inconsistent Markdown table width at line {number}')
        table_len = columns
    else:
        table_len = None
passed('Markdown structure', 'All 17 sections, 8 acceptance groups, balanced code fences and consistent table column counts present')

hashes = json.loads((root / 'baseline_hashes.json').read_text())
for name, expected in hashes.items():
    require(hashlib.sha256((workspace/name).read_bytes()).hexdigest() == expected, f'SHA-256 mismatch for {name}')
passed('Vendor baseline preservation', 'All pinned vendor source hashes unchanged')

report = {'artifact': spec_path.name, 'sha256': hashlib.sha256(spec_path.read_bytes()).hexdigest(),
          'results': results, 'limitations': ['Document and ideal contract arithmetic checks only',
             'This checker does not simulate RTL', 'No Quartus/STA/physical FPGA checks']}
(workspace / 'build/spec').mkdir(parents=True, exist_ok=True)
(workspace / 'build/spec/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'passed_checks':len(results),'requirements':len(requirements),
                  'pin_bits':len(pins),'legacy_ids':len(legacy),'rx_ideal_cases':cases,
                  'fifo_rule_cases':fifo_cases,'irq_rule_cases':irq_cases},indent=2))
