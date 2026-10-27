"""Register the local repository's skill and prepare its isolated runtime."""
import argparse,hashlib,os,shutil,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dest',type=Path,help='Skills parent directory (defaults to CODEX_HOME/skills)')
    p.add_argument('--skip-runtime',action='store_true',help='Packaging/registration tests only; not a ready installation')
    a=p.parse_args()
    if not (3,11)<=sys.version_info[:2]<=(3,13):raise RuntimeError('Use Python3.11–3.13 for installation.')
    source=Path(__file__).resolve().parent/'skills/render-redistort'
    base=a.dest or Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'
    target=base/'render-redistort'
    excluded={'.runtime','__pycache__','.pytest_cache','runtime.local.json'}
    files=[f for f in source.rglob('*') if f.is_file() and not any(s in excluded for s in f.relative_to(source).parts)]
    if target.exists():
        for f in files:
            existing=target/f.relative_to(source)
            if not existing.is_file() or f.read_bytes()!=existing.read_bytes():
                raise RuntimeError('Existing skill differs; refusing overwrite: '+str(existing))
        print('Identical registered skill found; resuming runtime setup.')
    else:
        base.mkdir(parents=True,exist_ok=True)
        shutil.copytree(source,target,ignore=shutil.ignore_patterns(*excluded))
    if not a.skip_runtime:subprocess.run([sys.executable,str(target/'scripts/setup_runtime.py')],check=True)
    print('Registered: '+str(target))
    print('Runtime was skipped; not ready.' if a.skip_runtime else 'Ready. Use $render-redistort on the next Codex turn.')

if __name__=='__main__':main()
