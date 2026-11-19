"""Exercise the Python terminal against UART pins of the full RTL board top on Linux."""
import argparse
import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
import tty

HERE = Path(__file__).resolve().parent
PAYLOAD = bytes.fromhex("55 aa 00 ff")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def build_peer(root, profile, build, wrapper):
    build.mkdir(parents=True, exist_ok=True)
    cmd = [wrapper, "verilator"] if wrapper else ["verilator"]
    cmd += ["--cc", "--exe", "--build", "-j", "1", "-Wno-fatal", "--prefix", "VBoard",
            "--Mdir", str(build)]
    if profile == "pulp":
        cmd += ["--top-module", "de2_115_pulp_uart", "-F", "fpga/de2_115/rtl.f"]
    else:
        cmd += ["--top-module", "de2_115_apb_uart_bringup"]
        cmd += [str(p) for p in sorted((root / "rtl/modified/pulp_apb_uart_sv").glob("*.sv"))]
        cmd += [str(root / "rtl/fpga" / name) for name in
                ("de2_uart_controller.sv", "de2_115_apb_uart_bringup.sv")]
    cmd.append(str(HERE / "serial_peer.cpp"))
    log = build / "compile.txt"
    with log.open("w") as stream:
        rc = subprocess.run(cmd, cwd=root, stdout=stream, stderr=subprocess.STDOUT).returncode
    require(rc == 0, f"Verilator compilation failed, see {log}")
    return build / "VBoard"


def check_wire(exe, parity):
    burst = bytes(range(16)).hex()
    commands = f"wire {PAYLOAD.hex()}\nkey 41\nwire 7e810d0a\nwire {burst}\n"
    result = subprocess.run([exe, parity], input=commands, text=True, capture_output=True,
                            timeout=15, check=True)
    expected = ["READY", "RX " + PAYLOAD.hex(), "RX 41", "RX 7e810d0a", "RX " + burst]
    require(result.stdout.splitlines() == expected, f"GPIO mismatch in 8{parity}1: {result.stdout}")
    print(f"GPIO_PASS 8{parity}1: three binary bursts (24 bytes), KEY1 41, checked framing")


def menu_check(root, profile, exe, temp):
    master, slave = pty.openpty()
    try:
        tty.setraw(slave)
        log = temp / "traffic.jsonl"
        tty_name = os.ttyname(slave)
        args = [sys.executable, "-X", "utf8", str(root / "host/uart_menu.py"),
                "--port", tty_name, "--profile", profile, "--log", str(log)]
        with subprocess.Popen([exe, "N"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              text=True) as board, (temp / "menu.txt").open("w") as transcript:
            try:
                require(select.select([board.stdout], [], [], 4)[0] and
                        board.stdout.readline().strip() == "READY", "FPGA wrapper failed to initialise")
                switch_echo(board, enabled=False)
                with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=transcript,
                                      stderr=subprocess.STDOUT, text=True) as menu:
                    try:
                        # Retry the first failed echo, then enter the manual receive test.
                        menu.stdin.write("e\n55 AA 00 FF\nr\nr\nq\n")
                        menu.stdin.close()
                        sent = bytearray()
                        enabled = False
                        pressed = False
                        deadline = time.monotonic() + 14
                        while menu.poll() is None:
                            require(time.monotonic() < deadline, "UART menu timed out")
                            if select.select([master], [], [], 0.05)[0]:
                                outgoing = os.read(master, 8192)
                                sent.extend(outgoing)
                                returned = board_response(board, "wire " + outgoing.hex())
                                if returned:
                                    os.write(master, returned)
                                if not enabled and sent == PAYLOAD:
                                    require(not returned, "echo returned while SW17 was off")
                                    switch_echo(board, enabled=True)
                                    enabled = True
                            if not pressed and log.is_file() and any(
                                row.get("event") == "ECHO" and row.get("status") == "MATCH"
                                for row in read_rows(log)
                            ):
                                manual = board_response(board, "key 41")
                                require(manual == b"A", f"KEY1 produced {manual!r}")
                                os.write(master, manual)
                                pressed = True
                        require(menu.returncode == 0 and pressed and sent == PAYLOAD * 2,
                                f"Menu exit={menu.returncode}, TX={sent.hex()}, KEY1={pressed}")
                    finally:
                        if menu.poll() is None:
                            menu.kill()
            finally:
                board.stdin.close()
        rows = read_rows(log)
        echoes = [r for r in rows if r["event"] == "ECHO"]
        rx = b"".join(bytes.fromhex(r["hex"]) for r in rows if r["event"] == "RX")
        tx = b"".join(bytes.fromhex(r["hex"]) for r in rows if r["event"] == "TX")
        require([r["status"] for r in echoes] == ["NO_RX", "MATCH"] and
                tx == PAYLOAD * 2 and rx == PAYLOAD + b"A", "Menu or traffic log mismatch")
        print(f"MENU_GPIO_PASS {profile} 8N1: SW17 off NO_RX, on MATCH 55 AA 00 FF, manual RX 41")
    finally:
        os.close(slave)
        os.close(master)


def board_response(board, command):
    board.stdin.write(command + "\n")
    board.stdin.flush()
    require(select.select([board.stdout], [], [], 4)[0], "External GPIO peer timed out")
    answer = board.stdout.readline().rstrip("\n")
    require(answer.startswith("RX "), f"Serial decoder failed: {answer!r}")
    return bytes.fromhex(answer[3:])


def read_rows(log):
    # Another process can still be appending the last JSON record.
    data = log.read_bytes()
    complete = data.rpartition(b"\n")[0]
    return [json.loads(line) for line in complete.splitlines()]


def switch_echo(board, enabled):
    board.stdin.write(f"echo {int(enabled)}\n")
    board.stdin.flush()
    require(select.select([board.stdout], [], [], 4)[0] and board.stdout.readline().strip() == "OK",
            "The model did not acknowledge SW17")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=HERE.parent,
                        help="checkout containing both the FPGA sources and host/uart_menu.py")
    parser.add_argument("--profile", choices=("pulp", "target"), default="pulp")
    parser.add_argument("--eda-wrapper", help="optional executable that runs Verilator in its environment")
    args = parser.parse_args()
    wrapper = args.eda_wrapper
    if wrapper is None and shutil.which("verilator") is None:
        fallback = Path.home() / ".local/bin/ic-eda"
        if fallback.is_file():
            wrapper = str(fallback)
    root = args.root.resolve()
    exe = build_peer(root, args.profile, root / "build" / ("interop_" + args.profile), wrapper)
    for mode in ("NE" if args.profile == "pulp" else "NEO"):
        check_wire(exe, mode)
    with tempfile.TemporaryDirectory(prefix="uart-interop-") as temp:
        menu_check(root, args.profile, exe, Path(temp))


if __name__ == "__main__":
    main()
