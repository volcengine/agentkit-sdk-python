# AgentKit Go base images

This directory contains the Dockerfiles used to publish the Go base images
referenced by the AgentKit Go templates.

## Images

- `agentkit-prod-public-cn-beijing.cr.volces.com/base/compile_basego:1.25`
- `agentkit-prod-public-cn-beijing.cr.volces.com/base/runtime_basego:latest`

## Build

```bash
docker build --platform linux/amd64 \
  -t agentkit-prod-public-cn-beijing.cr.volces.com/base/compile_basego:1.25 \
  docker/base-images/compile_basego/1.25

docker build --platform linux/amd64 \
  -t agentkit-prod-public-cn-beijing.cr.volces.com/base/runtime_basego:latest \
  docker/base-images/runtime_basego/latest
```

## Push

```bash
docker push agentkit-prod-public-cn-beijing.cr.volces.com/base/compile_basego:1.25
docker push agentkit-prod-public-cn-beijing.cr.volces.com/base/runtime_basego:latest
```
