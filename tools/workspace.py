#!/usr/bin/env python3
"""Fetch exactly the commits used by this multi-repository snapshot."""
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('action',choices=['fetch','status']);p.add_argument('--dest',type=Path,required=True);a=p.parse_args()
lock=json.loads((Path(__file__).resolve().parents[1]/'manifests/repos.lock.json').read_text())
a.dest.mkdir(parents=True,exist_ok=True)
for r in lock['repositories']:
 d=a.dest/r['name']
 if a.action=='fetch':
  if not d.exists():subprocess.run(['git','clone',r['url'],str(d)],check=True)
  if subprocess.check_output(['git','-C',str(d),'status','--porcelain'],text=True).strip():raise SystemExit(f'Uncommitted work: {d}')
  subprocess.run(['git','-C',str(d),'fetch','origin',r['commit']],check=True)
  subprocess.run(['git','-C',str(d),'checkout','--detach',r['commit']],check=True)
 print(r['name'],subprocess.check_output(['git','-C',str(d),'rev-parse','HEAD'],text=True).strip())
# Copy the orchestrator itself from the caller checkout, preserving its Git.
if a.action=='fetch':
 d=a.dest/'mocha-moze-debian';src=Path(__file__).resolve().parents[1]
 if not d.exists():subprocess.run(['git','clone','--no-hardlinks',str(src),str(d)],check=True)
