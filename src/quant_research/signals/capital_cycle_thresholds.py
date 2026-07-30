from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CapitalCycleThresholds:
    """Threshold profile for capital-cycle classification."""

    name: str

    growth_gap_level: Decimal
    capex_intensity_yoy_level: Decimal
    fcf_margin_yoy_level: Decimal

    growth_gap_momentum: Decimal
    capex_intensity_momentum: Decimal
    fcf_margin_momentum: Decimal

    def __post_init__(self) -> None:
        """Ensure every deadband is non-negative."""

        threshold_values = (
            self.growth_gap_level,
            self.capex_intensity_yoy_level,
            self.fcf_margin_yoy_level,
            self.growth_gap_momentum,
            self.capex_intensity_momentum,
            self.fcf_margin_momentum,
        )

        if any(
            value < Decimal(0)
            for value in threshold_values
        ):
            raise ValueError(
                "Capital-cycle thresholds cannot be negative."
            )

    def to_payload(self) -> dict[str, object]:
        """Return a dashboard-friendly representation."""

        return {
            "name": self.name,
            "levels": {
                "growth_gap": float(
                    self.growth_gap_level
                ),
                "capex_intensity_yoy": float(
                    self.capex_intensity_yoy_level
                ),
                "fcf_margin_yoy": float(
                    self.fcf_margin_yoy_level
                ),
            },
            "momentum": {
                "growth_gap": float(
                    self.growth_gap_momentum
                ),
                "capex_intensity": float(
                    self.capex_intensity_momentum
                ),
                "fcf_margin": float(
                    self.fcf_margin_momentum
                ),
            },
        }


BASELINE_THRESHOLDS = CapitalCycleThresholds(
    name="baseline",
    growth_gap_level=Decimal(0),
    capex_intensity_yoy_level=Decimal(0),
    fcf_margin_yoy_level=Decimal(0),
    growth_gap_momentum=Decimal(0),
    capex_intensity_momentum=Decimal(0),
    fcf_margin_momentum=Decimal(0),
)


CALIBRATED_THRESHOLDS = CapitalCycleThresholds(
    name="calibrated",
    # Ratio values are stored as decimals:
    # 0.05 = 5 percentage points.
    growth_gap_level=Decimal("0.05"),
    capex_intensity_yoy_level=Decimal("0.01"),
    fcf_margin_yoy_level=Decimal("0.02"),
    growth_gap_momentum=Decimal("0.05"),
    capex_intensity_momentum=Decimal("0.01"),
    fcf_margin_momentum=Decimal("0.02"),
)


THRESHOLD_PROFILES: dict[
    str,
    CapitalCycleThresholds,
] = {
    BASELINE_THRESHOLDS.name: BASELINE_THRESHOLDS,
    CALIBRATED_THRESHOLDS.name: CALIBRATED_THRESHOLDS,
}
