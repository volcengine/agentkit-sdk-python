# AgentKit Harness Sidecar Extension

Public integration for configuring and launching the private Harness Sidecar
Runtime. Projects that use the capability can declare the SDK extra:

```bash
pip install "agentkit-sdk-python[harness-sidecar]"
```

The extension source is always bundled in the single SDK wheel, matching the
existing veADK extension convention. The extra does not change the wheel contents
and currently adds no public dependency; it is a stable install selector for
Sidecar users. The private Runtime artifact is supplied only by AgentKit-managed
cloud runtimes.
