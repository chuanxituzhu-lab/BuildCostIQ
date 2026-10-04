"""Offline payload verification with disposable synthetic data only."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen, Request
from urllib.error import HTTPError

payload = Path(sys.argv[1]).resolve()
python = payload / 'runtime/python.exe'
checks = []
license_file=payload/'licenses/Inno-Setup-Chinese-Simplified-Translation-LICENSE.txt'
assert license_file.is_file() and 'MIT License' in license_file.read_text(encoding='utf-8')
checks.append('third-party translation license included')
p=subprocess.run([str(python),'-B','-c','import openpyxl,pypdf,markitdown,mammoth,pdfminer,pandas,lxml,onnxruntime'],capture_output=True,text=True)
assert p.returncode==0,p.stderr
checks.append('packaged recognition dependencies import')
ledger_probe = r'''
import os, tempfile
from pathlib import Path
from adapters.deployment import DeploymentConfig, DeploymentStorageAdapter
from adapters.workspace import LocalProjectWorkspace
from core.execution_ledger import ExecutionLedgerError
with tempfile.TemporaryDirectory(prefix='bciq-ledger-') as scratch:
    env = dict(os.environ, BUILDCOSTIQ_DATA_ROOT=str(Path(scratch) / 'Data'))
    config = DeploymentConfig.from_environment(env)
    storage = DeploymentStorageAdapter(config)
    workspace = LocalProjectWorkspace(config.roots.projects, storage_adapter=storage)
    workspace.create('smoke-project', 'Synthetic project')
    source_hash = 'a' * 64
    workspace.add_source('smoke-project', {
        'source_id': 'smoke-source', 'content_hash': source_hash, 'status': 'active',
    })
    workspace.append_execution_event('smoke-project', {
        'run_id': 'smoke-run', 'workflow_id': 'WF02', 'module_id': '02',
        'event_type': 'AGENT_OPS_PLAN_RECORDED', 'actor_type': 'agent',
        'actor_id': 'synthetic-agent', 'target_type': 'run', 'target_id': 'smoke-run',
        'payload_summary': 'Synthetic plan only', 'evidence_refs': ['sha256:' + source_hash],
        'result_version_refs': [], 'checkpoint_ref': '',
        'idempotency_key': 'smoke-plan-v1', 'data_classification': 'Restricted',
        'agent_ops_state': 'WORKING',
    })
    workspace.append_execution_event('smoke-project', {
        'run_id': 'smoke-run', 'workflow_id': 'WF02', 'module_id': '02',
        'event_type': 'RESULT_VERSIONED', 'actor_type': 'agent',
        'actor_id': 'synthetic-agent', 'target_type': 'result_version', 'target_id': 'smoke-result-v1',
        'payload_summary': 'Synthetic result version registered', 'evidence_refs': [],
        'result_version_refs': [], 'checkpoint_ref': '',
        'idempotency_key': 'smoke-result-v1', 'data_classification': 'Restricted',
    })
    workspace.append_execution_event('smoke-project', {
        'run_id': 'smoke-run', 'workflow_id': 'WF02', 'module_id': '02',
        'event_type': 'AGENT_OPS_PLAN_RECORDED', 'actor_type': 'agent',
        'actor_id': 'synthetic-agent', 'target_type': 'run', 'target_id': 'smoke-run',
        'payload_summary': 'Synthetic plan updated', 'evidence_refs': ['sha256:' + source_hash],
        'result_version_refs': ['result-version:smoke-result-v1'], 'checkpoint_ref': '',
        'idempotency_key': 'smoke-plan-v2', 'data_classification': 'Restricted',
        'agent_ops_state': 'READY',
    })
    workspace.append_execution_event('smoke-project', {
        'run_id': 'smoke-run', 'workflow_id': 'WF02', 'module_id': '02',
        'event_type': 'CHECKPOINT_CREATED', 'actor_type': 'system',
        'actor_id': 'synthetic-system', 'target_type': 'checkpoint', 'target_id': 'smoke-checkpoint-1',
        'payload_summary': 'Synthetic checkpoint marker only', 'evidence_refs': [],
        'result_version_refs': [], 'checkpoint_ref': '',
        'idempotency_key': 'smoke-checkpoint-v1', 'data_classification': 'Restricted',
    })
    checkpoint_ref = 'checkpoint:smoke-checkpoint-1'
    try:
        workspace.append_execution_event('smoke-project', {
            'run_id': 'smoke-run', 'workflow_id': 'WF02', 'module_id': '02',
            'event_type': 'RECOVERY_COMPLETED', 'actor_type': 'system',
            'actor_id': 'synthetic-system', 'target_type': 'checkpoint', 'target_id': 'smoke-checkpoint-1',
            'payload_summary': 'Reject unmatched recovery completion', 'evidence_refs': [],
            'result_version_refs': [], 'checkpoint_ref': checkpoint_ref,
            'idempotency_key': 'smoke-recovery-orphan', 'data_classification': 'Restricted',
        })
        raise AssertionError('Unmatched recovery completion accepted')
    except ExecutionLedgerError:
        pass
    workspace.append_execution_event('smoke-project', {
        'run_id': 'smoke-run', 'workflow_id': 'WF02', 'module_id': '02',
        'event_type': 'RECOVERY_STARTED', 'actor_type': 'system',
        'actor_id': 'synthetic-system', 'target_type': 'checkpoint', 'target_id': 'smoke-checkpoint-1',
        'payload_summary': 'Synthetic recovery record started', 'evidence_refs': [],
        'result_version_refs': [], 'checkpoint_ref': checkpoint_ref,
        'idempotency_key': 'smoke-recovery-start', 'data_classification': 'Restricted',
    })
    workspace.append_execution_event('smoke-project', {
        'run_id': 'smoke-run', 'workflow_id': 'WF02', 'module_id': '02',
        'event_type': 'RECOVERY_COMPLETED', 'actor_type': 'system',
        'actor_id': 'synthetic-system', 'target_type': 'checkpoint', 'target_id': 'smoke-checkpoint-1',
        'payload_summary': 'Synthetic recovery record completed', 'evidence_refs': [],
        'result_version_refs': [], 'checkpoint_ref': checkpoint_ref,
        'idempotency_key': 'smoke-recovery-complete', 'data_classification': 'Restricted',
    })
    handoff = {
        'run_id': 'smoke-run', 'workflow_id': 'WF02', 'module_id': '02',
        'actor_type': 'human', 'actor_id': 'synthetic-user', 'target_type': 'handoff', 'target_id': 'smoke-handoff-1',
        'payload_summary': 'Synthetic handoff relationship only', 'evidence_refs': [],
        'result_version_refs': [], 'checkpoint_ref': '', 'data_classification': 'Restricted',
    }
    workspace.append_execution_event('smoke-project', dict(handoff,
        event_type='HANDOFF_CREATED', idempotency_key='smoke-handoff-created'))
    workspace.append_execution_event('smoke-project', dict(handoff,
        event_type='HANDOFF_CONSUMED', idempotency_key='smoke-handoff-consumed'))
    try:
        workspace.append_execution_event('smoke-project', dict(handoff,
            event_type='HANDOFF_CONSUMED', idempotency_key='smoke-handoff-consumed-duplicate'))
        raise AssertionError('Duplicate handoff consumption accepted')
    except ExecutionLedgerError:
        pass
    try:
        workspace.append_execution_event('smoke-project', {
            'run_id': 'smoke-run', 'workflow_id': 'WF02', 'module_id': '02',
            'event_type': 'RUN_CREATED', 'actor_type': 'agent',
            'actor_id': 'synthetic-agent', 'target_type': 'run', 'target_id': 'smoke-run',
            'payload_summary': 'Reject unresolved evidence', 'evidence_refs': ['sha256:' + 'f' * 64],
            'result_version_refs': [], 'checkpoint_ref': '',
            'idempotency_key': 'smoke-invalid-ref', 'data_classification': 'Restricted',
        })
        raise AssertionError('Unresolved evidence reference accepted')
    except ExecutionLedgerError:
        pass
    result = workspace.execution_ledger_snapshot('smoke-project')
    assert result['valid'] and result['event_count'] == 8
    assert result['agent_ops_plan_states'][0]['state'] == 'READY'
    assert result['agent_ops_plan_states'][0]['state_meaning'] == 'plan_ready_only'
'''
p=subprocess.run([str(python),'-B','-c',ledger_probe],capture_output=True,text=True)
assert p.returncode==0,p.stderr
checks.append('embedded S06 reference/checkpoint recovery/handoff validation and Agent Ops plan projection')
with tempfile.TemporaryDirectory(prefix='buildcostiq-smoke-') as scratch:
    root = Path(scratch)
    c = dict(project_name='Smoke project', project_code='smoke', currency='CNY', timezone='Asia/Shanghai',
             username='smoke-admin', password='Smoke@12', data_root=str(root/'Data'), backup_root=str(root/'Backups'))
    short_password=dict(c,password='short77',data_root=str(root/'ShortData'),backup_root=str(root/'ShortBackups'))
    p=subprocess.run([str(python),str(payload/'initialize.py')],input=json.dumps(short_password),text=True,capture_output=True)
    assert p.returncode!=0 and not Path(short_password['data_root']).exists(),p.stderr
    checks.append('seven-character password rejected')
    bom_password=dict(c,password='short77',data_root=str(root/'BomData'),backup_root=str(root/'BomBackups'))
    p=subprocess.run([str(python),str(payload/'initialize.py')],input='\ufeff'+json.dumps(bom_password),text=True,capture_output=True)
    assert p.returncode!=0 and '至少8位' in p.stderr and not Path(bom_password['data_root']).exists(),p.stderr
    checks.append('UTF-8 BOM stdin accepted and validated')
    p = subprocess.run([str(python), str(payload/'initialize.py')], input=json.dumps(c), text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    checks.extend(['bootstrap creates project/admin','eight-character password accepted'])
    assert 'password' not in json.loads((root/'Data/installation.json').read_text(encoding='utf-8'))
    assert c['password'] not in (root/'Data/auth/users.json').read_text(encoding='utf-8')
    checks.append('plaintext password excluded')
    p = subprocess.run([str(python), str(payload/'initialize.py')], input=json.dumps(c), text=True, capture_output=True)
    assert p.returncode != 0
    checks.append('repeat bootstrap refuses overwrite')
    original=(root/'Data/auth/users.json').read_bytes()
    for label,override in (
        ('nested backup rejected',{'backup_root':str(root/'Data/Backups')}),
        ('relative storage rejected',{'data_root':'relative-data'}),
        ('drive root rejected',{'data_root':str(Path(root.anchor))}),
    ):
        invalid=dict(c,**override)
        p=subprocess.run([str(python),str(payload/'initialize.py')],input=json.dumps(invalid),text=True,capture_output=True)
        assert p.returncode!=0,label
        assert (root/'Data/auth/users.json').read_bytes()==original
        checks.append(label)
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); port=s.getsockname()[1]
    c.update(host='127.0.0.1',port=port)
    configdir=root/'ProgramData/BuildCostIQ'
    configdir.mkdir(parents=True)
    configdir.joinpath('server.json').write_text(json.dumps({k:v for k,v in c.items() if k!='password'}), encoding='utf-8')
    env = dict(os.environ, ProgramData=str(root/'ProgramData'), PYTHONDONTWRITEBYTECODE='1')
    with (root/'server.log').open('w') as log:
        server=subprocess.Popen([str(python), str(payload/'launch.py')],
                                env=env, cwd=root, stdout=log, stderr=log)
        try:
            health=None
            for _ in range(60):
                if server.poll() is not None: raise RuntimeError((root/'server.log').read_text())
                try:
                    with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=1) as response: health=json.load(response)
                    break
                except OSError: time.sleep(0.25)
            assert health and 'rc9' in health['runtime']['version'], health
            with urlopen(f'http://127.0.0.1:{port}/', timeout=2) as response:
                assert response.status==200
                page=response.read().decode('utf-8')
                assert 'href="/sayelf-logo.png"' in page and 'src="/sayelf-logo.png"' in page
                assert '新版业务流程' in page
            with urlopen(f'http://127.0.0.1:{port}/sayelf-logo.png', timeout=2) as response:
                assert response.headers.get_content_type()=='image/png'
                assert response.read(8)==b'\x89PNG\r\n\x1a\n'
            checks.append('packaged product logo and browser icon served')
            checks.extend(['embedded runtime/API rc9 health', 'WebUI HTTP 200'])
            req=Request(f'http://127.0.0.1:{port}/api/auth/login',
                        data=json.dumps({'username':c['username'],'password':c['password']}).encode(), headers={'Content-Type':'application/json'})
            with urlopen(req, timeout=5) as response: login=json.load(response)
            checks.append('initialized administrator login')
            req=Request(f'http://127.0.0.1:{port}/api/business-workflows?project_id={c["project_code"]}',
                        headers={'Authorization':'Bearer '+login['token']})
            with urlopen(req, timeout=5) as response: workflow_catalog=json.load(response)
            assert len(workflow_catalog['modules'])==8, workflow_catalog
            assert workflow_catalog['recovery']['status']=='replayed', workflow_catalog['recovery']
            checks.append('packaged S01-S09 workflow runtime and S06 ledger replay API')
            agent_username='smoke-cost-manager'
            req=Request(f'http://127.0.0.1:{port}/api/personnel',
                        data=json.dumps({'project_id':c['project_code'],'username':agent_username,
                                         'role':'cost_manager','password':'Smoke-Agent-123'}).encode(),
                        headers={'Content-Type':'application/json','Authorization':'Bearer '+login['token']})
            with urlopen(req,timeout=5) as response: personnel=json.load(response)
            agent_user=next(item for item in personnel['users'] if item['username']==agent_username)
            req=Request(f'http://127.0.0.1:{port}/api/auth/login',
                        data=json.dumps({'username':agent_username,'password':'Smoke-Agent-123'}).encode(),
                        headers={'Content-Type':'application/json'})
            with urlopen(req,timeout=5) as response: agent_login=json.load(response)
            role_request={'project_id':c['project_code'],'job_title':'实验员',
                          'responsibilities':'负责混凝土试件取样送检和试验报告'}
            req=Request(f'http://127.0.0.1:{port}/api/agent-ops/role-assignment',
                        data=json.dumps(role_request,ensure_ascii=False).encode(),
                        headers={'Content-Type':'application/json','Authorization':'Bearer '+login['token']})
            with urlopen(req,timeout=5) as response: role_result=json.load(response)
            assert role_result['source']=='sayelf-agent-ops-local'
            assert role_result['human_confirmation_required'] and role_result['input_persisted'] is False
            assert role_result['recommendation']['status']=='MATCHED'
            assert role_result['recommendation']['recommended_role']=='lab_testing_officer'
            lab_role=next(item for item in role_result['role_options'] if item['role']=='lab_testing_officer')
            personnel_request=Request('http://127.0.0.1:%s/api/personnel?project_id=%s' % (port,c['project_code']),
                                      headers={'Authorization':'Bearer '+login['token']})
            with urlopen(personnel_request,timeout=5) as response: role_catalog=json.load(response)['roles']
            catalog_lab=next(item for item in role_catalog if item['role']=='lab_testing_officer')
            assert {item['key'] for item in lab_role['permissions']}=={item['key'] for item in catalog_lab['permissions']}
            req=Request(f'http://127.0.0.1:{port}/api/agent-ops/role-assignment',
                        data=json.dumps(role_request,ensure_ascii=False).encode(),
                        headers={'Content-Type':'application/json','Authorization':'Bearer '+agent_login['token']})
            try:
                urlopen(req,timeout=5)
                raise AssertionError('Non-manager can request personnel role assignment')
            except HTTPError as e:
                assert e.code==403
            conflict=dict(role_request,job_title='施工员',responsibilities='负责技术方案审核')
            req=Request(f'http://127.0.0.1:{port}/api/agent-ops/role-assignment',
                        data=json.dumps(conflict,ensure_ascii=False).encode(),
                        headers={'Content-Type':'application/json','Authorization':'Bearer '+login['token']})
            with urlopen(req,timeout=5) as response: conflict_result=json.load(response)['recommendation']
            assert conflict_result['status']=='NEEDS_REVIEW' and not conflict_result['recommended_role']
            checks.append('local role routing, exact RBAC permission preview, conflict review, and manager-only access')
            plan={'project_id':c['project_code'],'run_id':'smoke-agentops-run','workflow_id':'WF02',
                  'module_id':'02','target_type':'workflow_plan','target_id':'smoke-bid-plan',
                  'payload_summary':'Synthetic plan is ready','idempotency_key':'smoke-agentops-v1',
                  'agent_ops_state':'READY'}
            req=Request(f'http://127.0.0.1:{port}/api/agent-ops/plan',
                        data=json.dumps(plan).encode(),
                        headers={'Content-Type':'application/json','Authorization':'Bearer '+agent_login['token']})
            with urlopen(req,timeout=5) as response: recorded=json.load(response)['event']
            assert recorded['actor_id']==agent_user['id']
            assert recorded['agent_ops_state_meaning']=='plan_ready_only'
            forged=dict(plan,actor_id='forged-user',idempotency_key='forged-agentops-v1')
            req=Request(f'http://127.0.0.1:{port}/api/agent-ops/plan',
                        data=json.dumps(forged).encode(),
                        headers={'Content-Type':'application/json','Authorization':'Bearer '+agent_login['token']})
            try:
                urlopen(req,timeout=5)
                raise AssertionError('Client-supplied actor_id accepted')
            except HTTPError as e:
                assert e.code==422
            req=Request(f'http://127.0.0.1:{port}/api/agent-ops/ledger?project_id={c["project_code"]}',
                        headers={'Authorization':'Bearer '+agent_login['token']})
            with urlopen(req,timeout=5) as response:
                ledger=json.load(response)
            assert ledger['verification']['valid'] and ledger['verification']['event_count']==1
            assert ledger['agent_ops_plan_states'][0]['state']=='READY'
            assert ledger['agent_ops_plan_states'][0]['state_meaning']=='plan_ready_only'
            checks.append('authenticated Agent Ops plan record, project scope, READY meaning, and verified ledger read')
            req=Request(f'http://127.0.0.1:{port}/api/project',
                        data=json.dumps({'project_id':'other','name':'Other'}).encode(),
                        headers={'Content-Type':'application/json','Authorization':'Bearer '+login['token']})
            try:
                urlopen(req,timeout=5)
                raise AssertionError('Second project accepted')
            except HTTPError as e:
                assert e.code==422
            assert not (root/'Data/projects/other.json').exists()
            checks.append('second project rejected')
        finally:
            server.terminate(); server.wait(timeout=10)
    assert not (payload/'runtime/auth').exists()
    assert not (payload/'runtime/projects').exists()
    checks.append('payload excludes local account/project stores')
result={'status':'passed','checks':checks}
if len(sys.argv)>2:
    from delivery_check import record
    record(payload,Path(sys.argv[2]).resolve(),result)
    (payload.parent/'dependencies.complete').write_text('Existing pip success confirmed by packaged imports and smoke',encoding='ascii')
print(json.dumps(result, ensure_ascii=False, indent=2))
