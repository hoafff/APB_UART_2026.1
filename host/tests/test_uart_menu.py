import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from serial.tools.list_ports_common import ListPortInfo

HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST))
import uart_menu as uart


class EchoVerdictTests(unittest.TestCase):
    def test_exact_bytes_and_negative_results(self):
        sent = b"\x55\xaa\x00\xff"
        for received, status in (
            (sent, "MATCH"),
            (b"", "NO_RX"),
            (sent[:3], "SHORT"),
            (b"\x55\xaa\xff\x00", "MISMATCH"),
            (sent + b"\x00", "EXTRA"),
        ):
            with self.subTest(status=status):
                self.assertEqual(uart.classify_echo(sent, received), status)


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.stream = io.StringIO()
        self.log = uart.Journal(self.stream)
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def test_numbered_manual_com_and_cancel(self):
        infos = [ListPortInfo("COM12"), ListPortInfo("COM3")]
        with patch.object(uart.list_ports, "comports", return_value=infos):
            with patch("builtins.input", side_effect=["99", "2"]):
                self.assertEqual(uart.choose_port(), "COM12")
        with patch.object(uart.list_ports, "comports", return_value=[]):
            with patch("builtins.input", return_value="COM101"):
                self.assertEqual(uart.choose_port(), "COM101")
            with patch("builtins.input", return_value=""):
                self.assertIsNone(uart.choose_port())

    def test_explicit_profiles_and_native_com_settings(self):
        for profile, inputs, parities in [
            ("target", ["N", "O", "8E1"], ["N", "O", "E"]),
            ("pulp", ["O", "8E1"], ["N", "E"]),
        ]:
            with self.subTest(profile=profile):
                menu = uart.Menu(profile, self.log)
                port = Mock(port="COM12", in_waiting=0)
                port.read.return_value = b""
                with patch.object(uart.serial, "Serial", return_value=port) as driver:
                    try:
                        menu.connect("com12")
                        with patch("builtins.input", side_effect=inputs):
                            if profile == "target":
                                menu.action("f")  # Same 8N1 keeps the handle.
                                menu.action("f")
                            menu.action("f")
                        self.assertEqual([c.kwargs["parity"] for c in driver.call_args_list],
                                         parities)
                        for call in driver.call_args_list:
                            self.assertEqual(call.args, ("COM12",))
                            settings = call.kwargs
                            self.assertEqual(settings["baudrate"], 115200)
                            self.assertEqual((settings["bytesize"], settings["stopbits"]), (8, 1))
                            self.assertFalse(any(settings[k] for k in ("xonxoff", "rtscts", "dsrdtr")))
                            self.assertEqual(settings["timeout"], 0)
                            self.assertGreater(settings["write_timeout"], 0)
                            self.assertLessEqual(settings["write_timeout"], 1)
                    finally:
                        menu.disconnect()

    def test_bad_hex_reprompts_and_cancel_sends_nothing(self):
        with patch("builtins.input", side_effect=["F", "GG", "  ", "00fF"]):
            self.assertEqual(uart.payload("x"), b"\x00\xff")
        with patch("builtins.input", return_value=":q"):
            self.assertIsNone(uart.payload("e"))
        with patch("builtins.input", return_value=""):
            self.assertIsNone(uart.payload("t"))

    def test_partial_or_uncertain_driver_write_never_claims_full_tx(self):
        port = Mock(in_waiting=0)
        port.read.return_value = b""
        port.write.side_effect = [1, uart.serial.SerialTimeoutException("test timeout")]
        link = uart.Link(port, self.log)
        try:
            for _ in range(2):
                with self.assertRaises(uart.serial.SerialTimeoutException):
                    link.send(b"\x00\xff")
        finally:
            link.close()
        rows = [json.loads(line) for line in self.stream.getvalue().splitlines()]
        self.assertEqual([row["event"] for row in rows], ["TX", "TX_UNCERTAIN"])
        self.assertEqual(rows[0]["hex"], "00")
        self.assertEqual(rows[1]["requested_hex"], "00 FF")

    def test_main2_help_uses_its_wrapper_mapping(self):
        pulp = io.StringIO()
        with contextlib.redirect_stdout(pulp):
            uart.board_help("pulp")
        for mapping in ("SW14=0", "SW14=1", "SW15 dự phòng", "KEY0", "SW16=1", "SW17=1", "KEY1"):
            self.assertIn(mapping, pulp.getvalue())
        for rc1_only in ("8O1", "LEDR1", "LEDR2"):
            self.assertNotIn(rc1_only, pulp.getvalue())
