"""AI Compute tab: UI projects evidence; worker operations never touch Tk."""
import json
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from arx.ai_compute.engine import DEFAULT_ROOT, discover, preserve, verify, write_reports
from .widgets import ToolTip, set_text


def cudnn_display(code):
    if not isinstance(code, int): return "Unknown"
    scale = 10000 if code >= 90000 else 1000
    return f"{code//scale}.{(code%scale)//100}.{code%100} (code {code})"


def environment_summary(environment, result=None):
    result = result or {}
    packages = {p["name"].lower():p["version"] for p in environment.get("packages", [])}
    torch = result.get("torch", {})
    outcomes = {t["name"]:t["outcome"] for t in result.get("tests", [])}
    return "\n".join([
        "ARX AI COMPUTE", "",
        "Python: "+environment.get("python", {}).get("version", "Unknown"),
        "Interpreter: "+environment.get("executable", "Not selected"),
        "Scope: "+environment.get("scope", "Unknown"),
        "GPU: "+result.get("gpu", {}).get("name", "Untested"),
        "CUDA runtime (PyTorch): "+str(torch.get("cuda_runtime") or "Untested / unavailable"),
        "PyTorch: "+str(torch.get("version") or packages.get("torch", "Unavailable in this context")),
        "cuDNN: "+cudnn_display(torch.get("cudnn_version")), "",
        "GPU Tensor Test: "+outcomes.get("gpu_tensor", "NOT TESTED"),
        "GPU Matrix Test: "+outcomes.get("gpu_matrix", "NOT TESTED"),
        "cuDNN Convolution: "+outcomes.get("cudnn_convolution", "NOT TESTED"),
        "TorchVision Import: "+outcomes.get("torchvision_import", "NOT TESTED"),
        "TorchAudio Import: "+outcomes.get("torchaudio_import", "NOT TESTED"),
        "Environment Health: "+result.get("health", "DETECTED — verification not run"),
        "Evidence time: "+str(result.get("generated_at") or environment.get("generated_at", "Unknown")),
    ])


class AIComputePanel(ttk.Frame):
    def __init__(self, parent, host):
        super().__init__(parent, padding=12)
        self.host = host
        self.report = {"environments":[], "verification":[], "preservation":[], "hardware":{}, "search_notes":[]}
        self.destination = tk.StringVar(value=str(DEFAULT_ROOT))
        self.selection = tk.StringVar()
        self._choices = []
        controls = ttk.Frame(self); controls.pack(fill="x")
        for label, command in (("Discover environments", self.scan), ("Add search folder…", self.scan_folder), ("Load saved evidence…", self.load_dialog)):
            self.button(controls, label, command)
        ttk.Label(self, text="Select a Python environment. Verification runs short tests in a separate process; normal machine scans remain unchanged.", wraplength=1000).pack(anchor="w", pady=8)
        self.selector = ttk.Combobox(self, textvariable=self.selection, state="readonly")
        self.selector.pack(fill="x"); self.selector.bind("<<ComboboxSelected>>", lambda _event:self.render())
        operations = ttk.Frame(self); operations.pack(fill="x", pady=8)
        for label, command in (("Verify selected", self.run_verification), ("Benchmark selected", lambda:self.run_verification(True)), ("Preserve selected", self.run_preservation), ("Export reports…", self.export)):
            self.button(operations, label, command)
        location = ttk.Frame(self); location.pack(fill="x")
        ttk.Label(location, text="Preservation destination:").pack(side="left")
        ttk.Label(location, textvariable=self.destination).pack(side="left", padx=8)
        self.button(location, "Choose destination…", self.choose_destination)
        self.details = host._text_panel(self)
        self.details.pack(fill="both", expand=True, pady=(8,0))
        self.render()

    def button(self, parent, label, command):
        button = ttk.Button(parent, text=label, command=command)
        button.pack(side="left", padx=(0,8))
        self.host._action_buttons.append(button)
        descriptions = {
            "Discover environments":"Inspect known interpreter and environment locations with bounded searches.",
            "Add search folder…":"Include a chosen folder in bounded environment discovery.",
            "Load saved evidence…":"View timestamped reports; use Verify selected to refresh the evidence.",
            "Verify selected":"Run bounded import, CUDA, NumPy and explicit cuDNN tests in the selected Python.",
            "Benchmark selected":"Run verification and six short synchronized microbenchmarks.",
            "Preserve selected":"Copy package files and matching cached wheels to a unique snapshot; verify SHA-256.",
            "Export reports…":"Write the seven AI Compute JSON/Markdown reports to a chosen directory.",
            "Choose destination…":"Choose the parent directory for future preservation snapshots.",
        }
        self.host._tooltips.append(ToolTip(button, descriptions[label]))
        return button

    def selected(self):
        index = self.selector.current()
        return self.report["environments"][index] if 0 <= index < len(self.report["environments"]) else None

    def accept_inventory(self, report):
        self.report = report
        self._choices = [f"{e.get('python',{}).get('version','Unknown')} | {e.get('scope','Unknown')} | {e['executable']}" for e in report["environments"]]
        self.selector.configure(values=self._choices)
        if self._choices:
            preferred = next((i for i,e in enumerate(report["environments"]) if any(p["name"].lower()=="torch" for p in e.get("packages",[]))), 0)
            self.selector.current(preferred)
        self.render()

    def scan(self, roots=()):
        self.host._run("AI environment discovery", lambda:discover(roots), self.accept_inventory, completed_status="AI environment discovery complete")

    def scan_folder(self):
        folder = filedialog.askdirectory(parent=self, title="Additional environment search root")
        if folder: self.scan([folder])

    def choose_destination(self):
        folder = filedialog.askdirectory(parent=self, title="Preservation parent directory")
        if folder: self.destination.set(folder)

    def run_verification(self, benchmark=False):
        env = self.selected()
        if env is None: self.host._set_status("Discover and select an environment first."); return
        def complete(result):
            self.report["verification"] = [r for r in self.report["verification"] if r["environment_id"] != env["id"]]+[result]
            self.render()
        self.host._run("AI benchmark" if benchmark else "AI functional verification", lambda:verify(env, benchmark=benchmark), complete, completed_status="AI tests finished — inspect individual outcomes")

    def run_preservation(self):
        env = self.selected()
        if env is None: self.host._set_status("Discover and select an environment first."); return
        destination = self.destination.get()
        def complete(result):
            self.report["preservation"].append(result)
            self.render()
        def cancelled():
            token = self.host._operation_cancel
            return bool(token and token.is_set()) or self.host._closed
        self.host._run("AI package preservation", lambda:preserve(env, destination, cancel=cancelled), complete, completed_status="Preservation finished — inspect hashes and status")

    def export(self):
        folder = filedialog.askdirectory(parent=self, title="Save the seven AI Compute reports")
        if folder:
            self.host._run("AI evidence export", lambda:write_reports(self.report,folder), lambda _p:None, completed_status="AI reports exported")

    def load_dialog(self):
        path = filedialog.askopenfilename(parent=self, title="Load saved AI inventory", filetypes=[("AI inventory", "ARX-AI-ENVIRONMENT-INVENTORY.json"), ("JSON", "*.json")])
        if path:
            self.host._run("Load AI evidence", lambda:self.read_saved(path), self.accept_inventory, completed_status="Saved evidence loaded; run verification to refresh")

    @staticmethod
    def read_saved(path):
        path = Path(path)
        def read(file, fallback):
            if not file.exists(): return fallback
            if file.stat().st_size > 32*1024*1024: raise ValueError("Evidence file exceeds 32 MiB")
            return json.loads(file.read_text(encoding="utf-8"))
        report = read(path,{})
        if not isinstance(report.get("environments"), list): raise ValueError("Not an AI environment inventory")
        report["verification"] = read(path.parent/"ARX-GPU-FUNCTIONAL-TESTS.json", [])
        report["preservation"] = read(path.parent/"ARX-AI-PRESERVATION-MANIFEST.json", [])
        report["saved_evidence"] = True
        return report

    def render(self):
        env = self.selected()
        if env is None:
            set_text(self.details, "ARX AI COMPUTE\n\nNo environment selected. Discover existing installations or load saved evidence. No tests have run.")
            return
        result = next((r for r in self.report["verification"] if r["environment_id"]==env["id"]), None)
        text = environment_summary(env,result)
        if self.report.get("saved_evidence"): text += "\n\nSaved evidence — use Verify selected for a fresh test."
        if result:
            text += "\n\nIndividual tests\n"+"\n".join(f"{t['name']}: {t['outcome']} {t.get('error',t.get('reason',''))}" for t in result.get("tests",[]))
            text += "\n\nBenchmarks\n"+"\n".join(f"{b['name']}: {b['outcome']} | {b.get('mean_ms','—')} ms | {b.get('device','—')} | peak GPU allocation {b.get('peak_allocated_gpu_bytes','—')} bytes" for b in result.get("benchmarks",[]))
        copies = [p for p in self.report["preservation"] if p["environment_id"]==env["id"]]
        text += "\n\nPreservation\n"+("\n".join(f"{p['status']}: {p['destination']}\n{len(p.get('files',[]))} copied files; {len(p.get('wheels',[]))} cached wheels. Restore not tested." for p in copies) or "Not yet preserved")
        set_text(self.details,text)


def ai_ui_smoke_test(interpreter, inventory, output, timeout=360):
    """Exercise the actual tab; inventory '-' runs fresh GUI discovery first."""
    from .app import ARXDesktopApp
    from arx.ai_compute.engine import save
    app=ARXDesktopApp();app.withdraw()
    try:
        panel=app.ai_compute
        deadline=time.monotonic()+timeout;ticks=0
        def wait_for_worker():
            nonlocal ticks
            while app._started is not None:
                app.update();ticks+=1
                if time.monotonic()>deadline: raise TimeoutError("AI GUI verification deadline exceeded")
                time.sleep(.02)
            app.update()
        if inventory == "-":
            panel.scan()
            wait_for_worker()
        else:
            panel.accept_inventory(panel.read_saved(inventory))
        index=next(i for i,e in enumerate(panel.report["environments"]) if Path(e["executable"]).resolve()==Path(interpreter).resolve() and not e.get("user_site"))
        panel.selector.current(index);app.tabs.select(panel);panel.render()
        panel.run_verification(True)
        wait_for_worker()
        env=panel.selected()
        result=next(r for r in panel.report["verification"] if r["environment_id"]==env["id"])
        text=panel.details.get("1.0","end")
        from arx import RELEASE_NAME, __version__
        record={"app_version":__version__,"release_name":RELEASE_NAME,"window_title":app.title(),
                "fresh_discovery":inventory=="-","environments":panel.report["environments"],
                "health":result["health"],"selected_interpreter":env["executable"],"summary":text,"ui_events_processed":ticks,
                "tabs":[app.tabs.tab(t,"text") for t in app.tabs.tabs()],"display_matches_result":result["health"] in text and result.get("torch",{}).get("version", "UNAVAILABLE") in text,
                "verification":result,"existing_ui_controls_present":hasattr(app,"machine_tree") and hasattr(app,"project_tree") and hasattr(app,"check_tree")}
        save(output,record)
        return record
    finally:app.destroy()
