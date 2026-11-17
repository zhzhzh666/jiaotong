"""Run selected stages sequentially; preserve every run and fail on errors."""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phases',nargs='+',choices=[f'{i:02d}' for i in range(4,14)],required=True)
    parser.add_argument('--include-full-nanshan',action='store_true',help='Also run full-Nanshan Phase 07 (~22 min on the recorded machine)')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    print('Optimization and ten-seed experiments use the small real network. Full-Nanshan optimization is not implemented.',flush=True)
    for phase in args.phases:
        configs=[f'configs/phase{phase}.yaml']
        if phase=='11':configs=['configs/phase11_fresh.yaml']
        if phase=='07' and args.include_full_nanshan:configs.append('configs/phase07_nanshan.yaml')
        for config in configs:
            command=[sys.executable,'-m','uftr.cli','--root',str(ROOT),'run','--phase',phase,'--config',config]
            print(subprocess.list2cmdline(command),flush=True)
            if not args.dry_run:subprocess.run(command,cwd=ROOT,check=True)

if __name__=='__main__':main()
