"""Domain tag auto-derivation engine.

Matches paper titles and abstracts against keyword rules to suggest
domain tags. Supports both static rule tables and lightweight
embedding-based matching (optional).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from .models import ConfidenceLevel, DomainTag, Paper, PaperTag

logger = logging.getLogger(__name__)


@dataclass
class TagRule:
    """A single keyword-based tagging rule."""

    tag_id: str
    keywords: list[str]
    case_sensitive: bool = False
    weight: float = 1.0
    require_all: bool = False  # If True, all keywords must match

    def matches(self, text: str) -> bool:
        """Check whether the text matches this rule."""
        t = text if self.case_sensitive else text.lower()
        if self.require_all:
            return all(kw in t for kw in self.keywords)
        return any(kw in t for kw in self.keywords)


# ---------------------------------------------------------------------------
# Default rule set — curated for CS/AI literature
# ---------------------------------------------------------------------------

DEFAULT_TAG_RULES: list[TagRule] = [
    # Level 1: Broad fields
    TagRule("artificial_intelligence", ["artificial intelligence", "ai ", "ai-based", "ai-driven"]),
    TagRule("computer_vision", ["computer vision", "vision transformer", "image classification", "object detection", "semantic segmentation", "image generation", "visual ", "cnn", "convolutional neural"]),
    TagRule("natural_language_processing", ["natural language", "nlp", "language model", "text generation", "machine translation", "sentiment analysis", "named entity", "question answering", "bert", "gpt"]),
    TagRule("speech_processing", ["speech recognition", "text-to-speech", "speaker recognition", "audio ", "wav2vec", "asr"]),
    TagRule("robotics", ["robotics", "robot ", "manipulation", "navigation", "slam", "autonomous"]),
    TagRule("reinforcement_learning", ["reinforcement learning", "rl ", "q-learning", "policy gradient", "actor-critic", "multi-agent", "markov decision"]),

    # Level 2: Method paradigms
    TagRule("deep_learning", ["deep learning", "neural network", "deep neural", "neural architecture"]),
    TagRule("classical_ml", ["support vector machine", "random forest", "gradient boosting", "decision tree", "logistic regression", "naive bayes", "k-means", "pca ", "svd ", "kernel method"]),
    TagRule("graph_learning", ["graph neural", "gnn", "graph convolution", "graph attention", "network embedding", "knowledge graph"]),
    TagRule("generative_models", ["generative adversarial", "gan", "variational autoencoder", "vae", "diffusion model", "flow-based", "normalizing flow", "energy-based model", "generative model"]),
    TagRule("self_supervised_learning", ["self-supervised", "contrastive learning", "masked autoencoder", "pretext task", "representation learning"]),
    TagRule("federated_learning", ["federated learning", "federated ", "decentralized learning"]),

    # Level 3: Architectures / Tasks
    TagRule("transformer", ["transformer", "attention mechanism", "self-attention", "multi-head attention", "attention is all you need"]),
    TagRule("cnn", ["convolutional neural network", "cnn", "resnet", "vgg", "inception", "densenet", "efficientnet"]),
    TagRule("rnn", ["recurrent neural", "rnn", "lstm", "gru", "seq2seq", "sequence-to-sequence"]),
    TagRule("mlp", ["multilayer perceptron", "mlp", "fully connected", "feed-forward network"]),
    TagRule("time_series_forecasting", ["time series", "time-series", "temporal forecasting", "forecasting", "predictive modeling temporal", "arima", "prophet", "informer", "autoformer"]),
    TagRule("object_detection", ["object detection", "yolo", "rcnn", "faster rcnn", "mask rcnn", "ssd ", "detr", "anchor-free"]),
    TagRule("semantic_segmentation", ["semantic segmentation", "instance segmentation", "panoptic segmentation", "u-net", "unet", "deeplab", "fcn ", "mask2former"]),
    TagRule("machine_translation", ["machine translation", "neural machine translation", "nmt", "translation model", "bilingual"]),
    TagRule("summarization", ["summarization", "text summarization", "abstractive summarization", "extractive summarization"]),
    TagRule("question_answering", ["question answering", "reading comprehension", "squad", "open-domain qa", "multi-hop qa"]),
    TagRule("recommendation", ["recommendation system", "recommender", "collaborative filtering", "matrix factorization", "session-based recommendation"]),

    # Level 3+: Specific techniques
    TagRule("efficient_attention", ["efficient attention", "linear attention", "performer", "flash attention", "sparse attention", "local attention", "sliding window attention", "longformer", "bigbird", "reformer", "linformer"]),
    TagRule("vision_transformer", ["vision transformer", "vit ", "swin transformer", "deit", "cvt ", "pvt ", "image transformer"]),
    TagRule("large_language_model", ["large language model", "llm", "foundation model", "chatgpt", "claude", "llama", "gpt-4", "gpt-3", "instruction tuning", "rlhf", "alignment"]),
    TagRule("prompt_engineering", ["prompt engineering", "prompt tuning", "prefix tuning", "p-tuning", "soft prompt", "in-context learning", "chain-of-thought", "few-shot"]),
    TagRule("quantization", ["quantization", "int8", "int4", "binary neural", "model compression", "knowledge distillation", "pruning", "low-rank"]),
    TagRule("interpretability", ["interpretability", "explainability", "explainable ai", "xai", "attention visualization", "saliency map", "feature attribution", "concept-based"]),
    TagRule("adversarial", ["adversarial", "adversarial attack", "adversarial training", "robustness", "certified robust", "pgd attack", "fgsm"]),
    TagRule("multi_modal", ["multi-modal", "multimodal", "vision-language", "cross-modal", "clip", "align", "blip", "flamingo", "image-text"]),
    TagRule("anomaly_detection", ["anomaly detection", "outlier detection", "novelty detection", "fraud detection"]),
    TagRule("meta_learning", ["meta learning", "few-shot learning", "zero-shot learning", "meta-", "maml", "prototypical network"]),
    TagRule("continual_learning", ["continual learning", "lifelong learning", "catastrophic forgetting", "incremental learning"]),
    TagRule("bayesian_methods", ["bayesian", "variational inference", "mcmc", "gaussian process", "bayesian neural", "uncertainty quantification", "mc dropout"]),
    TagRule("optimization", ["optimization", "sgd", "adam", "adamw", "learning rate", "second-order", "hessian", "convex optimization"]),
    TagRule("distributed_training", ["distributed training", "data parallel", "model parallel", "pipeline parallel", "zero redundancy", "horovod", "deepspeed"]),
    TagRule("neural_architecture_search", ["neural architecture search", "nas", "auto-ml", "automated machine learning", "hyperparameter optimization"]),
]


class TagEngine:
    """Engine for deriving domain tags from paper metadata."""

    def __init__(self, rules: list[TagRule] | None = None):
        self.rules = rules or list(DEFAULT_TAG_RULES)
        self._rules_by_tag = {r.tag_id: r for r in self.rules}

    def tag_paper(
        self,
        paper: Paper,
        source_project: str = "",
        auto_only: bool = False,
    ) -> list[PaperTag]:
        """Derive tags for a paper based on title and abstract.

        Returns a list of ``PaperTag`` associations.  If ``auto_only`` is True,
        only automatically-derived tags are returned (no manual ones).
        """
        text = f"{paper.title} {paper.abstract}"
        tags: list[PaperTag] = []
        matched_tags: set[str] = set()

        for rule in self.rules:
            if rule.tag_id in matched_tags:
                continue
            if rule.matches(text):
                confidence = ConfidenceLevel.HIGH if rule.weight >= 1.0 else ConfidenceLevel.MEDIUM
                tags.append(
                    PaperTag(
                        paper_id=paper.paper_id,
                        tag_id=rule.tag_id,
                        confidence=confidence,
                        source="auto_keyword",
                        added_by_project=source_project,
                    )
                )
                matched_tags.add(rule.tag_id)

        logger.debug(
            "Auto-tagged paper %s with %d tags", paper.paper_id, len(tags)
        )
        return tags

    def get_rule(self, tag_id: str) -> TagRule | None:
        """Return the rule for a given tag_id."""
        return self._rules_by_tag.get(tag_id)

    def add_rule(self, rule: TagRule) -> None:
        """Add a custom rule at runtime."""
        self.rules.append(rule)
        self._rules_by_tag[rule.tag_id] = rule

    def suggest_tags_for_query(self, query: str) -> list[str]:
        """Given a search query, suggest relevant tag_ids."""
        text = query.lower()
        suggestions: list[str] = []
        for rule in self.rules:
            if rule.matches(text):
                suggestions.append(rule.tag_id)
        return suggestions
