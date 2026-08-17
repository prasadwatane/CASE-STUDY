#!/usr/bin/env python3
"""Rebuild a wiped GPU container in one command, reusing whatever survived.

The college JupyterHub recycles containers between sessions. Everything under
/home/jovyan is discarded except a persistent volume — in this deployment,
/home/jovyan/vault. Three times now that has cost a full rebuild: a ten-minute
virtual environment and a fifteen-gigabyte model download, neither of which has
anything to do with the audit.

This script makes the rebuild idempotent and, where the filesystem allows,
nearly free. It finds a writable persistent directory, keeps the venv and the
HuggingFace cache there, and reuses both on the next boot. If nothing
persistent is writable it degrades to the ephemeral path and says so, rather
than failing — the run still works, it just costs the download again.

Stdlib only, on purpose. It has to run before there is a virtual environment.

Run it from a bare container with:

    !git clone https://github.com/prasadwatane/CASE-STUDY.git /home/jovyan/work 2>/dev/null; \
     python3 /home/jovyan/work/scripts/bootstrap_server.py

Both halves are safe to repeat: the clone is skipped if the directory exists,
and every step below checks before it acts.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

REPO_URL = "https://github.com/prasadwatane/CASE-STUDY.git"
WORK = "/home/jovyan/work"

# Ordered by preference. The first writable one wins, so a persistent volume is
# always chosen over the ephemeral home directory when it is available.
PERSIST_CANDIDATES = [
    "/home/jovyan/vault/grail-cache",
    "/home/jovyan/vault/CASE-STUDY/.grail-cache",
    "/home/jovyan/models/grail-cache",
    "/home/jovyan/work/.grail-cache",          # ephemeral fallback
]


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def writable(path: str) -> bool:
    """Can we actually create files here? Asking the filesystem, not os.access.

    os.access lies under some container mounts, and a false positive here costs
    a ten-minute venv build that fails at the end.
    """
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".probe")
        with open(probe, "w") as fh:
            fh.write("x")
        os.remove(probe)
        return True
    except OSError:
        return False


def pick_persistent() -> tuple[str, bool]:
    for path in PERSIST_CANDIDATES:
        if writable(path):
            return path, not path.startswith(WORK)
    return os.path.join(WORK, ".grail-cache"), False


def have_gpu() -> str:
    import glob
    devs = glob.glob("/dev/nvidia*")
    return f"{len(devs)} device nodes" if devs else "NONE VISIBLE"


def main() -> int:
    print("=" * 68)
    print("GRAIL server bootstrap")
    print("=" * 68)

    persist, is_persistent = pick_persistent()
    hf_home = os.path.join(persist, "hf")
    venv = os.path.join(persist, "venv") if is_persistent else os.path.join(WORK, ".venv")
    py = os.path.join(venv, "bin", "python")

    print(f"  cache root : {persist}")
    print(f"               {'PERSISTENT — survives a recycle' if is_persistent else 'EPHEMERAL — will be lost; venv and weights re-fetch each session'}")
    print(f"  venv       : {venv}")
    print(f"  HF_HOME    : {hf_home}")
    print(f"  gpu        : {have_gpu()}")

    # --- repo ---------------------------------------------------------------
    if os.path.isdir(os.path.join(WORK, ".git")):
        r = run(["git", "-C", WORK, "pull", "--ff-only"])
        print(f"  repo       : pulled — {(r.stdout or r.stderr).strip().splitlines()[-1][:60]}")
    else:
        os.makedirs(os.path.dirname(WORK), exist_ok=True)
        r = run(["git", "clone", REPO_URL, WORK])
        if r.returncode:
            print("  repo       : CLONE FAILED\n" + r.stderr[-800:])
            return 1
        print("  repo       : cloned")
    head = run(["git", "-C", WORK, "log", "--oneline", "-1"]).stdout.strip()
    print(f"               {head}")

    # --- venv ---------------------------------------------------------------
    os.makedirs(hf_home, exist_ok=True)
    if os.path.isfile(py):
        print("  venv       : reused (already present)")
    else:
        print("  venv       : building — vLLM is a large install, allow ~10 minutes")
        steps = [
            [sys.executable, "-m", "venv", venv],
            [os.path.join(venv, "bin", "pip"), "install", "-q", "-U",
             "pip", "setuptools", "wheel"],
            # vLLM pins its own torch. Installing torch separately is what broke
            # this environment before; do not add it here.
            [os.path.join(venv, "bin", "pip"), "install", "-q", "vllm", "pytest"],
        ]
        for step in steps:
            r = run(step)
            if r.returncode:
                print(f"               FAILED: {' '.join(step[:3])}\n" + (r.stdout + r.stderr)[-1200:])
                return 1
            print(f"               ok  {os.path.basename(step[0])} {step[1] if len(step) > 1 else ''}")

    # --- verify -------------------------------------------------------------
    r = run([py, "-c",
             "import torch,vllm;print(f'torch {torch.__version__} cuda '"
             "f'{torch.cuda.is_available()} gpus {torch.cuda.device_count()} vllm {vllm.__version__}')"])
    print(f"  stack      : {(r.stdout or r.stderr).strip()[:90]}")

    env = dict(os.environ, HF_HOME=hf_home)
    r = run([py, "-m", "pytest", "-q"], cwd=WORK, env=env)
    tail = [l for l in (r.stdout or "").splitlines() if l.strip()]
    print(f"  tests      : {tail[-1][:70] if tail else 'no output'}")

    cached = os.path.isdir(os.path.join(hf_home, "hub"))
    size = shutil.disk_usage(persist) if os.path.isdir(persist) else None

    print("-" * 68)
    print("Next, paste these two cells:\n")
    print("  import os")
    print(f"  os.environ['HF_HOME'] = '{hf_home}'")
    print(f"  !cd {WORK} && HF_HOME={hf_home} {py} scripts/generate_probes.py finance --force\n")
    print(f"  !cd {WORK} && HF_HOME={hf_home} {py} scripts/run_probes.py finance \\")
    print("        --local Qwen/Qwen2.5-7B-Instruct --eager")
    print()
    print(f"  model weights {'already cached — no download this run' if cached else 'not cached yet — expect a ~15 GB download once'}")
    if size:
        print(f"  free space on the cache volume: {size.free / 2**30:.0f} GiB")
    if not is_persistent:
        print()
        print("  WARNING: no persistent writable directory was found, so the venv and")
        print("  the model cache will be lost on the next recycle. If the vault volume")
        print("  should be writable, that is worth raising with whoever administers it —")
        print("  it is the difference between a 20-second restart and a 15-minute one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
