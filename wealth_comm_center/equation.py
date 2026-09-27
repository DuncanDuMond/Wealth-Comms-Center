"""An explicitly user-defined experiment, separate from the canonical score."""
from __future__ import annotations

import math
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PersonalEquation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    profile_id: str
    timing: float = Field(default=1, ge=0, le=2)
    location: float = Field(default=1, ge=0, le=2)
    capital: float = Field(default=0, ge=0, le=100)
    human: float = Field(default=0, ge=0, le=100)
    intellectual: float = Field(default=0, ge=0, le=100)
    social: float = Field(default=0, ge=0, le=100)
    execution: float = Field(default=0, ge=0, le=100)
    weights: dict[str, float] = Field(default_factory=lambda: {
        "capital": .2, "human": .2, "intellectual": .2, "social": .2, "execution": .2})
    allocation: float = Field(default=0, ge=0, le=100)
    feedback: float = Field(default=0, ge=-100, le=100)
    risk: float = Field(default=0, ge=0, le=100)
    normalize_low: float = Field(default=0, ge=-10000, le=10000)
    normalize_high: float = Field(default=300, ge=-10000, le=10000)
    save: bool = False

    @model_validator(mode="after")
    def valid_weights(self):
        if set(self.weights) != {"capital", "human", "intellectual", "social", "execution"}:
            raise ValueError("Weights must specify the five real-world dimensions")
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in self.weights.values()):
            raise ValueError("Weights must be between zero and one")
        if abs(sum(self.weights.values())-1) > 1e-8:
            raise ValueError("Weights must sum to one")
        if self.normalize_high - self.normalize_low < 0.000001:
            raise ValueError("The normalization upper bound must exceed its lower bound")
        return self


def evaluate(inputs: PersonalEquation, baseline: float) -> dict:
    if not math.isfinite(baseline) or not 0 <= baseline <= 100:
        raise ValueError("A valid canonical symbolic baseline is required")
    terms = {
        "P": baseline, "T": inputs.timing, "L": inputs.location,
        "R": sum(getattr(inputs, key)*weight for key, weight in inputs.weights.items()),
        "A": inputs.allocation, "F": inputs.feedback, "Q": inputs.risk,
    }
    raw = terms["P"]*terms["T"]*terms["L"]+terms["R"]+terms["A"]+terms["F"]-terms["Q"]
    normalized = max(0, min(100, 100*(raw-inputs.normalize_low)/(inputs.normalize_high-inputs.normalize_low)))
    return {"version": "personal-equation-experiment-0.1", "kind": "experimental",
        "formula": "N(P × T × L + R + A + F − Q)", "terms": terms, "raw": raw,
        "normalized": normalized, "normalization": {"low": inputs.normalize_low, "high": inputs.normalize_high},
        "inputs": inputs.model_dump(exclude={"save", "profile_id"}),
        "warnings": ["This is an uncalibrated, user-defined experiment, not a financial forecast or a measure of a person's worth.",
                     "T/L multipliers are your hypotheses, not inferred planetary or location effects.",
                     "Capital and other real-world dimensions are self-ratings on a 0–100 scale, not currency balances.",
                     "Initial equal weights and normalization bounds are editable placeholders, not evidence-backed recommendations.",
                     "This result never changes the canonical natal score. Record outcomes and alternative explanations before revising hypotheses."]}
