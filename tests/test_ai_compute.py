import json
import sys
import zipfile
from pathlib import Path

import pytest

from arx.ai_compute import engine
from arx.ai_compute.__main__ import configure, run_cli
from arx.desktop.ai_compute import cudnn_display, environment_summary


def test_probe_ignores_inherited_pythonhome_and_path(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTHONHOME", str(tmp_path/"invalid-home"))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path/"invalid-path"))
    result = engine.probe(sys.executable, timeout=20)
    assert result["status"] == "DETECTED"
    assert result["tests"][0]["outcome"] == "PASS"
    assert str(tmp_path/"invalid-path") not in result["python"]["site_paths"]


def test_walk_budget_and_site_packages_exclusion(tmp_path):
    (tmp_path/"site-packages").mkdir()
    (tmp_path/"site-packages"/"python.exe").write_bytes(b"not an interpreter")
    for i in range(10): (tmp_path/f"item{i}").write_text("x")
    assert len(list(engine.bounded_walk([tmp_path], max_entries=3))) == 3
    assert not any(p.name=="python.exe" for p in engine.bounded_walk([tmp_path]))


def test_conda_package_cache_is_not_an_environment(tmp_path):
    cache=tmp_path/"pkgs/python-package";cache.mkdir(parents=True)
    (cache/"python.exe").write_bytes(b"unusable package-cache runtime")
    env=tmp_path/"envs/work";env.mkdir(parents=True)
    (env/"python.exe").write_bytes(b"environment runtime")
    paths=list(engine.bounded_walk([tmp_path]))
    assert env/"python.exe" in paths and cache/"python.exe" not in paths


def test_library_version_is_not_cudnn_functional_verification(monkeypatch):
    names = ["python_core_imports", "torch_import", "torchvision_import", "torchaudio_import", "numpy_interoperability", "gpu_tensor", "gpu_matrix", "cuda_synchronize"]
    data = {"torch":{"cudnn_version":92600}, "tests":[{"name":n,"outcome":"PASS"} for n in names]}
    monkeypatch.setattr(engine, "probe", lambda *a,**kw:data)
    result = engine.verify({"id":"first", "executable":"python.exe"})
    assert result["health"] == "PARTIAL"
    data["tests"].append({"name":"cudnn_convolution", "outcome":"FAIL"})
    assert engine.verify({"id":"first", "executable":"python.exe"})["health"] == "PARTIAL"


def test_copy_verifies_hash_and_refuses_existing_destination(tmp_path):
    source=tmp_path/"source"; dest=tmp_path/"copy"; source.write_bytes(b"precious package")
    record=engine.copy_verified(source,dest)
    assert record["verified"] and record["sha256"]==engine.sha256(source)
    assert source.read_bytes()==b"precious package"
    with pytest.raises(FileExistsError): engine.copy_verified(source,dest)


def test_copy_corruption_never_reports_preserved(monkeypatch,tmp_path):
    source=tmp_path/"source"; source.write_bytes(b"abc")
    monkeypatch.setattr(engine,"sha256",lambda _p:"wrong-hash")
    with pytest.raises(OSError,match="mismatch"): engine.copy_verified(source,tmp_path/"copy")
    assert source.read_bytes()==b"abc"


def fake_inventory(tmp_path):
    prefix=tmp_path/"python"; root=prefix/"Lib/site-packages";root.mkdir(parents=True)
    executable=prefix/"python.exe";executable.write_bytes(b"runtime")
    package=root/"torch.py";package.write_bytes(b"package content")
    return {"status":"DETECTED","python":{"prefix":str(prefix)},"packages":[{"name":"torch","version":"2.15.0+cu134","root":str(root),"requires":[],"files":[str(package)]}]}, {"id":"env","executable":str(executable)}


def test_preservation_rejects_record_escape_and_keeps_sources(monkeypatch,tmp_path):
    data,env=fake_inventory(tmp_path)
    outside=tmp_path/"private.txt";outside.write_text("not part of environment")
    data["packages"][0]["files"].append(str(outside))
    monkeypatch.setattr(engine,"probe",lambda *a,**kw:data)
    monkeypatch.setattr(engine,"cached_wheels",lambda _p:[])
    result=engine.preserve(env,tmp_path/"snapshots")
    assert result["status"]=="PARTIAL"
    assert not any(f["source"]==str(outside) for f in result["files"])
    assert all(Path(f["source"]).is_file() for f in result["files"])
    assert (Path(result["destination"])/"RESTORE.md").is_file()
    assert json.loads((Path(result["destination"])/"PACKAGE-MANIFEST.json").read_text())[0]["version"]=="2.15.0+cu134"


def test_preservation_never_copies_into_environment(monkeypatch,tmp_path):
    data,env=fake_inventory(tmp_path)
    monkeypatch.setattr(engine,"probe",lambda *a,**kw:data)
    with pytest.raises(ValueError,match="outside"):engine.preserve(env,Path(data["python"]["prefix"])/"backup")


def test_preservation_allows_only_declared_external_scripts_root(monkeypatch,tmp_path):
    data,env=fake_inventory(tmp_path)
    scripts=tmp_path/"relocated-Scripts";scripts.mkdir()
    console=scripts/"torchrun.exe";console.write_bytes(b"launcher")
    data["python"]["scripts_path"]=str(scripts)
    data["packages"][0]["files"].append(str(console))
    monkeypatch.setattr(engine,"probe",lambda *a,**kw:data)
    monkeypatch.setattr(engine,"cached_wheels",lambda _p:[])
    result=engine.preserve(env,tmp_path/"snapshots")
    assert result["status"]=="PRESERVED"
    assert any(f["source"]==str(console) and f["verified"] for f in result["files"])
    assert console.read_bytes()==b"launcher"


def test_missing_package_file_inventory_prevents_complete_preservation(monkeypatch,tmp_path):
    data,env=fake_inventory(tmp_path)
    data["packages"][0].update(files=[],files_unavailable=True)
    monkeypatch.setattr(engine,"probe",lambda *a,**kw:data)
    monkeypatch.setattr(engine,"cached_wheels",lambda _p:[])
    result=engine.preserve(env,tmp_path/"snapshots")
    assert result["status"]=="PARTIAL" and result["issues"]


def test_cancelled_copy_has_manifest_and_does_not_delete_sources(monkeypatch,tmp_path):
    data,env=fake_inventory(tmp_path)
    monkeypatch.setattr(engine,"probe",lambda *a,**kw:data)
    monkeypatch.setattr(engine,"cached_wheels",lambda _p:[])
    result=engine.preserve(env,tmp_path/"snapshots",cancel=lambda:True)
    assert result["status"]=="FAILED"
    assert Path(env["executable"]).is_file()
    assert (Path(result["destination"])/"ARX-AI-PRESERVATION-MANIFEST.json").is_file()


def test_pip_http_cache_wheel_is_identified_without_extracting(monkeypatch,tmp_path):
    cache=tmp_path/"pip/Cache/http-v2/a";cache.mkdir(parents=True)
    with zipfile.ZipFile(cache/"entry.body","w") as wheel:
        wheel.writestr("torch-2.15.0.dist-info/METADATA","Name: torch\nVersion: 2.15.0+cu134\n")
        wheel.writestr("torch-2.15.0.dist-info/WHEEL","Wheel-Version: 1.0\nTag: cp315-cp315-win_amd64\n")
        wheel.writestr("../../escape.txt","must not be extracted")
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    result=engine.cached_wheels([{"name":"torch","version":"2.15.0+cu134"}])
    assert result[0]["filename"]=="torch-2.15.0+cu134-cp315-cp315-win_amd64.whl"
    assert not (tmp_path/"escape.txt").exists()
    assert engine.cached_wheels([{"name":"torch","version":"2.15.0+cu132"}])==[]


def test_gui_summary_never_borrows_other_environment_success():
    env={"executable":"other-python.exe","packages":[{"name":"torch","version":"cpu-only"}]}
    text=environment_summary(env)
    assert "GPU Matrix Test: NOT TESTED" in text and "VERIFIED" not in text
    assert "cpu-only" in text
    assert cudnn_display(92600)=="9.26.0 (code 92600)"


def test_cli_preservation_requires_unambiguous_interpreter():
    import argparse
    args=configure(argparse.ArgumentParser()).parse_args(["--preserve"])
    with pytest.raises(ValueError,match="exactly one"):run_cli(args)


def test_evidence_redacts_url_credentials_without_losing_host():
    assert engine.redact_text("https://secret-token@example.invalid/package") == "https://[REDACTED]@example.invalid/package"
    assert engine.redact_text("https://user:password@example.invalid/package") == "https://[REDACTED]@example.invalid/package"
