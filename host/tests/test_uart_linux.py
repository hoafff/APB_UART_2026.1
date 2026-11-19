import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import venv

import serial
from serial.tools.list_ports_common import ListPortInfo

HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST))
import uart_linux


@unittest.skipUnless(sys.platform.startswith("linux"), "cần Linux")
class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dev = Path(temp.name) / "dev"
        self.dev.mkdir()

    def test_by_id_deduplicates_and_follows_device_renumbering(self):
        by_id = self.dev / "serial" / "by-id"
        by_id.mkdir(parents=True)
        alias = by_id / "usb-CP2102-board-A"
        duplicate = by_id / "usb-CP2102-board-B"
        (by_id / "unplugged").symlink_to("../../ttyUSB9")

        for name in ("ttyUSB0", "ttyUSB3"):
            port = self.dev / name
            port.touch()
            for link in (alias, duplicate):
                link.symlink_to("../../" + name)
            info = ListPortInfo(str(port))
            info.vid, info.pid, info.description = 0x10C4, 0xEA60, "CP2102"
            output = io.StringIO()
            with patch.object(uart_linux.list_ports, "comports", return_value=[info]), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(uart_linux.usb_devices(self.dev), [str(alias)])
            self.assertIn(str(port), output.getvalue())
            self.assertIn("10C4:EA60", output.getvalue())
            alias.unlink()
            duplicate.unlink()
            port.unlink()

    def test_by_id_and_device_nodes_survive_failed_sysfs_enumeration(self):
        by_id = self.dev / "serial" / "by-id"
        by_id.mkdir(parents=True)
        (self.dev / "board").touch()
        alias = by_id / "usb-board"
        alias.symlink_to("../../board")
        fallback = self.dev / "ttyACM0"
        fallback.touch()
        with patch.object(uart_linux.list_ports, "comports", side_effect=OSError("sysfs")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(uart_linux.usb_devices(self.dev), [str(alias), str(fallback)])

    def test_without_by_id_lists_usb_and_omits_legacy_uarts(self):
        native = ListPortInfo(str(self.dev / "ttyS0"))
        usb = ListPortInfo(str(self.dev / "ttyCustom"))
        usb.vid, usb.pid = 0x0403, 0x6001
        with patch.object(uart_linux.list_ports, "comports", return_value=[native, usb]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(uart_linux.usb_devices(self.dev), [usb.device])
        raw = self.dev / "ttyUSB0"
        raw.touch()
        with patch.object(uart_linux.list_ports, "comports", return_value=[native]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(uart_linux.usb_devices(self.dev), [str(raw)])
        raw.unlink()
        output = io.StringIO()
        with patch.object(uart_linux.list_ports, "comports", return_value=[native]), \
                contextlib.redirect_stdout(output):
            self.assertEqual(uart_linux.usb_devices(self.dev), [])
        self.assertIn("Chưa thấy cổng USB-UART", output.getvalue())


@unittest.skipUnless(sys.platform.startswith("linux"), "cần Linux")
class LauncherTests(unittest.TestCase):
    def test_project_venv_used_from_another_cwd_only_when_provisioned(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            host = project / "host"
            host.mkdir(parents=True)
            for name in ("uart_linux.py", "uart_menu.py"):
                shutil.copyfile(HOST / name, host / name)
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            # -S models a caller without pySerial, even when running tests in a venv.
            args = [sys.executable, "-S", str(host / "uart_linux.py"), "--help"]

            def launch():
                return subprocess.run(args, cwd=tmp, env=env, stdin=subprocess.DEVNULL,
                                      capture_output=True, encoding="utf-8", timeout=5)

            missing = launch()
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("pyserial==3.5", missing.stderr)
            local = project / ".venv"
            venv.EnvBuilder(with_pip=False).create(local)
            empty = launch()
            self.assertNotEqual(empty.returncode, 0)
            self.assertIn("pyserial==3.5", empty.stderr)
            site = next(local.glob("lib/python*/site-packages"))
            (site / "serial").symlink_to(Path(serial.__file__).resolve().parent)
            ready = launch()
            self.assertEqual(ready.returncode, 0, ready.stderr)
            self.assertIn("/dev/ttyUSB0", ready.stdout)
