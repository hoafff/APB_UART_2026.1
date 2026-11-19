#!/usr/bin/env python3
"""Validate traceability/schema/source connections; never infer hardware PASS."""
from pathlib import Path
import hashlib,json,re

def require(condition, message):
    if not condition:
        raise SystemExit(f'DV document check failed: {message}')

root=Path(__file__).resolve().parents[1]
requirements=json.loads((root/'docs/spec/requirements.json').read_text())
trace=json.loads((root/'docs/dv/traceability.json').read_text())
cases=json.loads((root/'docs/dv/testcases.json').read_text())
coverage=json.loads((root/'docs/dv/coverage_model.json').read_text())
require(len(trace)==80 and {r['requirement_id'] for r in trace}=={r['id'] for r in requirements},
        'traceability.json must cover the 80 specification requirement IDs')
case_ids={c['id'] for c in cases}
require(len(case_ids)==len(cases), 'duplicate testcase ID in testcases.json')
for row in trace:
    require(row['testcase_ids'] and set(row['testcase_ids'])<=case_ids,
            f"{row['requirement_id']} needs valid testcase IDs")
    require(row['observer'] and row['acceptance_meaning'],
            f"{row['requirement_id']} needs an observer and acceptance meaning")
    for name in row['rtl_owners']:
        require((root/name).is_file(), f"{row['requirement_id']} references missing RTL owner {name}")
for c in cases:
    source=(root/c['source']).read_text()
    if c['kind']=='UVM':
        require(re.search(r'\bclass\s+'+c['name']+r'\b',source), f"missing class {c['name']} in {c['source']}")
    if c['kind'] in ['SYSTEM_SIM','SUPPLEMENTAL_RTL']:
        require(re.search(r'\bmodule\s+'+c['name']+r'\b',source), f"missing module {c['name']} in {c['source']}")
    require(c['requirement_ids'], f"{c['id']} has no requirement IDs")
    require(c['stimulus'] and c['oracle'] and c['pass_fail'], f"{c['id']} needs stimulus, oracle and pass/fail criteria")
all_bins=[b for g in coverage['groups'].values() for b in g]
require(len(all_bins)==len(set(all_bins)), 'duplicate functional coverage bin')
require(len(coverage['groups']['uart_modes'])==48, 'expected 48 UART mode bins')
require(len(coverage['groups']['tx_onehot'])==192, 'expected 192 TX one-hot bins')
require(coverage['required_random_seeds']==[17,29,101], 'required random seeds must be 17, 29 and 101')
# Compare the real top-level port declarations with every entry in the pin map.
pins=json.loads((root/'docs/spec/pins.json').read_text())
ports={}
for line in (root/'rtl/fpga/de2_115_apb_uart_bringup.sv').read_text().splitlines():
 m=re.match(r'\s*(input|output) logic(?: \[(\d+):0\])? (.+?)[,]?$',line)
 if m:
  direction,hi,names=m.groups()
  for name in names.rstrip(',').split(','):
   name=name.strip()
   if hi is None: ports[name]=direction
   else:
    for bit in range(int(hi)+1): ports[f'{name}[{bit}]']=direction
require(len(ports)==65, f'expected 65 top-level RTL port bits, found {len(ports)}')
pin_directions={p['port']:p['direction'] for p in pins}
require(ports.keys()==pin_directions.keys(), 'RTL port names differ from pins.json')
for name, direction in ports.items():
    require(pin_directions[name]==direction, f'{name}: pins.json gives {pin_directions[name]}, RTL declares {direction}')
print(json.dumps({'result':'PASS_DOCUMENT_CHECK','requirements':len(trace),'testcase_definitions':len(cases),'mandatory_functional_bins':len(all_bins),'actual_top_ports_match_pin_map':65,'limitations':'Does not execute RTL or close requirements'},indent=2))
