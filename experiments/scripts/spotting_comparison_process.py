"""Windows process liveness/memory and exclusive recoverable run locks."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import uuid


def utc():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def exclusive_lock(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    # Keep the lock inode/name permanently. OS releases its byte lock after a crash.
    with path.open('a+b') as handle:
        handle.seek(0,2)
        if handle.tell()==0: handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if sys.platform=='win32':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc: raise ValueError('another run is active: '+str(path)) from exc
        owner=path.with_name(path.name+'.owner.json')
        if owner.exists(): owner.rename(owner.with_name(owner.name+'.stale-'+uuid.uuid4().hex))
        owner.write_text(json.dumps(dict(pid=os.getpid(),created_at_utc=utc())),encoding='utf-8')
        try: yield
        finally:
            owner.unlink();handle.seek(0)
            if sys.platform=='win32': msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def memory():
    if sys.platform!='win32': return dict(rss_bytes=None,process_peak_rss_bytes_to_date=None)
    size=ctypes.c_size_t
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(k,size) for k in
            ('peak','working','quota_peak_paged','quota_paged','quota_peak_nonpaged','quota_nonpaged','pagefile','peak_pagefile')]
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    kernel=ctypes.windll.kernel32;kernel.GetCurrentProcess.restype=wintypes.HANDLE
    query=ctypes.windll.psapi.GetProcessMemoryInfo
    query.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    if not query(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
        return dict(rss_bytes=None,process_peak_rss_bytes_to_date=None)
    return dict(rss_bytes=counters.working,process_peak_rss_bytes_to_date=counters.peak)
