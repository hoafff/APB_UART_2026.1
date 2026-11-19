"""Terminal UART thô cho DE2-115 và CP2102. Chạy với Python 3 và pyserial."""

import argparse
from collections import deque
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("Thiếu pyserial. Hãy chạy py -3 -m pip install pyserial")


BAUD = 115200
PARITIES = {"target": ("N", "O", "E"), "pulp": ("N", "E")}
DEFAULT_ECHO = bytes.fromhex("55 AA 00 FF")
MAX_TX = 1024
POLL = 0.01
QUIET_TIME = 0.12
QUIET_LIMIT = 0.70
ECHO_WINDOW = 1.0
KEY_WINDOW = 3.0
PORT_ERRORS = (OSError, ValueError)
if os.name == "posix":
    import termios
    PORT_ERRORS += (termios.error,)


def hex_bytes(data):
    return data.hex(" ").upper()


def show_packet(stamp, direction, data):
    view = data[:48]
    ascii_view = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in view)
    more = " … (xem đủ trong log)" if len(view) < len(data) else ""
    print(f"{stamp}  {direction}  {len(data)} B  {hex_bytes(view)}  |{ascii_view}|{more}")


class LogError(Exception):
    """A traffic record could not be persisted."""


class Journal:
    def __init__(self, stream):
        self.stream = stream
        self.lock = threading.Lock()

    def record(self, event, **fields):
        with self.lock:
            stamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
            row = {"time": stamp, "event": event, **fields}
            try:
                self.stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                self.stream.flush()
            except OSError as exc:
                raise LogError(str(exc)) from exc
        return stamp

    def packet(self, direction, data, phase):
        return self.record(direction, phase=phase, size=len(data), hex=hex_bytes(data))


def classify_echo(expected, received):
    if not received:
        return "NO_RX"
    if received == expected:
        return "MATCH"
    if expected.startswith(received):
        return "SHORT"
    if received.startswith(expected):
        return "EXTRA"
    return "MISMATCH"


class Link:
    """One owner of serial I/O at a time, including the handoff from idle to echo."""

    def __init__(self, port, journal):
        self.port = port
        self.log = journal
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.failure = None
        # Only the menu preview is bounded. Every packet is written to the log first.
        self.pending = deque(maxlen=256)
        self.pending_bytes = 0
        self.reader = threading.Thread(target=self._read_at_menu, name="uart-rx", daemon=True)
        self.reader.start()

    def close(self, drain=True):
        self.stopping.set()
        self.reader.join()
        try:
            # Capture bytes already queued when the operator disconnects, even if
            # the menu reader has not polled yet. New arrivals cannot prolong close.
            remaining = self.port.in_waiting if drain and self.failure is None else 0
            while remaining > 0:
                packet = self._read("close", remaining)
                if not packet:
                    break
                remaining -= len(packet[1])
        finally:
            self.port.close()

    def _read(self, phase, limit=4096):
        size = min(self.port.in_waiting or 1, 4096, limit)
        data = self.port.read(size)
        if data:
            stamp = self.log.packet("RX", data, phase)
            return stamp, data
        return None

    def _read_at_menu(self):
        while not self.stopping.is_set():
            with self.lock:
                try:
                    packet = self._read("menu")
                    if packet:
                        self.pending.append(packet)
                        self.pending_bytes += len(packet[1])
                except (*PORT_ERRORS, LogError) as exc:
                    self.failure = exc
                    return
            self.stopping.wait(POLL)

    def check(self):
        if self.failure is not None:
            raise self.failure

    def _window(self, seconds, phase):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            packet = self._read(phase)
            if packet:
                yield packet
            else:
                time.sleep(POLL)

    def receive(self):
        with self.lock:
            self.check()
            total = self.pending_bytes
            self.log.record("LISTEN", queued=total, seconds=KEY_WINDOW)
            archived = total - sum(len(data) for _, data in self.pending)
            if archived:
                print(f"Có {archived} byte cũ hơn trong log.")
            while self.pending:
                stamp, data = self.pending.popleft()
                self.pending_bytes -= len(data)
                show_packet(stamp, "RX", data)
            self.pending_bytes = 0
            print(f"Đang nhận {KEY_WINDOW:g} s. Có thể nhấn KEY1 hoặc Ctrl+C để về menu.")
            for stamp, data in self._window(KEY_WINDOW, "receive"):
                total += len(data)
                show_packet(stamp, "RX", data)
            self.log.record("RECEIVE", rx_size=total)
            print(f"Đã nhận {total} byte (gồm byte đang chờ).")

    def _write(self, data, phase):
        try:
            size = self.port.write(data)
        except (OSError, KeyboardInterrupt) as exc:
            # After a driver error even the number of bytes sent may be unknown.
            self.log.record("TX_UNCERTAIN", phase=phase, requested_hex=hex_bytes(data),
                            error=type(exc).__name__)
            raise
        if size:
            stamp = self.log.packet("TX", data[:size], phase)
            show_packet(stamp, "TX", data[:size])
        if size != len(data):
            raise serial.SerialTimeoutException(f"Driver chỉ nhận {size}/{len(data)} byte TX.")

    def send(self, data):
        with self.lock:
            self.check()
            self._write(data, "send")

    def _wait_quiet(self):
        # Menu RX is already logged. Also drain what is still in the driver.
        stale = self.pending_bytes
        self.pending.clear()
        self.pending_bytes = 0
        last_rx = time.monotonic()
        deadline = last_rx + QUIET_LIMIT
        while time.monotonic() < deadline:
            packet = self._read("before_echo")
            if packet:
                stale += len(packet[1])
                last_rx = time.monotonic()
            elif time.monotonic() - last_rx >= QUIET_TIME:
                return True, stale
            else:
                time.sleep(POLL)
        return False, stale

    def echo(self, expected):
        with self.lock:
            self.check()
            self.log.record("ECHO_BEGIN", expected_hex=hex_bytes(expected))
            quiet, stale = self._wait_quiet()
            count = 0
            prefix = bytearray()
            status = "BUSY"
            if quiet:
                self._write(expected, "echo")
                # Keep at most one extra byte for classification. _read logs every byte.
                for _, data in self._window(ECHO_WINDOW, "echo"):
                    count += len(data)
                    prefix.extend(data[:len(expected) + 1 - len(prefix)])
                status = classify_echo(expected, prefix)
            self.log.record("ECHO", status=status, expected_hex=hex_bytes(expected),
                            rx_size=count, rx_prefix_hex=hex_bytes(prefix), before_tx=stale)
        print(f"Echo {status} — {VERDICTS[status]}. RX {count} byte, trước TX {stale} byte.")
        if count:
            print(f"RX đầu gói  {hex_bytes(prefix[:48])}")
        return status


VERDICTS = {
    "MATCH": "RX khớp từng byte với TX trong cửa sổ đo",
    "NO_RX": "hết thời gian chờ RX",
    "SHORT": "RX đúng phần đầu nhưng thiếu byte",
    "MISMATCH": "nội dung hoặc thứ tự byte khác TX",
    "EXTRA": "đúng gói rồi có thêm byte",
    "BUSY": "RX chưa yên, chưa gửi gói thử",
}


def devices():
    try:
        ports = sorted(list_ports.comports())
    except OSError as exc:
        print(f"Lỗi liệt kê cổng ({exc}). Có thể nhập tên cổng bằng tay.")
        return []
    for index, port in enumerate(ports, 1):
        print(f"  {index}. {port.device}  {port.description}  [{port.hwid}]")
    if not ports:
        print("Chưa thấy cổng nối tiếp. Xem Ports (COM & LPT) trong Device Manager.")
    return [port.device for port in ports]


def choose_port():
    ports = devices()
    by_number = {str(i): device for i, device in enumerate(ports, 1)}
    while True:
        choice = input("Số thứ tự hoặc tên cổng (vd. COM10), Enter hủy > ").strip()
        if not choice:
            return None
        if not choice.isdecimal():
            return choice
        if choice in by_number:
            return by_number[choice]
        print("Số thứ tự ngoài danh sách. Nếu là cổng Windows, nhập cả chữ COM.")


def choose_profile():
    while True:
        value = input("Chọn bitstream [1] target RC1, [2] pulp, [q] thoát > ").strip().lower()
        if value in ("1", "target"):
            return "target"
        if value in ("2", "pulp"):
            return "pulp"
        if value == "q":
            return None
        print("Hãy chọn profile của thiết kế đang nạp.")


def choose_parity(profile):
    choices = PARITIES[profile]
    while True:
        value = input(f"Khung cho {profile} ({', '.join('8'+p+'1' for p in choices)}), Enter hủy > ")
        value = value.strip().upper()
        if not value:
            return None
        for parity in choices:
            if value in (parity, f"8{parity}1"):
                return parity
        print("Profile này không hỗ trợ khung vừa nhập.")


def payload(mode):
    prompts = {
        "t": "Văn bản UTF-8, Enter hủy",
        "x": "Byte HEX (vd. 41 00 FF), Enter hủy",
        "e": "Gói echo HEX, Enter dùng 55 AA 00 FF, :q hủy",
    }
    while True:
        value = input(prompts[mode] + " > ")
        if mode == "e" and value.strip().lower() == ":q":
            return None
        if not value:
            return DEFAULT_ECHO if mode == "e" else None
        try:
            data = value.encode("utf-8") if mode == "t" else bytes.fromhex(value)
        except ValueError:
            print("Dữ liệu không hợp lệ. Mỗi byte HEX cần đủ hai chữ số 0–9, A–F.")
            continue
        if 0 < len(data) <= MAX_TX:
            return data
        print(f"Mỗi lần gửi từ 1 đến {MAX_TX} byte.")


def board_help(profile):
    print("Nối CP2102 mức logic 3,3 V qua TXD → GPIO[2]/AB21, RXD ← GPIO[0]/AB22 và GND chung.")
    print("Bo dùng nguồn riêng. Bắt đầu ở 115200 8N1 với SW14=SW16=SW17=0.")
    print("Giữ switch ổn định ≥1 ms, nhấn/nhả KEY0. Đợi LEDG0 sáng và LEDG1 tắt.")
    print("1. Gửi từ PC bằng x, nhập 41. Xem HEX5:4 hiện 41.")
    print("2. Để gửi từ KEY1, đặt SW[7:0]=0x41, giữ ≥1 ms. Chọn r, nhấn/nhả KEY1 ≥10 ms.")
    print("   Mỗi lần nhấn cho một byte RX 41. Giữ phím chỉ gửi một lần.")
    print("3. Bật echo với SW16=0, SW17=1, để KEY1 yên. Chọn e rồi Enter cho 55 AA 00 FF.")
    print("   Mong đợi RX đúng bốn byte và MATCH. Hạ SW17 khi xong.")
    print("4. Giữ RX bằng SW16=1, gửi A5 qua x. HEX5:4 giữ số cũ. Hạ SW16, xem A5.")
    if profile == "target":
        print("   Để thử tràn trên RC1, bật lại SW16, gửi 17 byte rồi hạ SW16. Xem OE tại LEDR1.")
        print("5. RC1 dùng 8N1 khi SW14=0. Khi SW14=1, SW15=0 chọn 8O1, SW15=1 chọn 8E1.")
        print("   Reset KEY0, dùng f chọn cùng khung, lặp bước 1–3. Thử PE riêng bằng")
        print("   O/E trái nhau, gửi 41 và quan sát LEDR2. Khớp lại khung, KEY0 xóa cờ.")
    else:
        print("5. Trên PULP main2, SW14=0 chọn 8N1, SW14=1 chọn 8E1, SW15 dự phòng.")
        print("   Đặt SW14 trước KEY0, dùng f chọn cùng khung, lặp bước 1–3.")
        print("   Nhật ký PC chỉ thể hiện byte. Kết luận cờ parity cần quan sát riêng DUT.")


class Menu:
    def __init__(self, profile, journal):
        self.profile = profile
        self.parity = "N"
        self.log = journal
        self.link = None

    def disconnect(self, drain=True):
        if self.link is not None:
            link, self.link = self.link, None
            try:
                link.close(drain=drain)
            except PORT_ERRORS as exc:
                self.log.record("IO_ERROR", port=link.port.port, detail=str(exc))
                print(f"Lỗi cổng khi đóng {link.port.port}: {exc}")
            finally:
                self.log.record("CLOSE", port=link.port.port)
            print(f"Đã đóng {link.port.port}.")

    def connect(self, device):
        self.disconnect()
        if re.fullmatch(r"COM[0-9]+", device, re.IGNORECASE):
            device = device.upper()
        port = serial.Serial(device, baudrate=BAUD, bytesize=serial.EIGHTBITS,
                             parity=self.parity, stopbits=serial.STOPBITS_ONE,
                             timeout=0, write_timeout=0.5,
                             xonxoff=False, rtscts=False, dsrdtr=False)
        try:
            self.log.record("OPEN", port=device, profile=self.profile, baud=BAUD,
                            frame=f"8{self.parity}1")
            self.link = Link(port, self.log)
        except BaseException:
            port.close()
            raise
        print(f"Đã mở {device}. RX được ghi cả khi đang ở menu.")

    def io_error(self, exc):
        self.log.record("IO_ERROR", detail=str(exc))
        print(f"Lỗi cổng: {exc}\nKiểm tra cáp, đóng terminal khác, chọn c để mở lại.")
        self.disconnect(drain=False)

    def action(self, cmd):
        if cmd == "c":
            device = choose_port()
            if device:
                self.connect(device)
        elif cmd == "d":
            self.disconnect()
        elif cmd == "f":
            parity = choose_parity(self.profile)
            if parity and parity != self.parity:
                self.parity = parity
                print("Đã chọn khung PC. Đặt switch và reset bo theo profile (h để xem).")
                if self.link:
                    self.connect(self.link.port.port)
        elif cmd == "h":
            board_help(self.profile)
        elif cmd not in ("t", "x", "r", "e"):
            print("Chọn một lệnh trong menu.")
        elif self.link is None:
            print("Chưa kết nối. Chọn c để mở cổng CP2102.")
        elif cmd == "r":
            self.link.receive()
        else:
            if cmd == "e":
                print("Bật echo trên bo (SW16=0, SW17=1), để KEY1 yên rồi nhập gói thử.")
            data = payload(cmd)
            if data is None:
                return
            if cmd != "e":
                self.link.send(data)
                return
            while self.link.echo(data) != "MATCH":
                if input("[r] Gửi lại cùng gói, Enter về menu > ").strip().lower() != "r":
                    break

    def run(self, device):
        try:
            if device:
                try:
                    self.connect(device)
                except PORT_ERRORS as exc:
                    self.io_error(exc)
            while True:
                if self.link and self.link.failure is not None:
                    if isinstance(self.link.failure, LogError):
                        raise self.link.failure
                    self.io_error(self.link.failure)
                name = self.link.port.port if self.link else "chưa mở cổng"
                print(f"\n{self.profile} | {name} | {BAUD} 8{self.parity}1")
                print("[c] Cổng  [f] Khung  [t] Gửi chữ  [x] Gửi HEX  [r] Nhận/KEY")
                print("[e] So echo raw  [d] Ngắt  [h] Hướng dẫn bo  [q] Thoát")
                cmd = input("Chọn > ").strip().lower()
                if cmd == "q":
                    break
                try:
                    self.action(cmd)
                except KeyboardInterrupt:
                    self.log.record("CANCEL", command=cmd)
                    print("\nĐã hủy thao tác.")
                except PORT_ERRORS as exc:
                    self.io_error(exc)
        finally:
            self.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PARITIES, help="profile của bitstream đang nạp")
    parser.add_argument("--port", help="mở cổng khi khởi động, ví dụ COM10")
    parser.add_argument("--list", action="store_true", help="liệt kê cổng rồi thoát")
    parser.add_argument("--log", type=Path, help="ghi nối tiếp vào file JSON Lines UTF-8")
    args = parser.parse_args()
    if args.list:
        devices()
        return 0
    try:
        profile = args.profile or choose_profile()
        if profile is None:
            return 0
        path = args.log or Path(datetime.now().strftime("uart-%Y%m%d-%H%M%S-%f.log"))
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            print(f"Ghi log tại {path.resolve()}")
            log = Journal(stream)
            log.record("SESSION", profile=profile)
            Menu(profile, log).run(args.port)
    except (EOFError, KeyboardInterrupt):
        print("\nKết thúc phiên UART.")
    except (LogError, OSError) as exc:
        print(f"Lỗi ghi hoặc mở file log: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
