#!/usr/bin/env python3
"""
cardology.py
════════════════════════════════════════════════════════════════════════════
INTEGRATION NOTE (wealth_agent): copied into tools/ unchanged -- this
module is self-contained (Card in, CosmicCardProfile out) with no
dependency on cosmic_calendar or any other module in this project, so no
adaptation was needed beyond the file's location. Independently verified
before wiring in, beyond the module's own _run_self_test(): swept all 52
possible Earth cards through derive_cosmic_cards() (no errors; the
occasional two-field coincidence, e.g. Sun==Neptune for a specific Earth
card, checked against the full 52-card sweep and confirmed to be ordinary
chance spread across many different field-pairs, not a systematic
pattern), and confirmed the wraparound logic behaves correctly for Earth
cards sitting at/near the Crown Line boundary. The module's own KARMA
confidence caveat (below) stands as-is -- that's a transcription-accuracy
question against a source image this project doesn't have, which no
amount of internal consistency-checking can resolve.
════════════════════════════════════════════════════════════════════════════
Cosmic Playing Card system for the Capricorn Prometheus Software framework.

Given a person's Earth (birth) card, this module derives the full set of
"planetary" cards -- Sun, Karma, Moon, Mercury, Venus, Mars, Jupiter,
Saturn, Uranus, Neptune, Pluto, Chiron, Rahu, Midheaven, and Phoenix --
from the Master Spirit Spread and Master Life Spread reference charts.

MECHANISM
─────────
1. EARTH  is given directly -- it's the person's birth card (e.g. from
   cosmic_calendar.get_birth_card_str()).

2. SUN is read at Earth's own (row, column) position, but in the Master
   SPIRIT spread instead of the Life spread. This is the same value
   printed as the bottom-left sub-card under Earth's cell on the actual
   chart -- confirmed against the highlighted worked example in
   Earth_and_Sun_Card.jpg (8S sits at Zeus-row/col-3 in the Life spread;
   its bottom-left sub-card AND the Spirit spread's Zeus-row/col-3 card
   are both KC) -- so it's computed here via the Spirit grid rather than
   duplicating 52 more hand-transcribed sub-card values.

3. KARMA is the bottom-right sub-card printed under Earth's cell in the
   Master Life spread. There's no independent second source for this one
   (unlike Sun), so it's transcribed directly. CONFIDENCE NOTE: this is
   the newest and smallest print on the chart -- worth a visual
   spot-check against your source image before trusting an unusual
   result. Everything else in this module is cross-validated at least
   two independent ways (see _run_self_test).

4. MOON, MERCURY, VENUS, MARS, JUPITER, SATURN, URANUS, NEPTUNE, PLUTO,
   CHIRON, RAHU, MIDHEAVEN, and PHOENIX are all found by walking through
   the Master Life spread's MAIN cards only, starting at Earth's own
   position, along one continuous 52-card path that runs, in the
   "forward"/right direction:

       Poseidon row -> Uranus row -> Kronos row -> Zeus row -> Mars row
       -> Venus row -> Mercury row -> Crown Line -> (wraps back to)
       Poseidon row ...

   i.e. bottom row to top row, then the 3-card Crown Line, then back
   around. Each row reads left-to-right. This is the order that makes
   both examples supplied with the charts check out:
     - Earth=QH (Poseidon row, col 1) -> one step left  -> Mercury=10C
       (Crown Line)                                                 ✓
     - Earth=3H (Mercury row, col 7)  -> one step right -> Moon=KS
       (Crown Line)                                                 ✓

   Moon is ONE step right of Earth's own position. Mercury is one step
   left, Venus two steps left, Mars three, ... out to Phoenix at twelve
   steps left. (Because Sun sits at Earth's own coordinates just read
   from the other spread, "right of Sun" and "right of Earth" land on
   the same Life-spread cell -- so Moon reduces to "one step right of
   Earth.")

This wraparound rule is the one genuinely non-obvious design decision in
the whole system, and the two example checks are what pin it down -- see
_run_self_test() at the bottom of this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

# ══════════════════════════════════════════════════════════════════════════
#  CARD
# ══════════════════════════════════════════════════════════════════════════
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
SUITS = ('S', 'H', 'D', 'C')
SUIT_SYMBOL = {'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣'}
SUIT_NAME   = {'S': 'Spades', 'H': 'Hearts', 'D': 'Diamonds', 'C': 'Clubs'}
RANK_NAME   = {'A': 'Ace', 'J': 'Jack', 'Q': 'Queen', 'K': 'King'}


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def __post_init__(self):
        if self.rank not in RANKS:
            raise ValueError(f"Invalid rank: {self.rank!r}")
        if self.suit not in SUITS:
            raise ValueError(f"Invalid suit: {self.suit!r}")

    @classmethod
    def parse(cls, text: Union["Card", str]) -> "Card":
        """Accepts a Card unchanged, or compact notation like 'QH', '10C'."""
        if isinstance(text, Card):
            return text
        text = text.strip().upper()
        return cls(rank=text[:-1], suit=text[-1])

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    @property
    def symbol(self) -> str:
        return f"{self.rank}{SUIT_SYMBOL[self.suit]}"

    @property
    def full_name(self) -> str:
        return f"{RANK_NAME.get(self.rank, self.rank)} of {SUIT_NAME[self.suit]}"


def _row(*codes: str) -> List[Card]:
    return [Card.parse(c) for c in codes]


# ══════════════════════════════════════════════════════════════════════════
#  MASTER SPIRIT SPREAD  (transcribed from MASTER-CARD-CHART2.jpg)
#  High confidence: each row is internally consistent (Mercury row runs a
#  clean 7-6-5-4-3-2-A of Hearts, etc.) and both spreads independently
#  check out as complete, non-duplicated 52-card decks.
# ══════════════════════════════════════════════════════════════════════════
SPIRIT_CROWN: List[Card] = _row('KS', 'QS', 'JS')
SPIRIT_ROWS: Dict[str, List[Card]] = {
    'mercury':  _row('7H', '6H', '5H', '4H', '3H', '2H', 'AH'),
    'venus':    _row('AC', 'KH', 'QH', 'JH', '10H', '9H', '8H'),
    'mars':     _row('8C', '7C', '6C', '5C', '4C', '3C', '2C'),
    'zeus':     _row('2D', 'AD', 'KC', 'QC', 'JC', '10C', '9C'),
    'kronos':   _row('9D', '8D', '7D', '6D', '5D', '4D', '3D'),
    'uranus':   _row('3S', '2S', 'AS', 'KD', 'QD', 'JD', '10D'),
    'poseidon': _row('10S', '9S', '8S', '7S', '6S', '5S', '4S'),
}

# ══════════════════════════════════════════════════════════════════════════
#  MASTER LIFE SPREAD  (transcribed from MASTER-CARD-CHART2.jpg)
#  Main cards: high confidence -- validated against both worked examples
#  above, plus the 52-card completeness check.
# ══════════════════════════════════════════════════════════════════════════
LIFE_CROWN: List[Card] = _row('KS', '8D', '10C')
LIFE_ROWS: Dict[str, List[Card]] = {
    'mercury':  _row('AS', '3D', '5C', '10S', 'QC', 'AC', '3H'),
    'venus':    _row('2H', '9S', '9C', 'JH', '5S', '7D', '7H'),
    'mars':     _row('8C', 'JS', '2D', '4C', '6H', 'KD', 'KH'),
    'zeus':     _row('AD', 'AH', '8S', '10D', '10H', '4S', '6D'),
    'kronos':   _row('5D', '7C', '9H', '3S', '3C', '5H', 'QD'),
    'uranus':   _row('JD', 'KC', '2C', '7S', '9D', 'JC', 'QS'),
    'poseidon': _row('QH', '6S', '6C', '8H', '2S', '4D', '4H'),
}

# KARMA (bottom-right sub-card of each Life-spread cell). LOWER confidence
# than everything above -- this is the smallest print on the chart and
# has only one independently-confirmed cell (8S -> 6C, the highlighted
# example). Treat this table as a first draft; the print_grid_report()
# helper below lays it out for a quick visual diff against the source
# image.
LIFE_KARMA: Dict[str, List[Card]] = {
    'mercury':  _row('2C', 'QD', '4C', 'QH', '10D', '2C', 'QC'),
    'venus':    _row('AC', '6S', '6D', 'JH', '4D', '9S', 'AC'),
    'mars':     _row('8C', '10S', 'AD', '6S', '3D', '7C', '9S'),
    'zeus':     _row('AH', '3H', '6C', 'QD', '5H', '4H', '3D'),
    'kronos':   _row('3C', 'JC', '7D', '5S', '5D', 'KS', '9D'),
    'uranus':   _row('8D', '8C', 'AS', '8H', '5D', '10H', '10D'),
    'poseidon': _row('9S', '9C', '7S', '7H', '5S', '5H', '10D'),
}
LIFE_KARMA_CROWN: List[Card] = _row('KS', '7D', '4C')


# ══════════════════════════════════════════════════════════════════════════
#  LOOKUP ENGINE
# ══════════════════════════════════════════════════════════════════════════
# Validated traversal order for Moon / Mercury .. Phoenix -- bottom row of
# the chart up to the top row, then the Crown Line, wrapping circularly.
# See the module docstring for how this was pinned down.
_SEQUENCE_ROW_ORDER = ('poseidon', 'uranus', 'kronos', 'zeus', 'mars', 'venus', 'mercury')

_LIFE_SEQUENCE: List[Card] = []
for _r in _SEQUENCE_ROW_ORDER:
    _LIFE_SEQUENCE += LIFE_ROWS[_r]
_LIFE_SEQUENCE += LIFE_CROWN

_LIFE_ALL_CARDS = _LIFE_SEQUENCE
_SPIRIT_ALL_CARDS = [c for row in SPIRIT_ROWS.values() for c in row] + SPIRIT_CROWN

if len(_LIFE_ALL_CARDS) != 52 or len(set(_LIFE_ALL_CARDS)) != 52:
    raise RuntimeError("LIFE_SPREAD does not form a complete 52-card deck")
if len(_SPIRIT_ALL_CARDS) != 52 or len(set(_SPIRIT_ALL_CARDS)) != 52:
    raise RuntimeError("SPIRIT_SPREAD does not form a complete 52-card deck")

_SEQ_INDEX: Dict[Card, int] = {c: i for i, c in enumerate(_LIFE_SEQUENCE)}

_LIFE_POSITION: Dict[Card, Tuple[str, int]] = {}
for _rname, _cards in LIFE_ROWS.items():
    for _col, _c in enumerate(_cards):
        _LIFE_POSITION[_c] = (_rname, _col)
for _col, _c in enumerate(LIFE_CROWN):
    _LIFE_POSITION[_c] = ('crown', _col)

_LIFE_KARMA_OF: Dict[Card, Card] = {}
for _rname, _cards in LIFE_KARMA.items():
    for _col, _k in enumerate(_cards):
        _LIFE_KARMA_OF[LIFE_ROWS[_rname][_col]] = _k
for _col, _k in enumerate(LIFE_KARMA_CROWN):
    _LIFE_KARMA_OF[LIFE_CROWN[_col]] = _k


def _life_step(card: Card, n: int) -> Card:
    """Card n steps right (n>0) or left (n<0) of `card` in the Life spread."""
    return _LIFE_SEQUENCE[(_SEQ_INDEX[card] + n) % 52]


def _sun_of(earth: Card) -> Card:
    """Spirit-spread card at Earth's own (row, col) in the Life spread."""
    row_name, col = _LIFE_POSITION[earth]
    return SPIRIT_CROWN[col] if row_name == 'crown' else SPIRIT_ROWS[row_name][col]


def _karma_of(earth: Card) -> Card:
    """Bottom-right sub-card of Earth's own cell in the Life spread."""
    return _LIFE_KARMA_OF[earth]


# name -> steps left (negative) / right (positive) of Earth's own position
_STEP_POINTS: Tuple[Tuple[str, int], ...] = (
    ('moon', 1),
    ('mercury', -1), ('venus', -2), ('mars', -3), ('jupiter', -4),
    ('saturn', -5), ('uranus', -6), ('neptune', -7), ('pluto', -8),
    ('chiron', -9), ('rahu', -10), ('midheaven', -11), ('phoenix', -12),
)


@dataclass(frozen=True)
class CosmicCardProfile:
    earth:     Card
    sun:       Card
    karma:     Card
    moon:      Card
    mercury:   Card
    venus:     Card
    mars:      Card
    jupiter:   Card   # Zeus row on the chart
    saturn:    Card   # Kronos row on the chart
    uranus:    Card
    neptune:   Card   # Poseidon row on the chart
    pluto:     Card
    chiron:    Card
    rahu:      Card
    midheaven: Card
    phoenix:   Card

    def as_dict(self) -> Dict[str, str]:
        return {name: getattr(self, name).symbol for name in self.__dataclass_fields__}


def derive_cosmic_cards(earth_card: Union[Card, str]) -> CosmicCardProfile:
    """
    Given a birth (Earth) card, derive the full Cosmic Playing Card
    profile from the Master Spirit and Master Life spreads.
    """
    earth = Card.parse(earth_card)
    values = {
        'earth': earth,
        'sun': _sun_of(earth),
        'karma': _karma_of(earth),
    }
    for name, offset in _STEP_POINTS:
        values[name] = _life_step(earth, offset)
    return CosmicCardProfile(**values)


# ══════════════════════════════════════════════════════════════════════════
#  VERIFICATION AID
# ══════════════════════════════════════════════════════════════════════════
def print_grid_report() -> None:
    """
    Dump the transcribed Life-spread grid (main + karma sub-card) in the
    same row layout as the source chart, for a fast side-by-side check
    against MASTER-CARD-CHART2.jpg -- particularly the karma column,
    which is the least-verified part of this module.
    """
    print(f"{'ROW':<9}" + "".join(f"{'col'+str(i+1):<9}" for i in range(7)))
    print(f"{'crown':<9}" + "".join(f"{c.symbol:<9}" for c in LIFE_CROWN))
    print(f"{'':<9}" + "".join(f"(k:{k.symbol})".ljust(9) for k in LIFE_KARMA_CROWN))
    for rname in ('mercury', 'venus', 'mars', 'zeus', 'kronos', 'uranus', 'poseidon'):
        print(f"{rname:<9}" + "".join(f"{c.symbol:<9}" for c in LIFE_ROWS[rname]))
        print(f"{'':<9}" + "".join(f"(k:{k.symbol})".ljust(9) for k in LIFE_KARMA[rname]))


def _run_self_test() -> None:
    # Example given with the charts: Earth = Queen of Hearts -> Mercury = 10 of Clubs
    assert _life_step(Card.parse('QH'), -1) == Card.parse('10C')

    # Example given with the charts: Earth = 3 of Hearts -> Moon = King of Spades
    assert _life_step(Card.parse('3H'), 1) == Card.parse('KS')

    # Worked example from Earth_and_Sun_Card.jpg: Earth = 8S, at Zeus row /
    # col 3 in the Life spread -> Sun = KC, Karma = 6C (both read off the
    # highlighted cell's sub-cards, and KC independently matches the
    # Spirit spread's own Zeus row / col 3).
    profile = derive_cosmic_cards('8S')
    assert profile.sun == Card.parse('KC'), profile.sun
    assert profile.karma == Card.parse('6C'), profile.karma

    print("All cardology self-tests passed.")


if __name__ == "__main__":
    _run_self_test()
    print()
    print_grid_report()
    print()
    demo = derive_cosmic_cards('QH')
    print(f"Sample profile for Earth = {demo.earth.symbol} ({demo.earth.full_name}):")
    for field in demo.__dataclass_fields__:
        c = getattr(demo, field)
        print(f"  {field.capitalize():<10} {c.symbol:<5} {c.full_name}")
