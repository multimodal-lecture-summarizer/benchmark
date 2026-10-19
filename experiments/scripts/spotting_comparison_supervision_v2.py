"""Bind worker heartbeat to attempt identity and terminate Windows launcher trees."""
import ctypes
import os
import subprocess
import time

from experiments.scripts.spotting_runtime_binding import require


def bound_progress(state, identity, attempt):
    return state if (state.get('run_id')==identity['run_id'] and
                     state.get('attempt_path')==str(attempt.resolve()) and
                     isinstance(state.get('pid'),int) and state['pid']>0) else {}


def process_alive(pid):
    if not pid: return False
    if os.name!='nt':
        try: os.kill(pid,0);return True
        except ProcessLookupError: return False
    native=ctypes.WinDLL('kernel32',use_last_error=True)
    native.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
    native.OpenProcess.restype=ctypes.c_void_p
    native.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    native.WaitForSingleObject.restype=ctypes.c_ulong
    native.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=native.OpenProcess(0x100000,False,pid)
    if not handle:
        require(ctypes.get_last_error()==87,'cannot establish worker liveness')
        return False
    try:
        result=native.WaitForSingleObject(handle,0)
        require(result in (0,258),'cannot inspect worker termination')
        return result==258
    finally: native.CloseHandle(handle)


def terminate_tree(process,state):
    worker=state.get('pid')
    if os.name=='nt':
        result=subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],
                              capture_output=True,text=True,errors='replace')
        evidence=dict(command=['taskkill','/PID',str(process.pid),'/T','/F'],
                      returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
        require(result.returncode==0 or (process.poll() is not None and not process_alive(worker)),
                'failed to terminate launcher/worker process tree')
    else:
        process.kill();evidence=dict(command='Popen.kill',returncode=0)
    process.wait(timeout=30)
    deadline=time.monotonic()+30
    while process_alive(worker) and time.monotonic()<deadline: time.sleep(.1)
    require(not process_alive(worker),'native worker remains alive after launcher termination')
    return dict(evidence,launcher_pid=process.pid,worker_pid=worker,worker_confirmed_terminated=True)
