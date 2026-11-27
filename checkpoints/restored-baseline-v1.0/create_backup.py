"""Create and verify a new, byte-preserving baseline; never alter website files."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,shutil
OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[1]
SITE=PROJECT/'2mcrafters.com'
BACKUP=PROJECT/'backups'/'restored-baseline-v1.0'/'website'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
if BACKUP.exists():raise SystemExit('Baseline backup already exists; refusing to overwrite it.')
files=sorted(p for p in SITE.rglob('*')if p.is_file())
expected={r['path']:r['sha256']for r in json.loads((PROJECT/'restoration/backup-verification.json').read_text(encoding='utf-8'))['manifest']}
for r in json.loads((PROJECT/'restoration/final-file-changes.json').read_text(encoding='utf-8')):expected[r['path']]=r['afterSHA256']
manifest=[];mismatch=[]
for p in files:
 rel=p.relative_to(SITE).as_posix();digest=sha(p)
 manifest.append({'path':rel,'absolutePath':str(p),'bytes':p.stat().st_size,'sha256':digest})
 if expected.get(rel)!=digest:mismatch.append(rel)
missing=sorted(set(expected)-{r['path']for r in manifest})
if mismatch or missing:raise SystemExit('Current site differs from restoration manifest: '+json.dumps({'changedOrAdded':mismatch,'missing':missing}))
BACKUP.mkdir(parents=True)
for r in manifest:
 dest=BACKUP/r['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SITE/r['path'],dest)
 if sha(dest)!=r['sha256']:raise RuntimeError('Backup mismatch: '+r['path'])
 if sha(SITE/r['path'])!=r['sha256']:raise RuntimeError('Source changed during backup: '+r['path'])
assert len([p for p in BACKUP.rglob('*')if p.is_file()])==len(manifest)
payload={'tag':'restored-baseline-v1.0','createdUTC':datetime.now(timezone.utc).isoformat(),'source':str(SITE),'backup':str(BACKUP),'fileCount':len(manifest),'bytes':sum(r['bytes']for r in manifest),'matchesRestorationManifest':True,'sourceAndBackupSHA256Verified':True,'files':manifest}
encoded=json.dumps(payload,indent=2,ensure_ascii=False)
(OUT/'website-manifest.json').write_text(encoded,encoding='utf-8')
(BACKUP.parent/'backup-manifest.json').write_text(encoded,encoding='utf-8')
print(json.dumps({k:v for k,v in payload.items()if k!='files'},indent=2))
