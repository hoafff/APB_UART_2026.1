"""Decode completed UVM reports and hold the declared functional-bin denominator."""
import hashlib
import re
from collections import Counter
from itertools import product


DIRECTED = ("registers", "baud", "modes", "fifo", "errors", "irq", "thresholds")
SEEDS = (17, 29, 101)
GROUPS = {
    "apb": [f"{rw}_{off}_{page}" for rw, off, page in product("RW", range(8), range(2))],
    "alias": [f"{rw}_{high}" for rw, high in product("RW", range(2))],
    "lcr": [f"bits654_{n}" for n in range(8)],
    "serial": [f"{d}_{w}_{p}_{s}" for d, w, p, s in
               product(("RX", "TX"), range(5, 9), range(2), (1, 2))],
    "lsr": ["dr_0", "dr_1", "tx_00", "tx_01", "tx_11"],
    "fifo": ["bit0_0", "bit0_1", "rx_clear", "rx_17_of_18", "tx_17_of_18", "tx_clear_inflight",
             "both_clear_6", "both_clear_7"],
    "fault": [f"pe{p}_stop{s}" for p, s in product(range(2), repeat=2)],
    "irq": ["disabled", "rda_empty", "rda_with_rx", "clear_code_zero",
            "thre_empty", "rda_over_thre", "line_status_silent", "masked_first", "masked_second",
            "unrelated_reads", "empty_rbr_ack", "lsr_ack"],
    "trigger": [f"{t}_{t+d}" for t, d in product((1, 4, 8, 14), (-1, 0, 1))],
}
NEGATIVE = {
    "tx": ("TX_DATA", "55", "54"),
    "rbr": ("RBR_DATA", "96", "97"),
}


def normal_lines(raw):
    # Questa's stdout prefixes simulation output with "# ".
    return "\n".join(line.removeprefix("# ") for line in raw.splitlines())


def inspect_run(raw, case, seed, inject, rc):
    log = normal_lines(raw)
    done = re.findall(r"^DONE\|case=(\w+)\|seed=(\d+)\|setups=(\d+)\|accesses=(\d+)\|gated=(\d+)$", log, re.M)
    totals = re.findall(r"^SB\|checks=(\d+)\|tx=(\d+)\|rx_wire=(\d+)\|rbr=(\d+)\|tx_drop=(\d+)\|rx_drop=(\d+)$", log, re.M)
    severities = {}
    for kind in ("ERROR", "FATAL"):
        counts = re.findall(rf"^\s*UVM_{kind}\s*:\s*(\d+)\s*$", log, re.M)
        severities[kind] = int(counts[0]) if len(counts) == 1 else None
    observed = {}
    problems = []
    for group, bin_name, count in re.findall(r"^COV\|([^|]+)\|([^|]+)\|(\d+)$", log, re.M):
        key = f"{group}|{bin_name}"
        if bin_name not in GROUPS.get(group, ()) or key in observed:
            problems.append(f"unexpected/duplicate coverage bin {key}")
        observed[key] = int(count)
    sb = dict(zip(("checks", "tx", "rx_wire", "rbr", "tx_drop", "rx_drop"),
                  map(int, totals[0]))) if len(totals) == 1 else {}
    bus = {}
    if len(done) == 1:
        name, sim_seed, setups, accesses, gated = done[0]
        bus = dict(setups=int(setups), accesses=int(accesses), gated=int(gated))
        if name != case or int(sim_seed) != seed:
            problems.append("wrong test identity in DONE")
        if bus["setups"] != bus["accesses"] + (2 if case == "registers" else 0) or min(bus.values()) <= 0:
            problems.append("APB monitor counts disagree")
        if sum(v for k, v in observed.items() if k.startswith("apb|")) != bus["accesses"]:
            problems.append("APB cross samples disagree with completed transfers")
    else:
        problems.append("missing/duplicate test completion")
    if not sb.get("checks") or not observed:
        problems.append("scoreboard or coverage did not execute")
    # Compare against independent case-sized output counts. A silent subtest is a failure.
    counts = {
        "registers": (17, 1, 1), "baud": (3, 3, 3), "modes": (32, 32, 32),
        "fifo": (22, 30, 23), "errors": (0, 4, 4), "irq": (0, 2, 2),
        "thresholds": (24, 81, 81),
    }
    if case in counts and tuple(sb.get(k) for k in ("tx", "rx_wire", "rbr")) != counts[case]:
        problems.append("case-specific serial counts disagree")
    trace = re.findall(r"^STIM\|[^\n]+$", log, re.M)
    if case == "random":
        if sum(s.startswith("STIM|reg|") for s in trace) != 48 or sum(s.startswith("STIM|frame|") for s in trace) != 32:
            problems.append("random stimulus count mismatch")
        if sb.get("tx", 0) + sb.get("rbr", 0) != 32 or sb.get("rx_wire") != sb.get("rbr"):
            problems.append("random frame checks missing")
    if case == "baud" and len(re.findall(r"^EDGE\|", log, re.M)) != 20:
        problems.append("missing transition measurements")
    if case == "modes" and len(re.findall(r"^SPACING\|", log, re.M)) != 16:
        problems.append("missing queued-frame measurements")
    if case == "thresholds" and len(re.findall(r"^THRESHOLD\|", log, re.M)) != 12:
        problems.append("missing threshold observations")
    if case == "errors" and len(re.findall(r"^FAULT\|", log, re.M)) != 4:
        problems.append("missing per-byte fault observations")
    diagnostic = None
    if inject:
        ident, wire, expected = NEGATIVE[inject]
        injection = f"INJECT|{ident}|wire={wire}|perturbed_expected={expected}"
        if injection not in log:
            problems.append("expected one-bit injection did not occur")
        diagnostic = re.findall(rf"^UVM_ERROR [^\n]*\[{ident}\] observed=000000{wire} expected=000000{expected}$", log, re.M)
        if len(diagnostic) != 1 or severities != {"ERROR": 1, "FATAL": 0}:
            problems.append("wrong UVM diagnostic or severity counts")
        if rc == 0 or "DV_CHECKS_FAILED" not in log or "DV_EXIT|PASS" in log:
            problems.append("process did not reject checker failure")
        verdict = "DETECTED" if not problems else "FAIL"
    else:
        if rc != 0 or severities != {"ERROR": 0, "FATAL": 0} or "DV_EXIT|PASS" not in log:
            problems.append("process status, UVM counts or end marker failed")
        verdict = "PASS" if not problems else "FAIL"
    return dict(verdict=verdict, problems=problems, scoreboard=sb, bus=bus, uvm=severities,
                diagnostic=diagnostic[0] if diagnostic else None, bins=observed,
                stimulus_sha256=hashlib.sha256(("\n".join(trace)+"\n").encode()).hexdigest() if trace else None)


def combine(rows):
    counts = Counter()
    for row in rows:
        if row["role"] == "normal" and row["verdict"] == "PASS":
            counts.update(row["bins"])
    groups = {}
    for name, names in GROUPS.items():
        bins = {key: counts[f"{name}|{key}"] for key in names}
        groups[name] = dict(hit=sum(v > 0 for v in bins.values()), total=len(bins),
                            samples=sum(bins.values()), bins=bins)
    return groups


def native_counts(data, observed):
    """Read the Verilator Coverage-3 counters and cross-check every cross cell."""
    text = data.decode("utf-8")
    if not text.startswith("# SystemC::Coverage-3"):
        raise ValueError("Unrecognized native coverage format")
    pattern = re.compile(r"\x01h\x02pulp_uart_pkg::uart_scoreboard::(apb_cg|serial_cg)\.(\w+)\.([^']+)' (\d+)$")
    counters = {}
    for line in text.splitlines():
        m = pattern.search(line)
        if not m:
            continue
        group, point, label, value = m.groups()
        name = ".".join((group, point, label))
        if name in counters:
            raise ValueError(f"Duplicate native coverage record {name}")
        counters[name] = int(value)
        if point == "access_cross":
            wr, off, page = map(int, re.fullmatch(r"<auto_(\d),offsets\[(\d)\],auto_(\d)>", label).groups())
            key = f"apb|{'W' if wr else 'R'}_{off}_{page}"
        elif point == "frame_cross":
            tx, w, p, s = map(int, re.fullmatch(r"<auto_(\d),sizes\[(\d)\],auto_(\d),count\[(\d)\]>", label).groups())
            key = f"serial|{'TX' if tx else 'RX'}_{5+w}_{p}_{1+s}"
        else:
            continue
        if counters[name] != observed.get(key, 0):
            raise ValueError(f"Native covergroup differs from observed {key}")
    if len(counters) != 86:  # 22 individual coverpoint bins and two 32-bin crosses.
        raise ValueError(f"Expected 86 native records, found {len(counters)}")
    return counters
