"""Menu UART Linux cho DE2-115 và CP2102."""

import errno
import os
from pathlib import Path
import sys

try:
    from serial.tools import list_ports
except ImportError:
    if __name__ != "__main__":
        raise
    project_env = Path(__file__).resolve().parents[1] / ".venv"
    python = project_env / "bin" / "python"
    if (project_env / "pyvenv.cfg").is_file() and Path(sys.prefix).resolve() != project_env.resolve():
        if os.access(python, os.X_OK):
            try:
                os.execv(python, [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
            except OSError as exc:
                sys.exit(f"Không chạy được {python}: {exc}")
    sys.exit("Thiếu pySerial. Từ thư mục gốc dự án, chạy:\n"
             "  python -m venv .venv\n"
             "  .venv/bin/python -m pip install pyserial==3.5")

from uart_menu import Menu, main


def usb_devices(dev=Path("/dev")):
    paths = {}
    descriptions = {}
    for alias in sorted((dev / "serial" / "by-id").glob("*")):
        if alias.is_symlink() and alias.exists():
            paths.setdefault(alias.resolve(), alias)

    try:
        ports = list_ports.comports()
    except OSError as exc:
        print(f"Không đọc được danh sách từ pySerial ({exc}). Đang tìm trong {dev}.")
        ports = []
    for port in ports:
        path = Path(port.device)
        target = path.resolve()
        if (target not in paths and port.vid is None and not (port.hwid or "").startswith("USB ")
                and not path.name.startswith(("ttyUSB", "ttyACM"))):
            continue
        paths.setdefault(target, path)
        description = port.description if port.description != "n/a" else ""
        if port.vid is not None and port.pid is not None:
            description += f" [{port.vid:04X}:{port.pid:04X}]"
        descriptions[target] = description

    for pattern in ("ttyUSB*", "ttyACM*"):
        for path in sorted(dev.glob(pattern)):
            if path.exists():
                paths.setdefault(path.resolve(), path)

    choices = []
    for target, path in sorted(paths.items(), key=lambda item: item[1]):
        choices.append(str(path))
        mapping = f" → {target}" if path != target else ""
        print(f"  {len(choices)}. {path}{mapping}  {descriptions.get(target, '')}".rstrip())
    if not choices:
        print("Chưa thấy cổng USB-UART. Kiểm tra CP2102 và cáp USB dữ liệu, "
              "hoặc nhập đường dẫn cổng bằng tay.")
    return choices


class LinuxMenu(Menu):
    list_devices = staticmethod(usb_devices)
    port_example = "/dev/ttyUSB0"
    exclusive = True

    def run(self, device):
        super().run(device or self.choose_port())

    @staticmethod
    def port_hint(exc):
        code = getattr(exc, "errno", None)
        if code is None and exc.args:
            code = exc.args[0]  # termios.error can carry errno only in args.
        if code in (errno.EACCES, errno.EPERM):
            return "Thiếu quyền đọc/ghi cổng. Kiểm tra ls -lL <cổng> và id (nhóm uucp trên Arch)."
        if code in (errno.EBUSY, errno.EAGAIN):
            return "Cổng đang bận. Đóng chương trình đang giữ cổng rồi chọn c để mở lại."
        if code == errno.ENOENT:
            return "Không thấy đường dẫn cổng. Cắm lại thiết bị, chọn c để xem danh sách mới."
        if code in (errno.EIO, errno.ENXIO, errno.ENODEV) or "disconnected" in str(exc).lower():
            return "Mất kết nối UART. Kiểm tra cáp USB, cắm lại thiết bị rồi chọn c."
        return "Kiểm tra đường dẫn, cáp USB và cấu hình cổng. Chọn c để mở lại."


if __name__ == "__main__":
    sys.exit(main(LinuxMenu))
