---
title: Claude Code Sends 4.7x More Tokens Than OpenCode Before Reading Your Prompt
source_url: https://systima.ai/blog/claude-code-vs-opencode-token-overhead
source_site: systima.ai
scraped_at: 2026-07-13
type: raw_source
tags:
  - agentic-ai
  - token-overhead
  - claude-code
  - opencode
---

# Claude Code Sends 4.7x More Tokens Than OpenCode Before Reading Your Prompt

Source: https://systima.ai/blog/claude-code-vs-opencode-token-overhead

We put Claude Code and OpenCode on the same model, the same machine, and the same tasks, then examined everything sent and received.

**Claude Code is far hungrier:**

When we asked both harnesses for a one-line reply, Claude Code used roughly 33,000 tokens of system prompt, tool schemas, and injected scaffolding before the prompt even arrived. OpenCode used about 7,000.

That first test was on Sonnet 4.5. Re-running on Claude Fable 5 narrowed the gap to about 3.3x, because Claude Code sends newer models a much smaller system prompt; still far hungrier, but the multiple is model-dependent.

**Claude Code is far more cache inefficient:**

OpenCode's request prefix was byte-identical in every run we captured; it paid to cache its payload once per session and read it back for pennies.

Claude Code on the other hand re-wrote tens of thousands of prompt-cache tokens mid-session, run after run, and on the same task wrote up to 54x more cache tokens than OpenCode.

Cache writes of course are billed at a premium, which accounted for the usage dashboard climbing when using Claude Code.

**Config further bloats the prompt:**

A production repository's 72KB instruction (AGENTS.md or CLAUDE.md) file adds another (avg) 20,000 tokens to every single request. Five modest MCP servers add 5,000 to 7,000 more. By the time a real working setup sends its first request, it is 75,000 to 85,000 tokens deep before the user has typed a word.

**Subagents add to the cost:**

A small task that cost 121,000 tokens done directly cost 513,000 tokens when fanned out to two subagents, because every subagent has its own bootstrap cost, and the parent then consumes its transcript.

**We found one result in favour of Claude Code:**

On a multi-step task Claude Code's whole-task total came out lower than OpenCode's, because it batches tool calls into fewer requests while OpenCode re-pays its smaller baseline turn after turn. The meter starts higher; how the session unfolds decides who spends more.

The rest of this post shows how we measured all of this at the API boundary, where the tokens go, and what prompt caching does and does not save you.

## Why measure this at all

Token overhead is cost, latency, and context budget. Every token of harness payload is a token of working context you cannot spend on code, and the baseline is re-sent, or re-read from cache, on every single turn.

If you operate agentic AI in production, particularly under the EU AI Act where Article 12 expects you to log and understand your system's behaviour, "what does my agent actually send" is a question you should be able to answer with data rather than folklore.

## Method

We spliced a logging proxy between each harness and the model endpoint.

```
harness (Claude Code / OpenCode)
  → logging proxy (captures request payloads + response usage)
    → model endpoint
```

The proxy records two things per request. The first is the exact JSON payload the harness emitted, meaning the system blocks, tool schemas, and messages. The second is the usage block the API returned, covering input tokens, cache writes, cache reads, and output tokens.

The payload capture is ground truth for what the harness sends. The usage block is ground truth for what was metered.

We tested under these conditions.

- **Harnesses.** Claude Code 2.1.207 and OpenCode 1.17.18, both pinned to `claude-sonnet-4-5`, July 2026. A reduced matrix (the floor, the cache task, and the multi-step task) was later re-run pinned to claude-fable-5; where the model changed the result, we say so inline.
- **Baseline isolation.** Fresh config directories with no MCP servers, no user settings, and no memory; an empty workspace with no instruction files; permissions bypassed. Multiplier lanes then add one variable at a time.
- **Tasks.** T1 says "Reply with exactly: OK" and isolates fixed overhead (three runs per harness). T2 reads a seeded file and summarises it. T3 is a write-run-test-fix loop against FizzBuzz plus a checker script.
- **Zero-tools variant.** Claude Code with `--tools ""` and OpenCode with `"tools": {"*": false}`, separating system prompt from tool schema weight.

One honesty note before the numbers. Our traffic passes through a local LLM gateway that wraps requests in its own envelope, a constant we measured at roughly 6,200 tokens with bare calibration requests and subtracted from every metered figure below. Payload-level figures come from the captured request bodies, which the gateway cannot affect, and are exact.

Character-to-token conversion for component estimates uses each harness's own measured ratio of 4.1 to 4.4 characters per token, derived from cold-cache anchors where the metered write equals the full payload, rather than a generic heuristic.

## Part I. The floor

### The fixed overhead of saying OK

The task was 22 characters. Here is what each harness sent with it on its first request.

| Component | Claude Code | OpenCode |
| --- | --- | --- |
| System prompt | 27,344 chars, 3 blocks | 9,324 chars, 1 block |
| Tool schemas | 27 tools, 99,778 chars | 10 tools, 20,856 chars |
| First-message scaffolding | 7,997 chars of `<system-reminder>` blocks | none |
| The actual prompt | 22 chars | 22 chars |
| **First-turn payload (calibrated)** | **~32,800 tokens** | **~6,900 tokens** |

OpenCode's request is close to minimal. There is one system block that opens with "You are OpenCode, the best coding agent on the planet", ten classic coding tools, and your prompt as the only user content.

Claude Code's request is a platform bootstrap. The 27 tools include the coding core plus an entire background-agent and orchestration suite, from `CronCreate` and `Monitor` to the `Task` family, worktree management, and push notifications.

Before your prompt, its first user message carries three injected reminder blocks; a catalogue of agent types for delegation, a catalogue of available skills, and user context.

Tool schemas are the dominant term for both. Roughly 24,000 of Claude Code's ~33,000 tokens are tool definitions, versus roughly 4,800 of OpenCode's ~6,900.

### Zero tools, pure harness

Stripping the tools isolates the system prompt itself. Claude Code's weighs in at 26,891 chars, about 6.5k tokens. OpenCode's is 8,811 chars, about 2.0k tokens.

Both harnesses trim their prompt slightly when tools are disabled. Even with no tools at all, Claude Code's instruction set is over three times the size of OpenCode's; the residual is behavioural doctrine, meaning tone rules, safety guidance, task-management instructions, and environment description.

### A one-tool task

T2 asked each harness to read a file and summarise it. Both produced correct summaries.

Claude Code took 6 HTTP requests and roughly 199,000 cumulative metered input tokens. OpenCode took 4 requests and roughly 41,000, plus one Haiku side call for session titling.

Most of those tokens are cache reads billed at a tenth of the input price. Three things scale with payload regardless; the first-turn cache write, the per-turn read, and context-window consumption, which no cache discount reduces.

A 33k-token baseline means every turn starts a sixth of the way into a 200k window before any code enters the conversation.

### A multi-step task, where the gap closes

T3, the write-run-test-fix loop, inverted the expectation set by the baselines.

| Metric | Claude Code | OpenCode |
| --- | --- | --- |
| Model requests | 3 | 9 (+1 title call) |
| Tool-calling style | parallel batch in one round trip | one tool call per turn |
| Cumulative metered input | ~121,000 tokens | ~132,000 tokens |

Claude Code batched the entire job, two file writes and two script executions, into a single parallel tool round trip. OpenCode made exactly one tool call per turn and took nine.

Because the baseline is re-sent on every request, request count multiplies baseline. OpenCode paid its ~7k baseline nine times, Claude Code paid its ~33k three times, and the totals converged.

Whole-task input roughly equals baseline times request count, plus conversation growth. A large-baseline harness that batches aggressively and a small-baseline harness that serialises can land in the same place.

Two structural details emerged from the payloads. Claude Code injects an additional `<system-reminder>` block as the conversation progresses, three on the first turn and four by the first tool round trip, so its scaffolding grows with turn count. OpenCode's per-turn marginal payload, roughly 400 to 2,200 chars per turn, is pure conversation content.

### Does a newer model change the picture?

We re-ran the floor on Claude Fable 5 to check whether the gap was a Sonnet artefact. It shrank, for a reason we did not expect.

Claude Code's system prompt is model-conditional. It sent 27,787 chars of instructions to Sonnet but only 10,526 to Fable, with tool schemas also trimmed from 99,778 to 82,283 chars. Same 27 tools, much less doctrine.

OpenCode's payload was byte-identical across both models.

The floor gap on Fable comes out at roughly 3.3x by payload against 4.7x on Sonnet. Still far hungrier, but the ratio is model-dependent.

## Part II. The multipliers

The floor explains a session that starts lean and stays short. Real sessions do neither. We measured each layer that real usage stacks on top.

### Multiplier 1. The instruction file

We dropped a real 72KB `AGENTS.md` from a production repository into the workspace and re-ran T1.

The effect is symmetrical and large. **Both harnesses gained just over 20,000 tokens per request.** OpenCode's metered total went from 13,152 to 33,336. Claude Code's went from 39,005 to 59,243.

The asymmetry is in the mechanics, and it bit us during the experiment. Claude Code 2.1.207 ignored `AGENTS.md` entirely and only ingested the file when renamed `CLAUDE.md`, injecting it into the first user message. OpenCode reads either filename and injects it into the system prompt.

Two practical consequences follow. Check which filename your harness actually honours, because an ignored instruction file is silent. And know that a heavy instruction file nearly quadruples a lean harness's baseline; it rides on every request of every session in that repository.

### Multiplier 2. MCP servers

We attached public, credential-free MCP servers in one-server and five-server configurations.

The schemas are identical across harnesses, so the tax is nearly identical too; roughly **1,000 to 1,400 tokens per small server, per request**. Five servers added 4,900 tokens to Claude Code by payload and 6,967 metered to OpenCode, growing the tool counts from 27 to 69 and from 10 to 52.

Small public servers are the gentle case. Production servers with rich APIs ship schemas several times larger, which is exactly what the everything measurement below shows.

One operational footnote. Claude Code silently ignored a project-scoped `.mcp.json` in print mode until passed an explicit `--mcp-config` flag. If you assume a server is attached, verify it at the boundary.

### Multiplier 3. Framework templates

Story-driven workflow frameworks such as BMAD expand a slash command into a large prompt template of personas, protocols, and checklists.

We ran an 8,405-char representative template as the prompt for the same T3 story in both harnesses. The template itself is only about 2,100 tokens, but it enters the conversation history and is re-carried by **every subsequent request in the session**. A 9-request session re-sends it nine times.

Framework tax is template size times request count, and it stacks on top of everything above.

### Multiplier 4. Subagents

We asked each harness to fan the work out to two parallel subagents. This is where the totals climb fastest.

Claude Code completed the task with 9 model requests across three distinct request classes. There was the main session with its full ~33k baseline, and five subagent calls each carrying their own bootstrap of a 3,554-char agent system prompt plus 24 of the 27 tools.

Cumulative metered input reached **513,000 tokens, against 121,000 for the same work done directly. That is a 4.2x multiplier** for one modest fan-out, because every subagent pays its own bootstrap and its transcript is then ingested by the parent.

OpenCode's design here is notably leaner. Its subagent requests carry a reduced profile of a 1,379-char system prompt and 5 tools. Its subagent lane did not complete cleanly through our gateway, so we report the design difference from the captured payloads and leave its totals unquantified.

If your heavy sessions surprise you, this is the first place to look. Delegation is powerful and sometimes correct; it is also the single largest token multiplier we measured.

### Multiplier 5. Extended thinking

Thinking output bills at output rates, five times the input rate, and reasoning blocks are carried forward inside the conversation.

We attempted to toggle extended thinking in both harnesses and are declining to publish numbers. Our gateway applies its own thinking policy, neither harness's toggle demonstrably survived the path, and anything we quoted would be noise.

The mechanism is not in doubt, though. On reasoning-heavy work it compounds with every multiplier above, because the thinking blocks join the history that gets re-sent.

### The everything number

Finally, the bridging measurement. We ran T1 again under a real working configuration.

For OpenCode that meant eleven MCP servers covering email and calendar, task management, reference management, product analytics, and others, plus the 72KB instruction file. The first request metered **90,817 tokens on a cold cache write**, carrying 179 tools and 277KB of schemas, before the user had typed a word.

For Claude Code, four MCP servers plus installed plugins and the same instruction file produced a 311KB payload of roughly **75,000 tokens** with 118 tools.

After subtracting the gateway envelope, that is roughly a 12x configuration multiplier against OpenCode's ~7,000-token floor. The harness sets the floor; your configuration sets the bill.

## The cache economics

Prompt caching changes the units but not the conclusions.

Both harnesses set cache breakpoints correctly. The payload is written once, at a 1.25x premium for the 5-minute TTL, and re-read at a tenth of the price thereafter.

Three costs survive the discount.

First, the write itself, re-paid whenever a pause exceeds the TTL. A five-minute think, a meeting, a lunch; each re-primes the full stack at write rates.

Second, the read multiplied by request count, which subagent fan-outs and serial tool loops inflate quickly.

Third, context-window consumption, which is completely immune to caching. An 85k-token bootstrap occupies more than 40 per cent of a 200k window on every single request, shrinking the room for actual code before compaction kicks in and spends yet more tokens summarising.

### Cache stability, the decisive difference

Caching only pays if the prefix stays stable, so we hashed the tools array and system blocks of every request in the dataset.

OpenCode emitted byte-identical prefixes across every request and every run. Three separate T1 sessions produced the same tools bytes, the same system bytes, and the same message bytes; the repeat runs wrote zero cache tokens and read everything. Its nine-request T3 session held one stable prefix throughout.

Claude Code emitted three distinct request classes per session; a warmup probe, the main conversation, and subagent calls, each with its own prefix and therefore its own cache entry. Its system bytes also varied between sessions in the same workspace, and its first-message scaffolding varied between runs.

The consequence shows up in the cache-write column. On the identical file-summarise task, Claude Code wrote 53,839 cache tokens across five requests, including one complete mid-task re-write of its full ~43k prefix. OpenCode wrote 1,003.

We re-ran the matched task to check whether that was a one-off. It was not. The large mid-session re-write reproduced, 43,342 tokens in the first run and 36,899 in the second, while a third run against a freshly warmed cache wrote almost nothing. OpenCode showed zero mid-session re-writes in every session we could cleanly meter.

We then repeated the matched task on Claude Fable 5. The behaviour replicated almost exactly; another complete mid-session re-write, this time 50,053 tokens with zero cache read, and a cache-write gap of 52x against Sonnet's 54x. Two model families, same pattern. OpenCode's prefix stayed byte-identical on both.

**Depending on cache temperature, Claude Code's cache-write volume on the same task ranged from 5.9x to 54x OpenCode's**, and cache writes bill at a premium, 1.25x base rate for the 5-minute tier and 2x for the 1-hour tier.

One attribution caveat is owed here. A single mid-task cache miss could in principle be our gateway evicting rather than the harness moving its cache breakpoints; reproduction across runs makes systematic harness behaviour the likelier explanation, and the prefix instability itself is harness-side, visible in the captured bytes before any gateway involvement.

If you have watched a usage meter climb dramatically under Claude Code but stay flat under OpenCode with the same model, this is the likeliest mechanism; bigger prefixes, more distinct prefixes per session, and more re-writes of them, multiplied by any subagent fan-out.

## What about quality?

A fair objection to everything above is that a bill says nothing about the work. Paying more is rational if the output is better.

The tasks here were chosen so that quality could not be the explanation. Both harnesses completed every scored task correctly. The multi-step task was verified by an assertion script each harness had to write and then pass, and both exited clean. The file summaries were both accurate. On these tasks the token gap is the cost difference for an identical outcome, which is exactly what makes it measurable.

Whether the premium buys quality on real engineering work is a different question, and we did not measure it. Claude Code's background agents, skills, and orchestration surface may well earn their tokens on harder tasks. That claim deserves its own benchmark, with a proper test suite and enough runs to score pass rates, and the rig here can drive it.

Two of the findings are independent of quality, though. Re-writing a byte-identical cache prefix mid-session buys no code quality at all; it is the same content, paid for again at premium rates. An instruction file the harness silently ignores buys nothing either. Whatever the capability argument for a larger platform, those two are waste on any definition.

## Dogfooding, or the benchmark dataset as an audit log

The honest version of this experiment is "trust the captured payloads", so we treated the dataset the way we tell clients to treat production inference logs.

Every one of the 185 captured request/response records was written into a tamper-evident, SHA-256 hash-chained audit trail using our open-source library [`@systima/aiact-audit-log`](https://github.com/systima-ai/aiact-audit-log), and the chain verifies end to end.

```
Chain verified: 185 entries
No breaks detected
Hash chain integrity: VALID
```

This is the same mechanism the library provides for EU AI Act Article 12 logging; structured records, integrity you can hand to a third party, and reconstruction of exactly what was sent and returned.

A token benchmark is a low-stakes use of it. A credit-decisioning agent is not.

## Caveats

- One machine, one pair of versions, two model families for the floor and cache lanes (Sonnet 4.5 and Fable 5), one for the multiplier lanes, small n (three T1 runs, three T2 runs, one run per multiplier lane). Harness prompts change frequently, so treat the numbers as a July 2026 snapshot and the method as the durable artefact.
- A local gateway sat in the measurement path. Component-level figures come from captured payloads, which it cannot affect. Metered figures are cold-cache anchors calibrated against its measured constant; warm-run metered numbers were unattributable, so we only quote cold anchors. The gateway also silently substituted a newer model snapshot than the one we pinned, which is its own lesson. If you are not logging at the API boundary, you do not know what model you are actually running. On the Fable path the gateway also resumed a stale server-side session in one lane and executed tools host-side in another, so the Fable multi-step lane for Claude Code was excluded rather than reported.
- The T3 convergence is one observation of one task shape. A strictly sequential task would push Claude Code's request count, and therefore its total, back up. The OpenCode zero-tools and subagent lanes returned malformed streams through the gateway, so for those conditions we report captured payload sizes only.
- The real-configuration figures describe one practitioner's setup, reported in sizes and counts only. Yours will differ; the method transfers.

## Reproducing it

The measurement rig is roughly 200 lines of Node. It is an HTTP proxy that forwards to your model endpoint, writes each request body and response usage block to disk, and appends each pair to an audit chain.

Point `ANTHROPIC_BASE_URL` at it. Give the harness a fresh config directory and an empty workspace for the floor. Then add your instruction file, your MCP servers, and your workflows one at a time, and watch the boundary.

If your traffic passes through a gateway, measure its envelope with a bare request first, and check which model actually answers.

If you run agentic systems in production and cannot currently answer "what exactly did we send to the model last Tuesday", that is the gap worth closing first. The token accounting falls out of it for free.

Claude CodeOpenCodetokensprompt cachingcache writesagent harnessMCPsubagentsbenchmarks

## Related Articles

[Applied ResearchAgentic AIAI Governance\\
\\
**Continuous Conformity: Engineering Evidence for Orchestrated AI Systems** \\
\\
If a Tuesday conformity assessment says little about Wednesday, the static model breaks down for orchestrated AI. A continuous-conformity proposal.\\
\\
18 May 202612 min read](https://systima.ai/blog/continuous-conformity-orchestrated-ai-systems)[AI GovernanceAgentic AI\\
\\
**Systima Comply: EU AI Act Compliance Scanning for CI/CD Pipelines** \\
\\
Open-source static analysis that scans your codebase for AI framework usage and validates risk classifications against the EU AI Act. Snyk for AI.\\
\\
14 March 202610 min read](https://systima.ai/blog/systima-comply-eu-ai-act-compliance-scanning)[LLM Engineering\\
\\
**The Delimiter Hypothesis: Does Prompt Format Actually Matter?** \\
\\
600 model calls across four frontier LLMs testing XML, Markdown, and JSON delimiters. Format usually does not matter. MiniMax M2.5 is the exception.\\
\\
5 March 202617 min read](https://systima.ai/blog/delimiter-hypothesis)

🇺🇸Selling AI into the EU or UK?