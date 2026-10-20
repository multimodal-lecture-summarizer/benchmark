"""Inline notebook bootstrap: preserve scorer pins without requiring ensurepip."""

SETUP_CELL = '''ENV = WORK/'venv'
PYTHON = ENV/'bin/python'
RUN_ENV = dict(os.environ, USE_TF='0', USE_FLAX='0', TOKENIZERS_PARALLELISM='false',
               PYTHONPATH=str(BUNDLE), HF_HUB_DISABLE_TELEMETRY='1')
assert shutil.disk_usage('/content').free >= 12*1024**3, 'Need at least 12 GiB working disk before setup.'
def execute(command, log_name):
    remaining = SESSION_LIMIT_SECONDS-(time.monotonic()-SESSION_STARTED)
    assert remaining>0, 'Session guard reached'
    log_path = OUTPUT/log_name
    try:
        with log_path.open('w') as log:
            result = subprocess.run(command, cwd=BUNDLE, env=RUN_ENV, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=remaining)
        print('exit', result.returncode, '|', log_path)
        print(log_path.read_text(errors='replace')[-5000:])
        return result.returncode
    except Exception as error:
        bootstrap_hold(error)
        raise
# An unsuccessful ensurepip step can leave bin/python present. Always repair the
# venv structure without deleting it or bootstrapping pip inside the target.
created = execute([sys.executable,'-m','venv','--system-site-packages','--without-pip',str(ENV)],
                  'create-venv.log')
if created:
    bootstrap_hold('venv --without-pip failed; see create-venv.log')
assert created==0, 'HOLD: venv creation failed. Export evidence using the last cell.'
probe = "import json,sys; from pathlib import Path; assert sys.prefix != sys.base_prefix; assert Path(sys.prefix).absolute() == Path(sys.argv[1]).absolute(); print(json.dumps({'executable':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,'python':sys.version}))"
verified = execute([str(PYTHON),'-c',probe,str(ENV)],'venv-identity.log')
if verified:
    bootstrap_hold('Target interpreter is not the intended venv; see venv-identity.log')
assert verified==0, 'HOLD: target venv identity failed.'
# pip >=22.3 officially supports installing into a pip-less target interpreter.
# Use the base installer only as an installer, never as the scorer interpreter.
setup = execute([sys.executable,'-m','pip','--python',str(PYTHON),'install',
                 '-r',str(BUNDLE/'requirements-colab-t4.txt')], 'install.log')
if setup:
    bootstrap_hold('Pinned dependency installation failed; see install.log (base pip needs --python support)')
assert setup==0, 'HOLD: dependency setup failed. Export evidence using the last cell.'
'''
