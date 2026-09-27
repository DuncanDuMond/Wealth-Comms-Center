#!/usr/bin/env python3
"""
tarot.py
════════════════════════════════════════════════════════════════════════════
INTEGRATION NOTE (wealth_agent): copied into tools/ with one change --
`import cardology` became `from . import cardology` for the package
structure here. Independently verified before wiring in, beyond the
module's own _run_self_test(): swept all 52 real playing cards through
tarot_equivalent()/cosmic_card_number() and confirmed cosmic numbers 1-52
are each produced exactly once (a clean bijection, with 0 and 53 correctly
left unused by any real card, reserved for the two Jokers).
════════════════════════════════════════════════════════════════════════════
Maps the standard playing cards used by cardology.py to their Tarot
equivalents, per the correspondence table supplied with this module:

    Hearts -> Cups   Clubs -> Wands   Diamonds -> Pentacles   Spades -> Swords
    Jack -> Knight (there is no playing-card equivalent of the tarot Page --
    it's simply unreachable through this mapping)   Joker -> The Fool

Also carries the two numbered reference indices supplied alongside the
mapping, so a Cosmic Card or its Tarot equivalent can be looked up by
number against their sources:

    CARDS-OF-ILLUMINATION-FULL.jpg  -> 0-53, the 52-card deck + 2 Jokers,
                                        per itsallinthecards.com
    FOOL-78-SPREAD.jpg              -> 0-78, the full 78-card tarot deck
                                        (Fool appears at both 0 and 22),
                                        per teachmetarot.com

Both charts turned out to be regular, evenly-spaced blocks (13 ranks x 4
suits, and 14 ranks x 4 suits + 22 Major Arcana), so the numbers below are
computed from the block layout rather than hand-transcribed card by card
-- spot-checked against several cells in each image (see _run_self_test).

Nothing here fetches interpretation text from itsallinthecards.com or
teachmetarot.com -- it only carries the numbering those sites use, as
supplied. Hook up actual interpretation lookups later if wanted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Union

from . import cardology

# ══════════════════════════════════════════════════════════════════════════
#  PLAYING CARD <-> TAROT RANK/SUIT MAPPING
# ══════════════════════════════════════════════════════════════════════════
RANK_TO_TAROT_RANK: Dict[str, str] = {
    'A': 'Ace', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7',
    '8': '8', '9': '9', '10': '10', 'J': 'Knight', 'Q': 'Queen', 'K': 'King',
}
SUIT_TO_TAROT_SUIT: Dict[str, str] = {
    'H': 'Cups', 'C': 'Wands', 'D': 'Pentacles', 'S': 'Swords',
}

# ══════════════════════════════════════════════════════════════════════════
#  NUMBERING -- CARDS OF ILLUMINATION (0-53)
#  Regular block layout: Hearts 1-13, Clubs 14-26, Diamonds 27-39,
#  Spades 40-52, each block ordered Ace,2..10,J,Q,K (matches
#  cardology.RANKS exactly); Jokers sit at 0 and 53.
# ══════════════════════════════════════════════════════════════════════════
_DECK_SUIT_BLOCK_START: Dict[str, int] = {'H': 1, 'C': 14, 'D': 27, 'S': 40}


def cosmic_card_number(card: Union["cardology.Card", str]) -> int:
    """0-53 index for a standard playing card, per CARDS-OF-ILLUMINATION."""
    card = cardology.Card.parse(card)
    return _DECK_SUIT_BLOCK_START[card.suit] + cardology.RANKS.index(card.rank)


# ══════════════════════════════════════════════════════════════════════════
#  NUMBERING -- FOOL 78-CARD SPREAD (0-78)
#  Major Arcana 0-21 in standard order; Minor Arcana blocks of 14
#  (Ace,2..10,Page,Knight,Queen,King) starting at Wands=23, Cups=37,
#  Swords=51, Pentacles=65. Position 22 (Fool again) is not modeled
#  separately -- 0 is used as the Fool's canonical number throughout.
# ══════════════════════════════════════════════════════════════════════════
MAJOR_ARCANA: Dict[str, int] = {
    "The Fool": 0, "The Magician": 1, "The High Priestess": 2, "The Empress": 3,
    "The Emperor": 4, "The Hierophant": 5, "The Lovers": 6, "The Chariot": 7,
    "Strength": 8, "The Hermit": 9, "Wheel of Fortune": 10, "Justice": 11,
    "The Hanged Man": 12, "Death": 13, "Temperance": 14, "The Devil": 15,
    "The Tower": 16, "The Star": 17, "The Moon": 18, "The Sun": 19,
    "Judgement": 20, "The World": 21,
}
_MINOR_RANK_ORDER = ['Ace', '2', '3', '4', '5', '6', '7', '8', '9', '10',
                     'Page', 'Knight', 'Queen', 'King']
_TAROT_SUIT_BLOCK_START: Dict[str, int] = {
    'Wands': 23, 'Cups': 37, 'Swords': 51, 'Pentacles': 65,
}


def tarot_number(tarot_name: str) -> Optional[int]:
    """0-78 index for a Tarot card name, per FOOL-78-SPREAD."""
    if tarot_name in MAJOR_ARCANA:
        return MAJOR_ARCANA[tarot_name]
    rank_part, sep, suit_part = tarot_name.partition(" of ")
    if sep and suit_part in _TAROT_SUIT_BLOCK_START and rank_part in _MINOR_RANK_ORDER:
        return _TAROT_SUIT_BLOCK_START[suit_part] + _MINOR_RANK_ORDER.index(rank_part)
    return None


# ══════════════════════════════════════════════════════════════════════════
#  TAROT CARD + CONVERSION
# ══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class TarotCard:
    name:     str             # e.g. "Queen of Cups", "The Fool"
    number:   Optional[int]   # 0-78, per FOOL-78-SPREAD.jpg
    is_major: bool = False

    def __str__(self) -> str:
        return self.name


FOOL = TarotCard(name="The Fool", number=0, is_major=True)


def tarot_equivalent(card: Union["cardology.Card", str]) -> TarotCard:
    """Standard playing card (or 'Joker') -> its Tarot equivalent."""
    if isinstance(card, str) and card.strip().upper() in ("JOKER", "★"):
        return FOOL
    card = cardology.Card.parse(card)
    name = f"{RANK_TO_TAROT_RANK[card.rank]} of {SUIT_TO_TAROT_SUIT[card.suit]}"
    return TarotCard(name=name, number=tarot_number(name), is_major=False)


# ══════════════════════════════════════════════════════════════════════════
#  FULL COSMIC-CARD-PROFILE -> TAROT-PROFILE
# ══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class TarotCardProfile:
    earth:     TarotCard
    sun:       TarotCard
    karma:     TarotCard
    moon:      TarotCard
    mercury:   TarotCard
    venus:     TarotCard
    mars:      TarotCard
    jupiter:   TarotCard
    saturn:    TarotCard
    uranus:    TarotCard
    neptune:   TarotCard
    pluto:     TarotCard
    chiron:    TarotCard
    rahu:      TarotCard
    midheaven: TarotCard
    phoenix:   TarotCard

    def as_dict(self) -> Dict[str, dict]:
        return {
            name: {"name": getattr(self, name).name, "number": getattr(self, name).number}
            for name in self.__dataclass_fields__
        }


def derive_tarot_profile(cosmic_profile: "cardology.CosmicCardProfile") -> TarotCardProfile:
    """Cosmic Card profile (15 playing cards) -> matching Tarot profile."""
    values = {
        field: tarot_equivalent(getattr(cosmic_profile, field))
        for field in cosmic_profile.__dataclass_fields__
    }
    return TarotCardProfile(**values)


# ══════════════════════════════════════════════════════════════════════════
#  SELF-TEST
# ══════════════════════════════════════════════════════════════════════════
def _run_self_test() -> None:
    # Spot-checks against CARDS-OF-ILLUMINATION-FULL.jpg
    assert cosmic_card_number('AS') == 40   # column 4, row 1
    assert cosmic_card_number('KH') == 13   # column 1, row 13
    assert cosmic_card_number('AC') == 14   # column 2, row 1
    assert cosmic_card_number('KD') == 39   # column 3, row 13
    assert cosmic_card_number('KS') == 52   # column 4, row 13 (Joker sits at 53)

    # Spot-checks against FOOL-78-SPREAD.jpg
    assert tarot_number("The Fool") == 0
    assert tarot_number("The World") == 21
    assert tarot_number("Ace of Wands") == 23
    assert tarot_number("King of Wands") == 36
    assert tarot_number("Ace of Cups") == 37
    assert tarot_number("Knight of Swords") == 62
    assert tarot_number("10 of Pentacles") == 74
    assert tarot_number("King of Pentacles") == 78

    # The correspondence table itself
    assert tarot_equivalent('QH') == TarotCard("Queen of Cups", 49)
    assert tarot_equivalent('JS') == TarotCard("Knight of Swords", 62)
    assert tarot_equivalent('10D') == TarotCard("10 of Pentacles", 74)
    assert tarot_equivalent('AC') == TarotCard("Ace of Wands", 23)
    assert tarot_equivalent('Joker') == FOOL

    # Every reachable mapping resolves to a real position in the 78-spread
    # (Page of X is expected to never come up -- Jack only maps to Knight)
    for suit in cardology.SUITS:
        for rank in cardology.RANKS:
            t = tarot_equivalent(cardology.Card(rank, suit))
            assert t.number is not None, f"{rank}{suit} -> {t.name} has no tarot number"
            assert "Page" not in t.name

    print("All tarot self-tests passed.")


if __name__ == "__main__":
    _run_self_test()
    print()
    demo_earth = 'QH'
    cosmic = cardology.derive_cosmic_cards(demo_earth)
    tarot_profile = derive_tarot_profile(cosmic)
    print(f"Sample profile for Earth = {cosmic.earth.symbol}:")
    for field in cosmic.__dataclass_fields__:
        pc = getattr(cosmic, field)
        tc = getattr(tarot_profile, field)
        print(f"  {field.capitalize():<10} {pc.symbol:<5} -> {tc.name:<20} "
              f"(cosmic #{cosmic_card_number(pc)}, tarot #{tc.number})")
