#!/usr/bin/env python3
"""Validate traceability/schema/source connections; never infer hardware PASS."""
from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parents[1]
requirements=json.loads((root/'docs/spec/requirements.json').read_text())
trace=json.loads((root/'docs/dv/traceability.json').read_text())
cases=json.loads((root/'docs/dv/testcases.json').read_text())
coverage=json.loads((root/'docs/dv/coverage_model.json').read_text())
assert len(trace)==80 and {r['requirement_id'] for r in trace}=={r['id'] for r in requirements}
case_ids={c['id'] for c in cases}; assert len(case_ids)==len(cases)
for row in trace:
 assert row['testcase_ids'] and set(row['testcase_ids'])<=case_ids
 assert row['observer'] and row['acceptance_meaning']
 for name in row['rtl_owners']: assert (root/name).is_file(),name
for c in cases:
 source=(root/c['source']).read_text()
 if c['kind']=='UVM': assert re.search(r'\bclass\s+'+c['name']+r'\b',source),c['name']
 if c['kind'] in ['SYSTEM_SIM','SUPPLEMENTAL_RTL']: assert re.search(r'\bmodule\s+'+c['name']+r'\b',source),c['name']
 assert c['requirement_ids']
 assert c['stimulus'] and c['oracle'] and c['pass_fail']
all_bins=[b for g in coverage['groups'].values() for b in g]
assert len(all_bins)==len(set(all_bins))
assert len(coverage['groups']['uart_modes'])==48
assert len(coverage['groups']['tx_onehot'])==192
assert coverage['required_random_seeds']==[17,29,101]
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
assert len(ports)==65,(len(ports),ports)
assert ports=={p['port']:p['direction'] for p in pins}
print(json.dumps({'result':'PASS_DOCUMENT_CHECK','requirements':len(trace),'testcase_definitions':len(cases),'mandatory_functional_bins':len(all_bins),'actual_top_ports_match_pin_map':65,'limitations':'Does not execute RTL or close requirements'},indent=2))
