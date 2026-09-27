"""Run a child process inside a Windows Job Object with a hard commit-memory cap.

The cap turns an over-large tensor allocation into an in-process failure
(MemoryError / torch RuntimeError) instead of letting Windows page the whole
machine to death.  Usage: run_with_mem_cap.py <cap_gb> <command...>
"""
from __future__ import annotations

import subprocess
import sys

import win32api
import win32con
import win32job


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: run_with_mem_cap.py <cap_gb> <command...>", file=sys.stderr)
        return 2
    cap_gb = float(sys.argv[1])
    command = sys.argv[2:]
    job = win32job.CreateJobObject(None, "")
    info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    info["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
    info["ProcessMemoryLimit"] = int(cap_gb * 1024 ** 3)
    win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
    proc = subprocess.Popen(command)
    handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, proc.pid)
    win32job.AssignProcessToJobObject(job, handle)
    win32api.CloseHandle(handle)
    code = proc.wait()
    print(f"[mem-cap] child exited with {code} (cap={cap_gb} GB)", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
