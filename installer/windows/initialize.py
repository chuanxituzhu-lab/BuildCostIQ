"""Read bootstrap JSON from stdin, never from command-line credentials."""
import json
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo
from adapters import LocalAuthStore, LocalProjectWorkspace, ROLE_PROJECT_MANAGER

def initialize(c):
    for key in ('data_root','backup_root'):
        candidate=Path(c[key])
        if not candidate.is_absolute() or candidate.resolve()==Path(candidate.anchor):
                    raise ValueError('数据和备份目录必须使用绝对项目路径，不能是盘符根目录')
        for name in ('SystemRoot','ProgramFiles','ProgramFiles(x86)','ProgramData'):
            protected=os.environ.get(name)
            if protected:
                target=Path(protected).resolve()
                if candidate.resolve()==target or candidate.resolve() in target.parents:
                    raise ValueError('数据和备份目录不能是受保护的系统目录或其上级目录')
    data, backup = Path(c['data_root']).resolve(), Path(c['backup_root']).resolve()
    if data == backup or data in backup.parents or backup in data.parents:
        raise ValueError('数据目录和备份目录必须相互独立，不能相同或互相包含')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', c['project_code']):
        raise ValueError('项目编码只能使用英文字母、数字、下划线或短横线，长度不超过64位')
    if not re.fullmatch(r'[A-Z]{3}', c['currency']):
        raise ValueError('货币代码必须为3位大写英文字母')
    try:
        ZoneInfo(c['timezone'])
    except Exception as exc:
        raise ValueError('时区无效，请使用 IANA 格式，例如 Asia/Shanghai') from exc
    if not c['project_name'].strip() or len(c['password']) < 8:
        raise ValueError('请填写项目名称；管理员密码至少8位，可含字母和符号')
    data.mkdir(parents=True, exist_ok=True)
    backup.mkdir(parents=True, exist_ok=True)
    if (data / 'installation.json').exists():
        raise ValueError('检测到已有项目数据，已拒绝覆盖')
    auth = LocalAuthStore(data / 'auth')
    if auth.list_public_users() or list((data / 'projects').glob('*.json')):
        raise ValueError('数据目录中已有账号或项目，已拒绝覆盖')
    user = auth.register(c['username'], c['password'], ROLE_PROJECT_MANAGER)
    LocalProjectWorkspace(data / 'projects').create(c['project_code'], c['project_name'])
    auth.add_user_to_project(c['project_code'], user['id'])
    public = {k: v for k, v in c.items() if k != 'password'}
    (data / 'installation.json').write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding='utf-8')
    return public

if __name__ == '__main__':
    # Windows PowerShell/.NET Framework can prefix redirected stdin with a
    # UTF-8 BOM. Accept either form without making the caller's JSON fragile.
    initialize(json.loads(sys.stdin.buffer.read().decode('utf-8-sig')))
