import json,queue,threading,time,traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog,messagebox,ttk

from arx import __version__
from arx.core.models import serialize
from .controllers import DesktopController
from .theme import COLORS,apply_theme
from .widgets import StatusBadge,set_text,text_panel,tree

class ARXDesktopApp(tk.Tk):
    def __init__(self,controller=None):
        super().__init__();self.controller=controller or DesktopController();self._events=queue.Queue();self._started=None;self._selected_target=None
        self.title(f"ARX {__version__} — Project-Aware Compatibility Intelligence");self.geometry("1280x820");self.minsize(1000,680);self._last_error_details=None;apply_theme(self)
        self._build();self.after(100,self._poll)

    def _build(self):
        header=ttk.Frame(self,padding=(22,16));header.pack(fill="x")
        title=ttk.Frame(header);title.pack(side="left");ttk.Label(title,text="ARX",style="Title.TLabel").pack(anchor="w");ttk.Label(title,text="Project-Aware Compatibility Intelligence",style="Subtitle.TLabel").pack(anchor="w")
        self.details_button=ttk.Button(header,text="Technical details…",command=self._show_last_error,state="disabled");self.details_button.pack(side="right",padx=(10,0));self.activity=ttk.Label(header,text="Ready — read-only scanning",style="Muted.TLabel");self.activity.pack(side="right",anchor="e")
        actions=ttk.Frame(self,padding=(22,0,22,14));actions.pack(fill="x")
        buttons=(("PROJECT PREFLIGHT",self._project_preflight,"Accent.TButton"),("QUICK MACHINE SCAN",lambda:self._scan(False),"TButton"),("DEEP MACHINE SCAN",lambda:self._scan(True),"TButton"),("INSPECT SOFTWARE",self._inspect_file,"TButton"),("COMPARE SOFTWARE",self._compare,"TButton"),("EXPORT REPORT",self._export,"TButton"),("AI REPORT",self._show_codex,"TButton"))
        for text,command,style in buttons:ttk.Button(actions,text=text,command=command,style=style).pack(side="left",padx=(0,8))
        ttk.Button(actions,text="Select directory…",command=self._inspect_directory).pack(side="right")
        self.progress=ttk.Progressbar(self,mode="indeterminate");self.progress.pack(fill="x",padx=22)
        self.tabs=ttk.Notebook(self);self.tabs.pack(fill="both",expand=True,padx=22,pady=(12,18))
        self._dashboard_tab();self._capability_tab();self._software_tab();self._compatibility_tab();self._evidence_tab();self._project_tab()

    def _dashboard_tab(self):
        tab=ttk.Frame(self.tabs,padding=12);self.tabs.add(tab,text="Machine DNA")
        summary=ttk.Frame(tab);summary.pack(fill="x",pady=(0,10));self.os_label=ttk.Label(summary,text="Run a machine scan to begin",font=("Segoe UI Semibold",13));self.os_label.pack(side="left");self.machine_badge=StatusBadge(summary,"unknown");self.machine_badge.pack(side="right")
        holder=ttk.Frame(tab);holder.pack(fill="both",expand=True);self.machine_tree=tree(holder,("component","status","version","path","health","evidence"),{"component":190,"status":90,"version":120,"path":300,"health":100,"evidence":260})
        self.machine_tree.bind("<<TreeviewSelect>>",self._machine_selected)

    def _capability_tab(self):
        tab=ttk.Frame(self.tabs,padding=12);self.tabs.add(tab,text="Capabilities")
        split=ttk.Panedwindow(tab,orient="horizontal");split.pack(fill="both",expand=True)
        left=ttk.Frame(split);right=ttk.Frame(split);split.add(left,weight=3);split.add(right,weight=2)
        self.cap_tree=tree(left,("capability","status","reason"),{"capability":230,"status":100,"reason":430});self.cap_tree.bind("<<TreeviewSelect>>",self._capability_selected)
        self.cap_detail=text_panel(right);self.cap_detail.pack(fill="both",expand=True,padx=(12,0))

    def _software_tab(self):
        tab=ttk.Frame(self.tabs,padding=12);self.tabs.add(tab,text="Software DNA")
        self.software_heading=ttk.Label(tab,text="Choose a supported file or directory",font=("Segoe UI Semibold",13));self.software_heading.pack(anchor="w",pady=(0,8))
        split=ttk.Panedwindow(tab,orient="horizontal");split.pack(fill="both",expand=True)
        left=ttk.Frame(split);right=ttk.Frame(split);split.add(left,weight=2);split.add(right,weight=3)
        self.software_detail=text_panel(left);self.software_detail.pack(fill="both",expand=True)
        self.import_tree=tree(right,("kind","value","classification"),{"kind":170,"value":430,"classification":110})

    def _compatibility_tab(self):
        tab=ttk.Frame(self.tabs,padding=12);self.tabs.add(tab,text="Compatibility")
        banner=ttk.Frame(tab);banner.pack(fill="x",pady=(0,10));ttk.Label(banner,text="OVERALL COMPATIBILITY",font=("Segoe UI Semibold",13)).pack(side="left");self.compat_badge=StatusBadge(banner,"unknown");self.compat_badge.pack(side="right")
        split=ttk.Panedwindow(tab,orient="vertical");split.pack(fill="both",expand=True)
        upper=ttk.Frame(split);lower=ttk.Frame(split);split.add(upper,weight=3);split.add(lower,weight=2)
        self.check_tree=tree(upper,("check","status","required","observed","reason"),{"check":180,"status":90,"required":150,"observed":150,"reason":430})
        self.compat_detail=text_panel(lower);self.compat_detail.pack(fill="both",expand=True,pady=(10,0))

    def _evidence_tab(self):
        tab=ttk.Frame(self.tabs,padding=12);self.tabs.add(tab,text="Evidence Inspector")
        split=ttk.Panedwindow(tab,orient="horizontal");split.pack(fill="both",expand=True)
        left=ttk.Frame(split);right=ttk.Frame(split);split.add(left,weight=3);split.add(right,weight=2)
        self.evidence_tree=tree(left,("classification","source","value","confidence"),{"classification":120,"source":300,"value":330,"confidence":100});self.evidence_tree.bind("<<TreeviewSelect>>",self._evidence_selected)
        self.evidence_detail=text_panel(right);self.evidence_detail.pack(fill="both",expand=True,padx=(12,0));self._evidence_items=[]

    def _project_tab(self):
        tab=ttk.Frame(self.tabs,padding=12);self.tabs.add(tab,text="Project Readiness")
        banner=ttk.Frame(tab);banner.pack(fill="x",pady=(0,10));self.project_heading=ttk.Label(banner,text="Choose a project directory",font=("Segoe UI Semibold",13));self.project_heading.pack(side="left");self.project_badge=StatusBadge(banner,"unknown");self.project_badge.pack(side="right")
        split=ttk.Panedwindow(tab,orient="vertical");split.pack(fill="both",expand=True)
        upper=ttk.Frame(split);lower=ttk.Frame(split);split.add(upper,weight=3);split.add(lower,weight=2)
        self.project_tree=tree(upper,("capability","relevance","satisfaction","resolved","preferred","reason"),{"capability":190,"relevance":110,"satisfaction":120,"resolved":130,"preferred":130,"reason":380})
        self.project_detail=text_panel(lower);self.project_detail.pack(fill="both",expand=True,pady=(10,0))

    def _run(self,label,work,complete):
        if self._started is not None:return
        self._started=time.monotonic();self.activity.configure(text=f"Scanning… {label}");self.progress.start(12)
        def worker():
            try:self._events.put(("ok",complete,work()))
            except Exception as exc:self._events.put(("error",label,(exc,traceback.format_exc())))
        threading.Thread(target=worker,daemon=True,name="arx-scan-worker").start()

    def _poll(self):
        if self._started is not None:self.activity.configure(text=f"Scanning… {time.monotonic()-self._started:.1f}s elapsed")
        try:
            while True:
                kind,callback,payload=self._events.get_nowait();self.progress.stop();self._started=None
                if kind=="ok":callback(payload);self.activity.configure(text="Ready — scan completed")
                else:self._show_error(callback,*payload)
        except queue.Empty:pass
        self.after(100,self._poll)

    def _scan(self,deep):self._run("deep machine scan" if deep else "quick machine scan",lambda:self.controller.scan(deep),lambda _:self._render_machine())
    def _project_preflight(self):
        target=filedialog.askdirectory(title="Choose a project for read-only preflight")
        if target:self._run("project preflight",lambda:self.controller.preflight(target),lambda _:self._render_project())
    def _inspect_file(self):
        target=filedialog.askopenfilename(title="Inspect software without running it",filetypes=(("Supported software","*.exe *.dll *.msi *.zip *.jar *.apk *.ps1 *.bat *.cmd *.py *.js"),("All files","*.*")))
        if target:self._start_inspect(target)
    def _inspect_directory(self):
        target=filedialog.askdirectory(title="Inspect an application directory")
        if target:self._start_inspect(target)
    def _start_inspect(self,target):self._selected_target=target;self._run("static software inspection",lambda:self.controller.inspect(target),lambda _:self._render_software())
    def _compare(self):
        if self.controller.software is None:
            target=filedialog.askopenfilename(title="Choose software to compare",filetypes=(("Supported software","*.exe *.dll *.msi *.zip *.jar *.apk"),("All files","*.*")))
            if not target:return
        else:target=None
        self._run("machine/software comparison",lambda:self.controller.compare(target),lambda _:self._render_all())
    def _show_codex(self):
        self._run("Codex report",self.controller.codex,lambda report:self._show_report_window("Codex / AI Report",json.dumps(report,indent=2)))
    def _export(self):
        selected=filedialog.asksaveasfilename(title="Export redacted ARX report",defaultextension=".json",filetypes=(("ARX JSON","*.json"),("Human-readable text","*.txt"),("Codex JSON","*.codex.json")))
        if not selected:return
        kind="codex" if selected.lower().endswith(".codex.json") else "text" if selected.lower().endswith(".txt") else "json"
        self._run("report export",lambda:self.controller.export(selected,kind),lambda path:messagebox.showinfo("ARX",f"Redacted report exported to:\n{path}"))

    def _render_all(self):self._render_machine();self._render_software();self._render_compatibility();self.tabs.select(3)
    def _clear(self,view):
        for item in view.get_children():view.delete(item)
    def _render_machine(self):
        machine=self.controller.machine or {};osinfo=machine.get("os",{});self.os_label.configure(text=f"{osinfo.get('edition') or osinfo.get('system','Windows')}  •  {osinfo.get('architecture','unknown')}  •  build {osinfo.get('build','unknown')}");self.machine_badge.set("ready")
        self._clear(self.machine_tree);tools=machine.get("tools",{})
        for label,key in (("Git","git"),("GitHub CLI","github_cli"),("Java / JDK","javac"),("Node.js","node"),("npm","npm"),(".NET","dotnet"),("Visual Studio / MSBuild","msbuild"),("CMake","cmake"),("Ninja","ninja"),("Android SDK / ADB","adb"),("Flutter","flutter"),("CUDA","cuda"),("Docker","docker"),("WSL","wsl")):
            record=tools.get(key);status="ready" if record and record.detected else "missing";evidence=(record.evidence[0].method if record and record.evidence else "PATH / known locations")
            self.machine_tree.insert("","end",iid=f"tool:{key}",values=(label,status.upper(),record.version if record else "",record.path if record else "",("Healthy" if record and record.detected else "Unavailable"),evidence),tags=(status,))
        for index,item in enumerate(machine.get("python_installations",[])):
            status="ready" if item.get("healthy") else "blocked";name=f"Python {item.get('version') or 'unknown'}";self.machine_tree.insert("","end",iid=f"python:{index}",values=(name,status.upper(),item.get("version"),item.get("path"),"Healthy" if item.get("healthy") else "Installed but unhealthy",item.get("health_probe")),tags=(status,))
        self._render_capabilities();self._render_evidence()
    def _render_capabilities(self):
        self._clear(self.cap_tree)
        for name,cap in self.controller.capabilities.items():self.cap_tree.insert("","end",iid=name,values=(name.replace("."," ").replace("_"," ").title(),cap.status.value.upper(),cap.reason),tags=(cap.status.value,))
    def _render_software(self):
        software=self.controller.software or {};self.software_heading.configure(text=software.get("filename","Software DNA"));pe=software.get("pe",{});sig=software.get("signature",{});application=software.get("application",{})
        detail=(f"FILE\n{software.get('absolute_path','')}\n\nType: {software.get('detected_file_type','unknown')}\nSize: {software.get('size','n/a')} bytes\nSHA-256: {software.get('sha256','n/a')}\n\nBINARY-LEVEL EVIDENCE\nArchitecture: {pe.get('architecture','unknown')}\nPE CLR header: {'Present' if pe.get('is_dotnet') else 'Not present'}\nSubsystem: {pe.get('subsystem','unknown')}\nExecution level: {pe.get('requested_execution_level') or 'not detected'}\nSignature: {sig.get('Status',sig.get('status','not inspected'))}\nPublisher: {sig.get('SignerSubject') or 'not detected'}\n\nAPPLICATION-LEVEL RUNTIME EVIDENCE\n.NET application: {application.get('dotnet','not detected')}\nEvidence: {', '.join(application.get('evidence',[])) or 'none'}")
        if software.get("inspection_error"):detail+=f"\n\nWARNING\n{software['inspection_error']}"
        set_text(self.software_detail,detail);self._clear(self.import_tree)
        for item in pe.get("imports",[]):self.import_tree.insert("","end",values=("Imported library",item,"OBSERVED"))
        for item in software.get("runtime_indicators",[]):self.import_tree.insert("","end",values=("Runtime",item.get("runtime"),str(item.get("status","inferred")).upper()))
        for item in software.get("requirements",[]):self.import_tree.insert("","end",values=("Requirement",f"{item.get('capability')} {item.get('version','')}",str(item.get("status","unknown")).upper()))
        self._render_evidence()
    def _render_compatibility(self):
        report=self.controller.compatibility or {};self.compat_badge.set(report.get("status","unknown"));self._clear(self.check_tree)
        for check in report.get("checks",[]):self.check_tree.insert("","end",values=(check.get("name"),str(check.get("status","unknown")).upper(),check.get("required",""),check.get("observed",""),check.get("reason","")),tags=(check.get("status","unknown"),))
        lines=[f"Confidence: {report.get('confidence','unknown')}",f"Score: {report.get('score','unknown')}","","PRIMARY BLOCKERS",*(report.get("blockers") or ["None"]),"","WARNINGS",*(report.get("warnings") or ["None"])]
        set_text(self.compat_detail,"\n".join(map(str,lines)))
    def _render_project(self):
        report=getattr(self.controller,"project_preflight",None)
        if report is None:return
        project=report.project;providers={item.id:item for item in report.providers};requirements={item.id:item for item in [*project.requirements,*project.optional_requirements]}
        self.project_heading.configure(text=f"{project.identity}  •  Python project readiness");self.project_badge.set(report.severity.severity);self._clear(self.project_tree)
        tags={"satisfied":"ready","unsatisfied":"blocked","partial":"partial","conflict":"blocked","ambiguous":"unknown","unknown":"unknown","optional_unavailable":"not_applicable","not_applicable":"not_applicable"}
        for evaluation in report.evaluations:
            requirement=requirements[evaluation.requirement_id];resolved=providers.get(evaluation.resolved_provider_id or "");preferred=providers.get(evaluation.preferred_provider_id or "")
            self.project_tree.insert("","end",values=(requirement.capability,evaluation.relevance.value.upper(),evaluation.satisfaction.value.upper(),resolved.version if resolved else "",preferred.version if preferred else "",evaluation.reason),tags=(tags[evaluation.satisfaction.value],))
        issues=[*(f"BLOCKER  {item}" for item in report.severity.blocker_ids),*(f"WARNING  {item}" for item in report.severity.warning_ids)]
        steps=[f"{index}. {step.action}" for index,step in enumerate(report.plan.steps,1)]
        primary=report.evaluation if report.evaluations else None
        detail=[f"PROJECT READINESS: {report.severity.severity.value.upper()}",f"Satisfaction: {primary.satisfaction.value.upper() if primary else 'UNKNOWN'}",f"Satisfied: {report.severity.satisfied_count}",f"Warnings: {report.severity.warning_count}",f"Blockers: {report.severity.blocker_count}","","What is wrong?",*(issues or ["Nothing blocking was found."]),"","Why?",report.severity.reason,"","Shortest trusted path to GREEN:",*(steps or ["0 actions — current evaluated state is GREEN."])]
        set_text(self.project_detail,"\n".join(map(str,detail)));self._render_evidence();self.tabs.select(5)
    def _render_evidence(self):
        self._clear(self.evidence_tree);self._evidence_items=[]
        def add(evidence,context):
            data=serialize(evidence);data["context"]=context;self._evidence_items.append(data);index=len(self._evidence_items)-1
            self.evidence_tree.insert("","end",iid=f"e:{index}",values=(str(data.get("kind","unknown")).upper(),data.get("source",""),str(data.get("value",""))[:180],data.get("confidence","")),tags=(str(data.get("kind","unknown")).lower(),))
        for item in (self.controller.machine or {}).get("evidence",[]):add(item,"Machine DNA")
        for record in (self.controller.machine or {}).get("tools",{}).values():
            for item in record.evidence:add(item,f"Tool: {record.name}")
        for runtime in (self.controller.machine or {}).get("python_installations",[]):
            for item in runtime.get("evidence",[]):add(item,f"Python: {runtime.get('path')}")
        for item in (self.controller.software or {}).get("evidence",[]):add(item,"Software DNA")
        project_report=getattr(self.controller,"project_preflight",None)
        if project_report:
            for item in project_report.project.evidence:add(item,"Project DNA")
            for provider in project_report.providers:
                for item in provider.evidence:add(item,f"Provider: {provider.id}")
            for item in project_report.resolution.evidence:add(item,"Execution resolution")
    def _machine_selected(self,event):
        selection=self.machine_tree.selection()
        if selection and selection[0].startswith("tool:"):
            key=selection[0].split(":",1)[1];record=(self.controller.machine or {}).get("tools",{}).get(key)
            if record:self._select_evidence_source(f"Tool: {record.name}")
    def _capability_selected(self,event):
        selection=self.cap_tree.selection()
        if not selection:return
        cap=self.controller.capabilities.get(selection[0]);deps=[]
        for dependency in cap.dependencies:
            child=self.controller.capabilities.get(dependency);deps.append(f"{dependency:<28} {child.status.value.upper() if child else 'UNKNOWN'} — {child.reason if child else 'No provider'}")
        blockers=[line for line in deps if " READY " not in f" {line} "]
        set_text(self.cap_detail,f"{cap.name}\n{cap.status.value.upper()}\n\nWHY\n{cap.reason}\n\nDEPENDENCIES\n"+("\n".join(deps) or "No dependencies")+"\n\nPRIMARY BLOCKERS\n"+("\n".join(blockers) or "None"))
    def _evidence_selected(self,event):
        selection=self.evidence_tree.selection()
        if selection:
            item=self._evidence_items[int(selection[0].split(":")[1])];set_text(self.evidence_detail,"\n".join((f"Context: {item.get('context')}",f"Classification: {str(item.get('kind','unknown')).upper()}",f"Source: {item.get('source')}",f"Value: {item.get('value')}",f"Detection method: {item.get('method')}",f"Confidence: {item.get('confidence')}",f"Notes: {item.get('note') or 'None'}")))
    def _select_evidence_source(self,context):
        for index,item in enumerate(self._evidence_items):
            if item.get("context")==context:self.tabs.select(4);self.evidence_tree.selection_set(f"e:{index}");self.evidence_tree.see(f"e:{index}");self._evidence_selected(None);break
    def _show_report_window(self,title,content):
        window=tk.Toplevel(self);window.title(title);window.geometry("900x650");window.configure(bg=COLORS["bg"]);view=text_panel(window);view.pack(fill="both",expand=True,padx=12,pady=12);set_text(view,content)
    def _show_error(self,operation,exc,details):
        self.progress.stop();self._started=None;self._last_error_details=details;self.details_button.configure(state="normal");self.activity.configure(text="Ready — operation failed");messagebox.showerror("ARX",f"{operation.capitalize()} could not be completed.\n\n{exc}\n\nNo software was installed or executed. Technical details are available from the main window.")
    def _show_last_error(self):
        if self._last_error_details:self._show_report_window("Technical details",self._last_error_details)

def run():
    app=ARXDesktopApp();app.mainloop()

def ui_smoke_test(target,output,timeout=180):
    """Exercise packaged Tk view/controller paths without human interaction."""
    app=ARXDesktopApp();app.withdraw();started=time.monotonic()
    def wait():
        while app._started is not None:
            app.update()
            if time.monotonic()-started>timeout:raise TimeoutError("ARX desktop UI smoke test timed out")
            time.sleep(.02)
        app.update()
    app._scan(False);wait();quick_rows=len(app.machine_tree.get_children())
    app._scan(True);wait();deep_rows=len(app.machine_tree.get_children())
    app._start_inspect(target);wait();software_title=app.software_heading.cget("text")
    app._compare();wait();checks=len(app.check_tree.get_children());compatibility=app.compat_badge.cget("text")
    app.controller.export(output,"json");result={"quick_machine_rows":quick_rows,"deep_machine_rows":deep_rows,"software_title":software_title,"compatibility":compatibility,"compatibility_checks":checks,"evidence_rows":len(app.evidence_tree.get_children()),"export_exists":Path(output).is_file()}
    app.destroy();return result

def project_ui_smoke_test(target,output,timeout=180):
    """Exercise the packaged Project Preflight UI and schema 0.2 export."""
    app=ARXDesktopApp();app.withdraw();started=time.monotonic()
    def wait():
        while app._started is not None:
            app.update()
            if time.monotonic()-started>timeout:raise TimeoutError("ARX project UI smoke test timed out")
            time.sleep(.02)
        app.update()
    try:
        app._run("project preflight",lambda:app.controller.preflight(target),lambda _:app._render_project());wait()
        report=app.controller.project_preflight
        providers={item.id:item for item in report.providers}
        evaluation=report.evaluation
        resolved=providers.get(evaluation.resolved_provider_id or "")
        preferred=providers.get(evaluation.preferred_provider_id or "")
        compatible=[providers[item].version for item in evaluation.compatible_provider_ids]
        app.controller.export(output,"codex")
        contract=json.loads(Path(output).read_text(encoding="utf-8"))
        return {
            "app_version":__version__,
            "window_title":app.title(),
            "tabs":[app.tabs.tab(item,"text") for item in app.tabs.tabs()],
            "project":report.project.identity,
            "requirement":report.project.primary_python_requirement.constraint if report.project.primary_python_requirement else None,
            "decision":app.project_badge.cget("text"),
            "relevance":evaluation.relevance.value.upper(),
            "satisfaction":evaluation.satisfaction.value.upper(),
            "resolved_version":resolved.version if resolved else None,
            "compatible_versions":compatible,
            "preferred_version":preferred.version if preferred else None,
            "finding_ids":[*report.severity.blocker_ids,*report.severity.warning_ids],
            "plan_step_ids":[item.id for item in report.plan.steps],
            "project_rows":len(app.project_tree.get_children()),
            "evidence_rows":len(app.evidence_tree.get_children()),
            "project_tab_selected":app.tabs.tab(app.tabs.select(),"text")=="Project Readiness",
            "ai_schema_version":contract.get("schema_version"),
            "ai_decision":contract.get("decision"),
            "export_exists":Path(output).is_file(),
        }
    finally:
        app.destroy()
