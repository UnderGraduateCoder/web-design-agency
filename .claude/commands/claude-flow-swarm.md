---
name: claude-flow-swarm
description: Coordinate multi-agent swarms for complex tasks
---

# Claude-Flow Swarm

```bash
./claude-flow swarm "task" --strategy <type> [options]
```

## Strategies
`auto` · `development` · `research` · `analysis` · `testing` · `optimization` · `maintenance`

## Coordination Modes
`centralized` (default) · `distributed` · `hierarchical` · `mesh` · `hybrid`

## Key Options

| Flag | Default | Description |
|---|---|---|
| `--strategy` | auto | Execution strategy |
| `--mode` | centralized | Coordination mode |
| `--max-agents` | 5 | Max concurrent agents |
| `--timeout` | 60 min | Timeout |
| `--background` | — | Long-running tasks (>30 min) |
| `--monitor` | — | Real-time monitoring |
| `--parallel` | — | Parallel execution |
| `--review` | — | Peer review process |
| `--testing` | — | Automated testing |
| `--dry-run` | — | Preview without executing |

## Examples

```bash
# Development with review + testing
./claude-flow swarm "Build REST API" --strategy development --monitor --review --testing

# Long-running research in background
./claude-flow swarm "Analyze market trends" --strategy research --background --max-agents 8

# Performance optimization
./claude-flow swarm "Optimize database queries" --strategy optimization --testing --parallel
```

## Monitoring

```bash
./claude-flow monitor            # Real-time activity
./claude-flow status --verbose   # Detailed swarm status
./claude-flow agent list         # List active agents
```

## Memory Integration

```bash
./claude-flow memory store "key" "value" --namespace swarm
./claude-flow memory query "search" --namespace swarm
```

Docs: https://github.com/ruvnet/claude-code-flow/docs/swarm-system.md
