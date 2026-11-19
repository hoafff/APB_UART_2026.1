"""Serial controller for the Tk UART console. All traffic goes through uart_menu.Link."""

from contextlib import ExitStack
from datetime import datetime
import os
from pathlib import Path
from queue import Empty, SimpleQueue
import re
import sys
import threading

import serial
from serial.tools import list_ports

if __package__:
    from . import uart_menu as uart
else:
    import uart_menu as uart


_DEV = Path("/dev")


def _device_name(path):
    return path.upper() if re.fullmatch(r"COM[0-9]+", path, re.IGNORECASE) else path


def _is_usb(port):
    return (port.vid is not None or (port.hwid or "").startswith("USB ")
            or Path(port.device).name.startswith(("ttyUSB", "ttyACM")))


def ports():
    """Return selectable paths, preferring a live Linux by-id alias for each device."""
    linux = sys.platform.startswith("linux")
    devices = []
    if linux:
        devices.extend(str(p) for p in sorted((_DEV / "serial/by-id").glob("*"))
                       if p.is_symlink() and p.exists())
    try:
        devices.extend(port.device for port in list_ports.comports() if not linux or _is_usb(port))
    except OSError:
        pass  # sysfs may be unavailable; device paths can still be used.
    if linux:
        for pattern in ("ttyUSB*", "ttyACM*"):
            devices.extend(str(p) for p in _DEV.glob(pattern) if p.exists())

    choices = {}
    for device in devices:
        name = _device_name(device)
        key = os.path.realpath(name) if linux else name
        choices.setdefault(key, name)
    return sorted(choices.values())


def _payload(data):
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ValueError("Dữ liệu gửi phải là dãy byte.")
    if not 1 <= memoryview(data).nbytes <= uart.MAX_TX:
        raise ValueError(f"Mỗi lần gửi từ 1 đến {uart.MAX_TX} byte.")
    return bytes(data)


def parse_payload(text, mode):
    """Parse the exact text entered by the operator, including UTF-8 whitespace."""
    if not isinstance(text, str):
        raise ValueError("Hãy nhập dữ liệu dạng văn bản.")
    if mode == "HEX":
        try:
            data = bytes.fromhex(text)
        except ValueError as exc:
            raise ValueError("Mỗi byte HEX cần đủ hai chữ số 0–9, A–F.") from exc
    elif mode == "UTF-8":
        try:
            data = text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("Văn bản chứa ký tự không mã hóa được bằng UTF-8.") from exc
    else:
        raise ValueError("Hãy chọn HEX hoặc UTF-8.")
    return _payload(data)


class _Journal(uart.Journal):
    def __init__(self, stream, events):
        super().__init__(stream)
        self.events = events

    def record(self, event, **fields):
        try:
            stamp = super().record(event, **fields)
        except ValueError as exc:  # e.g. a closed stream
            raise uart.LogError(str(exc)) from exc
        if event in ("TX", "RX", "ECHO", "OPEN", "CLOSE"):
            self.events.put(dict(event=event, time=stamp, **fields))
        return stamp

    def error(self, port, detail):
        stamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
        self.events.put(dict(event="ERROR", time=stamp, port=port, detail=detail))

    def finish(self, port, errors):
        # Report to Tk independently of the stream that may just have failed.
        log_failed = False
        for exc in errors:
            detail = str(exc) or type(exc).__name__
            if isinstance(exc, uart.LogError):
                log_failed = True
                detail = f"Lỗi ghi nhật ký: {detail}"
            self.error(port, detail)
        try:
            with self.stream:
                if not log_failed:
                    for exc in errors:
                        self.record("IO_ERROR", port=port, detail=str(exc))
                    self.record("CLOSE", port=port)
        except (OSError, ValueError, uart.LogError) as exc:
            if not log_failed:
                self.error(port, f"Lỗi ghi hoặc đóng nhật ký: {exc}")


class _EchoCancelled(Exception):
    pass


class _Link(uart.Link):
    """Keep the submitted writer and its outcome with the port that owns them."""

    def __init__(self, port, journal):
        self.worker = None
        self.write_error = None
        super().__init__(port, journal, terminal_output=False)

    def _check_cancel(self, phase):
        if self.stopping.is_set() and phase in ("before_echo", "echo"):
            self.log.record("CANCEL", command="e")
            raise _EchoCancelled

    def _read(self, phase, limit=4096):
        self._check_cancel(phase)
        return super()._read(phase, limit)

    def _write(self, data, phase):
        self._check_cancel(phase)
        return super()._write(data, phase)

    def submit(self, data, echo):
        def run():
            try:
                if echo:
                    self.echo(data)
                else:
                    self.send(data)
            except _EchoCancelled:
                pass
            except Exception as exc:
                self.write_error = exc
                self.stopping.set()

        worker = threading.Thread(target=run, name="uart-tx")
        worker.start()
        self.worker = worker

    def finish(self):
        self.stopping.set()
        if self.worker is not None:
            self.worker.join()
        errors = []
        try:
            super().close(drain=self.write_error is None)
        except Exception as exc:
            errors.append(exc)
        # The writer can observe the same exception already saved by the reader.
        for exc in (self.write_error, self.failure):
            if exc is not None and exc not in errors:
                errors.append(exc)
        self.log.finish(self.port.port, errors)


class Console:
    def __init__(self, log_path):
        self._path = Path(log_path)
        self._events = SimpleQueue()
        self._lock = threading.RLock()
        self._link = None

    @property
    def connected(self):
        link = self._link
        return link is not None and link.failure is None and not link.stopping.is_set()

    @property
    def busy(self):
        link = self._link
        return link is not None and link.worker is not None and link.worker.is_alive()

    def open(self, device, profile, parity):
        """Explicitly open or replace a connection. Manual paths need no enumeration."""
        if isinstance(device, os.PathLike):
            device = os.fspath(device)
        if not isinstance(device, str) or not device.strip():
            raise ValueError("Hãy nhập tên cổng nối tiếp.")
        if not isinstance(profile, str) or profile not in uart.PARITIES:
            raise ValueError("Hãy chọn profile target hoặc pulp.")
        if parity not in uart.PARITIES[profile]:
            raise ValueError(f"Profile {profile} chỉ hỗ trợ parity {', '.join(uart.PARITIES[profile])}.")
        device = _device_name(device)
        try:
            with self._lock, ExitStack() as rollback:
                self.close()
                stream = rollback.enter_context(self._path.open("a", encoding="utf-8", newline="\n"))
                port = serial.Serial(device, baudrate=uart.BAUD, bytesize=serial.EIGHTBITS,
                                     parity=parity, stopbits=serial.STOPBITS_ONE, timeout=0,
                                     write_timeout=0.5, xonxoff=False, rtscts=False, dsrdtr=False,
                                     exclusive=True if sys.platform.startswith("linux") else None)
                rollback.callback(port.close)
                journal = _Journal(stream, self._events)
                journal.record("OPEN", port=device, profile=profile, baud=uart.BAUD, frame=f"8{parity}1")
                rollback.callback(journal.record, "CLOSE", port=device)
                self._link = _Link(port, journal)
                rollback.pop_all()
        except uart.LogError as exc:
            raise OSError(f"Lỗi ghi nhật ký: {exc}") from exc
        except uart.PORT_ERRORS as exc:
            if isinstance(exc, (OSError, ValueError)):
                raise
            raise OSError(*exc.args) from exc  # POSIX termios.error

    def send(self, data, echo=False):
        """Submit one packet. The port worker performs the entire send or echo."""
        with self._lock:
            if self.busy:
                raise RuntimeError("Cổng đang bận.")
            if not self.connected:
                raise RuntimeError("Chưa kết nối cổng nối tiếp.")
            self._link.submit(_payload(data), echo)

    def poll(self):
        """Collect completed records and retire a connection that has failed."""
        with self._lock:
            if self._link is not None and not self.connected:
                self.close()
            rows = []
            while True:
                try:
                    rows.append(self._events.get_nowait())
                except Empty:
                    return rows

    def close(self):
        with self._lock:
            if self._link is not None:
                self._link.finish()
                self._link = None
