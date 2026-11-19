"""Phiếu thử bo. Người vận hành chọn và ghi kết quả cho từng thiết kế."""

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from textwrap import fill
import tkinter as tk
from tkinter import filedialog, font, messagebox, simpledialog, ttk

from board_report import load_plans, new_results, save_sheet
from gui_theme import INK, LINE, MUTED, PALE, TEAL, WHITE, label


_STATUSES = ("NOT_RUN", "PASS", "FAIL")
_FIELDS = (("board_id", "Mã bo"), ("operator", "Người thử"),
           ("sof_sha256", "SHA-256 của tệp SOF"), ("cp2102_id", "Mã CP2102"))
_TEMPLATE = Path(__file__).resolve().parent.parent / "docs" / "07_FPGA_Board_Acceptance.csv"


class _SheetInfo(simpledialog.Dialog):
    def __init__(self, parent, profile, metadata):
        self.metadata = metadata
        self.entries = {}
        super().__init__(parent, title=f"Thông tin phiếu · {profile.upper()}")

    def body(self, master):
        self.configure(bg=WHITE)
        master.configure(bg=WHITE)
        for row, (key, caption) in enumerate(_FIELDS):
            label(master, caption).grid(row=row, column=0, padx=8, pady=5, sticky="w")
            entry = ttk.Entry(master, name=key, width=34)
            entry.grid(row=row, column=1, padx=8, pady=5, sticky="ew")
            entry.insert(0, self.metadata[key])
            self.entries[key] = entry
        return self.entries["board_id"]

    def buttonbox(self):
        bar = tk.Frame(self, bg=WHITE)
        bar.pack(fill="x", padx=13, pady=(4, 12))
        ttk.Button(bar, name="apply_metadata", text="Áp dụng", style="Accent.TButton",
                   command=self.ok).pack(side="right")
        ttk.Button(bar, name="cancel_metadata", text="Hủy", command=self.cancel).pack(side="right", padx=6)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

    def apply(self):
        self.result = {key: entry.get().strip() for key, entry in self.entries.items()}


def _scrollbar(parent, widget, row=0, on_view=None):
    bar = ttk.Scrollbar(parent, orient="vertical", command=widget.yview, takefocus=False)
    bar.grid(row=row, column=1, sticky="ns")

    def update(first, last):
        first, last = float(first), float(last)
        bar.set(first, last)
        if first <= 0 and last >= 1:
            bar.grid_remove()
        else:
            bar.grid()
        if on_view:
            on_view(first, last)

    widget.configure(yscrollcommand=update)


def _tab_moves_focus(widget):
    def move(event):
        backwards = event.keysym == "ISO_Left_Tab" or event.state & 1
        target = widget.tk_focusPrev() if backwards else widget.tk_focusNext()
        target.focus_set()
        return "break"

    widget.bind("<Tab>", move)
    if widget.tk.call("tk", "windowingsystem") == "x11":
        widget.bind("<ISO_Left_Tab>", move)


class BoardPane(tk.Frame):
    def __init__(self, parent, plans=None, on_uart=None):
        super().__init__(parent, bg=WHITE)
        self.plans = load_plans() if plans is None else plans
        self._cases = {p: {c["id"]: c for c in cases} for p, cases in self.plans.items()}
        self._results = new_results(self.plans)
        self._metadata = {p: dict.fromkeys((k for k, _ in _FIELDS), "") for p in self.plans}
        self._saved_results = deepcopy(self._results)
        self._saved_metadata = deepcopy(self._metadata)
        self._pending = {p: {} for p in self.plans}
        self._selected = {}
        self.profile = self.current_id = None
        self._folder = Path.home()
        self.columnconfigure(2, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_list()
        tk.Frame(self, width=1, bg=LINE).grid(row=0, column=1, sticky="ns")
        self._build_editor(on_uart)
        self.select_profile("target")

    def _build_list(self):
        side = tk.Frame(self, bg=WHITE, width=252)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        side.columnconfigure(0, weight=1)
        side.rowconfigure(1, weight=1)
        head = tk.Frame(side, bg=WHITE)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=13, pady=(12, 8))
        label(head, "Ca kiểm tra", face="AppSection").pack(side="left")
        self.count = label(head, face="AppSmall", fg=MUTED, name="count")
        self.count.pack(side="right")

        self._list_font = font.nametofont("TkDefaultFont", self)
        height = self._list_font.metrics("linespace")
        ttk.Style(self).configure("Board.Treeview", rowheight=2 * height + 7)
        self.case_list = ttk.Treeview(side, name="case_list", style="Board.Treeview",
                                      columns=("id", "title"), show="", selectmode="browse", height=1)
        self.case_list.column("id", width=56, minwidth=56, stretch=False)
        self.case_list.column("title", width=162, minwidth=80)
        self.case_list.tag_configure("recorded", foreground=MUTED)
        self.case_list.grid(row=1, column=0, sticky="nsew", padx=(8, 0))
        _scrollbar(side, self.case_list, 1, self._list_view_changed)
        self.case_list.bind("<<TreeviewSelect>>", self._list_selected)
        self.sheet_info = ttk.Button(side, name="sheet_info", text="Thông tin phiếu…", command=self._sheet_info)
        self.sheet_info.grid(row=2, column=0, columnspan=2, sticky="w", padx=13, pady=10)

    def _build_editor(self, on_uart):
        right = tk.Frame(self, bg=WHITE)
        right.grid(row=0, column=2, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=6)
        right.rowconfigure(2, weight=1)
        self.details = tk.Text(right, name="details", width=1, height=9, wrap="word", bg=WHITE, fg=INK,
                               font="TkDefaultFont", bd=0, highlightthickness=1, highlightbackground=WHITE,
                               highlightcolor=TEAL, padx=13, pady=8, takefocus=True, cursor="arrow")
        self.details.grid(row=0, column=0, sticky="nsew")
        _scrollbar(right, self.details)
        _tab_moves_focus(self.details)
        self.details.tag_configure("id", font="AppMono", foreground=TEAL, spacing3=5)
        self.details.tag_configure("title", font="AppTitle", spacing3=6)
        self.details.tag_configure("label", font="AppBold", spacing3=2)
        self.details.tag_configure("steps", spacing3=7)
        inset = dict(background=PALE, lmargin1=9, lmargin2=9, rmargin=7)
        self.details.tag_configure("expected_label", **inset, font="AppBold", foreground=TEAL, spacing1=5)
        self.details.tag_configure("expected", **inset, spacing3=5)
        self.details.tag_configure("hint", font="AppSmall", foreground=MUTED, spacing1=6)

        tk.Frame(right, height=1, bg=LINE).grid(row=1, column=0, columnspan=2, sticky="ew")
        form = tk.Frame(right, bg=WHITE)
        form.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=14, pady=(7, 10))
        form.columnconfigure(1, weight=1)
        form.rowconfigure(1, weight=1)
        label(form, "Ghi chú quan sát", face="AppBold").grid(row=0, column=0, columnspan=2, sticky="w")
        self.feedback = label(form, face="AppSmall", fg=MUTED, name="feedback")
        self.feedback.grid(row=0, column=1, columnspan=2, sticky="e")
        self.observed = tk.Text(form, name="observed", width=1, height=2, wrap="word", bg=WHITE, fg=INK,
                                font="TkDefaultFont", bd=0, highlightthickness=1, highlightbackground=LINE,
                                highlightcolor=TEAL, insertbackground=INK, padx=6, pady=3, takefocus=True)
        self.observed.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(2, 6))
        _tab_moves_focus(self.observed)
        label(form, "Minh chứng", face="AppBold").grid(row=2, column=0, sticky="w", padx=(0, 8))
        self.evidence_path = ttk.Entry(form, name="evidence_path", width=1)
        self.evidence_path.grid(row=2, column=1, sticky="ew")
        self.browse_evidence = ttk.Button(form, name="browse_evidence", text="Chọn tệp…", command=self._browse)
        self.browse_evidence.grid(row=2, column=2, sticky="e", padx=(6, 0))

        actions = tk.Frame(form, bg=WHITE)
        actions.grid(row=3, column=1, columnspan=2, sticky="ew", pady=(6, 0))
        actions.columnconfigure(2, weight=1)
        label(form, "Trạng thái", face="AppBold").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.status = ttk.Combobox(actions, name="status", values=_STATUSES, state="readonly", width=8)
        self.status.grid(row=0, column=0, sticky="w")
        self.status.bind("<<ComboboxSelected>>", lambda _event: self._show_record_state())
        self.record_result = ttk.Button(actions, name="record_result", text="Ghi kết quả",
                                        style="Accent.TButton", command=self._record)
        self.record_result.grid(row=0, column=1, padx=(7, 0))
        self.open_uart = None
        if on_uart is not None:
            self.open_uart = ttk.Button(actions, name="open_uart", text="Mở UART", width=7, command=on_uart)
            self.open_uart.grid(row=0, column=3, sticky="e")

    @property
    def results(self):
        self._capture()
        return self._results

    def _capture(self):
        if self.current_id is None:
            return
        row = self._results[self.profile][self.current_id]
        row["observed"] = self.observed.get("1.0", "end-1c")
        row["evidence_path"] = self.evidence_path.get()
        pending = self._pending[self.profile]
        choice = self.status.get()
        if choice == row["status"]:
            pending.pop(self.current_id, None)
        else:
            pending[self.current_id] = choice

    def dirty_profiles(self):
        self._capture()
        return tuple(p for p in self.plans if self._pending[p] or self._results[p] != self._saved_results[p]
                     or self._metadata[p] != self._saved_metadata[p])

    def _list_selected(self, _event):
        selected = self.case_list.selection()
        if selected and selected[0] != self.current_id:
            self.select_case(selected[0])

    def _list_view_changed(self, first, last):
        height = self.case_list.winfo_height()
        old_height, old_first, old_last = self._list_view
        self._list_view = height, first, last
        if height < old_height and self.current_id is not None:
            # Restore a row lost to resizing only if it was visible before the resize.
            position = (self.case_list.index(self.current_id) + 0.5) / len(self._cases[self.profile])
            if old_first <= position < old_last and not first <= position < last:
                self.case_list.see(self.current_id)

    def _row(self, case_id):
        status = self._results[self.profile][case_id]["status"]
        recorded = status != "NOT_RUN"
        code = f"{case_id}\n{status}" if recorded else case_id
        title = self._cases[self.profile][case_id]["title"]
        if self._list_font.measure(title) > 158:
            title = fill(title, width=22, max_lines=2, placeholder="…", break_on_hyphens=False)
        return dict(values=(code, title), tags=("recorded",) if recorded else ())

    def _update_count(self):
        rows = self._results[self.profile]
        done = sum(row["status"] != "NOT_RUN" for row in rows.values())
        self.count.configure(text=f"Đã ghi {done}/{len(rows)}")

    def select_profile(self, profile):
        cases = self._cases[profile]
        if profile == self.profile:
            return
        self._capture()
        self.profile, self.current_id = profile, None
        self._list_view = (0, 0.0, 1.0)
        self.case_list.delete(*self.case_list.get_children())
        for case_id in cases:
            self.case_list.insert("", "end", iid=case_id, **self._row(case_id))
        self._update_count()
        if cases:
            first = "HW01" if "HW01" in cases else next(iter(cases))
            self.select_case(self._selected.get(profile, first))
        else:
            self._display(None)

    def select_case(self, case_id):
        case = self._cases[self.profile][case_id]
        if case_id == self.current_id:
            self.case_list.see(case_id)
            return
        self._capture()
        self.current_id = self._selected[self.profile] = case_id
        self.case_list.selection_set(case_id)
        self.case_list.focus(case_id)
        self.case_list.see(case_id)
        self._display(case)

    def _display(self, case):
        text = self.details
        text.configure(state="normal")
        text.delete("1.0", "end")
        if case:
            text.insert("end", case["id"] + "   ", "id")
            text.insert("end", case["title"] + "\n", "title")
            text.insert("end", "Thao tác\n", "label")
            text.insert("end", case["steps"] + "\n", "steps")
            text.insert("end", "Kết quả mong đợi\n", "expected_label")
            text.insert("end", case["expected"] + "\n", "expected")
            if case["evidence"]:
                text.insert("end", "Minh chứng gợi ý · " + case["evidence"], "hint")
        else:
            text.insert("end", "Thiết kế này chưa có ca kiểm tra.")
        text.configure(state="disabled")
        text.yview_moveto(0)

        row = self._results[self.profile].get(self.current_id, {})
        self.observed.configure(state="normal")
        self.evidence_path.state(["!disabled"])
        self.observed.delete("1.0", "end")
        self.observed.insert("1.0", row.get("observed", ""))
        self.evidence_path.delete(0, "end")
        self.evidence_path.insert(0, row.get("evidence_path", ""))
        self.status.set(self._pending[self.profile].get(self.current_id, row.get("status", "NOT_RUN")))
        self.observed.configure(state="normal" if case else "disabled")
        for widget in (self.evidence_path, self.browse_evidence, self.status, self.record_result):
            widget.state(["!disabled" if case else "disabled"])
        self._show_record_state()

    def _show_record_state(self):
        row = self._results[self.profile].get(self.current_id, {})
        caption = ""
        if row and self.status.get() != row["status"]:
            caption = "Chờ ghi kết quả"
        elif row.get("datetime_local"):
            caption = f"Đã ghi lúc {row['datetime_local'][11:19]}"
        self.feedback.configure(text=caption)

    def _record(self):
        self._capture()
        row = self._results[self.profile][self.current_id]
        choice = self.status.get()
        row.update(status=choice, datetime_local=self._timestamp(choice))
        self._pending[self.profile].pop(self.current_id, None)
        self.case_list.item(self.current_id, **self._row(self.current_id))
        self._update_count()
        self._show_record_state()

    @staticmethod
    def _timestamp(status):
        return "" if status == "NOT_RUN" else datetime.now().astimezone().isoformat(timespec="seconds")

    def _browse(self):
        path = filedialog.askopenfilename(title="Chọn tệp minh chứng", parent=self.winfo_toplevel())
        if path:
            self.evidence_path.delete(0, "end")
            self.evidence_path.insert(0, path)

    def _sheet_info(self):
        dialog = _SheetInfo(self.winfo_toplevel(), self.profile, self._metadata[self.profile])
        if dialog.result is not None:
            self._metadata[self.profile] = dialog.result

    def export_dialog(self):
        self._capture()
        profile = self.profile
        parent = self.winfo_toplevel()
        path = filedialog.asksaveasfilename(parent=parent, title=f"Xuất phiếu {profile.upper()}",
                                            initialdir=self._folder, initialfile=f"phieu-{profile}.csv",
                                            defaultextension=".csv", filetypes=[("Phiếu CSV", "*.csv")])
        if not path:
            return False
        try:
            dest = Path(path).resolve()
            if dest.suffix.lower() != ".csv":
                raise ValueError("Chọn tên tệp có đuôi .csv.")
            if dest == _TEMPLATE.resolve():
                raise ValueError("Đây là phiếu mẫu của dự án. Hãy chọn tên hoặc thư mục khác.")
            sheet = deepcopy(self._results[profile])
            pending = self._pending[profile]
            if pending:
                choices = ", ".join(f"{key} = {value}" for key, value in pending.items())
                if not messagebox.askokcancel("Ghi kết quả còn chờ", f"{choices}\n\nGhi các lựa chọn này vào phiếu?",
                                              parent=parent):
                    return False
                for case_id, choice in pending.items():
                    sheet[case_id].update(status=choice, datetime_local=self._timestamp(choice))
            save_sheet(dest, profile, self.plans[profile], sheet, self._metadata[profile])
        except (OSError, ValueError) as exc:
            messagebox.showerror("Chưa xuất được phiếu", str(exc), parent=parent)
            return False

        for case_id in pending:
            self._results[profile][case_id].update(sheet[case_id])
            self.case_list.item(case_id, **self._row(case_id))
        pending.clear()
        self._saved_results[profile] = sheet
        self._saved_metadata[profile] = self._metadata[profile].copy()
        self._folder = dest.parent
        self._update_count()
        self.feedback.configure(text="Đã xuất phiếu CSV")
        return True
