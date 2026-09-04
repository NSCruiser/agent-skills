# Routing and task packets

Read this reference only when role selection, non-default context inheritance, nested delegation, write partitioning, or a complete task packet is non-obvious. Straightforward leaf assignments do not require it.

## Routing table

| Work | Role | Model | Effort | Context | Delegation |
|---|---|---|---|---|---|
| Narrow read-only lookup, source collection, or location work | `scout` | `gpt-5.6-sol` | `low` | `fork_turns: "none"` | Leaf |
| Fully specified coding with exact ownership and acceptance criteria | `coder` | `gpt-5.6-sol` | `medium` | `fork_turns: "none"` | Leaf |
| Routine execution that needs limited investigation or integration | `worker` | `gpt-5.6-sol` | `medium` | Prefer `fork_turns: "none"` | Leaf |
| Difficult but bounded execution, complex logic, or local ambiguity | `senior_worker` | `gpt-5.6-sol` | `high` | Prefer `fork_turns: "none"` | Leaf by default; bounded delegation when explicitly authorized |
| Independent correctness, risk, or completeness check | `reviewer` | `gpt-5.6-sol` | `high` | `fork_turns: "none"` | Leaf |
| Goal interpretation, cross-task decisions, approvals, and final synthesis | Main agent | User selection | User selection | Current context | Coordinator |

Use `coder` only when the task packet contains every input needed to act, exact ownership, hard constraints, a required output, and a concrete validation method. Use `worker` when the child must inspect a small amount of surrounding context. Use `senior_worker` only when higher reasoning is justified by difficult logic or meaningful local ambiguity.

The model and effort columns document the matching custom agent files under `~/.codex/agents/`. When selecting a named role, rely on that file and omit duplicate model or effort overrides. Use the table values explicitly only for the compatibility fallback described in [runtime-compatibility.md](runtime-compatibility.md).

## Context policy

Fresh context is the default because it keeps the assignment focused. A fresh task packet must repeat every relevant user decision, permission boundary, safety constraint, path, input, and output requirement.

Use a positive `fork_turns` count only when a small number of recent turns contains important source material that would be risky to restate. Use `fork_turns: "all"` only when the full history is necessary and cannot be replaced by a reliable task packet. Inherited context does not remove the leaf boundary. Tell the child not to spawn other agents.

## Naming

Use `<job>_<scope>` for `task_name`, such as `scout_auth`, `coder_cache`, `worker_report`, `senior_worker_parser`, or `reviewer_release`.

Names must describe the job and ownership. Do not put `sol`, `terra`, `low`, `medium`, `high`, or another model setting in the name.

## V2 spawn shape

Use only fields exposed by the active tool schema:

```json
{
  "agent_type": "coder",
  "task_name": "coder_cache",
  "fork_turns": "none",
  "message": "<complete task packet>"
}
```

`agent_type` represents the active interface's role selector; use its actual field name when different. Use this shape only after confirming that `coder` is registered in the active selector. If it is absent, use the preflight fallback in [runtime-compatibility.md](runtime-compatibility.md) instead of making a call that is expected to fail. A task name labels the assignment and does not select a custom role by itself. Do not add `model` or `reasoning_effort` when selecting a configured custom role.

## Task packet

```text
Role:
Act as the <job title>.

Delegation:
<For a leaf: "None. Complete this assignment directly and do not spawn other agents." For an explicitly authorized senior_worker: name the allowed child scopes, allow at most two independent leaf agents, and state the remaining concurrency budget.>

Objective:
<one concrete outcome>

Ownership:
<resources, files, records, sections, or questions owned by this agent>

Known context and inputs:
<only the facts, user decisions, and source material required to start>

Authorization basis:
<the exact user request or approval that permits local changes or other actions; state clearly when no write is authorized>

Constraints and approvals:
<permission limits, safety rules, style requirements, and prohibited actions>

Exclude:
<unrelated work, other agents' ownership, broad redesign, or external actions>

Required work:
<specific investigation, implementation, review, or production steps>

Validation:
<checks to run or evidence to collect>

Return:
1. Direct result or conclusion.
2. Evidence, sources, paths, symbols, or changed resources.
3. Validation performed and its result.
4. Uncertainty, missing input, or a decision reserved for the main agent.

Stop condition:
Stop when the required output and validation are complete, or when a named missing input prevents safe progress.
```

## Coordination

- Split work by independent question, resource, or subsystem rather than arbitrary count.
- Prefer two or three subagents and never exceed the current runtime's available slots or configured concurrency limit. Count nested descendants against the same budget.
- Do not run two writers against the same resource. Serialize them or redefine ownership.
- Keep every child as a leaf unless a `senior_worker` task packet explicitly authorizes bounded delegation. Its children must be independent leaves and may not delegate again.
- A child may message another active child when it discovers a specific dependency. Keep the message limited to the evidence or question needed by that child.
- Keep approvals, scope changes, prioritization, conflict resolution, and final synthesis in the main agent.

## Result contract

Require a direct answer first. Reports should contain distilled evidence rather than raw command transcripts, full files, or long logs. A result is incomplete when it omits required validation, hides uncertainty, crosses assigned ownership, or leaves the main agent unable to decide the next step.
