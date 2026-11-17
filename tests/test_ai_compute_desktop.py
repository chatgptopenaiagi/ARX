import time
from arx.desktop.app import ARXDesktopApp


def test_ai_tab_selects_evidence_per_environment():
    app=ARXDesktopApp();app.withdraw()
    try:
        panel=app.ai_compute
        environments=[{"id":"gpu","executable":"gpu-python.exe","scope":"virtual-environment","packages":[]}, {"id":"other","executable":"other-python.exe","scope":"system","packages":[]}]
        panel.accept_inventory({"environments":environments,"verification":[{"environment_id":"gpu","health":"VERIFIED","tests":[{"name":"gpu_matrix","outcome":"PASS"}],"torch":{"cuda_runtime":"13.4","version":"2.15.0+cu134","cudnn_version":92600}}],"preservation":[],"hardware":{}})
        assert "AI Compute" in [app.tabs.tab(t,"text") for t in app.tabs.tabs()]
        assert "GPU Matrix Test: PASS" in panel.details.get("1.0","end")
        panel.selector.current(1);panel.render()
        assert "GPU Matrix Test: NOT TESTED" in panel.details.get("1.0","end")
        assert "VERIFIED" not in panel.details.get("1.0","end")
    finally:app.destroy()


def test_ai_manual_verify_runs_off_ui_thread(monkeypatch):
    app=ARXDesktopApp();app.withdraw()
    try:
        panel=app.ai_compute;env={"id":"one","executable":"python.exe","packages":[],"scope":"test"}
        panel.accept_inventory({"environments":[env],"verification":[],"preservation":[],"hardware":{}})
        def slow_verify(chosen,benchmark=False):
            time.sleep(.2)
            return {"environment_id":chosen["id"],"health":"PARTIAL","tests":[{"name":"gpu_matrix","outcome":"FAIL","error":"GPU unavailable"}]}
        monkeypatch.setattr("arx.desktop.ai_compute.verify",slow_verify)
        panel.run_verification();assert app._started is not None
        ticks=0;deadline=time.monotonic()+3
        while app._started is not None and time.monotonic()<deadline:
            app.update();ticks+=1;time.sleep(.01)
        assert ticks>5 and app._started is None
        assert "GPU Matrix Test: FAIL" in panel.details.get("1.0","end")
        assert "VERIFIED" not in panel.details.get("1.0","end")
    finally:app.destroy()
