---
name: claude-flow-help
description: Show Claude-Flow commands and usage
---

# Claude-Flow Commands

## System
```bash
./claude-flow start [--ui]    # Start orchestration (--ui for process management UI)
./claude-flow status          # System status
./claude-flow monitor         # Real-time monitoring
./claude-flow stop            # Stop orchestration
```

## Agents
```bash
./claude-flow agent spawn <type>     # Create agent
./claude-flow agent list             # List active agents
./claude-flow agent terminate <id>   # Stop agent
```

## Tasks
```bash
./claude-flow task create <type> "description"
./claude-flow task list / status <id> / cancel <id>
./claude-flow task workflow <file>
```

## Memory
```bash
./claude-flow memory store "key" "value" [--namespace ns]
./claude-flow memory query "search" [--namespace ns]
./claude-flow memory export <file> / import <file>
./claude-flow memory stats
```

## SPARC
```bash
./claude-flow sparc "task"              # SPARC orchestrator
./claude-flow sparc modes               # List 17+ modes
./claude-flow sparc run <mode> "task"
./claude-flow sparc tdd "feature"
```

## Swarm
```bash
./claude-flow swarm "task" --strategy <type> [--background] [--monitor] [--distributed]
```

## Quick Examples
```bash
# Init with SPARC
npx -y claude-flow@latest init --sparc

# Development swarm
./claude-flow swarm "Build REST API" --strategy development --monitor --review

# TDD workflow
./claude-flow sparc tdd "user authentication"
```

Docs: https://github.com/ruvnet/claude-code-flow/docs
