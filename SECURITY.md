# Security

## Supply-chain posture

- Every release is scanned with [Cisco AI Defense `mcp-scanner`](https://github.com/cisco-ai-defense/mcp-scanner) (YARA analyzer) via the CI `security` workflow before publication to PyPI.
- Dependencies are pinned in `uv.lock`. Pin updates are reviewed before merge.
- The `colregs-mcp` package has no network dependencies at runtime — it reads only from the local vault path (`COLREGS_VAULT_PATH`). No outbound HTTP calls are made by the server.
- `requirements.yaml` and `regime-polygons.geojson` are local data files; they are not fetched from a remote source.

## Navigation safety disclaimer

The bundled `colregs-vault` is an **UNVERIFIED DRAFT**. `requirements.yaml` has not been independently certified against the official published rules. Do not use the output of `required_signals` or `check_compliance` as the sole basis for any real navigation decision. Always verify against the current official text of the applicable regulations.

## Reporting a vulnerability

If you discover a security issue in `colregs-mcp`, please report it privately rather than opening a public GitHub issue.

**Contact:** clarkbw@gmail.com — subject line `[colregs-mcp] Security`

Please include:
- A description of the issue and its potential impact
- Steps to reproduce
- Any suggested mitigation

We aim to acknowledge reports within 72 hours and resolve confirmed issues within 14 days.
