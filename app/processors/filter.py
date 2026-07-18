from app.models import NewsArticle
from datetime import datetime, timedelta


IMPORTANT_WORDS = [
    # Core AI / ML
    "ai",
    "artificial intelligence",
    "machine learning",
    "ml",
    "model",
    "foundation model",
    "training",
    "inference",
    "dataset",
    "sample",
    "feature",
    "label",
    "algorithm",
    "prediction",
    "optimization",
    "optimizer",
    "gradient",
    "neural network",
    "deep learning",

    # Deep Learning
    "transformer",
    "attention",
    "self-attention",
    "cnn",
    "rnn",
    "lstm",
    "embedding",
    "vector",
    "activation",
    "layer",
    "weight",
    "bias",

    # LLM
    "llm",
    "large language model",
    "gpt",
    "token",
    "tokenization",
    "context window",
    "prompt",
    "prompt engineering",
    "fine-tuning",
    "instruction tuning",
    "rlhf",
    "alignment",
    "hallucination",
    "reasoning",
    "chain of thought",

    # Generative AI
    "generative ai",
    "generative model",
    "multimodal",
    "image generation",
    "video generation",
    "audio model",
    "diffusion",
    "synthetic data",

    # RAG / Knowledge Systems
    "rag",
    "retrieval augmented generation",
    "retrieval",
    "vector database",
    "knowledge base",
    "grounding",
    "semantic search",

    # Agents
    "agent",
    "ai agent",
    "autonomous agent",
    "agentic",
    "workflow",
    "tool calling",
    "function calling",
    "multi-agent",
    "planning",
    "memory",

    # AI Engineering / Production
    "mlops",
    "model deployment",
    "model serving",
    "inference server",
    "production",
    "scaling",
    "latency",
    "throughput",
    "gpu",
    "cuda",
    "distributed training",
    "cloud",

    # Optimization
    "quantization",
    "distillation",
    "pruning",
    "optimization",
    "efficient model",
    "small language model",
    "slm",

    # Evaluation / Safety
    "benchmark",
    "evaluation",
    "eval",
    "accuracy",
    "precision",
    "recall",
    "f1 score",
    "safety",
    "security",
    "red team",
    "responsible ai",
    "trust",

    # Industry / Business
    "release",
    "launch",
    "introducing",
    "announcement",
    "research",
    "paper",
    "open source",
    "api",
    "sdk",
    "platform",
    "product",
    "startup",
    "funding",
    "investment",
    "acquisition",
    "company",
    "enterprise",
    "automation",

    # Infrastructure / Developer Tools
    "developer",
    "developers",
    "coding",
    "code generation",
    "software engineer",
    "copilot",
    "cli",
    "framework",
    "library",
    "openai",
    "anthropic",
    "google deepmind",
    "meta ai",
    "nvidia"
]


def calculate_score(article: NewsArticle):
    text = f"{article.title} {article.summary}".lower()

    score = 0

    for word in IMPORTANT_WORDS:
        if word in text:
            score += 1

    article.score = score

    return article


def filter_articles(articles, minimum_score: int = 2):

    scored = [
        calculate_score(article)
        for article in articles
    ]

    return [
        article
        for article in scored
        if article.score >= minimum_score
    ]


def filter_recent_articles(
    articles: list[NewsArticle],
    max_age_days: int = 3,
) -> list[NewsArticle]:
    cutoff = datetime.now() - timedelta(days=max_age_days)
    return [
        article
        for article in articles
        if article.published >= cutoff
    ]