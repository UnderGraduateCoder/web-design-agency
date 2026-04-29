---
name: claude-flow-memory
description: Interact with Claude-Flow memory system
---

# Claude-Flow Memory

## Store & Query
```bash
./claude-flow memory store "key" "value" [--namespace ns]
./claude-flow memory query "search" [--namespace ns] [--limit 10]
./claude-flow memory stats [--namespace ns]
```

## Export / Import / Cleanup
```bash
./claude-flow memory export backup.json [--namespace ns]
./claude-flow memory import backup.json
./claude-flow memory cleanup --days 30 [--namespace ns]
```

## Namespaces
`default` · `agents` · `tasks` · `sessions` · `swarm` · `project` · `spec` · `arch` · `impl` · `test` · `debug`

## Examples
```bash
# Store SPARC context
./claude-flow memory store "spec_auth" "OAuth2 + JWT with refresh tokens" --namespace spec
./claude-flow memory store "arch_api" "RESTful microservices" --namespace arch

# Query decisions
./claude-flow memory query "authentication" --namespace arch --limit 5

# Backup
./claude-flow memory export project-$(date +%Y%m%d).json --namespace project
```
