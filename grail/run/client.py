"""Models under audit — the interface, an offline stub, and an HTTP skeleton.

A model is anything with an `id` and a `generate`. The id is not decoration: it
is pinned into every response record, because "we audited Llama" is not a
reproducible claim and "llama-3.1-70b-instruct @ t=0.0, top_p=1.0" is.

`StubModel` keeps the pipeline runnable offline, exactly like the hashing
embedder in the index and the stub proposer in the gold pipeline. It is plumbing,
not evidence: the runner refuses to write a response log from it unless
`allow_stub` is passed, and its id stays in the log forever so a stub run can
never be mistaken for a real one.

The stub takes a `rule` so tests can make it sensitive or insensitive to a
particular field on purpose — that is how the positive controls are shown to
detect a known effect when one exists and to stay quiet when it does not.
"""
from __future__ import annotations

import hashlib
import json
from typing import Callable, Protocol


class Model(Protocol):
    id: str

    def generate(self, prompt: str, **params) -> str:
        """Return the raw response text for one prompt."""

    # Optional. A model that can answer many prompts at once should implement
    # this; the runner uses it when present and falls back to `generate`
    # otherwise. For a local GPU this is not a minor optimisation — batching
    # 3500 prompts through vLLM is roughly an order of magnitude faster than
    # 3500 sequential HTTP calls to the same GPU.
    # def generate_batch(self, prompts: list[str], **params) -> list[str]: ...


def params_hash(params: dict) -> str:
    return hashlib.sha256(
        json.dumps(params, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


# --- offline stub -----------------------------------------------------------
def hash_rule(prompt: str) -> str:
    """Deterministic but arbitrary: decides by hashing the prompt.

    Insensitive to everything meaningful, so a run against this rule SHOULD show
    controls failing to fire. That is the correct behaviour to see from plumbing,
    and a pilot report that flags it is working.
    """
    h = int(hashlib.blake2b(prompt.encode(), digest_size=8).hexdigest(), 16)
    return "APPROVE" if h % 100 < 55 else "DECLINE"


def field_sensitive_rule(field_label: str, threshold: float,
                         above_is_bad: bool = True) -> Callable[[str], str]:
    """A rule that actually reads one labelled field out of the prompt.

    Used in tests to give the runner something that responds to a known effect,
    so the controls can be shown to detect it.
    """
    import re

    def rule(prompt: str) -> str:
        m = re.search(rf"{re.escape(field_label)}:\s*(?:EUR\s*)?(-?\d+(?:\.\d+)?)",
                      prompt, re.IGNORECASE)
        if not m:
            return hash_rule(prompt)
        value = float(m.group(1))
        bad = value > threshold if above_is_bad else value < threshold
        return "DECLINE" if bad else "APPROVE"

    return rule


class StubModel:
    """Offline stand-in. Never evidence; only keeps the pipeline runnable."""

    is_stub = True

    def __init__(self, rule: Callable[[str], str] = hash_rule,
                 model_id: str = "stub/deterministic-1.0",
                 refusal_rate: float = 0.0):
        self.id = model_id
        self.rule = rule
        self.refusal_rate = refusal_rate

    def generate(self, prompt: str, **params) -> str:
        if self.refusal_rate:
            h = int(hashlib.blake2b(prompt.encode(), digest_size=4).hexdigest(), 16)
            if (h % 1000) / 1000.0 < self.refusal_rate:
                return "I'm not able to make lending decisions on individual applications."
        return self.rule(prompt)


# --- real backend skeleton --------------------------------------------------
class HTTPModel:
    """OpenAI-compatible chat endpoint (works for most local servers too).

    Deliberately thin and not wired to any provider by default: the audited
    models are a design decision with a hard constraint attached — the judge must
    come from a family DISJOINT from every model it grades — so the choice
    belongs in your config, not baked in here.
    """

    is_stub = False

    def __init__(self, model_id: str, base_url: str, api_key: str = "",
                 timeout: int = 60):
        self.id = model_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def generate(self, prompt: str, **params) -> str:
        import urllib.request

        body = json.dumps({
            "model": self.id,
            "messages": [{"role": "user", "content": prompt}],
            **params,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.loads(resp.read())
        return payload["choices"][0]["message"]["content"]


class VLLMModel:
    """A local model held in this process, via vLLM's offline API.

    No server, no ports, no second terminal — and every prompt in a run goes
    through one batched call, which is what makes a full 3500-prompt sweep on a
    single GPU take minutes rather than hours.

    The model id recorded in the log is the HuggingFace repo id plus the
    sampling parameters, because "we audited Qwen" is not a reproducible claim.
    """

    is_stub = False

    def __init__(self, model_id: str, max_model_len: int = 4096,
                 gpu_memory_utilization: float = 0.85, max_tokens: int = 512,
                 dtype: str = "auto", enforce_eager: bool = False,
                 **engine_kwargs):
        """`enforce_eager` skips torch.compile.

        Worth roughly 10-20% throughput, and worth paying on a shared machine
        where a stale native extension (a NumPy-1-era ml_dtypes, say) makes the
        compilation path segfault. The audit does not care how the tensors were
        scheduled, so a slower run that finishes beats a fast one that crashes.
        """
        from vllm import LLM

        self.id = model_id
        self.max_tokens = max_tokens
        self.llm = LLM(model=model_id, max_model_len=max_model_len,
                       gpu_memory_utilization=gpu_memory_utilization,
                       dtype=dtype, enforce_eager=enforce_eager, **engine_kwargs)

    def _sampling(self, params: dict):
        from vllm import SamplingParams
        return SamplingParams(
            temperature=params.get("temperature", 0.0),
            top_p=params.get("top_p", 1.0),
            max_tokens=params.get("max_tokens", self.max_tokens),
            seed=params.get("seed"))

    def _as_text(self, prompts: list[str]) -> list[str]:
        """Apply the model's own chat template — a raw prompt scores differently."""
        tok = self.llm.get_tokenizer()
        return [tok.apply_chat_template([{"role": "user", "content": p}],
                                        tokenize=False, add_generation_prompt=True)
                for p in prompts]

    def generate_batch(self, prompts: list[str], **params) -> list[str]:
        sp = self._sampling(params)
        try:                                    # newer vLLM: chat() templates for us
            outs = self.llm.chat([[{"role": "user", "content": p}] for p in prompts],
                                 sampling_params=sp, use_tqdm=True)
        except (AttributeError, TypeError):     # older vLLM: template by hand
            outs = self.llm.generate(self._as_text(prompts), sp, use_tqdm=True)
        return [o.outputs[0].text.strip() for o in outs]

    def generate(self, prompt: str, **params) -> str:
        return self.generate_batch([prompt], **params)[0]
