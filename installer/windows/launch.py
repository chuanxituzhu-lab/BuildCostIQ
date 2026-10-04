import json
import os
from pathlib import Path

base = Path(__file__).resolve().parent
config = json.loads((Path(os.environ.get('ProgramData', 'C:/ProgramData')) / 'BuildCostIQ/server.json').read_text(encoding='utf-8-sig'))
os.environ.update({
    'BUILDCOSTIQ_DATA_ROOT': config['data_root'],
    'BUILDCOSTIQ_BACKUP_ROOT': config['backup_root'],
    'BUILDCOSTIQ_HOST': config.get('host', '0.0.0.0'),
    'BUILDCOSTIQ_PORT': str(config.get('port', 8787)),
    'BUILDCOSTIQ_DEPLOYMENT_MODE': 'central',
})
os.chdir(config['data_root'])
from adapters import LocalProjectWorkspace

class ProjectServerWorkspace(LocalProjectWorkspace):
    def _path(self, project_id):
        if str(project_id) != config['project_code']:
            raise ValueError('此安装仅允许配置的施工项目')
        return super()._path(project_id)

from gui import server
server.LocalProjectWorkspace = ProjectServerWorkspace
server.main([])
