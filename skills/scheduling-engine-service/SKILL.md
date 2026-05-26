---
name: scheduling-engine-service
description: Use for candidate-defined scheduling API workflows.
disable-model-invocation: true
---

# Scheduling Engine Service

This skill is intentionally incomplete.

## TODOs For Candidate

- Define your API contract in this file (endpoints + payloads).
- Define the query language/constraint grammar agents should send.
- Add one happy-path workflow.
- Add one diagnostics workflow ("why no results").
- Add one failure workflow (invalid request, unsupported constraint, etc.).
- Add output format expectations so agent responses are consistent.

## Utility Script

Use `scripts/search.py` for quick local calls:

```bash
python skills/scheduling-engine-service/scripts/search.py --base-url http://127.0.0.1:8000
```

Replace this command and script behavior once your contract is finalized.
