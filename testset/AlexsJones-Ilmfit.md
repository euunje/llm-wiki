---
type: "raw-source"
author:
  - "[[Ja]]"
dateCreated: 2026-07-14
dateModified: 2026-07-14
dateIngested: 2026-07-14
source: "https://github.com/AlexsJones/llmfit"
category: "article"
clipType: "github"
status: "ingested"
collectionPurpose: "웹 원문을 보존하고 llm-wiki ingest로 source/concept/entity 생성을 검토하기 위해 캡처."
clip_type: "github"
repo: "AlexsJones/llmfit: Hundreds of models & providers. One command to find what runs on your hardware."
owner: "AlexsJones"
stars: "29.4k"
forks: "1.8k"
primary_language: "[\"Rust\",\"Python\",\"JavaScript\",\"CSS\",\"Shell\",\"HTML\",\"Other\"]"
license: "MIT license"
topics:
  - "skill"
  - "mlx"
  - "llm"
  - "localai"
  - "gguf"
  - "unsloth"
description: "Hundreds of models & providers. One command to find what runs on your hardware. - AlexsJones/llmfit"
platform: "GitHub"
tags:
  - "raw-source"
  - "web-clipper"
  - "article"
  - "github"
---
> [!info]+ Raw Source — Ja Vault
> Obsidian Web Clipper로 캡처한 원문입니다. `10. Raw Sources/`에 보존하고,
> 분석/요약/개념화는 llm-wiki 웹 UI의 `수집`/`작업` 흐름에서 수행합니다.

---

## Source Metadata

| Field | Value |
|-------|-------|
| Repo | AlexsJones/llmfit: Hundreds of models & providers. One command to find what runs on your hardware. |
| Owner | AlexsJones |
| Description | Hundreds of models & providers. One command to find what runs on your hardware. - AlexsJones/llmfit |
| ⭐ Stars | 29.4k |
| 🍴 Forks | 1.8k |
| 👀 Watchers |  |
| Primary Language | ["Rust","Python","JavaScript","CSS","Shell","HTML","Other"] |
| License | MIT license |
| Last Commit | Jul 10, 2026 |
| URL | https://github.com/AlexsJones/llmfit |

### Topics

skill, mlx, llm, localai, gguf, unsloth

---

## README / Content

## llmfit

[![llmfit icon](https://github.com/AlexsJones/llmfit/raw/main/assets/icon.svg)](https://github.com/AlexsJones/llmfit/blob/main/assets/icon.svg)

**English** · [中文](https://github.com/AlexsJones/llmfit/blob/main/README.zh.md) · [日本語](https://github.com/AlexsJones/llmfit/blob/main/README.ja.md)

> **📊 New: benchmark & share — real numbers from your machine, better estimates for everyone.** `llmfit bench --share` measures real tok/s on your hardware and contributes it back to the project as a PR — no `gh` CLI, no third-party account. Every run is saved locally first (skip sharing, upload the backlog any time), your own measurements replace estimates in the fit table, and each merged submission ships in the next release: anyone on identical hardware gets measured `✓` numbers and calibrated estimates before they ever run a benchmark. [Get started with sharing →](https://github.com/AlexsJones/llmfit/blob/main/docs/cli.md#contributing-benchmarks-bench---share)
> 
> *Previously: [llmfit 1.0 — the release where the numbers became verifiable →](https://github.com/AlexsJones/llmfit/discussions/708)*

**Hundreds of models & providers. One command to find what runs on your hardware.**

A terminal tool that right-sizes LLM models to your system's RAM, CPU, and GPU. Detects your hardware, scores each model across quality, speed, fit, and context dimensions, and tells you which ones will actually run well on your machine.

Ships with an interactive TUI (default) and a classic CLI mode. Supports multi-GPU setups, MoE architectures, dynamic quantization selection, speed estimation, and local runtime providers (Ollama, llama.cpp, MLX, Docker Model Runner, LM Studio).

> **Sister projects:**
> 
> - [sympozium](https://github.com/sympozium-ai/sympozium/) — managing agents in Kubernetes.
> - [llmserve](https://github.com/AlexsJones/llmserve) — a simple TUI for serving local LLM models. Pick a model, pick a backend, serve it.
> - [llama-panel](https://github.com/AlexsJones/llama-panel) — a native macOS app for managing local llama-server instances.

[![demo](https://github.com/AlexsJones/llmfit/raw/main/assets/demo.gif)](https://github.com/AlexsJones/llmfit/blob/main/assets/demo.gif)

## Documentation

|  |  |
| --- | --- |
| **Get started** | [Install](#install) · [Usage](#usage) · [How it works](#how-it-works) |
| **Guides** | [TUI guide](https://github.com/AlexsJones/llmfit/blob/main/docs/tui.md) · [CLI & automation](https://github.com/AlexsJones/llmfit/blob/main/docs/cli.md) · [Runtime providers](https://github.com/AlexsJones/llmfit/blob/main/docs/providers.md) · [OpenClaw integration](https://github.com/AlexsJones/llmfit/blob/main/docs/openclaw.md) |
| **Reference** | [How it works (full)](https://github.com/AlexsJones/llmfit/blob/main/docs/how-it-works.md) · [Platform & GPU support](https://github.com/AlexsJones/llmfit/blob/main/docs/platform-support.md) · [Custom models](https://github.com/AlexsJones/llmfit/blob/main/docs/custom-models.md) · [Development](https://github.com/AlexsJones/llmfit/blob/main/docs/development.md) |
| **Project** | [Contributing](#contributing) · [Alternatives](#alternatives) · [Code signing](#code-signing) · [License](#license) |

---

## Install

### Windows

```
scoop install llmfit
```

If Scoop is not installed, follow the [Scoop installation guide](https://scoop.sh/).

### macOS / Linux

#### Homebrew

Prebuilt binary (recommended, works on all macOS/Linux versions):

```
brew install AlexsJones/llmfit/llmfit
```

Or from the homebrew-core formula, which builds from source on macOS versions without a bottle:

```
brew install llmfit
```

#### MacPorts

```
port install llmfit
```

#### Quick install

```
curl -fsSL https://llmfit.axjns.dev/install.sh | sh
```

Downloads the latest release binary from GitHub and installs it to `/usr/local/bin` (or `~/.local/bin` if no sudo).

**Install to `~/.local/bin` without sudo:**

```
curl -fsSL https://llmfit.axjns.dev/install.sh | sh -s -- --local
```

### uv / pip

To install or update llmfit:

```
uv tool install -U llmfit
```

To run without installing:

```
uvx llmfit
```

You can also install llmfit as a Python package in the normal way with tools such as pip or uv.

### Docker / Podman

```
docker run ghcr.io/alexsjones/llmfit
```

This prints JSON from `llmfit recommend` command. The JSON could be further queried with `jq`.

```
podman run ghcr.io/alexsjones/llmfit recommend --use-case coding | jq '.models[].name'
```

To launch the interactive TUI instead, pass the global `--tui` flag:

```
docker run --rm -it ghcr.io/alexsjones/llmfit --tui
```

### From source

```
git clone https://github.com/AlexsJones/llmfit.git
cd llmfit
cargo build --release
# binary is at target/release/llmfit
```

---

## Usage

```
llmfit          # interactive TUI: your hardware, every model, ranked
```

The TUI shows your detected specs at the top and every model scored for fit, speed, quality, and context. See the [TUI guide](https://github.com/AlexsJones/llmfit/blob/main/docs/tui.md) for navigation, planning, simulation, downloads, the community leaderboard, and benchmarking.

For scripts, agents, and classic terminal output:

```
llmfit fit                    # table of all models ranked by fit
llmfit recommend --json       # top picks as JSON (agent/script consumption)
llmfit info "<model>"         # one model: fit analysis, estimate basis, verify commands
llmfit bench                  # measure real tok/s/TTFT against your running provider
llmfit doctor                 # hardware detection report for bug reports
```

Full reference: [CLI & automation](https://github.com/AlexsJones/llmfit/blob/main/docs/cli.md).

---

## How it works

llmfit detects your hardware (RAM, CPU, GPU/VRAM, backend), then scores every model in its catalog across four dimensions: memory fit, estimated speed, quality, and context. Speed estimates come from a memory-bandwidth model grounded in runtime sampling and real community measurements — and every estimate ships its inputs, so `llmfit info` shows exactly what a number assumes and how to verify it on your machine.

Full detail, including the estimation formulas and the model database: [How llmfit works](https://github.com/AlexsJones/llmfit/blob/main/docs/how-it-works.md).

---

## Contributing

Contributions are welcome, especially new models.

### Before submitting a PR

Please run `cargo fmt` before pushing your changes. Most CI check failures are caused by unformatted code:

```
cargo fmt
```

Guides for adding models — locally (no rebuild) or to the built-in catalog: [Custom models](https://github.com/AlexsJones/llmfit/blob/main/docs/custom-models.md).

---

## Alternatives

If you're looking for a different approach, check out [llm-checker](https://github.com/Pavelevich/llm-checker) -- a Node.js CLI tool with Ollama integration that can pull and benchmark models directly. It takes a more hands-on approach by actually running models on your hardware via Ollama, rather than estimating from specs. Good if you already have Ollama installed and want to test real-world performance. Note that it doesn't support MoE (Mixture-of-Experts) architectures -- all models are treated as dense, so memory estimates for models like Mixtral or DeepSeek-V3 will reflect total parameter count rather than the smaller active subset.

---

## Code signing

llmfit's Windows release binaries are digitally signed (Authenticode) via [SignPath.io](https://about.signpath.io/), with a free code signing certificate provided by the [SignPath Foundation](https://signpath.org/).

Signing happens automatically in the [release pipeline](https://github.com/AlexsJones/llmfit/blob/main/.github/workflows/release.yml): only artifacts built by GitHub Actions from this repository are submitted for signing, and signing requests are approved by the project maintainer ([@AlexsJones](https://github.com/AlexsJones)).

**Code signing policy:** see the [SignPath Foundation code signing policy and terms](https://signpath.org/terms).

**Privacy:** this program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it. llmfit only contacts external services when you explicitly use the corresponding feature (e.g. model downloads, runtime provider queries, or the community leaderboard).

---

## Original Content

## llmfit

[![llmfit icon](https://github.com/AlexsJones/llmfit/raw/main/assets/icon.svg)](https://github.com/AlexsJones/llmfit/blob/main/assets/icon.svg)

**English** · [中文](https://github.com/AlexsJones/llmfit/blob/main/README.zh.md) · [日本語](https://github.com/AlexsJones/llmfit/blob/main/README.ja.md)

> **📊 New: benchmark & share — real numbers from your machine, better estimates for everyone.** `llmfit bench --share` measures real tok/s on your hardware and contributes it back to the project as a PR — no `gh` CLI, no third-party account. Every run is saved locally first (skip sharing, upload the backlog any time), your own measurements replace estimates in the fit table, and each merged submission ships in the next release: anyone on identical hardware gets measured `✓` numbers and calibrated estimates before they ever run a benchmark. [Get started with sharing →](https://github.com/AlexsJones/llmfit/blob/main/docs/cli.md#contributing-benchmarks-bench---share)
> 
> *Previously: [llmfit 1.0 — the release where the numbers became verifiable →](https://github.com/AlexsJones/llmfit/discussions/708)*

**Hundreds of models & providers. One command to find what runs on your hardware.**

A terminal tool that right-sizes LLM models to your system's RAM, CPU, and GPU. Detects your hardware, scores each model across quality, speed, fit, and context dimensions, and tells you which ones will actually run well on your machine.

Ships with an interactive TUI (default) and a classic CLI mode. Supports multi-GPU setups, MoE architectures, dynamic quantization selection, speed estimation, and local runtime providers (Ollama, llama.cpp, MLX, Docker Model Runner, LM Studio).

> **Sister projects:**
> 
> - [sympozium](https://github.com/sympozium-ai/sympozium/) — managing agents in Kubernetes.
> - [llmserve](https://github.com/AlexsJones/llmserve) — a simple TUI for serving local LLM models. Pick a model, pick a backend, serve it.
> - [llama-panel](https://github.com/AlexsJones/llama-panel) — a native macOS app for managing local llama-server instances.

[![demo](https://github.com/AlexsJones/llmfit/raw/main/assets/demo.gif)](https://github.com/AlexsJones/llmfit/blob/main/assets/demo.gif)

## Documentation

|  |  |
| --- | --- |
| **Get started** | [Install](#install) · [Usage](#usage) · [How it works](#how-it-works) |
| **Guides** | [TUI guide](https://github.com/AlexsJones/llmfit/blob/main/docs/tui.md) · [CLI & automation](https://github.com/AlexsJones/llmfit/blob/main/docs/cli.md) · [Runtime providers](https://github.com/AlexsJones/llmfit/blob/main/docs/providers.md) · [OpenClaw integration](https://github.com/AlexsJones/llmfit/blob/main/docs/openclaw.md) |
| **Reference** | [How it works (full)](https://github.com/AlexsJones/llmfit/blob/main/docs/how-it-works.md) · [Platform & GPU support](https://github.com/AlexsJones/llmfit/blob/main/docs/platform-support.md) · [Custom models](https://github.com/AlexsJones/llmfit/blob/main/docs/custom-models.md) · [Development](https://github.com/AlexsJones/llmfit/blob/main/docs/development.md) |
| **Project** | [Contributing](#contributing) · [Alternatives](#alternatives) · [Code signing](#code-signing) · [License](#license) |

---

## Install

### Windows

```
scoop install llmfit
```

If Scoop is not installed, follow the [Scoop installation guide](https://scoop.sh/).

### macOS / Linux

#### Homebrew

Prebuilt binary (recommended, works on all macOS/Linux versions):

```
brew install AlexsJones/llmfit/llmfit
```

Or from the homebrew-core formula, which builds from source on macOS versions without a bottle:

```
brew install llmfit
```

#### MacPorts

```
port install llmfit
```

#### Quick install

```
curl -fsSL https://llmfit.axjns.dev/install.sh | sh
```

Downloads the latest release binary from GitHub and installs it to `/usr/local/bin` (or `~/.local/bin` if no sudo).

**Install to `~/.local/bin` without sudo:**

```
curl -fsSL https://llmfit.axjns.dev/install.sh | sh -s -- --local
```

### uv / pip

To install or update llmfit:

```
uv tool install -U llmfit
```

To run without installing:

```
uvx llmfit
```

You can also install llmfit as a Python package in the normal way with tools such as pip or uv.

### Docker / Podman

```
docker run ghcr.io/alexsjones/llmfit
```

This prints JSON from `llmfit recommend` command. The JSON could be further queried with `jq`.

```
podman run ghcr.io/alexsjones/llmfit recommend --use-case coding | jq '.models[].name'
```

To launch the interactive TUI instead, pass the global `--tui` flag:

```
docker run --rm -it ghcr.io/alexsjones/llmfit --tui
```

### From source

```
git clone https://github.com/AlexsJones/llmfit.git
cd llmfit
cargo build --release
# binary is at target/release/llmfit
```

---

## Usage

```
llmfit          # interactive TUI: your hardware, every model, ranked
```

The TUI shows your detected specs at the top and every model scored for fit, speed, quality, and context. See the [TUI guide](https://github.com/AlexsJones/llmfit/blob/main/docs/tui.md) for navigation, planning, simulation, downloads, the community leaderboard, and benchmarking.

For scripts, agents, and classic terminal output:

```
llmfit fit                    # table of all models ranked by fit
llmfit recommend --json       # top picks as JSON (agent/script consumption)
llmfit info "<model>"         # one model: fit analysis, estimate basis, verify commands
llmfit bench                  # measure real tok/s/TTFT against your running provider
llmfit doctor                 # hardware detection report for bug reports
```

Full reference: [CLI & automation](https://github.com/AlexsJones/llmfit/blob/main/docs/cli.md).

---

## How it works

llmfit detects your hardware (RAM, CPU, GPU/VRAM, backend), then scores every model in its catalog across four dimensions: memory fit, estimated speed, quality, and context. Speed estimates come from a memory-bandwidth model grounded in runtime sampling and real community measurements — and every estimate ships its inputs, so `llmfit info` shows exactly what a number assumes and how to verify it on your machine.

Full detail, including the estimation formulas and the model database: [How llmfit works](https://github.com/AlexsJones/llmfit/blob/main/docs/how-it-works.md).

---

## Contributing

Contributions are welcome, especially new models.

### Before submitting a PR

Please run `cargo fmt` before pushing your changes. Most CI check failures are caused by unformatted code:

```
cargo fmt
```

Guides for adding models — locally (no rebuild) or to the built-in catalog: [Custom models](https://github.com/AlexsJones/llmfit/blob/main/docs/custom-models.md).

---

## Alternatives

If you're looking for a different approach, check out [llm-checker](https://github.com/Pavelevich/llm-checker) -- a Node.js CLI tool with Ollama integration that can pull and benchmark models directly. It takes a more hands-on approach by actually running models on your hardware via Ollama, rather than estimating from specs. Good if you already have Ollama installed and want to test real-world performance. Note that it doesn't support MoE (Mixture-of-Experts) architectures -- all models are treated as dense, so memory estimates for models like Mixtral or DeepSeek-V3 will reflect total parameter count rather than the smaller active subset.

---

## Code signing

llmfit's Windows release binaries are digitally signed (Authenticode) via [SignPath.io](https://about.signpath.io/), with a free code signing certificate provided by the [SignPath Foundation](https://signpath.org/).

Signing happens automatically in the [release pipeline](https://github.com/AlexsJones/llmfit/blob/main/.github/workflows/release.yml): only artifacts built by GitHub Actions from this repository are submitted for signing, and signing requests are approved by the project maintainer ([@AlexsJones](https://github.com/AlexsJones)).

**Code signing policy:** see the [SignPath Foundation code signing policy and terms](https://signpath.org/terms).

**Privacy:** this program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it. llmfit only contacts external services when you explicitly use the corresponding feature (e.g. model downloads, runtime provider queries, or the community leaderboard).


---

## Ja Vault Processing Notes

- 저장 위치: `10. Raw Sources/`
- 처리 방식: 필요한 항목을 llm-wiki 웹 UI `수집`에서 선택해 source summary / concept / entity를 생성합니다.
- 원문 보존: `Original Content` 섹션은 캡처 후 가능한 한 수정하지 않습니다.
- Clipper 호환성: frontmatter key는 import 안정성을 위해 `dateCreated/dateModified/dateIngested`를 사용합니다. Ja schema의 `date created/date modified/date ingested`와 같은 의미입니다.
