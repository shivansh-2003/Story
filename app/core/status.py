from enum import Enum

from fastapi import HTTPException, status

from app.core.logging_utils import log_execution


@log_execution
def assert_transition(current: Enum, new: Enum, allowed: dict) -> None:
    """Shared status-transition guard for both stories and chapters. `allowed`
    is a `{current_status: {reachable_statuses}}` map defined next to each
    domain's enum. Same-status is always a no-op (PATCHing other fields
    alongside an unchanged status shouldn't 409)."""
    if current == new:
        return
    if new not in allowed.get(current, set()):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot transition from {current.value} to {new.value}")


def _demo() -> None:
    class Color(str, Enum):
        red = "red"
        green = "green"
        blue = "blue"

    rules: dict[Color, set[Color]] = {Color.red: {Color.green}, Color.green: {Color.blue}, Color.blue: set()}

    assert_transition(Color.red, Color.red, rules)  # same status always allowed, no-op
    assert_transition(Color.red, Color.green, rules)  # allowed transition, no raise

    raised = False
    try:
        assert_transition(Color.red, Color.blue, rules)
    except HTTPException as e:
        raised = True
        assert e.status_code == 409
    assert raised, "disallowed transition should have raised 409"

    print("status self-check passed")


if __name__ == "__main__":
    _demo()
