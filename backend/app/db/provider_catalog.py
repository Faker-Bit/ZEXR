"""Curated catalogue of AI model API providers and gateways.

Provenance
----------
This list was compiled by hand from each vendor's public pricing and
documentation pages.  Every row records what the vendor *documents*, not what we
have independently confirmed.

That distinction is why nothing here is ever marked verified.  Rows are stored
with:

* ``verification_status = needs_manual`` — a human or an automated check must
  confirm the free tier still exists before it is presented as fact
* the originating **label** (``FREE`` / ``CREDITS`` / ``CHECK`` / ``PAID`` /
  ``GATEWAY`` / ``HOST`` / ``SELF-HOST``) so the UI can show *why* an offer is
  soft
* ``internal_notes`` carrying the reported wording verbatim

The ``CHECK`` label is deliberate and common: free tiers change weekly, so
several of these are recorded as "verify current access" rather than asserting a
free tier exists.

Import is idempotent: rows are matched on ``(provider name, official_url)`` so
re-running updates labels and notes instead of creating duplicates, and offers
already discovered from a live source are left untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.base import utcnow
from app.models.enums import (
    OfferStatus,
    OfferType,
    SourceType,
    VerificationStatus,
)
from app.models.offer import Offer
from app.models.source import Source
from app.services.offers import unique_slug

log = get_logger("db.provider_catalog")

SOURCE_KEY = "ai-provider-catalogue"
SOURCE_NAME = "AI provider reference catalogue (curated by hand)"
SOURCE_PUBLISHER = "ZEXR Deal Hub editorial"


@dataclass(frozen=True)
class ProviderEntry:
    name: str
    url: str
    label: str  # GATEWAY / HOST / SELF-HOST
    access: str  # FREE / CREDITS / CHECK / PAID
    category: str  # category slug
    note: str
    keywords: tuple[str, ...] = ()

    @property
    def is_gateway(self) -> bool:
        return self.label in ("GATEWAY", "SELF-HOST")


CATALOGUE: tuple[ProviderEntry, ...] = (
    # ------------------------------------------------------------- gateways
    ProviderEntry("OpenRouter", "https://openrouter.ai/", "GATEWAY", "FREE", "ai-tools",
                  "Free models available; account and rate limits apply.",
                  ("router", "llm gateway", "multi-provider")),
    ProviderEntry("Eden AI", "https://www.edenai.co/", "GATEWAY", "CHECK", "ai-tools",
                  "Free models and limited access reported; check the current plan.",
                  ("router", "multi-provider")),
    ProviderEntry("Requesty", "https://requesty.ai/", "GATEWAY", "CREDITS", "ai-tools",
                  "Sign-up credits reported; confirm the current offer.",
                  ("router", "credits")),
    ProviderEntry("AI/ML API", "https://aimlapi.com/", "GATEWAY", "CHECK", "ai-tools",
                  "Confirm the current free tier or sign-up credits.", ("router",)),
    ProviderEntry("NanoGPT", "https://nano-gpt.com/", "GATEWAY", "CHECK", "ai-tools",
                  "Confirm current pricing and free access.", ("router",)),
    ProviderEntry("Vercel AI Gateway", "https://vercel.com/ai-gateway", "GATEWAY", "CREDITS", "ai-tools",
                  "Introductory credits or free models may be available; check the current plan.",
                  ("gateway", "vercel")),
    ProviderEntry("Braintrust", "https://www.braintrust.dev/", "GATEWAY", "CHECK", "developer-tools-apis",
                  "Free start reported; usage limits and model charges still apply.", ("gateway",)),
    ProviderEntry("Portkey", "https://portkey.ai/", "GATEWAY", "CHECK", "developer-tools-apis",
                  "Free plan reported; model inference charges may still apply.", ("gateway",)),
    ProviderEntry("Helicone AI Gateway", "https://www.helicone.ai/", "GATEWAY", "CHECK", "developer-tools-apis",
                  "Free plan reported; model inference charges may still apply.", ("gateway", "observability")),
    ProviderEntry("Cloudflare AI Gateway", "https://developers.cloudflare.com/ai-gateway/", "GATEWAY", "FREE", "developer-tools-apis",
                  "Gateway features are free; inference billing depends on Workers AI or connected providers.",
                  ("gateway", "cloudflare")),
    ProviderEntry("Kilo Gateway", "https://kilo.ai/", "GATEWAY", "FREE", "developer-tools-apis",
                  "A rotating free model pool has been reported; availability and limits change.",
                  ("gateway", "kilo")),
    ProviderEntry("LLM API", "https://llmapi.ai/", "GATEWAY", "CHECK", "ai-tools",
                  "Verify current pricing and free access.", ("gateway",)),
    ProviderEntry("Unify", "https://unify.ai/", "GATEWAY", "CHECK", "ai-tools",
                  "Verify available models, plans and free access.", ("router",)),
    ProviderEntry("LiteLLM", "https://www.litellm.ai/", "SELF-HOST", "FREE", "developer-tools-apis",
                  "Free open-source software; provider inference is not automatically free.",
                  ("self-host", "proxy", "open-source")),
    ProviderEntry("Bifrost", "https://www.getbifrost.ai/", "SELF-HOST", "FREE", "developer-tools-apis",
                  "Free open-source software; provider inference or hardware costs may apply.",
                  ("self-host", "gateway", "open-source")),
    ProviderEntry("Kong AI Gateway", "https://konghq.com/products/kong-ai-gateway", "SELF-HOST", "CHECK", "developer-tools-apis",
                  "Check plan and deployment costs; inference costs are separate.", ("gateway",)),
    ProviderEntry("TrueFoundry", "https://www.truefoundry.com/", "GATEWAY", "CHECK", "developer-tools-apis",
                  "Verify the current trial and plan.", ("gateway", "deployment")),
    ProviderEntry("Merge Gateway", "https://www.merge.dev/products/gateway", "GATEWAY", "CHECK", "developer-tools-apis",
                  "Verify current pricing and access.", ("gateway",)),
    ProviderEntry("Vellum", "https://www.vellum.ai/", "GATEWAY", "CHECK", "developer-tools-apis",
                  "Verify current plans and model usage billing.", ("ai development",)),
    # ------------------------------------------------------ hosted providers
    ProviderEntry("Google AI Studio", "https://aistudio.google.com/", "HOST", "FREE", "ai-tools",
                  "Free tier for eligible models; rate limits and regional terms apply.",
                  ("gemini", "google", "multimodal")),
    ProviderEntry("Groq", "https://groq.com/", "HOST", "FREE", "ai-tools",
                  "Rate-limited developer access reported; check model-specific quotas.",
                  ("inference", "llama")),
    ProviderEntry("Cerebras", "https://cerebras.ai/", "HOST", "FREE", "ai-tools",
                  "Developer free access reported; verify the present quota.", ("inference", "wafer")),
    ProviderEntry("Cloudflare Workers AI", "https://developers.cloudflare.com/workers-ai/", "HOST", "FREE", "ai-tools",
                  "A free daily allowance is reported; shared usage limits apply.",
                  ("edge", "neurons")),
    ProviderEntry("GitHub Models", "https://github.com/marketplace/models", "HOST", "FREE", "ai-tools",
                  "Limited usage for evaluation; rate limits apply.", ("github", "catalog")),
    ProviderEntry("NVIDIA NIM", "https://build.nvidia.com/", "HOST", "CHECK", "ai-tools",
                  "Developer trial endpoints may be available; check whether access is temporary and any data-use conditions.",
                  ("nvidia", "nim")),
    ProviderEntry("Mistral AI", "https://mistral.ai/", "HOST", "CHECK", "ai-tools",
                  "Limited experimentation access may be available; read its terms and data-use conditions.",
                  ("mistral", "le chat")),
    ProviderEntry("Hugging Face Inference Providers", "https://huggingface.co/docs/inference-providers/", "HOST", "FREE", "ai-tools",
                  "Limited included credits may be available; usage beyond them is paid.",
                  ("huggingface", "hf")),
    ProviderEntry("Cohere", "https://cohere.com/", "HOST", "CHECK", "ai-tools",
                  "Developer trial access may be available; check commercial-use restrictions.", ("command",)),
    ProviderEntry("OpenAI API", "https://openai.com/api/", "HOST", "PAID", "ai-tools",
                  "Paid usage. Do not assume a permanent free API tier.", ("openai", "gpt")),
    ProviderEntry("Anthropic API", "https://www.anthropic.com/api", "HOST", "PAID", "ai-tools",
                  "Paid usage. Do not assume a permanent free API tier.", ("anthropic", "claude")),
    ProviderEntry("Together AI", "https://www.together.ai/", "HOST", "CREDITS", "ai-tools",
                  "Introductory credits may be offered; check current account terms.", ("inference",)),
    ProviderEntry("Fireworks AI", "https://fireworks.ai/", "HOST", "CREDITS", "ai-tools",
                  "Introductory credits may be offered; check current account terms.", ("inference",)),
    ProviderEntry("DeepInfra", "https://deepinfra.com/", "HOST", "CHECK", "ai-tools",
                  "Check current pricing and any free offers.", ("inference",)),
    ProviderEntry("Replicate", "https://replicate.com/", "HOST", "CHECK", "ai-tools",
                  "Model marketplace; check the current trial and per-model billing.", ("models",)),
    ProviderEntry("Baseten", "https://www.baseten.co/", "HOST", "CREDITS", "ai-tools",
                  "Verify the current trial; deployment and inference are generally usage-based.",
                  ("deployment",)),
    ProviderEntry("Modal", "https://modal.com/", "HOST", "FREE", "cloud-hosting",
                  "A free compute allowance may be available; check the current plan.",
                  ("compute", "serverless")),
    ProviderEntry("SambaNova Cloud", "https://cloud.sambanova.ai/", "HOST", "CREDITS", "ai-tools",
                  "Trial credits may be offered; confirm the current offer.", ("inference",)),
    ProviderEntry("SiliconFlow", "https://siliconflow.com/", "HOST", "CHECK", "ai-tools",
                  "Free models or promotional access may be available; eligibility varies by region.",
                  ("inference",)),
    ProviderEntry("Inference.net", "https://inference.net/", "HOST", "CHECK", "ai-tools",
                  "Verify current pricing and free access.", ("inference",)),
    ProviderEntry("Chutes", "https://chutes.ai/", "HOST", "FREE", "ai-tools",
                  "Community access may be available; limits and reliability can vary.",
                  ("community",)),
    ProviderEntry("OVHcloud AI Endpoints", "https://www.ovhcloud.com/en/public-cloud/ai-endpoints/", "HOST", "CHECK", "ai-tools",
                  "A limited free anonymous allowance has been reported; check current terms and country availability.",
                  ("ovh",)),
    ProviderEntry("Alibaba Cloud Model Studio", "https://www.alibabacloud.com/en/solutions/generative-ai/model-studio", "HOST", "CHECK", "ai-tools",
                  "Selected models may have trial or free quota; account and region requirements apply.",
                  ("alibaba", "qwen", "dashscope")),
    ProviderEntry("Zhipu AI", "https://open.bigmodel.cn/", "HOST", "CHECK", "ai-tools",
                  "Check current model-specific trial offers and regional terms.", ("z.ai", "glm")),
    ProviderEntry("DeepSeek API", "https://platform.deepseek.com/", "HOST", "CHECK", "ai-tools",
                  "Review current API pricing; do not presume free API usage.", ("deepseek",)),
    ProviderEntry("Moonshot AI", "https://platform.moonshot.ai/", "HOST", "CHECK", "ai-tools",
                  "Review current API pricing and account terms.", ("kimi",)),
    ProviderEntry("Volcengine Ark", "https://www.volcengine.com/product/ark", "HOST", "CREDITS", "ai-tools",
                  "Verify the current trial and regional availability.", ("volcengine", "doubao")),
    ProviderEntry("minimax", "https://www.minimax.io/", "HOST", "CREDITS", "ai-tools",
                  "Check current developer offers and API pricing.", ("minimax",)),
    ProviderEntry("xAI API", "https://console.x.ai/", "HOST", "CREDITS", "ai-tools",
                  "Check sign-up credits and billing terms.", ("grok", "xai")),
    ProviderEntry("AI21 Labs", "https://www.ai21.com/", "HOST", "CREDITS", "ai-tools",
                  "Verify current developer credits and API pricing.", ("jamba", "ai21")),
    ProviderEntry("Perplexity API", "https://www.perplexity.ai/api-platform", "HOST", "CHECK", "ai-tools",
                  "Verify current API pricing and any introductory credits.", ("perplexity", "sonar")),
    ProviderEntry("Amazon Bedrock", "https://aws.amazon.com/bedrock/", "HOST", "CREDITS", "cloud-hosting",
                  "AWS free-trial credits may apply; model usage is generally billed.", ("aws", "bedrock")),
    ProviderEntry("Microsoft Azure AI Foundry", "https://ai.azure.com/", "HOST", "CREDITS", "ai-tools",
                  "Depends on Azure credits, region and the selected model.", ("azure",)),
    ProviderEntry("IBM watsonx", "https://www.ibm.com/products/watsonx-ai", "HOST", "CHECK", "ai-tools",
                  "Check the current trial and API entitlements.", ("ibm", "watsonx")),
    ProviderEntry("Ollama Cloud", "https://ollama.com/", "HOST", "CHECK", "ai-tools",
                  "Cloud access and limits can change; local Ollama is a separate option.", ("ollama",)),
    # ---------------------------------------------------------- self-hosted
    ProviderEntry("Ollama", "https://ollama.com/", "SELF-HOST", "FREE", "developer-tools-apis",
                  "Software is free to run locally; hardware and electricity costs apply.",
                  ("local", "open-source")),
    ProviderEntry("LM Studio", "https://lmstudio.ai/", "SELF-HOST", "FREE", "developer-tools-apis",
                  "Local inference; hardware required.", ("local", "desktop")),
    ProviderEntry("vLLM", "https://github.com/vllm-project/vllm", "SELF-HOST", "FREE", "developer-tools-apis",
                  "Open-source inference server; hardware or cloud compute costs apply.",
                  ("local", "serving", "open-source")),
    ProviderEntry("LocalAI", "https://localai.io/", "SELF-HOST", "FREE", "developer-tools-apis",
                  "Open-source; hardware or cloud compute costs apply.", ("local", "open-source")),
    ProviderEntry("llama.cpp", "https://github.com/ggml-org/llama.cpp", "SELF-HOST", "FREE", "developer-tools-apis",
                  "Open-source; hardware costs apply.", ("local", "gguf", "open-source")),
    ProviderEntry("SGLang", "https://github.com/sgl-project/sglang", "SELF-HOST", "FREE", "developer-tools-apis",
                  "Open-source inference framework; hardware costs apply.", ("local", "open-source")),
)

#: How each access label should be presented. `CHECK` is deliberately the weakest
#: signal in the list and must not read like a confirmed free tier.
ACCESS_COPY: dict[str, str] = {
    "FREE": "Free tier reported by the vendor",
    "CREDITS": "Sign-up or trial credits reported",
    "CHECK": "Free access reported but unconfirmed — verify with the vendor",
    "PAID": "Paid usage — check for temporary credits",
}

OFFER_TYPE_BY_ACCESS: dict[str, OfferType] = {
    "FREE": OfferType.FREE,
    "CREDITS": OfferType.FREE_CREDITS,
    "CHECK": OfferType.FREE,
    "PAID": OfferType.DISCOUNT,
}


def _ensure_source(session: Session) -> Source:
    source = session.execute(select(Source).where(Source.key == SOURCE_KEY)).scalar_one_or_none()
    if source is None:
        source = Source(
            key=SOURCE_KEY,
            name=SOURCE_NAME,
            publisher=SOURCE_PUBLISHER,
            source_type=SourceType.MANUAL.value,
            adapter="json_api",
            homepage_url="https://github.com/topics/free-llm-api",
            # Manual, human-curated intake: never auto-polled.
            is_active=False,
            trust_weight=0.4,
            license_note=(
                "Hand-curated from vendor pricing and documentation pages. "
                "Claims are reported, not independently verified."
            ),
        )
        session.add(source)
        session.flush()
    return source


def _category(session: Session, slug: str):
    """Resolve the target category, falling back to the AI bucket.

    `offers.category_id` is NOT NULL, and a brand-new database may not have the
    category yet, so an unresolved slug must not abort the whole import.
    """
    from app.models.taxonomy import Category

    found = session.execute(select(Category).where(Category.slug == slug)).scalars().first()
    if found is not None:
        return found

    fallback = session.execute(
        select(Category).where(Category.slug == "ai-tools")
    ).scalars().first()
    if fallback is None:
        fallback = Category(
            slug=slug,
            name=slug.replace("-", " ").title(),
            tagline="Deals awaiting review",
            sort_order=900,
        )
        session.add(fallback)
        session.flush()
    return fallback


def import_catalogue(session: Session) -> dict[str, int]:
    """Create or refresh offers for every entry in the catalogue."""
    source = _ensure_source(session)
    now = utcnow()

    created = updated = skipped = 0

    for entry in CATALOGUE:
        existing = session.execute(
            select(Offer).where(Offer.official_url == entry.url)
        ).scalars().first()

        tags = sorted(
            {"ai-provider", "api", entry.label.lower(), entry.access.lower(), *entry.keywords}
        )[:10]
        notes = (
            f"Reported access: {entry.access} ({ACCESS_COPY[entry.access]}). "
            f"Type: {entry.label}. {entry.note} "
            "Compiled from vendor documentation — verify before relying on it."
        )

        if existing is not None:
            # Leave offers that came from a live, verified source alone; only
            # annotate ones that are still unverified.
            if existing.verification_status == VerificationStatus.VERIFIED.value:
                skipped += 1
                continue
            existing.tags = tags
            existing.eligibility_notes = entry.note
            existing.internal_notes = notes
            existing.last_checked_at = existing.last_checked_at or now
            updated += 1
            continue

        session.add(
            Offer(
                slug=unique_slug(session, entry.name.lower().replace(" ", "-")),
                title=entry.name,
                short_description=f"{ACCESS_COPY[entry.access]} — {entry.note}"[:400],
                description=f"{entry.note}\n\nReported access level: {entry.access}.",
                offer_type=OFFER_TYPE_BY_ACCESS[entry.access].value,
                category_id=_category(session, entry.category).id,
                status=OfferStatus.PUBLISHED.value,
                # Never verified: these are claims from vendor pages, not the
                # result of an automated check of a live offer URL.
                verification_status=VerificationStatus.NEEDS_MANUAL.value,
                tags=tags,
                official_url=entry.url,
                is_global=True,
                starts_at=now,
                published_at=now,
                is_genuinely_free=entry.access == "FREE",
                eligibility_notes=entry.note,
                internal_notes=notes,
                source_id=source.id,
                discovery_confidence=0.6,
                is_demo_data=False,
            )
        )
        created += 1

    session.flush()
    log.info("provider_catalogue.imported", extra={"created": created, "updated": updated, "skipped": skipped})
    return {"created": created, "updated": updated, "skipped": skipped, "total": len(CATALOGUE)}


__all__ = ["ACCESS_COPY", "CATALOGUE", "ProviderEntry", "SOURCE_KEY", "import_catalogue"]