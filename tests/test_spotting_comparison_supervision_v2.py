"""Regression for observed Windows venv-launcher/native-worker PID mismatch."""
import json
import os
from pathlib import Path
import subprocess
import time

import pytest

from experiments.scripts.spotting_runtime_binding import VENV
from experiments.scripts.spotting_comparison_supervision_v2 import bound_progress,process_alive,terminate_tree


def test_progress_uses_attempt_and_run_not_launcher_pid(tmp_path):
    identity={'run_id':'run'}
    state=dict(run_id='run',attempt_path=str(tmp_path.resolve()),pid=123)
    assert bound_progress(state,identity,tmp_path)==state
    assert not bound_progress(dict(state,run_id='stale'),identity,tmp_path)
    assert not bound_progress(dict(state,attempt_path=str(tmp_path/'other')),identity,tmp_path)
    assert not bound_progress(dict(state,pid=-1),identity,tmp_path)


@pytest.mark.skipif(os.name!='nt',reason='actual Windows venv launcher regression')
def test_real_venv_launcher_heartbeat_and_tree_termination(tmp_path):
    target=tmp_path/'heartbeat.json'
    program="import json,os,pathlib,time;pathlib.Path("+repr(str(target))+ ").write_text(json.dumps(dict(pid=os.getpid(),run_id='run',attempt_path="+repr(str(tmp_path.resolve()))+")));time.sleep(60)"
    process=subprocess.Popen([str(VENV/'Scripts/python.exe'),'-s','-c',program])
    state={}
    try:
        deadline=time.monotonic()+15
        while not target.exists() and time.monotonic()<deadline: time.sleep(.1)
        state=json.loads(target.read_text())
        assert state['pid']!=process.pid
        assert process_alive(state['pid'])
        assert bound_progress(state,{'run_id':'run'},tmp_path)==state
        result=terminate_tree(process,state)
        assert result['worker_confirmed_terminated']
        assert process.poll() is not None and not process_alive(state['pid'])
        # Windows taskkill can report a nonzero race after terminating the tree;
        # termination is accepted only with independently confirmed dead processes.
        assert result['returncode']==0 or (process.poll() is not None and not process_alive(state['pid']))
        print('Actual launcher/worker termination evidence:',result)
    finally:
        if process.poll() is None: terminate_tree(process,state)
