# API Reference

- `Runtime(capabilities)`: registers an explicit capability set and reports health.
- `CapabilityGateway.register(capability)`: accepts unique P01–P08 implementations only.
- `CapabilityGateway.execute(id, context)`: invokes a registered capability with a defensive copy.
- `ImmutableSourceStore.ingest(name, content, media_type)`: stores source bytes by SHA-256 without overwriting existing content.
- `ImmutableSourceStore.read(source)`: reads and verifies source integrity.

