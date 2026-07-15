# AgentKit Sandbox Commands

The AgentKit CLI provides `agentkit sandbox` helper commands for creating and
reusing AgentKit tool sandbox sessions.

## Install From Current Branch

Use editable mode when testing sandbox CLI changes from the current checkout:

```bash
cd /path/to/agentkit-sdk-python
python3 -m pip install -e .
```

If `uv` is used for the active environment:

```bash
cd /path/to/agentkit-sdk-python
uv pip install -e .
```

If an older PyPI installation shadows the current checkout, uninstall it first
and then reinstall this branch:

```bash
python3 -m pip uninstall agentkit-sdk-python
python3 -m pip install -e .
```

Verify that the CLI is available from the current branch:

```bash
agentkit --help
python3 -m pip show agentkit-sdk-python
```

## Commands

### Build

Build and push a custom sandbox image with Volcano Engine Code Pipeline and
Container Registry. The command packages the project directory, uploads the
archive to TOS, creates or reuses the sandbox image build pipeline, and pushes
the resulting image to CR.

```bash
agentkit sandbox build \
  --project-dir ./sandbox-image \
  --dockerfile Dockerfile \
  --image-name agentkit-custom-sandbox-image \
  --namespace agentkit \
  --tag "{{timestamp}}"
```

Options:

- `--project-dir`: optional. Project directory to package as the Docker build
  context; defaults to the current directory.
- `--dockerfile`: optional. Dockerfile path relative to `--project-dir`;
  defaults to `Dockerfile`.
- `--image-name` / `--repo`: optional. Container Registry repository name;
  defaults to `agentkit-custom-sandbox-image`.
- `--namespace`: optional. Container Registry namespace; defaults to
  `agentkit`.
- `--tag`: optional. Container image tag; defaults to `{{timestamp}}`.

### Init Dockerfile

Create a Dockerfile template for a custom sandbox image.

```bash
agentkit sandbox init-dockerfile --template package
agentkit sandbox init-dockerfile --template skill
agentkit sandbox init-dockerfile --template web-server
agentkit sandbox init-dockerfile --template package -o ./Dockerfile
```

Options:

- `--template` / `-t`: optional. Dockerfile template to generate. Currently
  available: `package`, `skill`, `web-server`.
- `--output` / `-o`: optional. Output Dockerfile path. Defaults to
  `Dockerfile.install-package` for `package`, `Dockerfile.install-skills` for
  `skill`, and `Dockerfile.web-server` for `web-server`.
- `--force` / `-f`: optional. Overwrite the output file if it already exists.

The `skill` template copies local Codex skills from `./skills/` in the Docker
build context into `/home/gem/.codex/skills/`, matching the sandbox CodeEnv
`CODEX_HOME`.

The `web-server` template exposes nginx on port `8080` and proxies `/app/` to a
local server on `127.0.0.1:8000`. Put server code under `./server/` and adjust
the route or command in the generated Dockerfile as needed.

### Create

Create an AgentKit Tool for sandbox sessions. This command builds a `CreateTool`
request, waits until the tool reaches `Ready`, and prints the created tool ID.
When `--tos-bucket` is provided, it also prepares the backing TOS bucket/path and
mounts it into sandbox sessions.

```bash
agentkit sandbox create \
  --tool-type CodeEnv \
  --tool-name demo-sandbox-tool \
  --tos-bucket agentkit-platform-example
```

Options:

- `--tool-type`: optional. Tool type to create; defaults to `CodeEnv`.
  `Private` creates a private-image tool and applies the CLI's default
  aio-sandbox environment, command, and port profile.
- `--tool-name`: optional. Tool name. If omitted, the CLI generates a name like
  `agentkit-codeenv-<random>`.
- `--image-url`: optional custom image URL. Required when
  `--tool-type Private`.
- `--tos-bucket`: optional. TOS bucket to mount. If omitted, the tool is
  created without TOS mount configuration.
- `--tos-mount`: optional. Local mount path for `--tos-bucket`; defaults to
  `/home/gem/workspace`.
- `--cpu`: optional. Sandbox vCPU count; allowed values are `2`, `4`, `8`, and
  `16`. Defaults to `4`. Memory is derived as 2 GiB per vCPU.
- `--enable-snapshot`: optional. Enables snapshot support for the created
  sandbox tool. If omitted, the CLI does not send `EnableSnapshot` in the
  `CreateTool` request.
- `--network-config`: optional. Network configuration as inline JSON or a path
  to a JSON file. If omitted, the tool is created with public access enabled
  and private access disabled.
- `--model-provider`: optional. Model provider marker to inject into
  `AGENTKIT_SANDBOX_MODEL_PROVIDER`; defaults to `model_square`, or
  `byteplus_model_square` when `CLOUD_PROVIDER` / `AGENTKIT_CLOUD_PROVIDER` is
  `byteplus`. The built-in providers `model_square`, `coding_plan`,
  `agent_plan`, `byteplus_model_square`, and `byteplus_coding_plan` also
  provide base URLs, default models, and Codex model catalog entries. Other
  provider strings are passed through without built-in URL or catalog handling.
- `--model-name`: optional. Injected into the tool as `OPENCODE_MODEL`,
  `CODEX_MODEL`, and `ANTHROPIC_MODEL`. If omitted for a built-in provider,
  that provider's default model is used. Custom model names are allowed and are
  added to the Codex model catalog with default capabilities.
- `--model-base-url`: optional. Injected into `OPENCODE_BASE_URL`,
  `CODEX_BASE_URL`, `MODEL_BASE_URL`, and `ANTHROPIC_BASE_URL`. When provided,
  it takes precedence over provider base URLs. Built-in providers still receive
  `CODEX_CONFIG_TOML` and `CODEX_MODEL_CATALOG_JSON`; custom providers receive
  `CODEX_CONFIG_TOML` without `model_catalog_json`. If a custom provider name is
  reserved by Codex, such as `openai`, the generated Codex provider ID is
  renamed, for example to `openai-custom`. Non-Ark custom URLs require
  `--model-provider`.
- `--model-api-key`: optional. Injected into the tool as `OPENCODE_API_KEY`,
  `CODEX_API_KEY`, and `ANTHROPIC_AUTH_TOKEN`. If omitted, the CLI uses
  `MODEL_API_KEY` when that environment variable is set.

The sandbox create request maps `--cpu` to `CpuMilli=<cpu * 1000>` and
`MemoryMb=<cpu * 2048>`, so the default shape is 4 vCPU / 8 GiB.
When `--enable-snapshot` is present, the request also includes
`EnableSnapshot=true`; otherwise that field is omitted.

Network configuration uses the same access concepts as the AgentKit console:

```json
{
  "private_access": true,
  "public_access": true,
  "vpc_id": "vpc-xxxxxxxx",
  "subnet_ids": ["subnet-aaaaaaaa"],
  "enable_shared_internet_access": true
}
```

`public_access` defaults to `true`; `private_access` defaults to `false`.
When `private_access` is `true`, `vpc_id` is required. `subnet_ids` may be an
array of strings or a comma-separated string. The CLI validates JSON syntax,
field names, field types, and field combinations before calling `CreateTool`.
VPC and subnet existence or availability errors are returned by the control
plane.

Examples:

```bash
agentkit sandbox create \
  --network-config network.json

agentkit sandbox create \
  --network-config '{"private_access":true,"public_access":true,"vpc_id":"vpc-xxxxxxxx","subnet_ids":["subnet-aaaaaaaa"]}'
```

When `--tool-type Private` is used, the CLI creates a private-image tool and
applies the default aio-sandbox startup profile:

```bash
agentkit sandbox create \
  --tool-type Private \
  --image-url registry.example.com/custom-image:latest
```

The CreateTool request uses `ToolType: Private`, `Command: /opt/gem/run.sh`,
port `8080`, and the environment variables matching the aio-sandbox startup
profile. Future CLI options may expose command, port, and environment overrides.

The tool injects the selected built-in provider's Ark-compatible
endpoints into `OPENCODE_BASE_URL`, `CODEX_BASE_URL`, `MODEL_BASE_URL`, and
`ANTHROPIC_BASE_URL`, and stores the selected provider in
`AGENTKIT_SANDBOX_MODEL_PROVIDER`. For built-in provider URLs, the same provider
ID and base URL are written into `CODEX_CONFIG_TOML`, and provider-supported
models are written into `CODEX_MODEL_CATALOG_JSON`. The create request also
injects
`BROWSER_EXTRA_ARGS` for browser startup inside the sandbox:

```sh
--enable-unsafe-swiftshader --use-gl=angle --use-angle=swiftshader-webgl --ignore-gpu-blocklist
```

Provider defaults:

| Provider | Default model | Model base URL |
| --- | --- | --- |
| `model_square` | `glm-5-2-260617` | `https://ark.cn-beijing.volces.com/api/v3` |
| `coding_plan` | `deepseek-v4-flash` | `https://ark.cn-beijing.volces.com/api/coding/v3` |
| `agent_plan` | `deepseek-v4-flash` | `https://ark.cn-beijing.volces.com/api/plan/v3` |
| `byteplus_model_square` | `deepseek-v4-flash-260425` | `https://ark.ap-southeast.bytepluses.com/api/v3` |
| `byteplus_coding_plan` | `dola-seed-2.0-pro` | `https://ark.ap-southeast.bytepluses.com/api/coding/v3` |

Credential resolution is delegated to the underlying SDK/service clients:
`AgentkitToolsClient` handles `CreateTool` credentials, and `TOSService` handles
TOS credentials. The command supports the same credential sources as the shared
Volcengine configuration, including environment variables and global
`agentkit config --global` settings.

When `--tos-bucket` is set, the generated tool TOS mount uses
`LocalMountPath: /home/gem/workspace` by default, or the path provided by
`--tos-mount`:

```text
BucketPath: /sandbox-session/default/default
LocalMountPath: /home/gem/workspace
Endpoint: http://tos-<region>.ivolces.com
```

When `sandbox exec` or `sandbox shell` later creates a session from a tool with
TOS configuration, the session flow calls `GetTool`, reads this mount
configuration, and mounts a per-session path:

```text
/sandbox-session/tool-<tool-id>/session-<session-id>/
```

If the tool was created without `--tos-bucket`, `GetTool` has no TOS mount
configuration and session creation skips TOS mounting.

After the tool reaches `Ready`, `agentkit sandbox create` writes the tool
information to `.agentkit/sandbox/tools.json`. Only one tool record is stored
per `ToolType`; creating or resolving another tool of the same type replaces
that type's record. Tools created or resolved with snapshot support include
`EnableSnapshot: true`; older cached records without this field are treated as
snapshot-disabled.

### Get

Sync sessions for the current tool, then read sandbox sessions from the local
session store.

```bash
agentkit sandbox get --session-id 123456789
agentkit sandbox get
```

Options:

- `--session-id` / `--sid` / `-s`: optional. Sandbox session ID to look up. If omitted, the CLI
  returns all records from `.agentkit/sandbox/sessions.json` after syncing the
  current tool.
- `--tool-id`: optional. Defaults to `AGENTKIT_SANDBOX_TOOL_ID`. If neither is
  set, the CLI resolves an existing tool by `--tool-type`.
- `--tool-type`: optional. `CodeEnv` or `SkillEnv`; defaults to `CodeEnv`.
  Used when resolving the current tool after `--tool-id` and
  `AGENTKIT_SANDBOX_TOOL_ID` are both absent.

Before returning, `get` calls `ListSessions` for the resolved tool and follows
`NextToken` until all pages are loaded. The returned remote sessions replace
the same tool's records in `.agentkit/sandbox/sessions.json`; records for other
tools are preserved. Sessions whose `UserSessionId` is empty are ignored because
they were not created through this CLI's session flow. When `--session-id` is
omitted and no existing tool can be resolved, the command skips remote sync and
returns the current local store, or `{}` if the store does not exist.

When `--session-id` is provided but the session is not found after sync, the
command exits with status `1` and returns structured JSON:

```json
{
  "tool_id": "t-example",
  "session_id": "123456789",
  "error_msg": "Sandbox session not found: 123456789"
}
```

### SCP

Copy one file or directory between local storage and an existing sandbox
session. `scp` operates only on existing sessions; it does not create a session
when `--session-id` is missing.

Common options:

- `--session-id` / `--sid` / `-s`: required. Sandbox session ID used for the
  transfer.
- `--tool-id`: optional. Defaults to `AGENTKIT_SANDBOX_TOOL_ID`. If neither is
  set, the CLI resolves an existing tool by `--tool-type`.
- `--tool-type`: optional. `CodeEnv` or `SkillEnv`; defaults to `CodeEnv`.

Path rules:

- Local paths are normal local filesystem paths.
- Sandbox paths must be prefixed with `sandbox:`.
- Exactly one of `SOURCE` and `DESTINATION` must be a sandbox path.
- `sandbox:/absolute/path` is used as-is after normalization.
- `sandbox:relative/path` is resolved under `/home/gem`.
- Relative sandbox paths that escape `/home/gem` through `..` are rejected.
- Empty sandbox paths and paths containing NUL bytes are rejected.
- As with Linux `scp`, the destination's parent directory must already exist.

Upload a local file or directory:

```bash
agentkit sandbox scp -s 123456789 ./project sandbox:/home/gem/project
agentkit sandbox scp -s 123456789 ./a.txt sandbox:uploads/a.txt
```

Download from a sandbox:

```bash
agentkit sandbox scp -s 123456789 sandbox:/home/gem/project ./project-copy
agentkit sandbox scp -s 123456789 sandbox:uploads/a.txt ./downloads/
```

Implementation notes:

- Directories are copied recursively.
- Existing files are overwritten, and existing directories are merged, matching
  Linux `scp` behavior.
- File/directory type collisions are rejected.
- Transfers use temporary tar archives internally. Remote temporary archives are
  cleaned up after transfer; cleanup failures print a warning without masking
  the original result.
- Downloaded archive members must be relative regular files or directories;
  links, absolute paths, and `..` traversal are rejected.

### Shell

Execute a command in a sandbox shell.

```bash
agentkit sandbox shell \
  --session-id 123456789 \
  --command 'echo $TEST_VAR'

agentkit sandbox shell \
  --session-id 123456789 \
  --command 'ls -la /home/gem/project' \
  --copy ./README.md sandbox:/home/gem/project/README.md \
  --copy ./requirements.txt project/requirements.txt
```

Options:

- `--session-id` / `--sid` / `-s`: optional. Sandbox session ID used as the local session key.
  If omitted, a UUID is generated and the command creates a sandbox session
  through the same idempotent session ensure flow as `sandbox exec`.
- `--tool-id`: optional. Defaults to `AGENTKIT_SANDBOX_TOOL_ID`. If neither is
  set, the CLI resolves a tool by `--tool-type`.
- `--tool-type`: optional. `CodeEnv` or `SkillEnv`; defaults to `CodeEnv`.
  Used when resolving or creating a tool after `--tool-id` and
  `AGENTKIT_SANDBOX_TOOL_ID` are both absent.
- `--command`: required. Command to execute in the sandbox.
- `--exec-dir`: optional execution directory.
- `--copy SOURCE DESTINATION`: optional local-to-sandbox copy before executing
  the shell command. May be repeated. `DESTINATION` may be `sandbox:/absolute`
  or relative; relative destinations are resolved under `/home/gem`.

The command posts to `<endpoint>/v1/shell/exec` with:

```json
{
  "id": "",
  "exec_dir": "",
  "command": "echo $TEST_VAR"
}
```

The response is returned as JSON. If the service returns `data.session_id`, the
CLI renames it to `data.shell_id`.

When `--copy` is provided, `shell` uploads each local source before executing
`--command`. Sandbox sources are not supported by `--copy`; use `sandbox scp`
for downloads.

### Web

Return a browser URL for a sandbox session.

```bash
agentkit sandbox web --session-id 123456789
agentkit sandbox web --session-id 123456789 --tool-id t-example
```

Options:

- `--session-id` / `--sid` / `-s`: required. Sandbox session ID to open in a browser.
- `--tool-id`: optional. Defaults to `AGENTKIT_SANDBOX_TOOL_ID`. The
  underscore alias `--tool_id` is also accepted.

The command resolves the tool using the same existing-tool resolution flow as
the other session-scoped sandbox commands, syncs remote sessions for that tool,
then reads the session endpoint and appends `/vnc/index.html` with fixed
browser parameters: `autoconnect=true`, `resize=scale`, and `reconnect=1`.
When the endpoint includes `faasInstanceName` and `Authorization`, the command
also derives the VNC `path` query parameter from those values. The URL is opened
with the system default browser, and the response is JSON:

```json
{
  "url": "https://example.com/vnc/index.html?autoconnect=true&resize=scale&reconnect=1&faasInstanceName=vefaas-example&Authorization=...&path=websockify%3FfaasInstanceName%3Dvefaas-example%26Authorization%3D...",
  "tool_id": "t-example",
  "session_id": "123456789"
}
```

### Mount

Open a sandbox session's TOS path in TOS Browser.

```bash
agentkit sandbox mount \
  --session-id 123456789 \
  --oauth-url https://example.com/oauth
agentkit sandbox mount --session-id 123456789
```

Options:

- `--session-id` / `--sid` / `-s`: required. Sandbox session ID to mount.
- `--oauth-url`: optional. Base URL used to fetch
  `/.well-known/agentkit-cli`. If omitted, the CLI uses the newest file under
  `~/.agentkit/auth/sessions/`, validates the file name matches
  `agentkit-cli-*volces.com.json`, removes the `.json` suffix, and uses that as
  the OAuth URL.

The CLI reads `tool_id` from `.agentkit/sandbox/sessions.json` by
`--session-id`. If the session is not found locally, it syncs sessions for the
current tool using the same resolution behavior as `agentkit sandbox get`, then
checks the local session store again. After resolving the tool, the CLI calls
`GetTool` and reads the bucket from `TosMountConfig.MountPoints[].BucketName`;
if the tool has no TOS mount, the command exits with an error. The discovery
document is saved to `.agentkit/sandbox/agentkit-cli`. The CLI extracts
`role_trn`, `client_id`, and the user pool ID from `issuer`, then runs
`open "<command>"`, where `command` is the generated `tosbrowser://...` URL.
The response is JSON:

```json
{
  "tool_id": "t-example",
  "session_id": "123456789",
  "command": "tosbrowser://open?path=tos://sandbox-bucket/sandbox-session/tool-t-example/session-123456789/&type=oAuthLogin&role=...&userPool=...&clientId=..."
}
```

If macOS reports that no application can open the `tosbrowser://` URL, the CLI
returns JSON with the original `open` error and a TosBrowser install hint.

### Exec

Open a streaming WebSocket exec session to the sandbox. By default, this connects
without running an initial command.

```bash
agentkit sandbox exec --session-id 123456789
agentkit sandbox exec --session-id 123456789 --copy ./workspace sandbox:/home/gem/workspace
agentkit sandbox exec --session-id 123456789 --copy ./main.py project/main.py
agentkit sandbox exec --session-id 123456789 --copy ./README.md tmp/README.md --copy ./requirements.txt tmp/requirements.txt
```

Options:

- `--session-id` / `--sid` / `-s`: optional. Sandbox session ID used as the local
  session key. If omitted, a UUID is generated and the command creates a
  sandbox session through the same idempotent session ensure flow.
- `--tool-id`: optional. Defaults to `AGENTKIT_SANDBOX_TOOL_ID`. If neither is
  set, the CLI resolves a tool by `--tool-type`.
- `--tool-type`: optional. `CodeEnv` or `SkillEnv`; defaults to `CodeEnv`.
  Used when resolving or creating a tool after `--tool-id` and
  `AGENTKIT_SANDBOX_TOOL_ID` are both absent.
- `--command`: optional. Initial command to run after the exec session is ready.
  Omit this option to connect without running an initial command. Use
  `--command codex` to start the remote Codex TUI.
- `--mode`: optional. Omit this option or pass an empty value for the default
  `--command` behavior. Use `--mode tmux` to replace `--command` with

  ```bash
  tmux has-session -t <session-id> 2>/dev/null && tmux a -t <session-id> || tmux new -s <session-id> <command>
  ```

  Repeated execs then attach to the same tmux session.
- `--copy SOURCE DESTINATION`: optional local-to-sandbox copy before opening
  the exec session. May be repeated. `DESTINATION` may be `sandbox:/absolute`
  or relative; relative destinations are resolved under `/home/gem`.
- `--model-name`: optional. When creating a sandbox session, injects the value
  as `OPENCODE_MODEL`, `CODEX_MODEL`, and `ANTHROPIC_MODEL`. Custom model names
  are allowed.
- `--model-provider`: optional. When creating a sandbox session, injects the
  provider marker. The built-in providers `model_square`, `coding_plan`,
  `agent_plan`, `byteplus_model_square`, and `byteplus_coding_plan` also
  provide default models, base URL envs, and `CODEX_CONFIG_TOML` /
  `CODEX_MODEL_CATALOG_JSON` updates for `CodeEnv` sessions. Other provider
  strings are passed through without built-in URL or catalog handling.
- `--model-base-url`: optional. When creating a sandbox session, injects the
  value into `OPENCODE_BASE_URL`, `CODEX_BASE_URL`, `MODEL_BASE_URL`, and
  `ANTHROPIC_BASE_URL`. When provided, it takes precedence over provider base
  URLs. Built-in providers still receive `CODEX_CONFIG_TOML` and
  `CODEX_MODEL_CATALOG_JSON`; custom providers receive `CODEX_CONFIG_TOML`
  without `model_catalog_json`. If a custom provider name is reserved by Codex,
  such as `openai`, the generated Codex provider ID is renamed, for example to
  `openai-custom`. Non-Ark custom URLs require `--model-provider`.
- `--model-api-key`: optional. When creating a sandbox session, injects the
  value as `OPENCODE_API_KEY`, `CODEX_API_KEY`, and `ANTHROPIC_AUTH_TOKEN`. If
  omitted, the CLI uses `MODEL_API_KEY` when that environment variable is set.

The command connects to `<endpoint>/v1/shell/ws`, streams remote output to local
stdout, forwards local stdin as terminal input, sends terminal resize events, and
responds to WebSocket `ping` messages with `pong`.

When `--copy` is provided, the command uploads each local source before opening
the WebSocket exec connection. Sandbox sources are not supported by `--copy`;
use `sandbox scp` for downloads.

When the resolved tool has `TosMountConfig.MountPoints` in `GetTool`, session
creation passes those mount points to `CreateSession` and uses each returned
`LocalMountPath` as-is.

When the remote terminal returns a shell session ID, the CLI prints it and
stores it in the `terminal_shell_id` list in `.agentkit/sandbox/sessions.json`
while the connection is active. Multiple live WebSocket connections under the
same sandbox `session_id` are tracked in the same list. The CLI removes only the
current shell ID from the list when that connection is detached or closed.

When `--model-name` is provided without `--model-provider`, `exec` first tries
to reuse `AGENTKIT_SANDBOX_MODEL_PROVIDER` from the cached or remote tool
configuration. When no marker is available, it falls back to `model_square`, or
`byteplus_model_square` when `CLOUD_PROVIDER` / `AGENTKIT_CLOUD_PROVIDER` is
`byteplus`.
For built-in providers, it updates `CODEX_CONFIG_TOML` /
`CODEX_MODEL_CATALOG_JSON` for `CodeEnv` sessions. If the tool carries a custom
model base URL, exec inherits that URL and writes it into the generated Codex
provider config. Custom providers omit `model_catalog_json`; reserved Codex
provider IDs such as `openai` are renamed in the generated config.

Press `Ctrl-]`, or type `exit` / `exit()`, to detach from the local terminal.
`Ctrl-C` is forwarded to the remote process, which is useful for interrupting
Codex or shell commands without closing the local WebSocket client.

### Run

Open a local macOS Terminal tab with a tiled `tmux` layout and run different
`sandbox exec` commands from a YAML file. For `--terminal 4`, the four exec
sessions are arranged as a 2x2 grid. The CLI writes short temporary launcher
scripts and asks Terminal to run the launcher, so long prompts and quoted
commands are not embedded directly in AppleScript.

```bash
agentkit sandbox run --terminal 4
agentkit sandbox run --config sandbox-run.yaml --terminal 4 --dry-run
```

By default, the command reads `agentkit-sandbox-run.yaml`. The YAML can be a
top-level list or contain `exec`, `execs`, `tabs`, or `commands`:

```yaml
exec:
  - name: agent-a
    session_id: agent-a
    tool_id: t-example
    command: codex
    copy:
      - [./workspace, sandbox:/home/gem/project]
      - [./README.md, project/README.md]
  - name: agent-b
    args:
      - --session-id
      - agent-b
      - --command
      - opencode
```

Mapping entries support the same option names as `sandbox exec`, written with
underscores, such as `session_id`, `tool_id`, `tool_type`, `command`, `mode`,
`shell_id`, `git_config`, `model_name`, `model_api_key`, `model_provider`, and
`model_base_url`. Use `copy` or `copies` for one `[SOURCE, DESTINATION]` pair or
a list of pairs. Use `args` when you want to provide raw `sandbox exec`
arguments directly.

## Local Store

`agentkit sandbox exec` writes session results to:

```text
.agentkit/sandbox/sessions.json
```

The file is a JSON object keyed by `session_id`:

```json
{
  "123456789": {
    "session_id": "123456789",
    "tool_id": "t-example",
    "instance_id": "s-example",
    "endpoint": "https://example.com/?Authorization=...",
    "terminal_shell_id": ["shell-example"]
  }
}
```

Repeated exec opens with the same `session_id` refresh the previous
entry when the remote session is reachable, or overwrite it after recreating the
remote session.

When `--tool-id` and `AGENTKIT_SANDBOX_TOOL_ID` are both omitted,
`sandbox exec` and `sandbox shell` resolve one tool per type through:

1. `.agentkit/sandbox/tools.json`
2. `ListTools` filtered by `ToolType`
3. automatic `agentkit sandbox create --tool-type <type>`-equivalent creation

Cached and listed tools are reused only when their status is `Ready`; tools in
states such as `Creating`, `Error`, `Deleting`, or `Deleted` are ignored.
When a tool ID is provided explicitly, read from `AGENTKIT_SANDBOX_TOOL_ID`,
reused from an existing session record, or loaded from
`.agentkit/sandbox/tools.json`, the CLI calls `GetTool` before using it. If the
tool does not exist or its current status is not `Ready`, the command exits
with that error instead of creating a session against an unusable tool.

Resolved tool records are stored in:

```text
.agentkit/sandbox/tools.json
```

Example:

```json
{
  "CodeEnv": {
    "ToolId": "t-code-example",
    "Name": "agentkit-codeenv-example",
    "Status": "Ready",
    "ToolType": "CodeEnv",
    "EnableSnapshot": true
  },
  "SkillEnv": {
    "ToolId": "t-skill-example",
    "Name": "agentkit-skillenv-example",
    "Status": "Ready",
    "ToolType": "SkillEnv"
  }
}
```

## Module Layout

- `cli.py`: registers the sandbox subcommands.
- `../cli.py`: registers the `sandbox` command group.
- `session_create.py`: shared session creation and idempotent ensure helpers.
- `session_sync.py`: shared remote session list/sync helpers.
- `tool_resolve.py`: shared sandbox tool resolution and local tool cache helpers.
- `cli_create.py`: create command implementation.
- `cli_get.py`: get command implementation.
- `cli_shell.py`: shell command implementation.
- `cli_exec.py`: streaming exec command implementation.
- `cli_run.py`: multi-tab exec runner implementation.
- `cli_file.py`: sandbox `scp` transfer implementation.
- `sandbox_client.py`: shared store, URL, JSON, and error helpers.
