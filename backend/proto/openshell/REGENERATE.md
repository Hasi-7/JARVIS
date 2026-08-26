# OpenShell gRPC stubs — regeneration

Generated Python stubs live in `backend/app/openshell_pb/`. **Do not hand-edit them.**

## Source

Protos are vendored from NVIDIA/OpenShell at the tag matching the **installed**
gateway version, not `main` — the wire format can drift between releases.

| | |
|---|---|
| Vendored tag | `v0.0.111` (see `.source-ref`) |
| Upstream | https://github.com/NVIDIA/OpenShell/tree/v0.0.111/proto |

Confirm the installed version before regenerating:

```bash
wsl -e openshell --version        # must match .source-ref
```

## Regenerate

From `backend/`:

```bash
# 1. Re-fetch protos at the installed tag
TAG=v0.0.111
for f in openshell sandbox datamodel inference options \
         compute_driver credential_driver gateway_interceptor supervisor_middleware; do
  curl -sL -o "proto/openshell/$f.proto" \
    "https://raw.githubusercontent.com/NVIDIA/OpenShell/$TAG/proto/$f.proto"
done

# 2. Generate
python -m grpc_tools.protoc -Iproto/openshell \
  --python_out=app/openshell_pb --pyi_out=app/openshell_pb \
  --grpc_python_out=app/openshell_pb \
  openshell.proto sandbox.proto datamodel.proto inference.proto options.proto \
  compute_driver.proto credential_driver.proto gateway_interceptor.proto \
  supervisor_middleware.proto

# 3. Rewrite protoc's flat imports into package-relative ones.
#    Without this the stubs only import when app/openshell_pb is on sys.path.
cd app/openshell_pb
sed -i -E 's/^import ([a-z_]+_pb2) as /from . import \1 as /; s/^import ([a-z_]+_pb2)$/from . import \1/' \
  *_pb2.py *_pb2_grpc.py
```

Step 3 is mandatory. `protoc` emits `import openshell_pb2`, which breaks when the
stubs are imported as `app.openshell_pb.*`.

## Connection facts (verified 2026-08-23)

- Endpoint `https://127.0.0.1:17670` inside WSL2; reachable from Windows at
  `localhost:17670` via WSL2 localhost forwarding.
- Transport is **gRPC over HTTP/2** (ALPN `h2`), TLS 1.3, **mTLS required**.
  Plain REST paths all return 404 — there is no REST API.
- Client certs: `\\wsl.localhost\Ubuntu\home\<user>\.config\openshell\gateways\<gw>\mtls\`
  (`ca.crt`, `tls.crt`, `tls.key`), readable from Windows over UNC.
- The gateway's server cert SAN covers `localhost`, `127.0.0.1`, and
  `host.openshell.internal`. Set `grpc.ssl_target_name_override` to
  `host.openshell.internal`, or connect to `localhost` and let it verify normally.
- Server reflection is **UNIMPLEMENTED** — vendored protos are the only contract.
- If using stdlib `ssl` rather than grpc: the gateway CA omits an Authority Key
  Identifier, so OpenSSL 3.x rejects it under `VERIFY_X509_STRICT`. Clear that flag
  rather than disabling verification.

## Useful read-only RPCs

Service `openshell.v1.OpenShell`:

| RPC | Use |
|---|---|
| `Health` | Liveness — returns `SERVICE_STATUS_HEALTHY` + version. Use for the runtime probe. |
| `GetGatewayInfo` | Version + configured compute drivers. |
| `ListSandboxes` | Enumerate sandboxes. |
| `GetCurrentUser` | Authenticated identity (`subject`, `roles`). |
| `GetSandboxPolicyStatus` / `ListSandboxPolicies` | Policy inspection. |
| `ExecSandbox` | **Privileged** — server-streaming command execution. Gate behind the approval queue. |
