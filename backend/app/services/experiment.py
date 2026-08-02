"""A/B experiment aggregation, statistical testing, and decision rules."""

from decimal import Decimal
from math import sqrt
from typing import NamedTuple

from scipy.stats import norm

from backend.app.schemas.analytics import ExperimentDecision

ALPHA = Decimal("0.05")


class ExperimentTestResult(NamedTuple):
    """Stable decimal result from a two-sided two-proportion z-test."""

    uplift: Decimal | None
    p_value: Decimal | None


def evaluate_proportions(
    clicks_a: int,
    purchases_a: int,
    clicks_b: int,
    purchases_b: int,
) -> ExperimentTestResult:
    """Calculate relative uplift and a two-sided z-test when denominators are valid."""
    if clicks_a <= 0 or clicks_b <= 0:
        return ExperimentTestResult(None, None)

    rate_a = Decimal(purchases_a) / Decimal(clicks_a)
    rate_b = Decimal(purchases_b) / Decimal(clicks_b)
    uplift = None if rate_a == 0 else (rate_b - rate_a) / rate_a
    pooled_rate = (purchases_a + purchases_b) / (clicks_a + clicks_b)
    standard_error = sqrt(pooled_rate * (1 - pooled_rate) * (1 / clicks_a + 1 / clicks_b))
    if standard_error == 0:
        return ExperimentTestResult(uplift, Decimal("1"))
    z_score = (float(rate_b) - float(rate_a)) / standard_error
    return ExperimentTestResult(uplift, Decimal(str(2 * norm.sf(abs(z_score)))))


def decision_for(
    *, clicks_a: int, clicks_b: int, minimum_sample_size: int,
    rate_a: Decimal | None, rate_b: Decimal | None, p_value: Decimal | None,
) -> ExperimentDecision:
    """Map statistical output to the fixed business decision vocabulary."""
    if clicks_a < minimum_sample_size or clicks_b < minimum_sample_size:
        return ExperimentDecision(
            code="insufficient_sample",
            message="样本量不足，建议继续观察。",
            level="info",
        )
    if p_value is not None and rate_a is not None and rate_b is not None:
        if p_value < ALPHA and rate_b > rate_a:
            return ExperimentDecision(
                code="significantly_better",
                message="实验组显著优于对照组，可考虑扩大流量或全量上线。",
                level="success",
            )
        if p_value < ALPHA and rate_b < rate_a:
            return ExperimentDecision(
                code="significantly_worse",
                message="实验组存在负向影响，应暂停实验并排查原因。",
                level="error",
            )
    return ExperimentDecision(
        code="no_significant_difference",
        message="当前数据不足以证明实验组优于对照组，建议继续观察或复盘策略。",
        level="warning",
    )
