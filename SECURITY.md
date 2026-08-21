# Security

Do not commit secrets or production project data. Report vulnerabilities privately to the maintainers. RC1 enforces the frozen capability allowlist, immutable evidence payloads, source hash verification, and content-addressed source storage. Authentication and authorization belong at the deployment boundary and must be configured before production use.

For a multi-terminal project deployment, run one central WebUI/API node inside the project LAN or an approved VPN. Bind it behind a firewall (and TLS/reverse proxy when leaving a trusted local network); do not expose the service directly to the public internet. Keep the live project database/state on the central service host, use the configured backup root for recovery copies, and never treat a writable SMB/shared folder as the live database. Terminals must use the API so project permissions, project IDs, audit events, source hashes and project-level write locks remain in one authority.
