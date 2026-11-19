"""Drive the normal interactive process and an independent POSIX PTY master."""

from datetime import datetime
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "uart_menu.py"
PROBE = b"\x55\xaa\x00\xff"


@unittest.skipUnless(os.name == "posix" and hasattr(os, "openpty"), "cần PTY POSIX")
class PtyMenuTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.log_path = self.directory / "traffic.log"
        self.master, self.slave = os.openpty()
        self.device = os.ttyname(self.slave)
        self.proc = None
        self.addCleanup(self.close_peer)

    def close_peer(self):
        if self.proc:
            if self.proc.poll() is None:
                self.proc.kill()
                self.proc.wait(timeout=3)
            self.proc.stdin.close()
            self.proc.stdout.close()
        if self.master is not None:
            os.close(self.master)
        os.close(self.slave)

    def start(self, profile="target", device=None):
        args = [sys.executable, "-B", "-u", "-X", "utf8", str(SCRIPT),
                "--port", device or self.device, "--log", str(self.log_path)]
        if profile:
            args.extend(["--profile", profile])
        self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, encoding="utf-8", cwd=self.directory)
        if profile and device is None:
            self.wait_event("OPEN", profile=profile, frame="8N1")

    def keys(self, commands):
        self.proc.stdin.write(commands)
        self.proc.stdin.flush()

    def finish(self, keys="q\n"):
        output, _ = self.proc.communicate(keys, timeout=5)
        self.assertEqual(self.proc.returncode, 0, output)
        self.assertNotIn("Traceback", output)
        return output

    def rows(self):
        if not self.log_path.exists():
            return []
        # The process may be in the middle of writing the final UTF-8 record.
        raw = self.log_path.read_bytes().split(b"\n")
        return [json.loads(line) for line in raw[:-1]]

    def wait_event(self, event, occurrence=1, **fields):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            matches = [row for row in self.rows() if row["event"] == event
                       and all(row.get(k) == v for k, v in fields.items())]
            if len(matches) >= occurrence:
                return matches[occurrence - 1]
            if self.proc.poll() is not None:
                self.fail(self.proc.stdout.read())
            time.sleep(0.005)
        self.fail(f"Missing {event} {fields}. Last log records: {self.rows()[-3:]}")

    def peer_read(self, count):
        data = bytearray()
        deadline = time.monotonic() + 5
        while len(data) < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.master], [], [], remaining)[0]:
                self.fail(f"Timed out after {bytes(data)!r} of {count} peer bytes")
            data.extend(os.read(self.master, count - len(data)))
        return bytes(data)

    def test_two_way_manual_text_hex_and_key_with_log_roundtrip(self):
        self.start()
        os.write(self.master, b"\x00\xff")
        self.wait_event("RX", phase="menu")
        self.keys("r\n")
        self.assertGreaterEqual(self.wait_event("LISTEN")["queued"], 1)
        key = b"\x41\x00\xff\r\n"
        os.write(self.master, key)
        self.wait_event("RECEIVE", rx_size=7)
        self.keys("t\n  Aế  \nx\n00 FF 11 13 0D 0A\n")
        text = b"  A\xe1\xba\xbf  "
        binary = b"\x00\xff\x11\x13\r\n"
        self.assertEqual(self.peer_read(len(text) + len(binary)), text + binary)
        output = self.finish()
        self.assertIn("Đã nhận 7 byte", output)
        self.assertIn("00 FF", output)
        self.assertFalse(select.select([self.master], [], [], 0)[0], "unexpected extra TX")
        rows = self.rows()
        rx = [r for r in rows if r["event"] == "RX"]
        tx = [r for r in rows if r["event"] == "TX"]
        self.assertEqual(b"".join(bytes.fromhex(r["hex"]) for r in rx), b"\x00\xff" + key)
        self.assertEqual([bytes.fromhex(r["hex"]) for r in tx], [text, binary])
        for row in rx + tx:
            self.assertIsNotNone(datetime.fromisoformat(row["time"]).utcoffset())
            self.assertEqual(row["size"], len(bytes.fromhex(row["hex"])))

    def test_pulp_binary_echo_all_256_byte_values_fragmented(self):
        import termios

        self.start("pulp")
        iflag, oflag, cflag, lflag, ispeed, ospeed, _ = termios.tcgetattr(self.slave)
        self.assertEqual((ispeed, ospeed), (termios.B115200, termios.B115200))
        self.assertEqual(cflag & termios.CSIZE, termios.CS8)
        self.assertFalse(cflag & (termios.PARENB | termios.CSTOPB))
        self.assertFalse(iflag & (termios.IXON | termios.IXOFF))
        self.assertFalse(oflag & termios.OPOST)
        self.assertFalse(lflag & (termios.ECHO | termios.ICANON))
        all_bytes = bytes(range(256))
        self.keys("e\n" + all_bytes.hex() + "\n")
        self.assertEqual(self.peer_read(256), all_bytes)
        os.write(self.master, all_bytes[:17])
        self.wait_event("RX", phase="echo")
        os.write(self.master, all_bytes[17:])
        self.wait_event("ECHO", status="MATCH", rx_size=256, before_tx=0)
        self.finish()
        rx = [bytes.fromhex(r["hex"]) for r in self.rows() if r["event"] == "RX"]
        self.assertEqual(b"".join(rx), all_bytes)

    def test_partial_wrong_late_extra_and_explicit_retry(self):
        self.start()
        self.keys("e\n\n")
        for status, reply in [("SHORT", PROBE[:3]), ("MISMATCH", b"\x55\xaa\xff\x00"),
                              ("EXTRA", PROBE + b"\x00"), ("MATCH", PROBE)]:
            self.assertEqual(self.peer_read(4), PROBE)
            if status == "EXTRA":
                os.write(self.master, PROBE)
                # A correct prefix alone must not complete an echo.
                time.sleep(0.15)
                os.write(self.master, b"\x00")
            else:
                os.write(self.master, reply)
            self.wait_event("ECHO", status=status, rx_size=len(reply))
            if status != "MATCH":
                self.assertFalse(select.select([self.master], [], [], 0.02)[0], "automatic retry")
                self.keys("r\n")
        self.finish()
        results = [r["status"] for r in self.rows() if r["event"] == "ECHO"]
        self.assertEqual(results, ["SHORT", "MISMATCH", "EXTRA", "MATCH"])

    def test_exact_stale_bytes_before_tx_then_silence_and_cancel(self):
        self.start()
        os.write(self.master, PROBE)
        self.wait_event("RX", phase="menu")
        self.keys("e\n\n")
        self.wait_event("ECHO_BEGIN")
        os.write(self.master, PROBE)
        self.wait_event("RX", phase="before_echo")
        self.assertEqual(self.peer_read(4), PROBE)
        self.wait_event("ECHO", status="NO_RX", rx_size=0, before_tx=8)
        self.finish("\ne\n:q\nx\n\nt\n\nq\n")
        self.assertEqual(len([r for r in self.rows() if r["event"] == "TX"]), 1)
        self.assertFalse(select.select([self.master], [], [], 0)[0], "cancel sent data")

    def test_continuous_rx_aborts_without_writing(self):
        self.start()
        self.keys("e\n\n")
        self.wait_event("ECHO_BEGIN")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not any(r["event"] == "ECHO" for r in self.rows()):
            os.write(self.master, b"\xd5")
            time.sleep(0.02)
        self.wait_event("ECHO", status="BUSY")
        self.finish("\nq\n")
        self.assertFalse(any(r["event"] == "TX" for r in self.rows()))
        self.assertFalse(select.select([self.master], [], [], 0)[0])

    def test_failed_open_cancel_reconnect_disconnect_and_unplug(self):
        self.start(profile=None, device=str(self.directory / "missing-port"))
        self.keys("2\n")
        self.wait_event("IO_ERROR")
        self.keys(f"c\n\nc\n{self.device}\nd\nc\n{self.device}\n")
        self.wait_event("OPEN", occurrence=2, profile="pulp", frame="8N1")
        self.keys("e\n\n")
        self.assertEqual(self.peer_read(4), PROBE)
        os.close(self.master)
        self.master = None
        self.wait_event("IO_ERROR", occurrence=2)
        self.wait_event("CLOSE", occurrence=2)
        output = self.finish()
        self.assertIn("chưa mở cổng", output)
        self.assertFalse(any(r.get("status") == "MATCH" for r in self.rows()))

    def test_ctrl_c_during_receive_and_echo_then_send_and_eof(self):
        self.start()
        self.keys("r\n")
        self.wait_event("LISTEN")
        self.proc.send_signal(signal.SIGINT)
        self.wait_event("CANCEL", command="r")
        self.keys("e\n\n")
        self.assertEqual(self.peer_read(4), PROBE)
        self.proc.send_signal(signal.SIGINT)
        self.wait_event("CANCEL", command="e")
        self.keys("x\n7E\n")
        self.assertEqual(self.peer_read(1), b"\x7e")
        self.finish("")  # Closing stdin exits the idle menu and releases the handle.
        self.assertEqual(self.rows()[-1]["event"], "CLOSE")
        self.assertFalse(any(r["event"] == "ECHO" for r in self.rows()))
