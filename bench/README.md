# Aria Terminal-Bench

Harbor agent adapter for Aria AI agent to run Terminal-Bench 2.0 evaluations.

## Usage

```bash
harbor run -d terminal-bench@2.0 \
  --agent-import-path aria_terminal_bench:AriaAgent \
  -m anthropic/claude-sonnet-4-6
```
