"""Cửa sổ thử bo APB UART trên DE2-115."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def use_project_python():
    try:
        from serial.tools import list_ports
    except ImportError:
        venv = HERE.parent / ".venv"
        executable = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if executable.is_file() and Path(sys.prefix).resolve() != venv.resolve():
            os.execv(str(executable), [str(executable), str(Path(__file__).resolve()), *sys.argv[1:]])
        raise SystemExit("Cần pySerial 3.5. Cài bằng python -m pip install pyserial==3.5 trong môi trường của dự án.")


if __name__ == "__main__":
    use_project_python()

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError:
    raise SystemExit("Cần Tk cho Python. Trên Arch cài gói tk, trên Windows chọn Tcl/Tk trong bộ cài Python.")

from board_report import load_plans
from board_view import BoardPane
from gui_serial import Console, ports
from gui_theme import DARK, INK, LINE, MUTED, SURFACE, TEAL, WHITE, configure, label
from uart_menu import PARITIES
from uart_view import WirePane

NAMES = {"target": "TARGET  ·  main", "pulp": "PULP  ·  main2"}


def project_profile():
    qpf = HERE.parent / "fpga/de2_115/de2_115_pulp_uart.qpf"
    return "pulp" if qpf.is_file() else "target"


class Workbench:
    def __init__(self, root, profile, port=None, log_path=None):
        self.root = root
        configure(root)
        self.profile = profile
        self.log_path = Path(log_path or datetime.now().strftime("uart-%Y%m%d-%H%M%S-%f.jsonl")).resolve()
        self.console = Console(self.log_path)
        self.poll_id = None
        self.closing = False
        self.connected_before = False
        self.page = ""
        root.title("APB UART — DE2-115")
        width = min(1080, max(600, root.winfo_screenwidth() - 30))
        height = min(760, max(440, root.winfo_screenheight() - 80))
        root.geometry(f"{width}x{height}")
        root.minsize(min(795, width), min(520, height))
        root.configure(bg=SURFACE)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)
        self.port_name = tk.StringVar(root, port or "")
        self.profile_name = tk.StringVar(root, NAMES[profile])
        self.frame_name = tk.StringVar(root, "8N1")

        header = tk.Frame(root, bg=DARK)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(4, weight=1)
        # A UART start edge, three data transitions and the return to idle.
        mark = tk.Canvas(header, width=34, height=25, bg=DARK, bd=0, highlightthickness=0)
        mark.grid(row=0, column=0, padx=(19, 9), pady=13)
        mark.create_line(1, 6, 6, 6, 6, 18, 13, 18, 13, 6, 19, 6, 19, 18, 25, 18, 25, 6, 33, 6,
                         fill="#9bdac6", width=2, joinstyle="round")
        label(header, "APB UART", bg=DARK, fg=WHITE, face="AppSection").grid(row=0, column=1, sticky="w")
        tk.Frame(header, width=1, height=18, bg="#4d6667").grid(row=0, column=2, padx=11)
        label(header, "DE2-115", bg=DARK, fg="#c2d8d4").grid(row=0, column=3, sticky="w")
        self.indicator = tk.Canvas(header, width=13, height=16, bg=DARK, bd=0, highlightthickness=0)
        self.indicator.grid(row=0, column=5, sticky="e")
        self.dot = self.indicator.create_oval(3, 5, 10, 12, fill="#a5b2b0", outline="")
        self.connection = label(header, "Chưa mở cổng", bg=DARK, fg=WHITE, face="AppSmall")
        self.connection.grid(row=0, column=6, sticky="e", padx=(4, 22))

        bar = tk.Frame(root, bg=WHITE)
        bar.grid(row=1, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        self.profile_box = self.field(bar, 0, "Thiết kế", self.profile_name, tuple(NAMES.values()), 17)
        self.profile_box.bind("<<ComboboxSelected>>", self.change_profile)
        self.port_box = self.field(bar, 1, "Cổng CP2102", self.port_name, (), 21, editable=True)
        self.port_box.bind("<Return>", lambda _event: self.toggle_port())
        self.refresh_button = ttk.Button(bar, text="Quét cổng", command=self.refresh)
        self.refresh_button.grid(row=1, column=2, sticky="w", padx=(0, 16), pady=(0, 10))
        self.frame_box = self.field(bar, 3, "Khung · 115200 baud", self.frame_name, self.frames(), 7)
        self.connect_button = ttk.Button(bar, text="Kết nối", style="Accent.TButton", command=self.toggle_port)
        self.connect_button.grid(row=1, column=4, sticky="e", padx=(4, 20), pady=(0, 10))

        nav = tk.Frame(root, bg=SURFACE)
        nav.grid(row=2, column=0, sticky="ew", padx=18, pady=(4, 0))
        nav.columnconfigure(2, weight=1)
        self.tab_buttons = {}
        self.tab_lines = {}
        for i, (page, text) in enumerate((("board", "Phiếu thử bo"), ("wire", "Gửi / nhận UART"))):
            btn = tk.Button(nav, text=text, font="AppBold", bg=SURFACE, activebackground="#e3ece8",
                            fg=MUTED, activeforeground=TEAL, relief="flat", bd=0, padx=13, pady=9,
                            highlightthickness=1, highlightbackground=SURFACE, highlightcolor=TEAL,
                            command=lambda page=page: self.show(page))
            btn.grid(row=0, column=i, sticky="nsw")
            self.tab_buttons[page] = btn
            barline = tk.Frame(nav, height=2, bg=SURFACE)
            barline.grid(row=1, column=i, sticky="ew")
            self.tab_lines[page] = barline
        self.export_button = ttk.Button(nav, text="Xuất phiếu CSV…", command=self.export)
        self.export_button.grid(row=0, column=3, sticky="e", pady=(3, 1))
        body = tk.Frame(root, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
        body.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 6))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.board = BoardPane(body, load_plans(), lambda: self.show("wire"))
        self.wire = WirePane(body, self.console, self.log_path)
        self.board.select_profile(profile)
        self.message = label(root, "", bg=SURFACE, fg=MUTED, face="AppSmall")
        self.message.grid(row=4, column=0, sticky="ew", padx=21, pady=(0, 6))
        self.show("board")
        self.refresh()
        root.bind("<Control-Key-1>", lambda _event: self.show("board"))
        root.bind("<Control-Key-2>", lambda _event: self.show("wire"))
        root.bind("<Control-s>", lambda _event: self.export())
        root.protocol("WM_DELETE_WINDOW", self.quit)
        if port:
            self.toggle_port()
        self.poll_id = root.after(70, self.poll)

    def field(self, parent, column, title, textvariable, choices, width, editable=False):
        pad = (20, 8) if column == 0 else (4, 7)
        label(parent, title, fg=MUTED, face="AppSmall").grid(row=0, column=column, sticky="w", padx=pad, pady=(8, 3))
        box = ttk.Combobox(parent, textvariable=textvariable, values=choices, width=width,
                           state="normal" if editable else "readonly")
        box.grid(row=1, column=column, sticky="ew", padx=pad, pady=(0, 10))
        return box

    def frames(self):
        return tuple(f"8{x}1" for x in PARITIES[self.profile])

    def change_profile(self, _event=None):
        if self.console.connected:
            self.profile_name.set(NAMES[self.profile])
            return
        profile = next(key for key, value in NAMES.items() if value == self.profile_name.get())
        if profile == self.profile:
            return
        self.read_events()
        self.profile = profile
        self.wire.reset_history()
        self.wire.set_feedback("Mở cổng để bắt đầu lượt thử.")
        self.frame_box.configure(values=self.frames())
        if self.frame_name.get() not in self.frames():
            self.frame_name.set("8N1")
        self.board.select_profile(self.profile)

    def refresh(self):
        try:
            devices = ports()
        except OSError as exc:
            self.message.configure(text=f"Không quét được cổng. Bạn có thể nhập tên cổng. {exc}")
            return
        self.port_box.configure(values=devices)
        if devices and not self.port_name.get():
            self.port_name.set(devices[0])
        msg = (f"Tìm thấy {len(devices)} cổng. Chọn cổng của CP2102 rồi nhấn Kết nối." if devices
               else "Chưa thấy cổng USB-UART. Bạn có thể nhập tên cổng hoặc xem phiếu thử khi chưa cắm bo.")
        self.message.configure(text=msg, fg=MUTED)

    def show(self, page):
        self.page = page
        for key, pane in (("board", self.board), ("wire", self.wire)):
            active = page == key
            if active:
                pane.grid(row=0, column=0, sticky="nsew")
            else:
                pane.grid_remove()
            self.tab_buttons[key].configure(fg=TEAL if active else MUTED)
            self.tab_lines[key].configure(bg=TEAL if active else SURFACE)
        if page == "board":
            self.export_button.grid()
        else:
            self.export_button.grid_remove()

    def export(self):
        return self.board.export_dialog()

    def toggle_port(self):
        if self.console.busy:
            return
        if self.console.connected:
            self.console.close()
            self.wire.set_feedback("Đã đóng cổng.")
            self.message.configure(text="Đã đóng cổng.", fg=MUTED)
        else:
            device = self.port_name.get().strip()
            if not device:
                self.message.configure(text="Chọn hoặc nhập cổng CP2102 trước khi kết nối.", fg="#913b32")
                self.port_box.focus_set()
                return
            try:
                self.console.open(device, self.profile, self.frame_name.get()[1])
            except (OSError, RuntimeError, ValueError) as exc:
                self.message.configure(text=f"Không mở được cổng. {exc}", fg="#913b32")
                return
            self.message.configure(text=f"Đang ghi TX và RX vào {self.log_path.name}.", fg=MUTED)
        self.read_events()
        self.update_connection()

    def update_connection(self):
        connected = self.console.connected
        self.connected_before = connected
        self.connection.configure(text="Đã kết nối" if connected else "Chưa mở cổng")
        self.indicator.itemconfigure(self.dot, fill="#8ce5ae" if connected else "#a5b2b0")
        self.profile_box.configure(state="disabled" if connected else "readonly")
        self.frame_box.configure(state="disabled" if connected else "readonly")
        self.port_box.configure(state="disabled" if connected else "normal")
        self.refresh_button.configure(state="disabled" if connected else "normal")
        self.connect_button.configure(text="Ngắt cổng" if connected else "Kết nối",
                                      style="TButton" if connected else "Accent.TButton")
        self.wire.controls()

    def read_events(self):
        for row in self.console.poll():
            self.wire.event(row)
            if row["event"] == "ERROR":
                self.message.configure(text=row["detail"], fg="#913b32")

    def poll(self):
        self.read_events()
        if self.connected_before != self.console.connected:
            self.update_connection()
        self.connect_button.configure(state="disabled" if self.console.busy else "normal")
        self.wire.controls()
        if self.closing and not self.console.busy:
            self.finish()
        else:
            self.poll_id = self.root.after(70, self.poll)

    def quit(self):
        if self.closing:
            return
        dirty = list(self.board.dirty_profiles())
        if dirty:
            names = ", ".join(NAMES[p] for p in dirty)
            choice = messagebox.askyesnocancel("Phiếu chưa xuất", f"Xuất phiếu {names} trước khi đóng?",
                                               parent=self.root)
            if choice is None:
                return
            if choice:
                for profile in dirty:
                    self.board.select_profile(profile)
                    if not self.board.export_dialog():
                        self.board.select_profile(self.profile)
                        return
                self.board.select_profile(self.profile)
        if self.console.busy:
            self.closing = True
            self.message.configure(text="Đang hoàn tất thao tác UART trước khi đóng.")
            return
        self.finish()

    def finish(self):
        if self.poll_id:
            self.root.after_cancel(self.poll_id)
            self.poll_id = None
        try:
            self.console.close()
        finally:
            self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(NAMES), default=project_profile())
    parser.add_argument("--port", help="mở cổng này ngay khi khởi động")
    parser.add_argument("--log", type=Path, help="đường dẫn nhật ký TX/RX (JSON Lines)")
    args = parser.parse_args()
    try:
        root = tk.Tk(className="APBUart")
    except tk.TclError as exc:
        sys.exit(f"Không mở được cửa sổ Tk. Hãy chạy trong phiên desktop hoặc dùng host/uart_menu.py. {exc}")
    Workbench(root, args.profile, args.port, args.log)
    root.mainloop()


if __name__ == "__main__":
    main()
