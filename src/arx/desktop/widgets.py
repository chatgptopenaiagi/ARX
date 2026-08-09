import tkinter as tk
from tkinter import ttk
from .theme import COLORS,status_color

class StatusBadge(tk.Label):
    def __init__(self,parent,status="unknown",**kwargs):
        super().__init__(parent,font=("Segoe UI Semibold",9),padx=9,pady=4,**kwargs);self.set(status)
    def set(self,status):
        value=str(getattr(status,"value",status) or "unknown").upper();self.configure(text=value,bg=status_color(value),fg="#071018" if value not in {"BLOCKED","MISSING"} else "white")

def tree(parent,columns,widths=None):
    view=ttk.Treeview(parent,columns=columns,show="headings",selectmode="browse")
    for index,column in enumerate(columns):view.heading(column,text=column.replace("_"," ").title());view.column(column,width=(widths or {}).get(column,150),anchor="w")
    scroll=ttk.Scrollbar(parent,orient="vertical",command=view.yview);view.configure(yscrollcommand=scroll.set);view.pack(side="left",fill="both",expand=True);scroll.pack(side="right",fill="y")
    for status,color in ((s,status_color(s)) for s in ("ready","partial","missing","blocked","unknown","not_applicable")):view.tag_configure(status,foreground=color)
    return view

def text_panel(parent):
    widget=tk.Text(parent,bg=COLORS["panel"],fg=COLORS["text"],insertbackground=COLORS["text"],selectbackground=COLORS["selected"],relief="flat",wrap="word",font=("Consolas",10),padx=12,pady=12)
    widget.configure(state="disabled");return widget

def set_text(widget,value):
    widget.configure(state="normal");widget.delete("1.0","end");widget.insert("1.0",value);widget.configure(state="disabled")
