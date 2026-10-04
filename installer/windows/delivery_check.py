"""Local build receipts; no agent runtime, upload or business-data access."""
import hashlib
import json
from pathlib import Path
import sys

ROOT_FILES = {
    'launch.py', 'initialize.py', 'configure.ps1', 'BuildCostIQService.exe', 'LICENSE.txt',
    'licenses/Inno-Setup-Chinese-Simplified-Translation-LICENSE.txt',
}
REQUIRED_CHECKS={
    'packaged recognition dependencies import','bootstrap creates project/admin',
    'UTF-8 BOM stdin accepted and validated',
    'plaintext password excluded','repeat bootstrap refuses overwrite',
    'nested backup rejected','relative storage rejected','drive root rejected',
    'embedded S06 reference/checkpoint recovery/handoff validation and Agent Ops plan projection',
    'embedded runtime/API rc9 health','WebUI HTTP 200','initialized administrator login',
    'packaged product logo and browser icon served','second project rejected','payload excludes local account/project stores',
    'packaged S01-S09 workflow runtime and S06 ledger replay API',
    'third-party translation license included',
}

def inventory(payload):
    result = []
    for p in sorted(payload.rglob('*')):
        if p.is_symlink():
            raise ValueError('Payload links are forbidden')
        if not p.is_file():
            continue
        rel = p.relative_to(payload)
        if rel.parts[0] not in {'app', 'runtime'} and rel.as_posix() not in ROOT_FILES:
            raise ValueError('Unexpected payload root: ' + str(rel))
        if rel.parts[0] == 'runtime' and len(rel.parts)>1 and rel.parts[1] in {'auth','projects','sources','archive','backups','logs'}:
            raise ValueError('Runtime data included')
        if rel.parts[0] == 'app':
            if len(rel.parts) < 2 or rel.parts[1] not in {'core','plugins','adapters','gui','domains','pyproject.toml'}:
                raise ValueError('Unexpected application content')
            if p.suffix.lower() in {'.png','.ico'} and not (
                rel.parts[:3] == ('app','gui','static')
                and p.name in {'sayelf-logo.png','sayelf-logo.ico'}
            ):
                raise ValueError('Unapproved image asset: '+str(rel))
            if p.suffix.lower() not in {'.py','.pyc','.html','.css','.js','.toml','.png','.ico'}:
                raise ValueError('Non-code application file: '+str(rel))
        with p.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        result.append({'path':rel.as_posix(),'sha256':digest})
    required = ROOT_FILES | {'app/pyproject.toml','runtime/python.exe'}
    if not required.issubset({r['path'] for r in result}):
        raise ValueError('Required payload files missing')
    return result

def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def record(payload, output, smoke):
    if smoke.get('status') != 'passed' or not REQUIRED_CHECKS.issubset(set(smoke.get('checks',[]))):
        raise ValueError('Required smoke checks absent')
    rows=inventory(payload)
    output.mkdir(parents=True,exist_ok=True)
    (output/'payload-manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    smoke['payload_fingerprint']=fingerprint(rows)
    (output/'smoke-result.json').write_text(json.dumps(smoke,indent=2),encoding='utf-8')

def verify(payload, output):
    rows=inventory(payload)
    saved=json.loads((output/'payload-manifest.json').read_text(encoding='utf-8-sig'))
    smoke=json.loads((output/'smoke-result.json').read_text(encoding='utf-8-sig'))
    if rows != saved or smoke.get('payload_fingerprint') != fingerprint(rows) or smoke.get('status') != 'passed' or not REQUIRED_CHECKS.issubset(set(smoke.get('checks',[]))):
        raise ValueError('Payload changed or verification receipt missing; rerun smoke')
    return rows

def installer_receipt(payload, output):
    rows=verify(payload,output)
    exe=output/'BuildCostIQ-ProjectServer-v0.8.0-rc9-x64.exe'
    if not exe.is_file() or exe.stat().st_size < 1_000_000:
        raise ValueError('Compiled installer missing or incomplete')
    with exe.open('rb') as handle: digest=hashlib.file_digest(handle,'sha256').hexdigest()
    result={'compile_status':'passed','file':exe.name,'sha256':digest,'bytes':exe.stat().st_size,
            'payload_fingerprint':fingerprint(rows),'installation_verified':False}
    (output/'installer-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    mode,payload,output=sys.argv[1:4]
    if mode=='record': record(Path(payload),Path(output),json.load(sys.stdin))
    elif mode=='verify':
        rows=verify(Path(payload),Path(output))
        print(json.dumps({'verified':True,'files':len(rows),'fingerprint':fingerprint(rows)}))
    elif mode=='installer': print(json.dumps(installer_receipt(Path(payload),Path(output))))
    else: raise ValueError('Expected record or verify')
