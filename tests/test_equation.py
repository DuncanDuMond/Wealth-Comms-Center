import pytest
from pydantic import ValidationError
from wealth_command_center.equation import PersonalEquation, evaluate


def test_equation_traceable_and_separate():
    inputs = PersonalEquation(profile_id="p", capital=50, human=50, intellectual=50, social=50,
        execution=50, timing=1.1, location=1.2, allocation=10, feedback=-5, risk=20)
    result = evaluate(inputs, baseline=60)
    assert result["terms"]["R"] == 50
    assert result["raw"] == pytest.approx(114.2)
    assert result["normalized"] == pytest.approx(38.06666666667)
    assert result["kind"] == "experimental"
    assert inputs.capital == 50


@pytest.mark.parametrize("changes", [{"timing": -1}, {"risk": 101}, {"capital": float("nan")},
    {"weights": {"capital": 1}}, {"normalize_low": 500}, {"normalize_high": float("inf")},
    {"normalize_low": -1e308, "normalize_high": 1e308}])
def test_invalid_hypotheses_rejected(changes):
    with pytest.raises(ValidationError):
        PersonalEquation(profile_id="p", **changes)


def test_clamping_is_explicit():
    assert evaluate(PersonalEquation(profile_id="p", risk=100), 0)["normalized"] == 0
    assert evaluate(PersonalEquation(profile_id="p", timing=2, location=2), 100)["normalized"] == 100
