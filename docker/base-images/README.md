# AgentKit Go base images

This directory records the Go base images referenced by the AgentKit Go
templates.

The original Dockerfiles for these base images are not currently available in
this repository. The images published to the prod public registry were copied
from the existing cn-beijing registry images by retagging and pushing.

## Images

- `agentkit-prod-public-cn-beijing.cr.volces.com/base/compile_basego:1.25`
- `agentkit-prod-public-cn-beijing.cr.volces.com/base/runtime_basego:latest`

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
