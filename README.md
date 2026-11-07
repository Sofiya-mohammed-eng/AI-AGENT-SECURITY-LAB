# AI Agent Security Lab

A small tool-calling AI agent built to demonstrate real security
practices — not just claim them. It answers questions with two tools:
a sandboxed calculator and a search over a small local knowledge base.

See [`docs/SECURITY.md`](docs/SECURITY.md) for the threat model, the
mitigations, and the findings from testing (including an honest failure
case, not just the parts that worked).

## What's in this version

- **Grounded answers:** the model must answer only from knowledge-base
  results and say "I don't know" otherwise.
- **Better search:** relevance ranking (BM25), word stemming and synonym
  groups over 12 public documents. "How much does it cost?" finds the
  pricing entry. Internal documents are never indexed.
- **Safer calculator:** length, exponent and result-size caps (no more
  `9**9**9**9`).
- **Stronger injection guard:** catches reworded and lightly obfuscated
  attacks (zero-width characters, full-width letters).
- **Output checks:** API keys are redacted from answers and logs; an
  answer that quotes the system prompt is replaced.
- **Safe memory:** multi-turn chat that stores only user messages and
  final answers, never raw tool output.
- **Audit log:** every request, tool call and answer is written to
  `logs/agent.jsonl`. Datadog tracing is optional.
- **Tests:** 52 automated tests, mostly offline with a fake model, plus
  optional live tests against the real model.

## Run it

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    export GROQ_API_KEY=your-groq-key

    python3 main.py          # run the three demo scenarios
    python3 main.py chat     # chat with memory (/reset to forget, /quit to exit)
    python3 main.py logs     # show the latest audit-log entries

## Test it

    # Offline: no key, no internet, runs in about a second
    python3 -m unittest -v

    # Live: calls the real model (AI answers vary, so re-run a failure once)
    RUN_LIVE=1 python3 -m unittest tests.test_live -v

## Optional: Datadog tracing

    export DD_API_KEY=your-datadog-api-key
    export DD_LLMOBS_ENABLED=1
    export DD_LLMOBS_ML_APP=ai-agent-security-lab
    export DD_SITE=datadoghq.com
    ddtrace-run python3 main.py

Traces appear in Datadog under **AI Observability → ai-agent-security-lab**.
Without `DD_LLMOBS_ENABLED=1` tracing is simply off.

## Logging settings

    export AGENT_LOG=off                     # turn the local log off
    export AGENT_LOG_PATH=/path/agent.jsonl  # change where it is written

## Stack

Python, OpenAI SDK (pointed at Groq's OpenAI-compatible endpoint),
optional Datadog LLM Observability (`ddtrace`).
