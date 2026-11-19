"""Static project/pin checks. With --netlist, audit an OSS-elaborated board and replay its Tcl constraints."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "fpga/de2_115"
TOP = "de2_115_pulp_uart"
DEVICE = "EP4CE115F29C7"
SW_BITS = (*range(8), 14, 16, 17)
RX_REG = "apb_uart_sv:uart|uart_rx:uart_rx_i|reg_rx_sync"
GPIO = {"GPIO_UART_RX": "GPIO[2]", "GPIO_UART_TX": "GPIO[0]"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def port_bits(bus, width):
    return [bus] if width == 1 else [f"{bus}[{i}]" for i in range(width)]


def terasic_pins(path=ROOT / "reference/DE2_115_pin_assignments.csv"):
    with path.open(newline="") as stream:
        return {row[0]: row for row in csv.reader(stream) if len(row) >= 6 and row[2].startswith("PIN_")}


def qsf_lines(path):
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            yield line


def check_files():
    # Resolves tools/ and docs/spec/ relative to this checkout (also in a staged build).
    upstream = subprocess.run([sys.executable, str(ROOT / "tools/check_upstream.py")], cwd=ROOT)
    if upstream.returncode:
        raise SystemExit(upstream.returncode)
    qpf = (PROJECT / f"{TOP}.qpf").read_text()
    require(re.findall(r'^PROJECT_REVISION = "([^"]+)"$', qpf, re.M) == [TOP], "QPF revision")

    # These two QSF files are declarative. Consume every command so an extra
    # input or pin override cannot disappear between preflight and Quartus.
    settings = defaultdict(list)
    includes = []
    for line in qsf_lines(PROJECT / f"{TOP}.qsf"):
        include = re.fullmatch(r"source\s+([\w.]+)", line)
        if include:
            includes.append(include[1])
            continue
        assignment = re.fullmatch(r'set_global_assignment\s+-name\s+(\w+)\s+'
                                  r'(?:"([^"$\[\\]+)"|\{([^{}]+)\}|([\w./-]+))', line)
        require(assignment, f"unrecognized project QSF command: {line}")
        key = assignment[1].upper()
        require(not key.endswith(("_FILE", "_FILES")) or key in ("SYSTEMVERILOG_FILE", "SDC_FILE"),
                f"unstaged QSF input {key}: {line}")
        settings[key].append(next(value for value in assignment.groups()[1:] if value is not None))

    for key, value in {"FAMILY": "Cyclone IV E", "DEVICE": DEVICE, "TOP_LEVEL_ENTITY": TOP,
                       "SDC_FILE": f"{TOP}.sdc", "RESERVE_ALL_UNUSED_PINS": "AS INPUT TRI-STATED",
                       "PROJECT_OUTPUT_DIRECTORY": "../build/output_files"}.items():
        require(settings[key] == [value], f"QSF {key}")
    require(includes == ["pins.qsf", "synchronizers.qsf"], "QSF includes")
    require((PROJECT / "synchronizers.qsf").is_file(), "synchronizer assignment file")
    sdc = (PROJECT / f"{TOP}.sdc").read_text()
    require(re.findall(r"^create_(?:generated_)?clock\b.*$", sdc, re.M) ==
            ["create_clock -name CLOCK_50 -period 20.000 [get_ports {CLOCK_50}]"], "SDC clock declaration")
    vendor = ROOT / "rtl/vendor/pulp_apb_uart_sv"
    manifest = re.findall(r"\b\w+\.sv\b", (vendor / "src_files.yml").read_text())
    expected = {vendor / f for f in manifest} | {ROOT / "rtl/fpga" / f for f in
                                               ("de2_pulp_uart_master.sv", f"{TOP}.sv")}
    files = (PROJECT / "rtl.f").read_text().splitlines()
    require(files == settings["SYSTEMVERILOG_FILE"] and len(files) == 7 and len(manifest) == 5,
            "QSF, local filelist or vendor manifest mismatch")
    require(all(not Path(f).is_absolute() for f in files) and
            {(PROJECT / f).resolve(strict=True) for f in files} == expected, "source paths")

    rtl = (ROOT / "rtl/fpga" / f"{TOP}.sv").read_text()
    require(re.search(rf"^module {TOP}\s*\(", rtl, re.M), "top module declaration")
    ports = {}
    for direction, msb, bus in re.findall(r"^\s*(input|output)\s+logic\s+(?:\[(\d+):0\]\s+)?(\w+),?\s*$", rtl, re.M):
        ports.update(dict.fromkeys(port_bits(bus, int(msb or 0) + 1), direction))
    require(Counter(ports.values()) == {"input": 22, "output": 43}, "top port declaration")

    locations, standards = [], []
    port_arg = r'\s+-to\s+(?:\{([\w\[\]]+)\}|(\w+))'
    for line in qsf_lines(PROJECT / "pins.qsf"):
        loc = re.fullmatch(r"set_location_assignment\s+(PIN_\w+)" + port_arg, line)
        if loc:
            locations.append((loc[1], loc[2] or loc[3]))
        else:
            io = re.fullmatch(r'set_instance_assignment\s+-name\s+IO_STANDARD\s+"([\w. -]+)"' + port_arg, line)
            require(io, f"unrecognized pin QSF command: {line}")
            standards.append((io[1], io[2] or io[3]))
    location = {port: pin for pin, port in locations}
    standard = {port: io for io, port in standards}
    require(len(locations) == len(standards) == len(set(location.values())) == 65 and
            set(location) == set(standard) == set(ports), "65 unique pin and I/O assignments")
    board = terasic_pins()
    for port, direction in ports.items():
        row = board[GPIO.get(port, port)]
        require((location[port], standard[port]) == (row[2], row[5]), f"Terasic location/I/O {port}")
        require(row[1].lower() == ("bidir" if port in GPIO else direction), f"Terasic direction {port}")
    print("PROJECT PASS  EP4CE115F29C7 / de2_115_pulp_uart, 5 original manifest sources + 2 board sources, 20 ns SDC")
    print("PINS PASS  65 unique Terasic locations and standards, 22 input / 43 output bits")
    return ports


def check_netlist(path, ports):
    from tkinter import Tcl  # offline Tcl replay only, no display required

    net = json.loads(path.read_text())["modules"][TOP]
    actual = {port: info["direction"] for name, info in net["ports"].items()
              for port in port_bits(name, len(info["bits"]))}
    require(actual == ports, "elaborated top ports differ from pin contract")
    drivers = {}
    for cell in net["cells"].values():
        for i, bit in enumerate(cell["connections"].get("Y", [])):
            drivers[bit] = (cell["type"], cell["connections"], i)

    def source(bit):
        # The Slang frontend keeps instance port buffers and constant cfg_en muxes.
        while bit in drivers:
            kind, pins, i = drivers[bit]
            if kind == "$buf":
                bit = pins["A"][i]
            elif kind == "$mux" and (sel := source(pins["S"][0])) in ("0", "1"):
                bit = pins["B" if sel == "1" else "A"][i]
            else:
                break
        return bit

    clock = net["ports"]["CLOCK_50"]["bits"][0]
    data_input = {}
    clocked = 0
    for cell in net["cells"].values():
        pins = cell["connections"]
        if "CLK" in pins:
            require([source(b) for b in pins["CLK"]] == [clock] and
                    int(cell["parameters"]["CLK_POLARITY"], 2) == 1, "unexpected sequential clock")
            data_input.update({q: source(d) for q, d in zip(pins["Q"], pins["D"])})
            clocked += 1
        for name in ("RD_CLK", "WR_CLK"):
            for i, bit in enumerate(pins.get(name, [])):
                if int(cell["parameters"][name + "_ENABLE"], 2) & (1 << i):
                    require(source(bit) == clock, "unexpected memory clock")
    require(clocked > 0, "empty clock domain")

    def stages(bus, bits):
        return [f"{bus}[{i}]" for i in bits]

    chains = [stages("reset_sync", range(2)), stages("key_sync", range(2)),
              stages("rx_sync", range(2)) + stages(RX_REG, range(3))]
    chains.extend([[f"sw_meta[{i}]", f"sw_sync[{i}]"] for i in SW_BITS])
    registers = {}
    for chain in chains:
        for register in chain:
            name, index = register[:-1].rsplit("[", 1)
            yosys_name = "uart.uart_rx_i.reg_rx_sync" if name == RX_REG else name
            q = source(net["netnames"][yosys_name]["bits"][int(index)])
            require(q in data_input, f"missing sequential register {register}")
            registers[register] = q
        for first, second in zip(chain, chain[1:]):
            require(data_input[registers[second]] == registers[first], f"CDC hop {first} -> {second}")
    require(len(set(registers.values())) == 31, "distinct CDC stages")
    require(data_input[registers["rx_sync[0]"]] == net["ports"]["GPIO_UART_RX"]["bits"][0], "RX pad")
    for i in SW_BITS:
        require(data_input[registers[f"sw_meta[{i}]"]] == net["ports"]["SW"]["bits"][i], f"SW pad {i}")
    key_type, key_gate, _ = drivers[data_input[registers["key_sync[0]"]]]
    require(key_type in ("$not", "$logic_not") and source(key_gate["A"][0]) == net["ports"]["KEY"]["bits"][1],
            "active-low KEY1 pad")

    tcl = Tcl()
    calls = defaultdict(list)
    for name in ("set_instance_assignment", "create_clock", "derive_clock_uncertainty",
                 "set_false_path", "set_min_delay", "set_max_delay"):
        tcl.createcommand(name, lambda *args, name=name: calls[name].append(args) or "")

    def matches(query, names):
        patterns = [re.escape(p).replace(r"\*", ".*") for p in tcl.splitlist(query)]
        return tuple(name for name in names if any(re.fullmatch(p, name) for p in patterns))

    tcl.createcommand("get_ports", lambda query: matches(query, ports))
    tcl.createcommand("get_registers", lambda query: matches(query, registers))
    tcl.createcommand("get_collection_size", lambda nodes: len(tcl.splitlist(nodes)))
    tcl.call("source", str(PROJECT / "synchronizers.qsf"))
    tcl.call("source", str(PROJECT / f"{TOP}.sdc"))
    expected = {("-name", key, "ON", "-to", reg) for reg in registers
                for key in ("PRESERVE_REGISTER", "DONT_MERGE_REGISTER")}
    expected |= {("-name", "SYNCHRONIZER_IDENTIFICATION", "FORCED IF ASYNCHRONOUS", "-to", chain[0])
                 for chain in chains}
    require(Counter(calls["set_instance_assignment"]) == Counter(expected), "QSF CDC register assignments")
    require(calls["create_clock"] == [("-name", "CLOCK_50", "-period", "20.000", "CLOCK_50")] and
            calls["derive_clock_uncertainty"] == [()], "SDC board clock")
    wanted = {("KEY[0]", "reset_sync[0]"), ("KEY[0]", "reset_sync[1]"), ("KEY[1]", "key_sync[0]"),
              ("GPIO_UART_RX", "rx_sync[0]")} | {(f"SW[{i}]", f"sw_meta[{i}]") for i in SW_BITS}
    cuts = []
    for opt1, start, opt2, end in calls["set_false_path"]:
        require((opt1, opt2) == ("-from", "-to"), "false path options")
        cuts.extend((a, b) for a in tcl.splitlist(start) for b in tcl.splitlist(end))
    require(Counter(cuts) == Counter(wanted), "SDC boundary cuts")
    outputs = {name for name, direction in actual.items() if direction == "output"}
    for command, value in (("set_min_delay", "0.000"), ("set_max_delay", "20.000")):
        (delay, opt, endpoints), = calls[command]
        require((delay, opt) == (value, "-to") and set(tcl.splitlist(endpoints)) == outputs, command)
    print(f"CLOCK PASS  {clocked} clocked RTL cell groups resolve to rising CLOCK_50, SDC period 20 ns")
    print("CDC PASS  14 first stages, 31 distinct preserved registers, 17 connected intra-chain hops")
    print("SDC PASS  15 pad-to-register arcs exempted, 43 output min/max budgets, Tcl replay on RTL names")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netlist", type=Path, help="Yosys read_slang / memory_collect JSON before technology mapping")
    args = parser.parse_args()
    ports = check_files()
    if args.netlist:
        check_netlist(args.netlist, ports)
