from core import Runtime
from plugins import build_default_plugins


runtime = Runtime(build_default_plugins())
context = {"project_id": "demo-project", "source_id": "sanitized-source"}
for capability_id in runtime.gateway.registered:
    print(runtime.gateway.execute(capability_id, context))

