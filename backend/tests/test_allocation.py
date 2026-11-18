import pytest

from app.domain.allocation import AllocationError, OfferSlot, dedupe_offer_ids, recalculate_shares, split_even_last_gets_remainder


def test_dedupe_offer_ids():
    assert dedupe_offer_ids([1, 2, 2, 3]) == [1, 2, 3]


def test_four_equal_split_video_add():
    slots = [OfferSlot(offer_id=1), OfferSlot(offer_id=2), OfferSlot(offer_id=3), OfferSlot(offer_id=4)]
    shares = recalculate_shares(slots)
    assert list(shares.values()) == [25, 25, 25, 25]


def test_three_equal_split_video_fetch_order():
    """Video 0:38 — 33, 33, 34 with remainder on the last row in order."""
    slots = [OfferSlot(offer_id=101), OfferSlot(offer_id=102), OfferSlot(offer_id=103)]
    shares = recalculate_shares(slots)
    assert [shares[101], shares[102], shares[103]] == [33, 33, 34]


def test_split_even_helper():
    assert split_even_last_gets_remainder(75, [10, 20]) == {10: 37, 20: 38}


def test_removed_get_zero_and_recalc_rest():
    slots = [
        OfferSlot(offer_id=1),
        OfferSlot(offer_id=2),
        OfferSlot(offer_id=3, removed=True),
    ]
    shares = recalculate_shares(slots)
    assert shares[3] == 0
    assert [shares[1], shares[2]] == [50, 50]


def test_pin_25_video_push():
    slots = [
        OfferSlot(offer_id=1, pinned=True, pinned_share=25),
        OfferSlot(offer_id=2),
        OfferSlot(offer_id=3),
    ]
    shares = recalculate_shares(slots)
    assert shares[1] == 25
    assert [shares[2], shares[3]] == [37, 38]


def test_pins_sum_over_100():
    slots = [
        OfferSlot(offer_id=1, pinned=True, pinned_share=60),
        OfferSlot(offer_id=2, pinned=True, pinned_share=50),
    ]
    with pytest.raises(AllocationError):
        recalculate_shares(slots)


def test_all_pinned_must_sum_100():
    slots = [
        OfferSlot(offer_id=1, pinned=True, pinned_share=25),
        OfferSlot(offer_id=2, pinned=True, pinned_share=25),
    ]
    with pytest.raises(AllocationError):
        recalculate_shares(slots)