# Support Triage Agent

## Overview

This agent reads rows from an input CSV of customer support tickets, pulls evidence only from the local Markdown corpus under `data/`, assigns labels, and writes one output CSV row per ticket with reply or escalation metadata. The corpus is partitioned into three product domains: **HackerRank**, **Claude**, and **Visa** (`schemas.CANONICAL_COMPANIES`).

## How it works

- **Classify.** `classifier.classify_ticket` normalizes the CSV `company` field, optionally infers a company from retrieval scores when blank, assigns `request_type`, and attaches keyword-based `risk_tags` before anything else touches the ticket.
- **Retrieve.** `retriever.Retriever.search` runs hybrid BM25 + sparse TF-IDF over prebuilt chunks scoped to that company (when one is resolved), yielding the top snippets used as grounding context for answers.
- **Route.** `router.decide` applies fixed escalation rules (outages, unresolved company, security, refunds, legal hooks, Visa fraud carve-outs, weak retrieval scores) ahead of drafting a customer-facing reply—escalations are not negotiable in the responder.
- **Respond.** `responder.build_response` picks `product_area` heuristically, emits templates or chunked text for deterministic replies where applicable, optionally asks Groq (`providers.LLMProvider`) for polished JSON (`response`, `justification`), then hands the row to `validator.validate_row` before CSV write (`utils.csv_io.write_output`).

## Setup

Exact sequence from scratch (repository root; `requirements.txt` and `.env.example` live under `code/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r code/requirements.txt
cp code/.env.example code/.env
```

Then edit `code/.env` and set `GROQ_API_KEY` for LLM-backed phrasing (`main.load_env()` also honours a `./.env` in the cwd if you prefer the file at the repo root). Leaving `GROQ_API_KEY` empty still completes a full run—`providers.LLMProvider.complete_json` returns `{}` immediately and `responder` keeps its deterministic templates plus `_fallback_justification`.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `GROQ_API_KEY` | Required for Groq LLM formatting of `response` / `justification`; when missing, the run still finishes using templates only. | none |
| `GROQ_MODEL` | Model ID passed as `model=` to Groq completions. | `llama-3.3-70b-versatile` |
| `GROQ_BASE_URL` | REST base URL for the OpenAI client. | `https://api.groq.com/openai/v1` |

`ProviderConfig` also sets `temperature=0` and `timeout=45` (`providers.py`). CLI flag `--use-llm` makes `main.select_provider` construct an `LLMProvider` instance even without a key; completions stay empty unless the API key produces a chat response.

## Build the index

Run once before (or implicitly at the start of) `main.py`:

```bash
python3 code/build_index.py
```

This walks `data/`, shards Markdown into cached chunks plus IDF statistics, and writes `code/.cache/index.json`, skipping work when `ingest.data_hash` matches (`build_index.build_index`). On a typical laptop for this repository’s corpus, the cold build finishes in roughly **a few seconds to tens of seconds**; subsequent runs reuse the cached file until corpus bytes change.

`main.run` invokes `build_index()` automatically anyway, but building explicitly is useful after editing docs or wiping `.cache`.

## Run the agent

```bash
python3 code/main.py --in support_tickets/support_tickets.csv --out support_tickets/output.csv
```

Progress is logged to stderr and **`code/run.log`** each time a ticket finishes (**`Finished row i/N`**). The output CSV appears **only after all rows complete** (`write_output` runs at the end), so with **`GROQ_API_KEY`** set expect **one Groq HTTP call per non-escalated reply path** across the whole file—not a freeze.

Groq outages, quota errors, malformed JSON, or network failures resolve inside `responder.build_response`’s `try`/`except`: the row keeps the deterministic template or first-chunk answer and the ticket-specific `_fallback_justification`, so the CSV always contains every input row with no partial write.

## Run tests

```bash
cd code && python3 -m pytest tests/ -q
```

The suite exercises classification, routing, and an end-to-end pass over `support_tickets/sample_support_tickets.csv`.

## Output format

All columns are written in the order `schemas.OUTPUT_COLUMNS` with `csv.QUOTE_ALL`.

| Column | Allowed values | Produced by |
| --- | --- | --- |
| `issue` | Free text (echoed from input) | `main.process_ticket` (input passthrough) |
| `subject` | Free text (echoed from input) | `main.process_ticket` (input passthrough) |
| `company` | Free text (echoed from input, stripped) | `main.process_ticket` (input passthrough) |
| `response` | Free text; escalations forced to `Escalate to a human` | `responder.build_response` (templates + optional LLM); `validator.validate_row` enforces escalation copy |
| `product_area` | Must match `schemas.PRODUCT_AREAS` for the row’s company after normalization (or `""` when disallowed/unknown) | `responder.choose_product_area` + `validator.normalize_product_area` |
| `status` | `replied`, `escalated` | `router.decide` → `main.process_ticket`; invalid enum coerced in `validator` |
| `request_type` | `product_issue`, `feature_request`, `bug`, `invalid` | `classifier.classify_ticket`; coerced in `validator` if malformed |
| `justification` | Free text, stripped and truncated to 300 chars in validation | `responder.build_response` (deterministic escalation/invalid maps, `_fallback_justification`, optional LLM polish) |

## Swapping models

Change models by setting **`GROQ_MODEL`** to any ID Groq serves; **`LLMProvider`** forwards it to `chat.completions.create`. Today’s **[production](https://console.groq.com/docs/models)** options include **`llama-3.3-70b-versatile`**, **`llama-3.1-8b-instant`**, **`openai/gpt-oss-120b`**, and **`openai/gpt-oss-20b`**; preview slots such as **`meta-llama/llama-4-scout-17b-16e-instruct`** or **`qwen/qwen3-32b`** can relieve rate pressure but may deprecate abruptly—confirm with `curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models`.

For **local** checkpoints (recent **Google Gemma**, **Alibaba Qwen 3.x**/`qwen3` families, Moonshot/Kimi releases exposed as GGUF/API, etc.), run an OpenAI-compatible server (**Ollama**, **LM Studio**, **vLLM**), repoint **`GROQ_BASE_URL`** (typically `http://127.0.0.1:11434/v1` for Ollama’s shim), set **`GROQ_MODEL`** to the tag listed by `ollama list`/`vllm` config, dummy **`GROQ_API_KEY`** only if the shim demands a non-empty string, and loosen **`providers.py`** if **`response_format`** / **`seed`** are unsupported for that backend.
