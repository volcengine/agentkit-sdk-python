# AgentKit Go base images

This directory records the Go base images referenced by the AgentKit Go
templates.

The `compile_basego:1.25` Dockerfile is reconstructed from the published image
config/history. The image published to the prod public registry was copied from
the existing cn-beijing registry image by retagging and pushing.

## Images

- `agentkit-prod-public-cn-beijing.cr.volces.com/base/compile_basego:1.25`
- `agentkit-prod-public-cn-beijing.cr.volces.com/base/runtime_basego:latest`

## Build

```bash
docker build --platform linux/amd64 \
  -t agentkit-cn-beijing.cr.volces.com/base/compile_basego:1.25 \
  docker/base-images/compile_basego/1.25
```

## Publish history

```bash
docker tag \
  agentkit-cn-beijing.cr.volces.com/base/compile_basego:1.25 \
  agentkit-prod-public-cn-beijing.cr.volces.com/base/compile_basego:1.25

docker push agentkit-prod-public-cn-beijing.cr.volces.com/base/compile_basego:1.25

docker tag \
  agentkit-cn-beijing.cr.volces.com/base/runtime_basego:latest \
  agentkit-prod-public-cn-beijing.cr.volces.com/base/runtime_basego:latest

docker push agentkit-prod-public-cn-beijing.cr.volces.com/base/runtime_basego:latest
```
