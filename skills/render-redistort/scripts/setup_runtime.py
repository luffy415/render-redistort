"""Create/check this skill's isolated Python runtime. No global package changes."""
import argparse,json,os,subprocess,sys,venv
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-only',action='store_true');p.add_argument('--runtime',type=Path);a=p.parse_args()
    skill=Path(__file__).resolve().parents[1];root=(a.runtime or skill/'.runtime').resolve()
    py=root/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not a.check_only:
        if not (3,11)<=sys.version_info[:2]<=(3,13):raise RuntimeError('Use Python3.11–3.13; Windows/Python3.13 is the verified build.')
        if root.exists() and not (root/'pyvenv.cfg').is_file():raise RuntimeError('Runtime path already exists and is not a venv; refusing to replace it.')
        if not root.exists():venv.EnvBuilder(with_pip=True).create(root)
        subprocess.run([str(py),'-m','pip','install','--disable-pip-version-check','-r',str(skill/'requirements.txt')],check=True)
    if not py.is_file():raise RuntimeError('Runtime not installed. Run setup_runtime.py with Python3.11–3.13.')
    probe="import json,numpy,scipy,OpenImageIO as o;print(json.dumps(dict(numpy=numpy.__version__,scipy=scipy.__version__,OpenImageIO=o.VERSION_STRING)))"
    result=subprocess.run([str(py),'-c',probe],check=True,capture_output=True,text=True)
    versions=json.loads(result.stdout)
    expected={'numpy':'2.4.2','scipy':'1.17.1','OpenImageIO':'3.1.18.1'}
    if versions!=expected:raise RuntimeError('Runtime versions do not match the tested lock: '+str(versions))
    subprocess.run([str(py),str(skill/'scripts/self_test.py')],check=True)
    report=dict(status='ready',python=str(py),versions=versions,synthetic_self_test='passed',skill=str(skill))
    if not a.check_only:(skill/'runtime.local.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
