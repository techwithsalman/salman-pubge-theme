"""Read-only integrity checks for source, independent backup and Git baseline."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess, urllib.request

OUT=Path(__file__).resolve().parent
REPO=OUT.parent.parent
ROOT=REPO/'2mcrafters.com'
BACKUP=REPO/'backups/restored-baseline-v1.0/website'
TAG='restored-baseline-v1.0'
manifest=json.loads((OUT/'website-manifest.json').read_text(encoding='utf-8'))
expected={f['path']:f for f in manifest['files']}
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def check_tree(root):
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    assert actual==set(expected),(root,'path mismatch',actual^set(expected))
    for rel,record in expected.items():
        assert (root/rel).stat().st_size==record['bytes'],rel
        assert sha(root/rel)==record['sha256'],rel
    return len(actual)
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO)
source_count=check_tree(ROOT)
backup_count=check_tree(BACKUP)
tree=git('ls-tree','-r','-z',TAG,'--','2mcrafters.com/').split(b'\0')
tracked={}
for row in tree:
    if not row:continue
    meta,path=row.split(b'\t',1);mode,typ,oid=meta.split()
    assert typ==b'blob'
    tracked[path.decode('utf-8')[len('2mcrafters.com/'):]]=oid.decode()
assert set(tracked)==set(expected),'Git does not contain every website file'
proc=subprocess.Popen(['git','cat-file','--batch'],cwd=REPO,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
for rel,oid in tracked.items():
    proc.stdin.write((oid+'\n').encode());proc.stdin.flush()
    header=proc.stdout.readline().split(); assert header[1]==b'blob'
    remaining=int(header[2]);h=hashlib.sha256()
    while remaining:
        data=proc.stdout.read(min(1024*1024,remaining)); assert data
        h.update(data);remaining-=len(data)
    assert proc.stdout.read(1)==b'\n'
    assert h.hexdigest()==expected[rel]['sha256'],('Git byte mismatch',rel)
proc.stdin.close();assert proc.wait()==0
commit=git('rev-parse',TAG+'^{commit}').decode().strip()
assert git('rev-parse','HEAD').decode().strip()==commit
assert git('log','-1','--format=%s',commit).decode().strip()=='Complete original website restoration - stable baseline'
assert git('cat-file','-t',TAG).decode().strip()=='tag'
assert git('status','--porcelain')==b'','Working tree is not clean'
assert git('remote').strip()==b'','Unexpected remote'
with urllib.request.urlopen('http://127.0.0.1:8081/mohamedandaloussi/',timeout=15) as response:
    http_status=response.status;assert http_status==200
result={'verifiedUTC':datetime.now(timezone.utc).isoformat(),'commit':commit,'tag':TAG,'sourceFilesVerified':source_count,'backupFilesVerified':backup_count,'gitBlobsVerified':len(tracked),'websiteBytes':manifest['bytes'],'allSHA256Match':True,'cleanWorkingTree':True,'annotatedTagVerified':True,'remotes':[],'pushed':False,'serverHTTPStatus':http_status,'url':'http://localhost:8081/mohamedandaloussi/','browserLaunch':'Automatic launch was blocked by tool policy; native Chrome interface was unusable. Open the provided URL manually.','brandingChangesApplied':False}
(REPO/'restoration/baseline-checkpoint-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
