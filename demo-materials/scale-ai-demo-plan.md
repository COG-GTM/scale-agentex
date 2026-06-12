# Devin Demo Plan — Scale AI

**Duration:** 15–30 minutes
**Audience:** Scale AI engineering leadership (they build AI evals/infra — they KNOW models and agents)
**Repo for live demo:** `scale-agentex` (their open-source agent platform)

---

## Demo Structure

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  FLOW (pick 15 or 30 min version)                                        │
│                                                                          │
│  ┌─────────────┐   ┌──────────────────┐   ┌─────────────────────────┐   │
│  │  PITCH      │──▶│  LIVE DEMO       │──▶│  CLOSE + NEXT STEPS     │   │
│  │  (3-5 min)  │   │  (10-20 min)     │   │  (2-3 min)             │   │
│  └─────────────┘   └──────────────────┘   └─────────────────────────┘   │
│                                                                          │
│  Pitch:  Platform vs CLI, model-agnostic, deployment                     │
│  Demo:   DeepWiki → Ask Devin (live) → PR → Automation                   │
│  Close:  PoV offer                                                       │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Opening Pitch (3–5 min)

Use the tight 3-beat version from the talk track:

> "You're Scale — you literally evaluate frontier models for a living. I'm not going to pitch you on AI. What I want to show you is the difference between a CLI tool one engineer uses and an organizational platform that operates at fleet scale."

Hit these three beats fast:

1. **Model lock-in** — "You know the frontier moves quarterly. Claude Code locks you to one vendor. We route across all providers — whatever's best per task."

2. **Deployment** — "Claude Code is SaaS-only. For Donovan and anything touching IL4/FedRAMP, that's a non-starter. We deploy in your VPC via PrivateLink. Zero data retention."

3. **Platform, not CLI** — "Claude Code is a sharp chisel for one dev. Devin is a construction crew with a foreman, shared blueprints, and institutional memory. At 1000+ engineers, you need the crew."

Then transition:

> "But you're engineers — you want to see it work, not hear me talk. So let me show you Devin working on YOUR codebase. This is Agentex — your open-source agent platform."

---

## Part 2: Live Demo (10–20 min)

### Beat 1: DeepWiki — Instant Codebase Understanding (2 min)

**What you show:** Pull up DeepWiki for `scaleapi/scale-agentex`

**Talk track:**

> "First thing — Devin doesn't start from zero on any repo. This is DeepWiki. It's already indexed your entire Agentex codebase. I can see your DDD architecture, the domain entities, how Temporal workflows connect to the FastAPI routes, the whole thing."

> "This is institutional knowledge that compounds. Every engineer who touches this repo — Devin already knows the patterns, the conventions, the architecture. No CLAUDE.md needed."

Show:
- Architecture diagram
- Key concepts (ACP protocol, Task lifecycle, Temporal workflows)
- Navigate to a specific domain entity

---

### Beat 2: Ask Devin — Live Feature Implementation (8–12 min)

**What you do:** Kick off a Devin session live with a prompt that demonstrates real value on their repo.

**Prompt to use (copy into Ask Devin):**

```
Add an agent analytics summary endpoint to the Agentex API.

The endpoint should be GET /agents/{agent_id}/analytics and return:
- Total tasks (by status: pending, running, completed, failed)
- Average task duration (completed tasks only)
- Task throughput (tasks completed per hour, last 24h)
- Error rate (failed / total, last 24h)

Follow the existing DDD architecture:
- Add the use case in src/domain/use_cases/
- Add the route in src/api/routes/agents.py
- Add the response schema in src/api/schemas/
- Use the existing repository pattern for data access

This will power a dashboard view for agent operators to monitor fleet health.
```

**Why this prompt is perfect for Scale:**
- It's something their engineers would actually want (agent observability)
- It demonstrates understanding of their specific architecture (DDD, use cases, repos)
- It's a full vertical slice — not a toy "add a test" task
- The output is immediately useful for their agent platform

**Talk track while Devin works:**

> "So I just gave Devin a task that would take a mid-level engineer 2-3 hours. It needs to understand your DDD architecture, follow your patterns for use cases and repositories, add the API route, create the schema — the whole vertical slice."

> "Watch what's happening — it's reading your existing code to understand conventions. It's not hallucinating patterns. It's following YOUR architecture."

As Devin works, point out:
- How it reads existing use cases to match the pattern
- How it follows the dependency injection style
- How it creates proper Pydantic schemas
- How it adds the route with correct auth patterns

> "This is 10 minutes of Devin time. No context loading. No 'read the docs first.' It already knows this codebase from DeepWiki and the session knowledge."

---

### Beat 3: The PR (2 min)

**What you show:** The resulting PR once Devin finishes.

> "Clean PR. Follows your conventional commits. Passes your pre-commit hooks — ruff, ESLint, the works. This is ready for code review."

> "Now imagine this at scale: 50 of these running in parallel across your repos. Migrations, security patches, feature implementations — all following your org's patterns. That's what a platform gives you that a CLI never can."

---

### Beat 4: Automation & Knowledge (3–5 min) — if time allows

**Option A: Show event-driven triggers**

> "62% of Devin sessions at our customers trigger automatically. No human types a prompt. A Jira ticket gets created → Devin picks it up. A CVE fires → Devin patches all affected repos. A PR gets merged → Devin updates downstream dependencies."

Show the Devin automation UI or describe the Slack/Linear/Jira integration.

**Option B: Show knowledge compounding**

> "Every time Devin works on Agentex, it learns. Your migration patterns, your auth conventions, how you structure Temporal workflows. That knowledge persists across sessions and across engineers. It's institutional memory that a CLI can never build."

Show playbooks, knowledge base, or skills.

**Option C: Show parallel execution**

> "Let me kick off 3 more sessions simultaneously — one adding metrics to the frontend dashboard, one writing integration tests for the new endpoint, one updating your OpenAPI spec. Claude Code can't do this. It's one terminal, one session, one task."

---

## Part 3: Close (2–3 min)

> "So what you just saw: Devin understood your Agentex architecture in seconds, implemented a real feature following your exact patterns, produced a reviewable PR — and it can do 50 of those in parallel, triggered automatically, with org-wide knowledge.

> That's the difference between a CLI tool and infrastructure. At Scale's size — 1000+ engineers, multiple products, FedRAMP workloads — you need the infrastructure.

> For a proof of value: pick your most painful cross-repo migration, your security remediation backlog, or a feature backlog that's been sitting for months. We'll put a Delta Engineer with your team for two weeks and show you what this looks like at your scale.

> What's the right starting point?"

---

## Pre-Demo Prep Checklist

- [ ] Have `scale-agentex` DeepWiki page open and ready
- [ ] Have Devin session ready to go (logged in, repo connected)
- [ ] Pre-run the demo prompt once to verify it produces a clean PR (use the pre-baked PR as backup)
- [ ] Have the talk track comparison table ready as a leave-behind
- [ ] Know Scale's current tooling (likely Claude Code / Cursor)

---

## Backup: Pre-Baked PR

If live demo has connectivity issues or takes too long, have a pre-completed PR ready showing:
- The analytics endpoint fully implemented
- Clean commit history
- Passing CI checks
- Proper DDD architecture adherence

Walk through the PR diff as if it just completed.

---

## Key Differentiators to Emphasize for Scale

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│  WHAT SCALE CARES ABOUT              HOW DEVIN ANSWERS IT                  │
│                                                                            │
│  "We know models"                    Model-agnostic routing. Best per task. │
│  "We have FedRAMP workloads"         VPC deployment. PrivateLink. ZDR.     │
│  "We have 1000+ engineers"           Fleet orchestration. 50+ parallel.    │
│  "We build evaluation infra"         We USE evals internally. SWE-bench.   │
│  "We might build our own"            Would you build your own Datadog?     │
│  "Claude relationship"               We RUN Claude. Plus everything else.  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Timing Options

### 15-min version (tight)
| Section | Time |
|---------|------|
| Pitch (3 beats) | 3 min |
| DeepWiki | 1 min |
| Live Devin (kick off + narrate) | 7 min |
| Show PR | 2 min |
| Close | 2 min |

### 30-min version (full)
| Section | Time |
|---------|------|
| Pitch (full talk track) | 5 min |
| DeepWiki deep dive | 3 min |
| Live Devin (full implementation) | 12 min |
| Show PR + walk through code | 3 min |
| Automation/Knowledge/Parallel | 4 min |
| Close + Q&A | 3 min |
