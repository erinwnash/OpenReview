# OpenReview - Antigravity Agent Guidelines & Token Optimization Rules

## 1. Token Economy & Output Brevity
- **Concise Communication**: Provide direct, dense, actionable answers. Omit conversational filler, preamble, and re-explaining the user's prompt.
- **Surgical Edits**: Never rewrite entire files when small modifications suffice. Always make targeted changes using line-constrained edits.
- **Selective File Viewing**: Always specify `StartLine` and `EndLine` when viewing files longer than 150 lines. Avoid loading full multi-thousand line modules into context.

## 2. Command Execution & Output Throttling
- **Quiet Test Execution**: Use `pytest -q --tb=short` to avoid flooding the context window with hundreds of verbose test progress lines.
- **Compact Git / CLI Output**: Use concise status flags (e.g. `git status -s`, piping long directory listings or grep outputs).
- **Background Tasks**: Avoid rapid polling loops; rely on reactive task completion notifications.

## 3. Artifact & Scratch Management
- **Artifact Restraint**: Only create artifacts when explicitly requested by the user or when generating persistent formal documentation / architecture plans.
- **No Artifact Duplication**: Do not create redundant intermediate snapshots or duplicate markdown files.
- **Direct Answers**: For quick questions, debugging summaries, or single-step confirmations, respond directly in chat markdown rather than generating new artifact documents.
