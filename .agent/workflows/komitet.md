---
description: Komitet routine for logical git committing
---

# THE ROUTINE (Komitet Workflow):

- STEP 1 (Reconnaissance): Execute `git status` and `git diff HEAD` in the terminal to read all uncommitted changes (both staged and unstaged). This logic must handle everything from a single minor tweak to a massive, multi-day uncommitted diff.
- STEP 2 (Semantic Split): Analyze the diff. Isolate distinct logical units of work. Never group unrelated changes.
- STEP 3 (The Plan): Output a strict execution plan using this exact format for each group: `[Proposed Conventional Commit Message] -> [List of exact files or line ranges]`.
- STEP 4 (Halt for Validation): Stop completely. Wait for my explicit approval (e.g., "odobreno", "teraj", "proceed"). DO NOT modify git state before this point.
- STEP 5 (Execution): Upon my approval, use the terminal to iteratively apply `git add` and `git commit` for each logical group. Use precise partial staging (or exact file addition) if multiple distinct logical changes reside within the exact same file. If you cannot safely partial-stage, flag it as a conflict for manual resolution.
- STEP 6 (Verification): Run a final `git status` to ensure the working tree is clean and report any leftover scraps.
