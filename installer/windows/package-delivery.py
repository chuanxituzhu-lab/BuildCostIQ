"""Copy local-only build evidence and payload to the requested delivery directory."""
import json
from pathlib import Path
import shutil
import sys
import zipfile
from delivery_check import verify, fingerprint

repo=Path(__file__).resolve().parents[2]
output=Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=True)
source=repo/'installer/windows'
payload=repo/'work/windows-build/payload'
evidence=repo/'dist/windows'
rows=verify(payload,evidence)
with zipfile.ZipFile(output/'BuildCostIQ-ProjectServer-v0.8.0-rc9-build-sources.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in source.iterdir():
        if p.is_file(): z.write(p, 'installer/windows/'+p.name)
shutil.copy2(source/'INSTALL.md',output/'INSTALL.md')
archive=output/'BuildCostIQ-ProjectServer-v0.8.0-rc9-x64-payload.zip'
receipt=output/'archive-receipt.json'
import hashlib
reuse=False
if archive.exists() and receipt.exists():
    prior=json.loads(receipt.read_text(encoding='utf-8'))
    with archive.open('rb') as handle: archive_hash=hashlib.file_digest(handle,'sha256').hexdigest()
    reuse=prior.get('fingerprint')==fingerprint(rows) and prior.get('sha256')==archive_hash
elif archive.exists():
    # Adopt an earlier archive only after verifying every member, not its name.
    try:
        with zipfile.ZipFile(archive) as z:
            reuse=sorted(z.namelist())==sorted(row['path'] for row in rows)
            if reuse:
                for row in rows:
                    with z.open(row['path']) as handle:
                        if hashlib.file_digest(handle,'sha256').hexdigest()!=row['sha256']:
                            reuse=False; break
        if reuse:
            with archive.open('rb') as handle: archive_hash=hashlib.file_digest(handle,'sha256').hexdigest()
            receipt.write_text(json.dumps({'fingerprint':fingerprint(rows),'sha256':archive_hash}),encoding='utf-8')
    except (OSError,zipfile.BadZipFile): reuse=False
if not reuse:
    temporary=archive.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for row in rows: z.write(payload/row['path'],row['path'])
    verify(payload,evidence)  # reject mutation during packaging
    with temporary.open('rb') as handle: archive_hash=hashlib.file_digest(handle,'sha256').hexdigest()
    temporary.replace(archive)
    receipt.write_text(json.dumps({'fingerprint':fingerprint(rows),'sha256':archive_hash}),encoding='utf-8')
for name in ('dependencies.lock.txt','payload-manifest.json','smoke-result.json','installer-result.json'):
    p=repo/'dist/windows'/name
    if p.exists(): shutil.copy2(p,output/name)
shutil.copy2(source/'VALIDATION.md',output/'VALIDATION.md')
shutil.copy2(source/'AGENT_OPS_REVIEW.md',output/'AGENT_OPS_REVIEW.md')
installer=evidence/'BuildCostIQ-ProjectServer-v0.8.0-rc9-x64.exe'
installer_verified=False
if installer.exists() and (evidence/'installer-result.json').exists():
    compiled=json.loads((evidence/'installer-result.json').read_text(encoding='utf-8'))
    with installer.open('rb') as handle: exe_hash=hashlib.file_digest(handle,'sha256').hexdigest()
    if compiled.get('payload_fingerprint')!=fingerprint(rows) or compiled.get('sha256')!=exe_hash:
        raise ValueError('Installer does not match verified payload')
    installer_verified=compiled.get('compile_status')=='passed'
    if installer_verified: shutil.copy2(installer,output/installer.name)
status={'state':'WORKING','blocked_by':'installation verification absent' if installer.exists() else 'required installer absent; installation verification absent',
        'required_deliverable':'BuildCostIQ-ProjectServer-v0.8.0-rc9-x64.exe',
        'payload_verified':True,'payload_fingerprint':fingerprint(rows),'archive_reused':reuse,
        'installer_generated':installer.exists(),'installer_verified':installer_verified,'installation_verified':False,'convergence':'NOT_CONVERGED'}
(output/'BUILD_RESULT.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
print(json.dumps({'outputs':[{ 'file':p.name,'bytes':p.stat().st_size} for p in output.iterdir() if p.is_file()]}))
