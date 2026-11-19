"""Drive the Tk workbench against the two external UART pins of this branch's board top."""
import argparse
import csv
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
import tkinter as tk
import tty
from unittest.mock import patch

from test_host_rtl import board_response, build_peer, require, switch_echo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
from board_report import load_plans, save_sheet
from uart_gui import NAMES, Workbench, project_profile


def exercise(executable, scratch, capture=None):
    profile = project_profile()
    other = "pulp" if profile == "target" else "target"
    echo_id = "HW07" if profile == "target" else "HW04"
    plans = load_plans()
    master, slave = pty.openpty()
    tty.setraw(slave)
    root = tk.Tk()
    journal = scratch / "uart-test.jsonl"

    def screenshot(name):
        if capture:
            root.update()
            subprocess.run(["magick", "import", "-silent", "-window", str(root.winfo_id()),
                            str(capture / (profile + "-" + name + ".png"))], check=True)

    try:
        app = Workbench(root, profile, log_path=journal)
        root.update()
        require(not app.console.connected, "Unexpected initial serial connection")
        app.board.select_case(echo_id)
        root.update()
        require(app.board.current_id == echo_id, "Wrong board case selected")
        screenshot("plan")
        size = root.geometry().split("+")[0]
        root.geometry("820x560")
        root.update()
        screenshot("small")
        root.geometry(size)
        root.update()

        app.profile_name.set(NAMES[other])
        app.profile_box.event_generate("<<ComboboxSelected>>")
        root.update()
        require(app.profile == other, "Profile selector did not change the plan")
        app.profile_name.set(NAMES[profile])
        app.profile_box.event_generate("<<ComboboxSelected>>")
        root.update()
        require(app.board.current_id == echo_id, "Selected case lost on profile change")

        app.show("wire")
        app.port_name.set(os.ttyname(slave))
        app.connect_button.invoke()
        root.update()
        require(app.console.connected and str(app.profile_box['state']) == 'disabled', "Open port/profile binding")
        with subprocess.Popen([str(executable), "N"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              text=True) as board:
            try:
                require(select.select([board.stdout], [], [], 4)[0] and board.stdout.readline().strip() == "READY",
                        "Board peer initialization")
                def until(predicate):
                    deadline = time.monotonic() + 6
                    while time.monotonic() < deadline:
                        root.update()
                        if select.select([master], [], [], .012)[0]:
                            data = os.read(master, 4096)
                            answer = board_response(board, "wire " + data.hex())
                            if answer:
                                os.write(master, answer)
                        if predicate():
                            return
                    raise AssertionError("Timed out waiting for GUI. " + app.wire.feedback.get())

                def rows():
                    return [app.wire.history.item(item, "values") for item in app.wire.history.get_children()]
                until(lambda: str(app.wire.echo_button["state"]) == "normal")
                switch_echo(board, False)
                app.wire.payload.set("55 AA 00 FF")
                app.wire.echo_button.invoke()
                until(lambda: "NO_RX" in app.wire.feedback.get() and not app.console.busy)
                switch_echo(board, True)
                until(lambda: str(app.wire.echo_button["state"]) == "normal")
                app.wire.echo_button.invoke()
                until(lambda: "MATCH" in app.wire.feedback.get() and not app.console.busy)
                manual = board_response(board, "key 41")
                require(manual == b"A", "KEY1 did not produce 0x41")
                os.write(master, manual)
                until(lambda: any(r[1] == "RX" and r[3] == "41" for r in rows()))
                screenshot("uart")
                app.wire.mode.set("UTF-8")
                app.wire.payload.set("A")
                app.wire.send_button.invoke()
                until(lambda: any(r[1] == "TX" and r[3] == "41" for r in rows()) and not app.console.busy)
                until(lambda: str(app.connect_button["state"]) == "normal")
                app.connect_button.invoke()
                require(not app.console.connected, "Disconnect button failed")
            finally:
                board.stdin.close()
        events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
        require([r["status"] for r in events if r["event"] == "ECHO"] == ["NO_RX", "MATCH"], "Echo log results")
        require(b"".join(bytes.fromhex(r["hex"]) for r in events if r["event"] == "TX") == bytes.fromhex("55aa00ff55aa00ff41"), "TX log data")
        require(all(r["status"] == "NOT_RUN" for cases in app.board.results.values() for r in cases.values()),
                "Simulator activity marked a physical board case")
        sheet = scratch / "blank.csv"
        save_sheet(sheet, profile, plans[profile], app.board.results[profile], {})
        with sheet.open(encoding="utf-8-sig", newline="") as f:
            printed = list(csv.DictReader(f))
        require(len(printed) == len(plans[profile]) and all(r["status"] == "NOT_RUN" for r in printed), "Physical worksheet")
        # An operator records and exports a result explicitly. Keep this test sheet in scratch.
        app.show("board")
        app.board.select_case(echo_id)
        app.board.observed.insert("1.0", "Fixture: observed 55 AA 00 FE")
        app.board.evidence_path.insert(0, str(journal))
        app.board.status.set("FAIL")
        app.board.record_result.invoke()
        require(app.board.results[profile][echo_id]["status"] == "FAIL", "Manual verdict missing")
        app.profile_name.set(NAMES[other])
        app.change_profile()
        require(all(r["status"] == "NOT_RUN" for r in app.board.results[other].values()), "Cross-profile verdict leak")
        require(not app.wire.history.get_children(), "Old UART packets displayed for another design")
        app.profile_name.set(NAMES[profile])
        app.change_profile()
        require("55 AA 00 FE" in app.board.observed.get("1.0", "end"), "Observation lost on profile change")
        operator_sheet = scratch / "operator.csv"
        with patch("board_view.filedialog.asksaveasfilename", return_value=str(operator_sheet)):
            require(app.export(), "Operator CSV was not saved")
        with operator_sheet.open(encoding="utf-8-sig", newline="") as f:
            recorded = {r["test_id"]: r for r in csv.DictReader(f)}
        require(recorded[echo_id]["status"] == "FAIL" and recorded[echo_id]["datetime_local"]
                and recorded[echo_id]["evidence_path"] == str(journal)
                and "55 AA 00 FE" in recorded[echo_id]["observed"], "Exported observation differs from form")
        require(not app.board.dirty_profiles(), "Saved worksheet still has pending changes")
        print(f"{profile}: Tk, PTY and RTL: NO_RX then MATCH 55 AA 00 FF; KEY1 41; text TX 41; {len(printed)} hardware cases still NOT_RUN")
    finally:
        try:
            if 'app' in locals():
                app.finish()
            else:
                root.destroy()
        finally:
            os.close(master)
            os.close(slave)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, help="optional directory for screenshots, requires ImageMagick")
    args = parser.parse_args()
    if args.capture:
        args.capture.mkdir(parents=True, exist_ok=True)
    profile = project_profile()
    wrapper = None if shutil.which("verilator") else shutil.which("ic-eda")
    if not wrapper and not shutil.which("verilator"):
        fallback = Path.home() / ".local/bin/ic-eda"
        wrapper = str(fallback) if fallback.exists() else None
    exe = build_peer(ROOT, profile, ROOT / "build" / ("interop_" + profile), wrapper)
    with tempfile.TemporaryDirectory(prefix="de2-gui-") as folder:
        exercise(exe, Path(folder), args.capture)


if __name__ == "__main__":
    main()
