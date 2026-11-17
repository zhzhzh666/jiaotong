"""Save actual pip provenance and a portable version lock without local URLs."""
from pathlib import Path
import importlib.metadata
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
freeze=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True,encoding='utf-8')
(root/'docs/validation/installed-pip-freeze.txt').write_text(freeze,encoding='utf-8')
versions=[]
for line in freeze.splitlines():
    if line.startswith('-e '):continue
    if ' @ ' in line:
        name=line.split(' @ ',1)[0];line=name+'=='+importlib.metadata.version(name)
    versions.append(line)
text='# Installed versions; local Conda build URL normalized to version.\n# Project checkout: pip install -e . (separate from dependencies).\n'+'\n'.join(versions)+'\n'
(root/'requirements-lock.txt').write_text(text,encoding='utf-8')
print(f'Locked {len(versions)} installed dependency versions; original pip freeze retained as evidence.')
