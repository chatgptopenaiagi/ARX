from tkinter import ttk

COLORS={
    "bg":"#11141b","panel":"#1b202b","panel_alt":"#242b38","text":"#f5f7fb","muted":"#b8c0cc",
    "accent":"#4cc9f0","ready":"#4ade80","partial":"#f59e0b","missing":"#ff3d8d","blocked":"#ff5252",
    "unknown":"#facc15","not_applicable":"#94a3b8","external":"#a78bfa","selected":"#334155",
    "green":"#4ade80","yellow":"#facc15","red":"#ff5252",
}

def status_color(status):
    return COLORS.get(str(status or "unknown").lower(),COLORS["unknown"])

def apply_theme(root):
    root.configure(bg=COLORS["bg"]);style=ttk.Style(root);style.theme_use("clam")
    style.configure(".",background=COLORS["bg"],foreground=COLORS["text"],fieldbackground=COLORS["panel"],font=("Segoe UI",10))
    style.configure("TFrame",background=COLORS["bg"]);style.configure("Panel.TFrame",background=COLORS["panel"])
    style.configure("TLabel",background=COLORS["bg"],foreground=COLORS["text"]);style.configure("Muted.TLabel",foreground=COLORS["muted"])
    style.configure("Title.TLabel",font=("Segoe UI Semibold",24),foreground=COLORS["text"]);style.configure("Subtitle.TLabel",font=("Segoe UI",11),foreground=COLORS["accent"])
    style.configure("TButton",background=COLORS["panel_alt"],foreground=COLORS["text"],padding=(14,10),font=("Segoe UI Semibold",10),borderwidth=0)
    style.map("TButton",background=[("active",COLORS["selected"]),("disabled",COLORS["panel"])],foreground=[("disabled",COLORS["muted"])])
    style.configure("Accent.TButton",background=COLORS["accent"],foreground="#071018");style.map("Accent.TButton",background=[("active","#7ddcf5")])
    style.configure("TNotebook",background=COLORS["bg"],borderwidth=0);style.configure("TNotebook.Tab",background=COLORS["panel"],foreground=COLORS["muted"],padding=(14,9))
    style.map("TNotebook.Tab",background=[("selected",COLORS["selected"])],foreground=[("selected",COLORS["text"])])
    style.configure("Treeview",background=COLORS["panel"],fieldbackground=COLORS["panel"],foreground=COLORS["text"],rowheight=27,borderwidth=0)
    style.configure("Treeview.Heading",background=COLORS["panel_alt"],foreground=COLORS["text"],font=("Segoe UI Semibold",10))
    style.map("Treeview",background=[("selected",COLORS["selected"])],foreground=[("selected",COLORS["text"])])
    style.configure("Horizontal.TProgressbar",background=COLORS["accent"],troughcolor=COLORS["panel"])
