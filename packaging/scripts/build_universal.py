#!/usr/bin/env python3
import os, sys, subprocess, platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "Semantorium.spec"
PYTHON = sys.executable

def build(target):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    if target == "lite":
        env["SEMANTORIUM_LITE"] = "1"
        env["LEXIMA_LITE"] = "1"
    else:
        env.pop("SEMANTORIUM_LITE", None)
        env.pop("LEXIMA_LITE", None)
    cmd = [PYTHON, "-m", "PyInstaller", str(SPEC), "--noconfirm"]
    print(f"Building {target} on {platform.system()}...")
    res = subprocess.run(cmd, env=env, cwd=str(ROOT))
    return res.returncode == 0

if __name__ == "__main__":
    targets = sys.argv[1:] or ["full"]
    for t in targets:
        if not build(t):
            sys.exit(1)
