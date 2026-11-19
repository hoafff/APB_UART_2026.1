"""UART transmit controls and the live byte log."""
from pathlib import Path
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from gui_serial import parse_payload
from gui_theme import INK, LINE, MUTED, PALE, RED, SURFACE, TEAL, WHITE, label
from uart_menu import VERDICTS

HISTORY = 500


class WirePane(tk.Frame):
    def __init__(self, parent, console, log_path):
        super().__init__(parent, bg=WHITE)
        self.console = console
        self.log_path = Path(log_path)
        self.mode = tk.StringVar(self, "HEX")
        self.payload = tk.StringVar(self, "55 AA 00 FF")
        self.feedback = tk.StringVar(self)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        editor = tk.Frame(self, bg=WHITE)
        editor.grid(row=0, column=0, sticky="ew", padx=21, pady=(17, 5))
        editor.columnconfigure(1, weight=1)
        label(editor, "Gửi dữ liệu", face="AppSection").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.format_box = ttk.Combobox(editor, width=6, values=("HEX", "UTF-8"),
                                       textvariable=self.mode, state="readonly")
        self.format_box.grid(row=1, column=0, sticky="ew", padx=(0, 7))
        self.editor = ttk.Entry(editor, textvariable=self.payload, font="AppMono")
        self.editor.grid(row=1, column=1, sticky="ew")
        self.editor.bind("<Return>", lambda _event: self.submit(False))
        self.send_button = ttk.Button(editor, text="Gửi", command=lambda: self.submit(False))
        self.echo_button = ttk.Button(editor, text="Thử echo", style="Accent.TButton",
                                      command=lambda: self.submit(True))
        self.send_button.grid(row=1, column=2, padx=(9, 4))
        self.echo_button.grid(row=1, column=3)
        self.note = label(editor, "Để thử echo, đặt SW16 = 0 và SW17 = 1. Nhấn KEY1 trên bo để gửi về PC.",
                          fg=MUTED, face="AppSmall")
        self.note.grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 4))
        self.feedback_label = label(self, textvariable=self.feedback, fg=MUTED, bg=SURFACE,
                                    padx=12, pady=6, wraplength=760, justify="left")
        self.feedback_label.grid(row=1, column=0, sticky="ew", padx=21, pady=(1, 12))
        self.set_feedback("Mở cổng để gửi dữ liệu. PC sẽ tự hiển thị các byte nhận được.")

        heading = tk.Frame(self, bg=WHITE)
        heading.grid(row=2, column=0, sticky="ew", padx=21, pady=(0, 6))
        heading.columnconfigure(0, weight=1)
        label(heading, "Nhật ký truyền nhận", face="AppSection").grid(row=0, column=0, sticky="w")
        self.copy_button = ttk.Button(heading, text="Lưu bản sao log…", command=self.copy_log)
        self.copy_button.grid(row=0, column=1, sticky="e")
        table = tk.Frame(self, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
        table.grid(row=3, column=0, sticky="nsew", padx=21, pady=(0, 8))
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.history = ttk.Treeview(table, columns=("time", "dir", "size", "hex"), show="headings",
                                    selectmode="browse", style="Wire.Treeview")
        for key, name, width, stretch in (
                ("time", "Thời gian", 142, False), ("dir", "Chiều", 74, False),
                ("size", "Số byte", 82, False), ("hex", "Dữ liệu HEX", 390, True)):
            self.history.heading(key, text=name, anchor="w")
            self.history.column(key, width=width, minwidth=52, stretch=stretch, anchor="w")
        self.history.tag_configure("RX", foreground=TEAL)
        self.history.tag_configure("TX", foreground="#2e4e78")
        self.history.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.history.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.history.configure(yscrollcommand=scrollbar.set)
        self.empty = label(self.history, "Chưa có byte TX hoặc RX", fg=MUTED, face="AppSmall")
        self.empty.place(relx=.5, rely=.53, anchor="center")
        self.footer = label(self, self.log_path.name, fg=MUTED, face="AppSmall")
        self.footer.grid(row=4, column=0, sticky="ew", padx=21, pady=(0, 12))
        self.controls()

    def controls(self):
        state = "normal" if self.console.connected and not self.console.busy else "disabled"
        self.send_button.configure(state=state)
        self.echo_button.configure(state=state)
        self.copy_button.configure(state="normal" if self.log_path.is_file() else "disabled")

    def set_feedback(self, text, kind=""):
        self.feedback.set(text)
        bg, fg = (PALE, TEAL) if kind == "ok" else (("#fff0eb", RED) if kind == "error" else (SURFACE, MUTED))
        self.feedback_label.configure(bg=bg, fg=fg)

    def reset_history(self):
        self.history.delete(*self.history.get_children())
        self.empty.place(relx=.5, rely=.53, anchor="center")

    def submit(self, echo):
        if self.console.connected and not self.console.busy:
            try:
                data = parse_payload(self.payload.get(), self.mode.get())
                self.console.send(data, echo=echo)
            except (OSError, RuntimeError, ValueError) as exc:
                self.set_feedback(str(exc), "error")
                return
            if echo:
                self.set_feedback("Đang chờ FPGA trả lại gói thử…")
            else:
                self.set_feedback("Đang gửi dữ liệu…")
            self.controls()

    def event(self, row):
        kind = row["event"]
        if kind in ("RX", "TX"):
            self.empty.place_forget()
            stamp = row["time"].split("T")[-1][:12]
            packet = row["hex"]
            if row["size"] > 48:
                packet = packet[:48 * 3 - 1] + " …"
            end_visible = self.history.yview()[1] >= .999
            item = self.history.insert("", "end", values=(stamp, kind, row["size"], packet), tags=(kind,))
            children = self.history.get_children()
            if len(children) > HISTORY:
                self.history.delete(*children[:-HISTORY])
            if end_visible:
                self.history.see(item)
            if kind == "TX" and row.get("phase") != "echo":
                self.set_feedback(f"Đã gửi {row['size']} byte.")
        elif kind == "ECHO":
            status = row["status"]
            self.set_feedback(f"{status}   ·   {VERDICTS.get(status, status)}. Nhận {row['rx_size']} byte.",
                              "ok" if status == "MATCH" else "error")
        elif kind == "ERROR":
            self.set_feedback(row["detail"], "error")
        elif kind == "OPEN":
            self.reset_history()
            self.set_feedback("Cổng đã mở. Có thể gửi từ PC hoặc nhấn KEY1 trên bo.")

    def copy_log(self):
        dst = filedialog.asksaveasfilename(parent=self, title="Lưu bản sao nhật ký",
                                           initialfile=self.log_path.name, defaultextension=".jsonl",
                                           filetypes=[("Nhật ký UART", "*.jsonl"), ("Tất cả", "*")])
        if dst and Path(dst).resolve() != self.log_path.resolve():
            try:
                shutil.copyfile(self.log_path, dst)
                self.set_feedback(f"Đã lưu bản sao tại {dst}.")
            except OSError as exc:
                messagebox.showerror("Lưu nhật ký", str(exc), parent=self)
