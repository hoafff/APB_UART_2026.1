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

def passed(name, evidence):
    results.append({'check': name, 'result': 'PASS_DOCUMENT_CHECK', 'evidence': evidence})

definitions = re.findall(r'^\| `(TGT-[A-Z]+-\d{2})` \|', spec, re.M)
assert len(definitions) == 80 and len(set(definitions)) == 80
assert set(definitions) == {r['id'] for r in requirements}
references = set(re.findall(r'\bTGT-[A-Z]+-\d{2}\b', spec))
assert references <= set(definitions)
sections = set(re.findall(r'^#{2,3} (\d+(?:\.\d+)?)\.', spec, re.M))
for row in requirements:
    for section in row['sections'].split(','):
        assert section in sections, (row['id'], section)
    assert set(row['acceptance']) <= {'DOC', *('AT%02d' % i for i in range(1, 9))}
    assert row['target_execution_status'] == 'NOT_RUN'
passed('Requirement index and cross-references', '80 unique target IDs; section/group references resolve; all target execution statuses NOT_RUN')

old_spec = workspace / 'docs/history/01_System_Specification_v0.3.md'
old_ids = set(re.findall(r'\| `(REQ_[A-Z]+_\d{3})` \|', old_spec.read_text()))
assert len(legacy) == 36 and {row[0] for row in legacy} == old_ids
for _, ids, _ in legacy:
    assert set(ids.split(',')) <= set(definitions)
passed('Legacy traceability', 'All 36 legacy requirement IDs have explicit target mappings without overwriting the old SPEC')

pin_source = workspace / 'reference/DE2_115_pin_assignments.csv'
source_hash = hashlib.sha256(pin_source.read_bytes()).hexdigest()
assert source_hash == 'b3bedb3419d6ed39db5bc913e0910ec6dc4cb990e93b347cdfe765308ca0ba17'
lines = pin_source.read_text().splitlines()
start = next(i for i, line in enumerate(lines) if line.startswith('To,'))
source_rows = {row['To']: row for row in csv.DictReader(lines[start:])}
assert len(pins) == len({p['port'] for p in pins}) == len({p['pin'] for p in pins}) == 65
for p in pins:
    source = source_rows[p['board_signal']]
    assert p['pin'] == source['Location'] and p['io_standard'] == source['I/O Standard']
    assert f"| `{p['port']}` | {p['direction']} | `{p['board_signal']}` | `{p['pin']}` | {p['io_standard']} |" in spec
assert sum(p['direction'] == 'input' for p in pins) == 22
passed('Board pin map', '65/65 names, locations and I/O standards match CSV; 22 inputs, 43 outputs; no duplicate pin; physical voltage not checked')

baud_rows = []
for baud, expected in [(9600, 326), (19200, 163), (38400, 81), (57600, 54), (115200, 27)]:
    divisor = round(50_000_000 / (16 * baud))
    assert divisor == expected
    baud_rows.append({'target': baud, 'divisor': divisor, 'actual_calculated': 50_000_000/(16*divisor),
                      'error_percent': (50_000_000/(16*divisor)/baud-1)*100})
assert 16 * 27 == 432 and 432 * 20 == 8640
assert (1+8+0+1) * 432 == 4320
assert 500_000 * 20 == 10_000_000 and 5000 * 20 == 100_000
assert 16 * 65535 * 12 < 2**24
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
        assert sum(remote_start <= t < remote_end for t in samples) >= 2
    decision = (16*last_stop+9)*divisor+phase
    earliest_next_start = frame_bits*16*divisor/rate
    assert decision+1 < earliest_next_start
    cases += 1
passed('RX sample-window arithmetic', f'{cases} ideal cases: majority lies inside its intended peer bit; clean-stop decision plus one clock precedes next peer start at ±2%; not an RTL/tolerance pass')

fifo_cases = 0
for cap in [1,16]:
    for count, push, pop in product(range(cap+1), [0,1], [0,1]):
        pop_ok = bool(pop and count)
        push_ok = bool(push and (count<cap or pop_ok))
        after = count + int(push_ok) - int(pop_ok)
        assert 0 <= after <= cap
        if count == 0 and push and pop: assert after == 1 and not pop_ok
        if count == cap and push and pop: assert after == cap and push_ok
        if count == cap and push and not pop: assert not push_ok and after == cap
        fifo_cases += 1
passed('FIFO transition rules', f'{fifo_cases} occupancy/push/pop combinations respect bounds and specified full/empty behavior; formula check only')

irq_cases = 0
for fifo_on, ier, rx_count, threshold, error, tx_pending in product([0,1],range(8),range(17),[1,4,8,14],[0,1],[0,1]):
    if not fifo_on and rx_count>1: continue
    threshold_eff = threshold if fifo_on else 1
    code = 6 if (ier&4 and error) else 4 if (ier&1 and rx_count>=threshold_eff) else 2 if (ier&2 and tx_pending) else 1
    iir = (0xC0 if fifo_on else 0) | code
    event = code != 1
    assert (iir & 1) == (0 if event else 1)
    assert iir not in [0,0xC0]
    if ier == 0: assert not event
    if ier == 1 and rx_count == 0: assert not event
    irq_cases += 1
passed('IIR truth-table consistency', f'{irq_cases} modeled combinations; no-source returns bit0=1; RDA independent of TX-empty; not implementation verification')

digits = ['abcdef','bc','abdeg','abcdg','bcfg','acdfg','acdefg','abc','abcdefg','abcdfg','abcefg','cdefg','adef','bcdeg','adefg','aefg']
patterns = ['1000000','1111001','0100100','0110000','0011001','0010010','0000010','1111000','0000000','0010000','0001000','0000011','1000110','0100001','0000110','0001110']
for on, pattern in zip(digits, patterns, strict=True):
    derived = ''.join('0' if s in on else '1' for s in 'gfedcba')
    assert derived == pattern and pattern in spec
passed('HEX decoder table', 'All 16 patterns agree with {g,f,e,d,c,b,a} active-low convention')

assert spec.count('```') % 2 == 0
assert not re.search(r'@[A-Z_]+@', spec)
assert all(('**AT%02d —' % i) in spec for i in range(1,9))
assert all(('## %d.' % i) in spec for i in range(1,18))
table_len = None
for number, line in enumerate(spec.splitlines(),1):
    if line.startswith('|'):
        columns = len(line.split('|'))
        if table_len is not None: assert columns == table_len, (number, columns, table_len)
        table_len = columns
    else:
        table_len = None
passed('Markdown structure', 'All 17 sections, 8 acceptance groups, balanced code fences and consistent table column counts present')

hashes = json.loads((root / 'baseline_hashes.json').read_text())
for name, expected in hashes.items():
    assert hashlib.sha256((workspace/name).read_bytes()).hexdigest() == expected, name
passed('Vendor baseline preservation', 'All pinned vendor source hashes unchanged')

report = {'artifact': spec_path.name, 'sha256': hashlib.sha256(spec_path.read_bytes()).hexdigest(),
          'results': results, 'limitations': ['Document and ideal contract arithmetic checks only',
             'This checker does not simulate RTL', 'No Quartus/STA/physical FPGA checks']}
(workspace / 'build/spec').mkdir(parents=True, exist_ok=True)
(workspace / 'build/spec/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'passed_checks':len(results),'requirements':len(requirements),
                  'pin_bits':len(pins),'legacy_ids':len(legacy),'rx_ideal_cases':cases,
                  'fifo_rule_cases':fifo_cases,'irq_rule_cases':irq_cases},indent=2))
