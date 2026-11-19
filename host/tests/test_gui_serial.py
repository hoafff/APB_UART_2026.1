"""Exercise the GUI controller without Tk, using a real serial peer on POSIX."""

from datetime import datetime
import errno
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import serial
from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo

HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST))
import gui_serial as gui


class InputTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "openpty"), "POSIX PTY")
    def test_gui_echo_and_failures_are_silent_on_strict_ascii_stdout(self):
        # Use a separate interpreter so its stdout encoding is real and process-local.
        run = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()),
             "PtyConsoleTests.test_fragmented_match_and_wrong_echo_without_retry",
             "PtyConsoleTests.test_write_failure_survives_reopen_without_intervening_poll",
             "PtyConsoleTests.test_open_driver_and_journal_errors_reach_tk_as_oserror"],
            env=dict(os.environ, PYTHONIOENCODING="ascii:strict"), capture_output=True, timeout=15,
        )
        self.assertEqual(run.returncode, 0, run.stderr.decode("ascii", errors="replace"))
        self.assertEqual(run.stdout, b"")

    def test_payload_preserves_bytes_and_limits_encoded_length(self):
        parse = gui.parse_payload
        self.assertEqual(parse("00fF\t0d\n0A", "HEX"), b"\x00\xff\r\n")
        self.assertEqual(parse("  ế\x00\n", "UTF-8"), b"  \xe1\xba\xbf\x00\n")
        self.assertEqual(parse("FF" * 1024, "HEX"), b"\xff" * 1024)
        self.assertEqual(parse("Đ" * 512, "UTF-8"), b"\xc4\x90" * 512)
        for text, mode in [("", "HEX"), ("  ", "HEX"), ("F F", "HEX"), ("GG", "HEX"),
                           ("0x00", "HEX"), ("00" * 1025, "HEX"), ("", "UTF-8"),
                           ("Đ" * 513, "UTF-8"), ("\ud800", "UTF-8"), ("A", "ASCII"),
                           (None, "UTF-8")]:
            with self.subTest(text=repr(text)[:15], mode=mode):
                with self.assertRaisesRegex(ValueError, r"[^\x00-\x7f]"):
                    parse(text, mode)

    def test_com_discovery_and_profile_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            console = gui.Console(Path(tmp) / "traffic.log")
            self.addCleanup(console.close)
            mock_port = Mock(port="COM12", in_waiting=0)
            mock_port.read.return_value = b""
            with patch.object(serial, "Serial", return_value=mock_port) as driver:
                self.assertFalse(console.connected)
                self.assertFalse(console.busy)
                with patch.object(sys, "platform", "win32"), patch.object(
                    list_ports, "comports", return_value=[ListPortInfo("COM12"), ListPortInfo("com12")]
                ), patch("builtins.print") as printed:
                    self.assertEqual(gui.ports(), ["COM12"])
                    printed.assert_not_called()
                for device, profile, parity in [("", "target", "N"), ("COM12", "other", "N"),
                                                ("COM12", "pulp", "O"), ("COM12", "target", "S")]:
                    with self.subTest(device=device, profile=profile, parity=parity):
                        with self.assertRaises(ValueError):
                            console.open(device, profile, parity)
                driver.assert_not_called()
                for profile, parity in [("target", "O"), ("target", "E"), ("pulp", "E")]:
                    self.assertIsNone(console.open("com12", profile, parity))
                    self.assertEqual(driver.call_args.args, ("COM12",))
                    self.assertEqual(driver.call_args.kwargs["parity"], parity)
                    console.close()

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux by-id")
    def test_by_id_preferred_and_raw_fallback_when_enumeration_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            dev = Path(tmp)
            raw, other = dev / "ttyUSB0", dev / "ttyACM1"
            raw.touch()
            other.touch()
            by_id = dev / "serial/by-id"
            by_id.mkdir(parents=True)
            alias = by_id / "usb-board-a"
            alias.symlink_to(raw)
            (by_id / "usb-board-b").symlink_to(raw)
            (by_id / "gone").symlink_to(dev / "missing")
            with patch.object(gui, "_DEV", dev), patch("builtins.print") as printed:
                with patch.object(list_ports, "comports", return_value=[ListPortInfo(str(raw))]):
                    self.assertCountEqual(gui.ports(), [str(alias), str(other)])
                with patch.object(list_ports, "comports", side_effect=OSError("sysfs")):
                    self.assertCountEqual(gui.ports(), [str(alias), str(other)])
                printed.assert_not_called()

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux serial enumeration")
    def test_32_builtin_uarts_hidden_but_manual_path_and_usb_metadata_work(self):
        legacy = [ListPortInfo(f"/dev/ttyS{i}") for i in range(32)]
        by_vid = ListPortInfo("/dev/ttyCustom0")
        by_vid.vid = 0x10C4
        by_hwid = ListPortInfo("/dev/ttyCustom1")
        by_hwid.hwid = "USB VID:PID=0403:6001"
        with tempfile.TemporaryDirectory() as tmp, patch.object(gui, "_DEV", Path(tmp)):
            with patch.object(list_ports, "comports", return_value=legacy):
                self.assertEqual(gui.ports(), [])
                console = gui.Console(Path(tmp) / "traffic.log")
                port = Mock(port="/dev/ttyS17", in_waiting=0)
                port.read.return_value = b""
                with patch.object(serial, "Serial", return_value=port) as driver:
                    try:
                        console.open("/dev/ttyS17", "target", "N")
                        self.assertEqual(driver.call_args.args, ("/dev/ttyS17",))
                    finally:
                        console.close()
            with patch.object(list_ports, "comports", return_value=legacy + [by_vid, by_hwid]):
                self.assertCountEqual(gui.ports(), [by_vid.device, by_hwid.device])


@unittest.skipUnless(hasattr(os, "openpty"), "POSIX PTY")
class PtyConsoleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "traffic.jsonl"
        self.console = gui.Console(self.path)
        self.master, slave = os.openpty()
        self.device = os.ttyname(slave)
        os.close(slave)
        self.addCleanup(self.unplug)
        self.addCleanup(self.console.close)
        self.rows = []

    def unplug(self):
        if self.master is not None:
            os.close(self.master)
            self.master = None

    def connect(self):
        self.assertIsNone(self.console.open(self.device, "pulp", "N"))
        self.assertTrue(self.console.connected)

    def until(self, predicate):
        deadline = time.monotonic() + 4
        while not predicate():
            if time.monotonic() >= deadline:
                self.fail(f"Timed out waiting for controller, events {self.rows}")
            time.sleep(0.005)

    def collect(self, event, **fields):
        def seen():
            self.rows.extend(self.console.poll())
            return any(row["event"] == event and fields.items() <= row.items() for row in self.rows)
        self.until(seen)
        return next(row for row in self.rows if row["event"] == event and fields.items() <= row.items())

    def peer_read(self, size):
        data = bytearray()
        deadline = time.monotonic() + 3
        while len(data) < size:
            remaining = max(0, deadline - time.monotonic())
            self.assertTrue(select.select([self.master], [], [], remaining)[0], bytes(data))
            data.extend(os.read(self.master, size - len(data)))
        return bytes(data)

    def journal(self):
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]

    def test_manual_port_rx_tx_and_journal_round_trip(self):
        with self.assertRaises(RuntimeError):
            self.console.send(b"A")
        manual = self.path.with_name("manual port")
        manual.symlink_to(self.device)
        self.assertIsNone(self.console.open(str(manual), "target", "N"))
        for data in (b"", b"A" * 1025, 2):
            with self.subTest(data=repr(data)[:10]), self.assertRaises(ValueError):
                self.console.send(data)
        os.write(self.master, b"\x00\xff")
        self.collect("RX")
        self.console.send(b"\xff\x00\x11\x13")
        self.assertEqual(self.peer_read(4), b"\xff\x00\x11\x13")
        self.console.close()
        self.console.close()
        self.rows.extend(self.console.poll())
        self.assertEqual(self.console.poll(), [])
        self.assertFalse(self.console.connected)
        self.assertFalse(self.console.busy)
        self.assertEqual(self.rows, self.journal())
        self.assertEqual(self.rows[0]["port"], str(manual))
        for event, expected in (("TX", b"\xff\x00\x11\x13"), ("RX", b"\x00\xff")):
            packets = [row for row in self.rows if row["event"] == event]
            self.assertEqual(b"".join(bytes.fromhex(row["hex"]) for row in packets), expected)
            for row in packets:
                self.assertEqual(row["size"], len(bytes.fromhex(row["hex"])))
                self.assertIsNotNone(datetime.fromisoformat(row["time"]).utcoffset())
        with serial.Serial(self.device, exclusive=True):
            pass

    def test_fragmented_match_and_wrong_echo_without_retry(self):
        self.connect()
        data = b"\x55\xaa\x00\xff"
        os.write(self.master, b"\x8b")
        self.collect("RX", phase="menu")
        for status, reply in [("MATCH", data), ("MISMATCH", b"\x55\x00\xaa\xff")]:
            with self.subTest(status=status):
                self.console.send(data, echo=True)
                self.assertTrue(self.console.busy)
                with self.assertRaises(RuntimeError):
                    self.console.send(b"X")
                self.assertEqual(self.peer_read(4), data)
                os.write(self.master, reply[:1])
                if status == "MATCH":
                    self.collect("RX", phase="echo", hex="55")
                os.write(self.master, reply[1:])
                result = self.collect("ECHO", status=status)
                self.assertEqual(result["expected_hex"], "55 AA 00 FF")
                self.assertEqual(result["rx_size"], 4)
                self.assertEqual(result["before_tx"], int(status == "MATCH"))
                self.until(lambda: not self.console.busy)
                self.assertTrue(self.console.connected)
        self.assertFalse(select.select([self.master], [], [], 0.05)[0], "unexpected retry")
        self.console.close()
        self.assertEqual([r for r in self.journal() if r["event"] == "ECHO"],
                         [r for r in self.rows if r["event"] == "ECHO"])

    def test_idle_unplug_detected_by_poll(self):
        self.connect()
        self.unplug()
        error = self.collect("ERROR")
        self.assertTrue(error["detail"])
        self.assertFalse(self.console.connected)
        self.assertFalse(self.console.busy)
        with self.assertRaises(RuntimeError):
            self.console.send(b"x")
        self.assertIn("IO_ERROR", [row["event"] for row in self.journal()])
        self.assertEqual(self.console.poll(), [])

    def test_unplug_during_echo_then_close_before_poll(self):
        self.connect()
        self.console.send(b"\xff", echo=True)
        self.assertEqual(self.peer_read(1), b"\xff")
        self.unplug()
        self.until(lambda: not self.console.busy)
        self.console.close()
        rows = self.console.poll()
        self.assertTrue(any(row["event"] == "ERROR" and row["detail"] for row in rows))
        self.assertFalse(any(row["event"] == "ECHO" for row in rows))

    def test_write_failure_survives_reopen_without_intervening_poll(self):
        self.connect()
        writing, release = threading.Event(), threading.Event()

        def fail_write(data):
            writing.set()
            if not release.wait(2):
                raise AssertionError("send or poll blocked the UI")
            raise serial.SerialTimeoutException("write timeout in test")

        with patch.object(serial.Serial, "write", side_effect=fail_write) as write:
            try:
                self.console.send(b"\xff")
                self.assertTrue(writing.wait(1))
                self.assertTrue(self.console.busy)
                with self.assertRaises(RuntimeError):
                    self.console.send(b"x")
                self.rows.extend(self.console.poll())
                self.assertTrue(self.console.busy)
            finally:
                release.set()
            self.until(lambda: not self.console.busy)
            with self.assertRaises(RuntimeError):
                self.console.send(b"y")
            write.assert_called_once_with(b"\xff")
        self.connect()
        self.console.send(b"\x00")
        self.assertEqual(self.peer_read(1), b"\x00")
        error = self.collect("ERROR")
        self.assertIn("write timeout in test", error["detail"])
        self.console.close()
        rows = self.journal()
        self.assertEqual([r["hex"] for r in rows if r["event"] == "TX"], ["00"])
        self.assertEqual([r["requested_hex"] for r in rows if r["event"] == "TX_UNCERTAIN"], ["FF"])

    def test_close_during_echo_then_reopen(self):
        self.connect()
        self.console.send(b"\x01", echo=True)
        self.assertEqual(self.peer_read(1), b"\x01")
        self.console.close()
        self.assertFalse(self.console.busy)
        self.connect()
        self.console.send(b"\x02")
        self.assertEqual(self.peer_read(1), b"\x02")
        self.console.close()
        events = [row["event"] for row in self.journal()]
        self.assertIn("CANCEL", events)
        self.assertNotIn("ECHO", events)
        self.assertEqual(events.count("CLOSE"), 2)

    def test_rx_journal_failure_reaches_ui_and_releases_stream_and_port(self):
        class FullOnRx(io.StringIO):
            def write(self, line):
                if json.loads(line)["event"] == "RX":
                    raise OSError(errno.ENOSPC, "test disk full")
                return super().write(line)

        stream = FullOnRx()
        with patch.object(Path, "open", return_value=stream):
            self.connect()
        os.write(self.master, b"\x00\xff")
        error = self.collect("ERROR")
        self.assertIn("test disk full", error["detail"])
        self.assertTrue(stream.closed)
        self.assertFalse(self.console.connected)
        self.assertFalse(any(row["event"] == "RX" for row in self.rows))
        self.connect()

    def test_open_failures_release_resources_and_allow_retry(self):
        with self.assertRaises(OSError):
            self.console.open(str(self.path.with_name("missing")), "target", "N")
        self.assertFalse(self.console.connected)
        if sys.platform.startswith("linux"):
            full = gui.Console("/dev/full")
            with self.assertRaises(OSError):
                full.open(self.device, "target", "N")
            full.close()
            self.assertFalse(full.connected)
        self.connect()

    def test_open_driver_and_journal_errors_reach_tk_as_oserror(self):
        import termios

        with patch.object(serial, "Serial", side_effect=termios.error(errno.EIO, "test driver")):
            with self.assertRaisesRegex(OSError, "test driver"):
                self.console.open(self.device, "target", "N")

        class FailOpenRecord(io.StringIO):
            def write(self, text):
                raise OSError(errno.ENOSPC, "test journal")

        stream = FailOpenRecord()
        with patch.object(Path, "open", return_value=stream):
            with self.assertRaisesRegex(OSError, "test journal"):
                self.console.open(self.device, "target", "N")
        self.assertTrue(stream.closed)
        self.assertFalse(self.console.connected)
        self.connect()

    def test_reader_start_failure_closes_the_open_session(self):
        with patch.object(threading.Thread, "start", side_effect=RuntimeError("cannot start reader")):
            with self.assertRaisesRegex(RuntimeError, "cannot start reader"):
                self.console.open(self.device, "target", "N")
        self.assertFalse(self.console.connected)
        self.assertEqual([r["event"] for r in self.console.poll()], ["OPEN", "CLOSE"])
        self.assertEqual([r["event"] for r in self.journal()], ["OPEN", "CLOSE"])
        self.connect()


if __name__ == "__main__":
    unittest.main()
