"""Publish an explicit, complete CSiM evidence run to the authorized demo host."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parent
run=Path(sys.argv[1]).resolve()
source=run/'public'
summary=json.loads((source/'summary.json').read_text())
expected={'all-charts','time-grouping','date-range','filter-selection','clear-filters','filter-options','native-import','dashboard-time-units'}
regression=json.loads((run/'regression-summary.json').read_text())
assert regression['completed'] and {w['id'] for w in regression['workflows']}=={f'{n:02}' for n in range(1,11)}
assert all(w['status']=='passed' for w in regression['workflows'])
assert summary['completed'] and {w['id'] for w in summary['workflows']}==expected
assert all(w['status']=='passed' and w.get('videoValidation') for w in summary['workflows'])
assert sum(a['type']=='video/mp4' for w in summary['workflows'] for a in w['assets'])==8
allowed={a['file'] for w in summary['workflows'] for a in w['assets']}|{'index.html','summary.json'}
assert {p.name for p in source.iterdir()}==allowed
assert all(Path(name).name==name for name in allowed)
secrets=[]
for env in ROOT.glob('.env.*'):
    for line in env.read_text().splitlines():
        if '=' in line and any(key in line.split('=',1)[0] for key in ['PASSWORD','SECRET_KEY']):
            secrets.append(line.split('=',1)[1].encode())
for file in source.iterdir():
    assert not any(secret and secret in file.read_bytes() for secret in secrets),file.name
hashes={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in sorted(allowed)}
stamp=run.name+'-'+hashes['summary.json'][:10]
archive=ROOT/'output'/('evidence-'+stamp+'.tar.gz')
with tarfile.open(archive,'w:gz') as tf:
    for name in sorted(allowed):tf.add(source/name,arcname=name)
os.chmod(archive,0o600)
subprocess.run(['scp','-4',str(archive),'catalyst.openelis-global.org:/home/ubuntu/csim-superset-demo/output/'],check=True)
remote='''from pathlib import Path
import os,tarfile,hashlib,json
stamp=STAMP
hashes=HASHES
media=Path('/home/ubuntu/catalyst-demo/targets/catalyst/runtime/media/csim-design')
release=media/'evidence-releases'/stamp
release.mkdir(parents=True,exist_ok=False)
archive=Path('/home/ubuntu/csim-superset-demo/output')/('evidence-'+stamp+'.tar.gz')
with tarfile.open(archive) as tf:
    assert all(Path(m.name).name==m.name and m.isfile() for m in tf.getmembers())
    tf.extractall(release,filter='data')
for name,digest in hashes.items():
    file=release/name
    assert hashlib.sha256(file.read_bytes()).hexdigest()==digest,name
    os.chmod(file,0o644)
os.chmod(release,0o755)
link=media/'evidence'
assert not link.exists() or link.is_symlink()
staged=media/'evidence.new'
if staged.is_symlink():staged.unlink()
staged.symlink_to(Path('evidence-releases')/stamp)
os.replace(staged,link)
print(json.dumps({'release':stamp,'verifiedFiles':len(hashes)}))
'''.replace('STAMP',repr(stamp)).replace('HASHES',repr(hashes))
subprocess.run(['ssh','-4','-o','BatchMode=yes','catalyst.openelis-global.org','python3 -'],input=remote,text=True,check=True)
