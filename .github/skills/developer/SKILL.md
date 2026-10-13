---
name: developer
description: 'General software development workflow for turning a request into a verified implementation. Use when debugging, reviewing an implementation, triaging a defect, or packaging a repeatable project workflow into a reusable skill.'
argument-hint: 'Describe the task, feature, bug, workflow, or test to run.'
user-invocable: true
disable-model-invocation: false
---

# Developer Workflow

## When to Use

Use this skill when a request needs a repeatable engineering workflow:

- Understand a user story, bug report, or feature request
- Diagnose a failure before making changes
- Plan an implementation with evidence and verification
- Turn a conversation pattern into a reusable project skill

## Procedure

1. Frame the Request
   - Identify the business outcome or user-visible behavior.
   - Extract inputs, constraints, files, endpoints, and expected evidence.
   - If the task is ambiguous, ask a short clarifying question before editing code.

2. Gather Project Context
   - Inspect the relevant files, tests, config, and repository conventions.
   - Prefer the existing structure and established patterns already present in the workspace.
   - Record any dependency or environment assumptions that could affect the solution.

3. Diagnose the Root Cause
   - Reproduce the symptom when possible.
   - Trace the data flow and the failing surface.
   - Separate evidence from inference before proposing a fix.

4. Create a Minimal Verification Signal
   - Add or identify a failing test, command, or reproducible check.
   - Verify that the test or reproduction demonstrates the bug or missing behavior.

5. Implement One Root-Cause Fix
   - Make the smallest change that addresses the verified reason the task failed.
   - Keep edits targeted and consistent with the repository’s style and structure.
   - Avoid speculative changes that are unrelated to the observed evidence.

6. Verify Before Completion
   - Re-run the relevant test, lint, build, or command.
   - Review concrete evidence from the command output rather than assuming success.
   - If verification fails, report the failing evidence and continue investigation.

7. Record the Reusable Pattern
   - Extract the stepwise method that solved the problem.
   - Generalize decision points, branching logic, and completion checks.
   - Preserve the workflow as a skill, instruction, or prompt when the pattern is repeatable.

## Quality Criteria

The workflow is complete only when all of the following are true:

- The request was clarified enough to act safely.
- Root cause or requirement assumptions were grounded in evidence.
- A verification command or regression signal was captured.
- The fix was minimal, consistent with workspace conventions, and tied to the observed need.
- The final status is reported with fresh evidence from execution.

## Example Prompts

- Debug a failing API endpoint and write a regression check.
- Review an implementation pattern and turn it into a reusable workflow.
- Create a minimal fix after reproducing a symptom in the workspace.
- Generalize a conversation workflow into a custom skill.
