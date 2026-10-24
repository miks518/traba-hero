"""The verification status vocabulary is the four establishment states.

The old green/yellow/red vocabulary is retired. The new vocabulary is:
- confirmed: the employer's own channel matches the posting's
- supported: an independent record names the employer, but the channel wasn't compared
- unknown: the lookup found nothing, or nothing that bears on identity
- contradicted: a retrieved source shows the posting's channel is not the entity's

Plus the retired-by-the-record state: stale.

This test asserts the new vocabulary is what reaches the wire.
"""

import pytest
from app.models.schemas import VerificationItem


def test_verification_item_status_is_an_establishment_state():
    """The `status` field on VerificationItem now carries the establishment state,
    not the old green/yellow/red."""
    # The type should only accept the new vocabulary
    item = VerificationItem(
        label="Test",
        status="confirmed",
        explanation="test",
    )
    assert item.status == "confirmed"

    item = VerificationItem(
        label="Test",
        status="supported",
        explanation="test",
    )
    assert item.status == "supported"

    item = VerificationItem(
        label="Test",
        status="unknown",
        explanation="test",
    )
    assert item.status == "unknown"

    item = VerificationItem(
        label="Test",
        status="contradicted",
        explanation="test",
    )
    assert item.status == "contradicted"

    item = VerificationItem(
        label="Test",
        status="stale",
        explanation="test",
    )
    assert item.status == "stale"


def test_the_old_green_yellow_red_are_not_valid_statuses():
    """The old green/yellow/red should not be valid statuses on VerificationItem."""
    with pytest.raises(ValueError):
        VerificationItem(
            label="Test",
            status="green",  # old vocabulary
            explanation="test",
        )

    with pytest.raises(ValueError):
        VerificationItem(
            label="Test",
            status="yellow",
            explanation="test",
        )

    with pytest.raises(ValueError):
        VerificationItem(
            label="Test",
            status="red",
            explanation="test",
        )