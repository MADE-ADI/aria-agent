#!/usr/bin/env python3
"""
Aria Terminal Agent v2.0 — optimized for Terminal-Bench 2.0 leaderboard.

Key features for high benchmark scores:
- Structured planning before execution
- Smart error recovery with multiple strategies
- Context-aware file editing (sed, awk, python3, patch)
- Automatic test discovery and verification
- Output truncation with smart summarization
- Adaptive retries with backoff
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import httpx

# ================================================================
# CONFIG
# ================================================================
API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", os.getenv("ANTHROPIC_API_KEY", "")))
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
MODEL = os.getenv("LLM_MODEL", "gpt-4o")
MAX_TURNS = int(os.getenv("ARIA_MAX_TURNS", "75"))
CMD_TIMEOUT = int(os.getenv("ARIA_CMD_TIMEOUT", "120"))
MAX_OUTPUT_CHARS = int(os.getenv("ARIA_MAX_OUTPUT", "12000"))

# ================================================================
# SYSTEM PROMPT — battle-tested for terminal benchmark tasks
# ================================================================
SYSTEM_PROMPT = r"""You are an elite terminal agent. You solve complex tasks by executing bash commands with precision.

RESPONSE FORMAT:
Respond with ONLY a valid JSON object. No markdown, no explanation, no extra text.
- Run command: {"action": "bash", "command": "..."}
- Task complete: {"action": "done"}
- Run multiple sequential commands: {"action": "bash", "command": "cmd1 && cmd2 && cmd3"}

MANDATORY WORKFLOW:
1. EXPLORE: Understand the environment (ls, cat, file, head, find, tree)
2. ANALYZE: Identify what needs to change and plan your approach
3. EXECUTE: Make the changes (write files, edit code, run scripts)
4. TEST: Run any available tests, verify output files exist and are correct
5. DONE: Only after verification succeeds

EXPERT TECHNIQUES:
File Operations:
- Read files: cat, head -n, tail -n, less -N (non-interactive)
- Create files: cat << 'HEREDOC' > file.txt ... HEREDOC
- Edit in-place: sed -i 's/old/new/g' file
- Complex edits: python3 -c "..." or python3 << 'EOF' ... EOF
- Patch files: Use python3 for surgical multi-line edits
- Permissions: chmod +x, chown as needed

Code & Debugging:
- Always check exit codes: cmd && echo OK || echo FAIL
- Syntax check scripts: bash -n script.sh, python3 -c "compile(open('f.py').read(),'f.py','exec')"
- Find errors: grep -rn "pattern" dir/, find . -name "*.py" -exec grep -l "pattern" {} \;
- Run tests: pytest, npm test, make test, bash test.sh — try whatever exists
- Check for test files: find . -name "test*" -o -name "*_test*" -o -name "*spec*"

Data Processing:
- CSV: awk -F, '{...}', sort -t, -kN, python3 csv module
- JSON: jq '.field', python3 json module
- Text: grep, sed, awk, cut, tr, sort, uniq, wc
- Math: echo "expr" | bc, python3 -c "print(eval('...'))", awk

Git Operations:
- Status: git status, git log --oneline -5, git diff
- Changes: git add, git commit, git checkout
- Branches: git branch, git switch

System:
- Package install: apt-get install -y (if root), pip install
- Process: ps, kill, lsof
- Network: curl, wget

ERROR RECOVERY:
- If command fails, READ the error message carefully
- Try alternative approaches (at least 3 before giving up)
- For permission errors: try sudo, chmod, or alternative paths
- For missing tools: install them or use alternatives
- For syntax errors: validate first, then fix incrementally
- If stuck, step back and re-examine the environment

CRITICAL RULES:
- NEVER call "done" without verifying your solution works
- NEVER run interactive commands (vim, nano, less, top, htop)
- NEVER include text outside the JSON object
- Chain related commands with && for efficiency
- Keep commands under 500 chars when possible (split if longer)
- If output is expected in a specific format, match it exactly
"""

# ================================================================
# PLANNING PROMPT — used for complex tasks
# ================================================================
PLANNING_ADDENDUM = """
Before starting, create a brief mental plan:
Step 1: Explore the files and understand the structure
Step 2: Identify exactly what needs to be done
Step 3: Execute the solution
Step 4: Verify everything works
Begin with Step 1 now.
"""


def call_llm(messages: list[dict], output_file=None) -> str:
    """Call the LLM and return the assistant's response text."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    url = BASE_URL.rstrip("/")
    if url.endswith("/v1"):
        url = f"{url}/chat/completions"
    elif "/chat/completions" not in url:
        url = f"{url}/v1/chat/completions"

    body = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 4096,
    }

    start = time.time()

    # Retry with exponential backoff
    last_err = None
    for attempt in range(3):
        try:
            resp = httpx.post(url, headers=headers, json=body, timeout=180)
            resp.raise_for_status()
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                wait = 2 ** (attempt + 1)
                print(f"[aria] LLM retry {attempt+1}/3 after {wait}s: {e}")
                time.sleep(wait)
    else:
        raise last_err

    elapsed = time.time() - start
    data = resp.json()
    choice = data["choices"][0]
    content = choice["message"].get("content", "")

    # Log usage
    usage = data.get("usage", {})
    if output_file:
        log_entry = {
            "type": "llm_call",
            "model": MODEL,
            "elapsed_s": round(elapsed, 2),
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
            "timestamp": time.time(),
        }
        with open(output_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    return content


def run_bash(command: str, timeout: int = CMD_TIMEOUT) -> dict:
    """Execute a bash command and return result."""
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
            env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
        )
        stdout = result.stdout
        stderr = result.stderr

        # Smart truncation — keep head and tail for long output
        if len(stdout) > MAX_OUTPUT_CHARS:
            head = stdout[:MAX_OUTPUT_CHARS // 2]
            tail = stdout[-(MAX_OUTPUT_CHARS // 2):]
            stdout = f"{head}\n\n... [{len(result.stdout)} chars total, middle truncated] ...\n\n{tail}"
        if len(stderr) > MAX_OUTPUT_CHARS // 2:
            stderr = stderr[:MAX_OUTPUT_CHARS // 2] + f"\n... [{len(result.stderr)} chars total, truncated]"

        return {
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"TIMEOUT: Command exceeded {timeout}s limit. Try a faster approach or add timeouts.",
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"EXEC ERROR: {str(e)}",
        }


def parse_action(text: str) -> dict | None:
    """Parse the LLM response to extract the JSON action."""
    text = text.strip()

    # Remove any markdown wrappers
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    # Try direct JSON parse
    try:
        data = json.loads(text)
        if "action" in data:
            return data
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in text
    patterns = [
        r'```(?:json)?\s*(\{.*?\})\s*```',
        r'(\{"action"\s*:\s*"(?:bash|done)"[^}]*\})',
        r'(\{[^{}]*"action"[^{}]*\})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if "action" in data:
                    return data
            except json.JSONDecodeError:
                continue

    # Last resort: try to fix common JSON issues
    # Missing quotes around keys
    fixed = re.sub(r'(\{|,)\s*(\w+)\s*:', r'\1"\2":', text)
    try:
        data = json.loads(fixed)
        if "action" in data:
            return data
    except json.JSONDecodeError:
        pass

    return None


def count_bash_turns(messages: list[dict]) -> int:
    """Count how many bash commands have been executed."""
    count = 0
    for m in messages:
        if m["role"] == "assistant":
            action = parse_action(m.get("content", ""))
            if action and action.get("action") == "bash":
                count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Aria Terminal Agent v2.0")
    parser.add_argument("instruction", help="Task instruction to execute")
    parser.add_argument("--output", help="JSONL output file for metrics", default=None)
    parser.add_argument("--max-turns", type=int, default=MAX_TURNS, help="Max turns")
    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: No API key. Set LLM_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(1)

    print(f"[aria] Model: {MODEL}")
    print(f"[aria] Task: {args.instruction[:300]}")
    print(f"[aria] Max turns: {args.max_turns}")
    print()

    # Build initial messages with planning
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"TASK:\n{args.instruction}\n\n{PLANNING_ADDENDUM}"},
    ]

    consecutive_parse_failures = 0
    consecutive_errors = 0

    for turn in range(args.max_turns):
        print(f"[aria] === Turn {turn + 1}/{args.max_turns} ===")

        # Call LLM
        try:
            response = call_llm(messages, output_file=args.output)
        except Exception as e:
            print(f"[aria] LLM FATAL: {e}", file=sys.stderr)
            break

        # Parse action
        action = parse_action(response)

        if action is None:
            consecutive_parse_failures += 1
            print(f"[aria] Parse fail #{consecutive_parse_failures}")

            if consecutive_parse_failures >= 3:
                # Force a simple exploration command
                print("[aria] Forcing exploration command")
                action = {"action": "bash", "command": "ls -la && pwd"}
                consecutive_parse_failures = 0
            else:
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": 'INVALID RESPONSE. You MUST reply with ONLY valid JSON: {"action": "bash", "command": "..."} or {"action": "done"}. No other text.',
                })
                continue
        else:
            consecutive_parse_failures = 0

        # Handle DONE
        if action["action"] == "done":
            bash_count = count_bash_turns(messages)
            if bash_count < 2:
                print(f"[aria] Too early (only {bash_count} commands run), continuing...")
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": "You have not completed the task yet. You need to: 1) explore, 2) execute the solution, 3) verify the result. Only call done after verification. Continue working now.",
                })
                continue

            print(f"[aria] Task completed after {bash_count} commands.")
            if args.output:
                with open(args.output, "a") as f:
                    f.write(json.dumps({"type": "done", "turn": turn + 1, "bash_commands": bash_count, "timestamp": time.time()}) + "\n")
            break

        # Handle BASH
        if action["action"] == "bash":
            command = action.get("command", "")
            if not command.strip():
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": "Empty command. Provide an actual bash command."})
                continue

            print(f"[aria] $ {command[:300]}")

            result = run_bash(command)
            exit_code = result["exit_code"]
            stdout = result["stdout"]
            stderr = result["stderr"]

            # Print condensed output
            if stdout:
                preview = stdout[:500].replace("\n", " | ")
                print(f"[aria] out: {preview}")
            if stderr and exit_code != 0:
                preview = stderr[:300].replace("\n", " | ")
                print(f"[aria] err: {preview}")
            print(f"[aria] exit: {exit_code}")

            # Track consecutive errors for recovery
            if exit_code != 0:
                consecutive_errors += 1
            else:
                consecutive_errors = 0

            # Log
            if args.output:
                with open(args.output, "a") as f:
                    f.write(json.dumps({
                        "type": "bash",
                        "command": command[:1000],
                        "exit_code": exit_code,
                        "stdout_len": len(result["stdout"]),
                        "stderr_len": len(result["stderr"]),
                        "turn": turn + 1,
                        "timestamp": time.time(),
                    }) + "\n")

            # Build observation
            observation = f"EXIT CODE: {exit_code}\n"
            if stdout:
                observation += f"STDOUT:\n{stdout}\n"
            if stderr:
                observation += f"STDERR:\n{stderr}\n"

            # Add recovery hints on repeated failures
            if consecutive_errors >= 3:
                observation += "\nHINT: You've had 3+ consecutive errors. Step back, re-examine the environment (ls, cat, pwd), and try a completely different approach.\n"
                consecutive_errors = 0

            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": observation})

            # Context window management — smart pruning
            if len(messages) > 80:
                # Keep: system(0), first user(1), last 50 messages
                preserved = messages[:2] + messages[-50:]
                # Add context summary
                pruned_count = len(messages) - len(preserved)
                preserved.insert(2, {
                    "role": "user",
                    "content": f"[Context note: {pruned_count} earlier messages were pruned. The task is still the same. Continue from where you left off.]",
                })
                messages = preserved

        else:
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": f"Unknown action '{action['action']}'. Use 'bash' or 'done' only.",
            })

    else:
        print(f"[aria] Max turns ({args.max_turns}) reached")
        if args.output:
            with open(args.output, "a") as f:
                f.write(json.dumps({"type": "max_turns", "turns": args.max_turns, "timestamp": time.time()}) + "\n")

    print("[aria] Finished.")


if __name__ == "__main__":
    main()
