"""Shared colors and native widget styles for the DE2-115 workbench."""
import tkinter as tk
from tkinter import font, ttk

WHITE = "#ffffff"
SURFACE = "#f4f7f6"
INK = "#172d30"
MUTED = "#4d6466"
LINE = "#d4dedc"
TEAL = "#09675b"
PALE = "#e6f4ef"
DARK = "#193537"
RED = "#9b3334"


def configure(root):
    families = set(font.families(root))
    default = font.nametofont("TkDefaultFont", root)
    sans = next((name for name in ("Segoe UI", "Adwaita Sans", "Google Sans", "Arial")
                 if name in families), default.actual("family"))
    mono = next((name for name in ("Cascadia Mono", "Consolas", "JetBrainsMono Nerd Font",
                                   "DejaVu Sans Mono") if name in families),
                font.nametofont("TkFixedFont", root).actual("family"))
    default.configure(family=sans, size=10)
    for name, family, size, weight in (
        ("AppTitle", sans, 18, "bold"), ("AppSection", sans, 13, "bold"),
        ("AppBold", sans, 10, "bold"), ("AppSmall", sans, 9, "normal"),
        ("AppMono", mono, 10, "normal"),
    ):
        # Named fonts are shared by labels, controls and the two pages.
        root.tk.call("font", "create", name, "-family", family, "-size", size, "-weight", weight)
    root.option_add("*Font", "TkDefaultFont")
    root.option_add("*TCombobox*Listbox.font", "TkDefaultFont")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=WHITE, foreground=INK, font="TkDefaultFont")
    style.configure("TFrame", background=WHITE)
    style.configure("TLabel", background=WHITE)
    style.configure("TButton", background=WHITE, foreground=INK, padding=(11, 6),
                    bordercolor=LINE, lightcolor=WHITE, darkcolor=WHITE, focusthickness=1,
                    focuscolor=TEAL, relief="flat")
    style.map("TButton", background=[("disabled", SURFACE), ("pressed", LINE), ("active", "#edf3f1")],
              foreground=[("disabled", "#607472")], bordercolor=[("focus", TEAL)])
    style.configure("Accent.TButton", background=TEAL, foreground=WHITE, font="AppBold",
                    bordercolor=TEAL, lightcolor=TEAL, darkcolor=TEAL, focuscolor=WHITE)
    style.map("Accent.TButton", background=[("disabled", "#dce5e2"), ("pressed", "#07483f"),
                                            ("active", "#09594f")],
              foreground=[("disabled", "#536765"), ("!disabled", WHITE)],
              bordercolor=[("disabled", LINE), ("!disabled", TEAL)],
              lightcolor=[("!disabled", TEAL)], darkcolor=[("!disabled", TEAL)])
    for name in ("TCombobox", "TEntry"):
        style.configure(name, fieldbackground=WHITE, background=WHITE, foreground=INK,
                        padding=(6, 5), bordercolor="#aebfbb", lightcolor=WHITE,
                        darkcolor=WHITE, arrowcolor=INK)
        style.map(name, fieldbackground=[("disabled", SURFACE), ("readonly", WHITE)],
                  foreground=[("disabled", "#617571"), ("readonly", INK)],
                  selectbackground=[("readonly", WHITE)], selectforeground=[("readonly", INK)],
                  bordercolor=[("focus", TEAL)])
    rowheight = default.metrics("linespace") + 14
    style.configure("Treeview", background=WHITE, fieldbackground=WHITE, foreground=INK,
                    rowheight=rowheight, borderwidth=0, relief="flat")
    style.map("Treeview", background=[("selected", "#d8eee7")], foreground=[("selected", "#104d43")])
    style.configure("Treeview.Heading", foreground=MUTED, background=SURFACE,
                    padding=(5, 6), font="AppSmall", relief="flat")
    style.configure("Wire.Treeview", font="AppMono")
    style.configure("Vertical.TScrollbar", background="#cdd9d5", troughcolor=SURFACE,
                    bordercolor=WHITE, arrowcolor=MUTED, arrowsize=12, gripcount=0)
    style.configure("Horizontal.TScrollbar", background="#cdd9d5", troughcolor=SURFACE,
                    bordercolor=WHITE, arrowcolor=MUTED, arrowsize=12, gripcount=0)


def label(parent, text="", *, bg=WHITE, fg=INK, face="TkDefaultFont", **options):
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=face, anchor="w",
                    borderwidth=0, highlightthickness=0, **options)
