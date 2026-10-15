# AI Agent Security Lab

A small tool-calling AI agent built to demonstrate real security
practices — not just claim them — and instrumented end-to-end with
Datadog LLM Observability.

## What it does

The agent answers questions using two tools: a sandboxed calculator
and a lookup against a small local knowledge base (standing in for a
vector DB). Every run, tool call, and model response is traced in
Datadog.

See [`docs/SECURITY.md`](docs/SECURITY.md) for the full threat model,
the mitigations implemented, and two real findings from testing,
including one honest failure case (hallucination), not just the parts
that worked.

## Run it

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

    export GROQ_API_KEY=your-groq-key
    export DD_API_KEY=your-datadog-api-key
    export DD_LLMOBS_ENABLED=1
    export DD_LLMOBS_ML_APP=ai-agent-security-lab
    export DD_SITE=datadoghq.com

    ddtrace-run python3 main.py

Traces appear in Datadog under **AI Observability → ai-agent-security-lab**.

## Stack

Python, OpenAI SDK (pointed at Groq's OpenAI-compatible endpoint),
Datadog LLM Observability (`ddtrace`).
