"""
Offer share allocation for stream rotation (wrapper-local pins).

Visual reference: https://youtu.be/jNloscEWCjA (reviewed 2026-11-18, separate from pytest).
Integer shares sum to 100 (Keitaro OfferStreamRequest.share).

Rules:
- Only active (non-removed) offers participate in the 100% split.
- Pinned offers keep pinned_share fixed.
- Unpinned remainder is split evenly in **existing row order**; any indivisible
  percentage points go to the **last** unpinned row(s) (e.g. 3→33,33,34; 75/2→37,38).
"""

from __future__ import annotations

from dataclasses import dataclass


class AllocationError(ValueError):
    pass


@dataclass(frozen=True)
class OfferSlot:
    offer_id: int
    removed: bool = False
    pinned: bool = False
    pinned_share: int | None = None


def dedupe_offer_ids(offer_ids: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for oid in offer_ids:
        if oid in seen:
            continue
        seen.add(oid)
        out.append(oid)
    return out


def split_even_last_gets_remainder(total: int, ordered_offer_ids: list[int]) -> dict[int, int]:
    """Split `total` across IDs preserving order; +1 pts assigned from the end."""
    n = len(ordered_offer_ids)
    if n <= 0:
        raise AllocationError("No offers to assign remainder")
    if total < 0:
        raise AllocationError("Remainder is negative")
    if total == 0:
        return {oid: 0 for oid in ordered_offer_ids}
    base = total // n
    rem = total - base * n
    out: dict[int, int] = {}
    for i, oid in enumerate(ordered_offer_ids):
        extra = 1 if i >= n - rem else 0
        out[oid] = base + extra
    return out


def recalculate_shares(slots: list[OfferSlot]) -> dict[int, int]:
    """Return offer_id -> share for all slots (removed get 0). Order of `slots` is preserved."""
    if not slots:
        raise AllocationError("At least one offer row is required")

    ids = [s.offer_id for s in slots]
    if len(dedupe_offer_ids(ids)) != len(ids):
        raise AllocationError("Duplicate offer IDs are not allowed")

    active = [s for s in slots if not s.removed]
    if not active:
        return {s.offer_id: 0 for s in slots}

    pinned_sum = 0
    for s in active:
        if s.pinned:
            if s.pinned_share is None or s.pinned_share < 0:
                raise AllocationError(f"Offer {s.offer_id} is pinned without a valid share")
            pinned_sum += s.pinned_share

    if pinned_sum > 100:
        raise AllocationError(f"Pinned shares sum to {pinned_sum}% (max 100)")

    unpinned = [s for s in active if not s.pinned]
    remainder = 100 - pinned_sum

    if unpinned and remainder < 0:
        raise AllocationError("Pinned shares exceed 100%")

    if not unpinned:
        if pinned_sum != 100:
            raise AllocationError(
                f"All active offers are pinned but shares sum to {pinned_sum}%, not 100%"
            )
        result = {s.offer_id: int(s.pinned_share or 0) for s in active}
        for s in slots:
            if s.removed:
                result[s.offer_id] = 0
        return result

    if remainder == 0 and unpinned:
        raise AllocationError("No percentage left for unpinned offers")

    unpinned_ids = [s.offer_id for s in unpinned]
    even = split_even_last_gets_remainder(remainder, unpinned_ids)

    result: dict[int, int] = {}
    for s in slots:
        if s.removed:
            result[s.offer_id] = 0
        elif s.pinned:
            result[s.offer_id] = int(s.pinned_share or 0)
        else:
            result[s.offer_id] = even[s.offer_id]

    if sum(result[s.offer_id] for s in active) != 100:
        raise AllocationError("Internal error: active shares do not sum to 100")
    return result


def normalize_shares(
    items: list[tuple[int, int | float | None]],
    *,
    preserve_if_sum_100: bool = True,
) -> list[tuple[int, int]]:
    """Backward-compatible helper (no pins)."""
    slots = [OfferSlot(offer_id=oid, removed=False) for oid, _ in items]
    if preserve_if_sum_100:
        raw = [w for _, w in items]
        if all(w is not None and float(w).is_integer() for w in raw) and sum(int(w) for w in raw) == 100:
            return [(oid, int(w)) for (oid, w), _ in zip(items, raw, strict=True)]
    shares = recalculate_shares(slots)
    return [(oid, shares[oid]) for oid, _ in items]