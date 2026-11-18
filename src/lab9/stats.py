"""Statistics for judge calibration, paired comparisons and seed reliability."""

from __future__ import annotations

from collections.abc import Sequence
from math import comb, isclose
from numbers import Integral

POS = "FAIL"


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """Use FAIL as the positive class."""
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    cells = {(POS, POS): "tp", ("PASS", POS): "fp", (POS, "PASS"): "fn", ("PASS", "PASS"): "tn"}
    for pair in zip(human, judge, strict=True):
        if pair not in cells:
            raise ValueError(f"expected PASS or FAIL labels, got {pair!r}")
        counts[cells[pair]] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    tp = cm["tp"]
    predicted, actual = tp + cm["fp"], tp + cm["fn"]
    return (tp / predicted if predicted else 0.0, tp / actual if actual else 0.0)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    cm = confusion(human, judge)
    n = sum(cm.values())
    agreements = cm["tp"] + cm["tn"]
    human_fails = cm["tp"] + cm["fn"]
    judge_fails = cm["tp"] + cm["fp"]
    chance = human_fails * judge_fails + (n - human_fails) * (n - judge_fails)
    if chance == n * n:
        raise ValueError("Cohen's kappa is undefined when agreement by chance is 1 or there are no labels")
    return (agreements * n - chance) / (n * n - chance)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct the observed failure rate for judge error."""
    if any(not 0 <= p <= 1 for p in (observed_rate, sensitivity, specificity)):
        raise ValueError("rates must be in [0, 1]")
    denominator = sensitivity + specificity - 1
    if isclose(denominator, 0.0, abs_tol=1e-12):
        raise ValueError("Rogan–Gladen is undefined when sensitivity plus specificity is 1")
    return max(0.0, min(1.0, (observed_rate + specificity - 1) / denominator))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """Return mean(PR - baseline) and the percentile CI for paired item means."""
    import numpy as np
    from scipy.stats import bootstrap

    pr, base = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if pr.ndim != 1 or base.shape != pr.shape or not pr.size:
        raise ValueError("paired samples must be nonempty vectors of the same length")
    if not np.isfinite(pr).all() or not np.isfinite(base).all():
        raise ValueError("paired samples must contain only finite values")
    if n_resamples < 1 or not 0 < confidence < 1:
        raise ValueError("expected positive n_resamples and confidence in (0, 1)")

    delta = float(np.mean(pr - base))
    if np.array_equal(pr, base) or len(pr) == 1:
        return delta, delta, delta

    def mean_difference(x, y, axis):
        return np.mean(x - y, axis=axis)

    ci = bootstrap((pr, base), mean_difference, paired=True, method="percentile",
                   n_resamples=n_resamples, rng=np.random.default_rng(rng),
                   confidence_level=confidence).confidence_interval
    return delta, float(ci.low), float(ci.high)


def _check_pass_counts(n: int, c: int, k: int) -> None:
    if any(isinstance(x, bool) or not isinstance(x, Integral) for x in (n, c, k)):
        raise ValueError("n, c and k must be integers")
    if not (1 <= k <= n and 0 <= c <= n):
        raise ValueError("expected 1 <= k <= n and 0 <= c <= n")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability of at least one pass in k trials drawn without replacement."""
    _check_pass_counts(n, c, k)
    total = comb(n, k)
    return (total - comb(n - c, k)) / total


def pass_hat_k(n: int, c: int, k: int) -> float:
    """Probability that all k trials drawn without replacement pass."""
    _check_pass_counts(n, c, k)
    return comb(c, k) / comb(n, k)
