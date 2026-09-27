#!/usr/bin/env python3
"""
cosmic_calendar.py
==================
Python implementation of the Cosmic Calendar — a 13-month, 28-day-per-month
calendar system beginning December 19, with playing cards assigned to each day.

Structure
---------
  • 13 months × 28 days = 364 days
  • Year begins: December 19
  • Leap Day:    December 18 (of the following year) → Joker
  • Feb 29 (Gregorian leap years) → intercalary day inside Month III → 7 ♦
  • Every cosmic month always maps to the same Gregorian date range,
    in both leap and non-leap years.

Usage
-----
  python cosmic_calendar.py                       # today
  python cosmic_calendar.py today
  python cosmic_calendar.py month 2026 3          # Month III, Cosmic Year 2026
  python cosmic_calendar.py year  2026            # full-year summary
  python cosmic_calendar.py lookup 2028-02-29     # look up any Gregorian date
  python cosmic_calendar.py lookup 2028-12-18     # look up the Leap Day
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

# ── Card System ────────────────────────────────────────────────────────────────

# Ordered K → A  (index 0 = K, index 12 = A)
CARD_VALUES: list[str] = [
    'K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3', '2', 'A'
]

def _ci(value: str) -> int:
    """Index of a card value in CARD_VALUES (K = 0 … A = 12)."""
    return CARD_VALUES.index(value)

SUIT_SYMBOL: dict[str, str] = {
    'spades':   '♠',
    'diamonds': '♦',
    'clubs':    '♣',
    'hearts':   '♥',
}
SUIT_NAME: dict[str, str] = {v: k.capitalize() for k, v in SUIT_SYMBOL.items()}
SUIT_NAME['★'] = 'Joker'

_S = SUIT_SYMBOL

# ── Month Segments ─────────────────────────────────────────────────────────────
# Each entry: (suit_symbol, start_day, end_day, card_start_index)
# Card for cosmic day d in segment = CARD_VALUES[card_start_index + (d - start_day)]

MONTH_SEGMENTS: list[list[tuple[str, int, int, int]]] = [
    # Month I    Dec 19 – Jan 15
    [(_S['spades'],   1, 13, _ci('K')),
     (_S['diamonds'], 14, 26, _ci('K')),
     (_S['clubs'],    27, 28, _ci('K'))],

    # Month II   Jan 16 – Feb 12
    [(_S['spades'],   1, 11, _ci('J')),
     (_S['diamonds'], 12, 24, _ci('K')),
     (_S['clubs'],    25, 28, _ci('K'))],

    # Month III  Feb 13 – Mar 12
    #   Spades   days  1– 9  (9→A)   Feb 13–21
    #   Diamonds days 10–22  (K→A)   Feb 22–Mar 6  [Feb 29 → 7♦ intercalary]
    #   Clubs    days 23–28  (K→8)   Mar 7–12
    [(_S['spades'],   1,  9,  _ci('9')),
     (_S['diamonds'], 10, 22, _ci('K')),
     (_S['clubs'],    23, 28, _ci('K'))],

    # Month IV   Mar 13 – Apr 9
    [(_S['spades'],   1,  7,  _ci('7')),
     (_S['diamonds'], 8,  20, _ci('K')),
     (_S['clubs'],    21, 28, _ci('K'))],

    # Month V    Apr 10 – May 7
    [(_S['spades'],   1,  5,  _ci('5')),
     (_S['diamonds'], 6,  18, _ci('K')),
     (_S['clubs'],    19, 28, _ci('K'))],

    # Month VI   May 8 – Jun 4
    [(_S['spades'],   1,  3,  _ci('3')),
     (_S['diamonds'], 4,  16, _ci('K')),
     (_S['clubs'],    17, 28, _ci('K'))],

    # Month VII  Jun 5 – Jul 2
    [(_S['spades'],   1,  1,  _ci('A')),
     (_S['diamonds'], 2,  14, _ci('K')),
     (_S['clubs'],    15, 27, _ci('K')),
     (_S['hearts'],   28, 28, _ci('K'))],

    # Month VIII Jul 3 – Jul 30
    [(_S['diamonds'], 1,  12, _ci('Q')),
     (_S['clubs'],    13, 25, _ci('K')),
     (_S['hearts'],   26, 28, _ci('K'))],

    # Month IX   Jul 31 – Aug 27
    [(_S['diamonds'], 1,  10, _ci('10')),
     (_S['clubs'],    11, 23, _ci('K')),
     (_S['hearts'],   24, 28, _ci('K'))],

    # Month X    Aug 28 – Sep 24
    [(_S['diamonds'], 1,  8,  _ci('8')),
     (_S['clubs'],    9,  21, _ci('K')),
     (_S['hearts'],   22, 28, _ci('K'))],

    # Month XI   Sep 25 – Oct 22
    [(_S['diamonds'], 1,  6,  _ci('6')),
     (_S['clubs'],    7,  19, _ci('K')),
     (_S['hearts'],   20, 28, _ci('K'))],

    # Month XII  Oct 23 – Nov 19
    [(_S['diamonds'], 1,  4,  _ci('4')),
     (_S['clubs'],    5,  17, _ci('K')),
     (_S['hearts'],   18, 28, _ci('K'))],

    # Month XIII Nov 20 – Dec 17
    [(_S['diamonds'], 1,  2,  _ci('2')),
     (_S['clubs'],    3,  15, _ci('K')),
     (_S['hearts'],   16, 28, _ci('K'))],
]

ROMAN: list[str] = [
    'I', 'II', 'III', 'IV', 'V', 'VI', 'VII',
    'VIII', 'IX', 'X', 'XI', 'XII', 'XIII',
]

MONTH_RANGES: list[str] = [
    'Dec 19 – Jan 15',   # I
    'Jan 16 – Feb 12',   # II
    'Feb 13 – Mar 12',   # III
    'Mar 13 – Apr  9',   # IV
    'Apr 10 – May  7',   # V
    'May  8 – Jun  4',   # VI
    'Jun  5 – Jul  2',   # VII
    'Jul  3 – Jul 30',   # VIII
    'Jul 31 – Aug 27',   # IX
    'Aug 28 – Sep 24',   # X
    'Sep 25 – Oct 22',   # XI
    'Oct 23 – Nov 19',   # XII
    'Nov 20 – Dec 17',   # XIII
]

# ── ANSI Colours ───────────────────────────────────────────────────────────────

class C:
    """Terminal colour codes."""
    RESET    = '\033[0m'
    BOLD     = '\033[1m'
    SPADES   = '\033[94m'          # blue
    DIAMONDS = '\033[93m'          # yellow
    CLUBS    = '\033[92m'          # green
    HEARTS   = '\033[91m'          # red
    JOKER    = '\033[95m'          # magenta
    TODAY    = '\033[43m\033[30m'  # gold background, black text
    HEADER   = '\033[96m'          # cyan

SUIT_COLOUR: dict[str, str] = {
    '♠': C.SPADES,
    '♦': C.DIAMONDS,
    '♣': C.CLUBS,
    '♥': C.HEARTS,
    '★': C.JOKER,
}

def _use_colour() -> bool:
    return sys.stdout.isatty()

def coloured(text: str, code: str) -> str:
    return f'{code}{text}{C.RESET}' if _use_colour() else text

# ── Core Logic ─────────────────────────────────────────────────────────────────

def is_greg_leap(year: int) -> bool:
    """Return True if *year* is a Gregorian leap year."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

def cosmic_year_start(cy: int) -> date:
    """Return December 19 of cosmic year *cy* (the first day of that year)."""
    return date(cy, 12, 19)

def cosmic_day_to_date(cy: int, month: int, day: int) -> date:
    """
    Return the Gregorian date for a given cosmic year / month / day.

    Feb 29 is an intercalary day that sits *outside* the 364-day cosmic
    structure.  To keep every month anchored to the same Gregorian date
    range regardless of leap year, any raw arithmetic result that falls on
    or after Feb 29 of the following Gregorian year is shifted forward by
    one day, effectively skipping Feb 29 in the regular day count.
    """
    d = cosmic_year_start(cy) + timedelta(days=(month - 1) * 28 + (day - 1))
    if is_greg_leap(cy + 1):
        feb29 = date(cy + 1, 2, 29)
        if d >= feb29:
            d += timedelta(days=1)
    return d

def leap_day_date(cy: int) -> date:
    """Return the Leap Day (December 18, cy+1) for cosmic year *cy*."""
    return date(cy + 1, 12, 18)

def get_card(month: int, day: int) -> tuple[str, str]:
    """
    Return (suit_symbol, card_value) for a cosmic month / day.

    This is a pure table lookup.  All leap-year adjustments are handled
    upstream in cosmic_day_to_date and date_to_cosmic, so no Gregorian
    context is needed here.  Feb 29 (7♦) and the Leap Day (Joker) are
    identified before this function is called.
    """
    for (suit, start, end, c_idx) in MONTH_SEGMENTS[month - 1]:
        if start <= day <= end:
            return (suit, CARD_VALUES[c_idx + (day - start)])
    raise ValueError(f'No card found for month={month}, day={day}')

def date_to_cosmic(d: date) -> dict | None:
    """
    Convert a Gregorian date to its cosmic calendar position.

    Returns a dict with one of three types:

      type='regular'
          cy, month (1–13), day (1–28), card=(suit, value), greg=date

      type='feb29'
          cy, month=3, day=17, card=('♦','7'), greg=date
          Feb 29 is an intercalary day placed between Month III days 16 & 17.

      type='leap_day'
          cy, card=('★','Joker'), greg=date
          December 18 — the cosmic Leap Day.

    Returns None if the date cannot be resolved.
    """
    for cy_offset in (-1, 0, 1):
        cy    = d.year + cy_offset
        start = cosmic_year_start(cy)

        # ── Leap Day (Dec 18) ──
        if d == leap_day_date(cy):
            return {'type': 'leap_day', 'cy': cy,
                    'card': ('★', 'Joker'), 'greg': d}

        # ── Feb 29 intercalary ──
        if is_greg_leap(cy + 1):
            feb29 = date(cy + 1, 2, 29)
            if d == feb29:
                return {'type': 'feb29', 'cy': cy, 'month': 3, 'day': 17,
                        'card': ('♦', '7'), 'greg': d}
            # Dates after Feb 29: remove the extra day from the offset so the
            # cosmic slot matches what cosmic_day_to_date assigns.
            diff = (d - start).days
            if d > feb29:
                diff -= 1
        else:
            diff = (d - start).days

        if 0 <= diff < 364:
            month = diff // 28 + 1
            day   = diff %  28 + 1
            return {'type': 'regular', 'cy': cy, 'month': month,
                    'day': day, 'card': get_card(month, day), 'greg': d}

    return None

# ── Formatting ─────────────────────────────────────────────────────────────────

WIDTH = 74

def _divider(char: str = '─') -> str:
    return char * WIDTH

def fmt_card(suit: str, value: str) -> str:
    """Coloured card string, e.g.  K♠  or  7♦."""
    return coloured(f'{value}{suit}', SUIT_COLOUR.get(suit, ''))

def fmt_date(d: date) -> str:
    return d.strftime('%b %d, %Y')

def fmt_cosmic_year(cy: int) -> str:
    """Canonical cosmic year label.
    The displayed year number is cy+1; the range runs Dec cy to December cy+1.
    Example: cy=2025  ->  Cosmic Year 2026 (Dec 2025 - December 2026)
    """
    return f'Cosmic Year {cy + 1} (Dec {cy} - December {cy + 1})'

# ── Display Functions ──────────────────────────────────────────────────────────

def print_today_info() -> None:
    """Print today's cosmic date and card."""
    today = date.today()
    info  = date_to_cosmic(today)

    print()
    print(coloured(_divider('═'), C.HEADER))
    print(coloured("  TODAY'S COSMIC DATE".center(WIDTH), C.HEADER + C.BOLD))
    print(coloured(_divider('═'), C.HEADER))

    if info is None:
        print(f'  {today.strftime("%B %d, %Y")} — could not resolve cosmic position.')
        print()
        return

    suit, value = info['card']

    if info['type'] == 'leap_day':
        print(f'  Gregorian Date  :  {today.strftime("%B %d, %Y")}')
        print(f'  Cosmic Position :  {coloured("Leap Day", C.JOKER)}'
              f'  ·  {fmt_cosmic_year(info["cy"])}')
        print(f'  Card            :  {fmt_card(suit, value)}')

    elif info['type'] == 'feb29':
        print(f'  Gregorian Date  :  {today.strftime("%B %d, %Y")}')
        print(f'  Cosmic Position :  '
              f'{coloured("Intercalary Day — Feb 29", C.DIAMONDS)}'
              f'  ·  {fmt_cosmic_year(info["cy"])}, Month III')
        print(f'  Card            :  {fmt_card(suit, value)}  (Diamonds)')

    else:
        m = info['month']
        print(f'  Gregorian Date  :  {today.strftime("%B %d, %Y")}')
        print(f'  Cosmic Year     :  {fmt_cosmic_year(info["cy"])}')
        print(f'  Cosmic Month    :  {ROMAN[m - 1]}  ({MONTH_RANGES[m - 1]})')
        print(f'  Cosmic Day      :  {info["day"]}')
        print(f'  Card            :  {fmt_card(suit, value)}'
              f'  ({SUIT_NAME.get(suit, "")})')

    print(coloured(_divider('═'), C.HEADER))
    print()


def print_month_calendar(cy: int, month: int) -> None:
    """Print a full day-by-day table for one cosmic month."""
    today = date.today()

    # Is there a Feb 29 intercalary day in this cosmic year?
    has_feb29 = is_greg_leap(cy + 1)
    leap_note = '  ✦ Leap Year — Feb 29 intercalary = 7♦' if (month == 3 and has_feb29) else ''

    title = (f'  Month {ROMAN[month - 1]}  ·  {MONTH_RANGES[month - 1]}'
             f'  ·  {fmt_cosmic_year(cy)}{leap_note}')

    print()
    print(coloured(_divider('═'), C.HEADER))
    print(coloured(title, C.HEADER + C.BOLD))
    print(coloured(_divider('═'), C.HEADER))
    print(f'  {"Day":>3}  │  {"Gregorian Date":<14}  │'
          f'  {"Card":<6}  │  {"Suit":<10}  │  Notes')
    print(_divider('─'))

    for day in range(1, 29):
        # Insert the Feb 29 intercalary row between days 16 and 17 of Month III
        if month == 3 and has_feb29 and day == 17:
            feb29 = date(cy + 1, 2, 29)
            f29_mark = coloured(' ◀ TODAY', C.TODAY) if feb29 == today else ''
            f29_card = fmt_card('♦', '7')
            pad = 6 - len('7♦')
            print(_divider('·'))
            print(f'  {"✦":>3}  │  {fmt_date(feb29):<14}  │'
                  f'  {f29_card}{" " * pad}│  {"Diamonds":<10}  │'
                  f'  Feb 29 · Intercalary{f29_mark}')
            print(_divider('·'))

        greg      = cosmic_day_to_date(cy, month, day)
        suit, val = get_card(month, day)
        card_str  = fmt_card(suit, val)
        suit_str  = SUIT_NAME.get(suit, '')
        pad       = 6 - len(f'{val}{suit}')

        notes: list[str] = []
        if greg == today:
            notes.append(coloured('◀ TODAY', C.TODAY))

        print(f'  {day:>3}  │  {fmt_date(greg):<14}  │'
              f'  {card_str}{" " * pad}│  {suit_str:<10}  │  {"  ".join(notes)}')

    # Feb 29 intercalary summary (Month III of leap years only)
    if month == 3 and has_feb29:
        feb29    = date(cy + 1, 2, 29)
        f29_mark = coloured('  ◀ TODAY', C.TODAY) if feb29 == today else ''
        print(_divider('─'))
        print(f'  {"✦ Feb 29":<8}  Intercalary day · always 7♦ · '
              f'{fmt_date(feb29)}{f29_mark}')

    # Leap Day (Dec 18)
    ld      = leap_day_date(cy)
    ld_mark = coloured('  ◀ TODAY', C.TODAY) if ld == today else ''
    print(_divider('─'))
    print(f'  {"★ Leap Day":<12}  Dec 18 · Joker · {fmt_date(ld)}{ld_mark}')
    print(coloured(_divider('═'), C.HEADER))
    print()


def print_year_summary(cy: int) -> None:
    """Print a compact overview of all 13 months in a cosmic year."""
    today     = date.today()
    today_pos = date_to_cosmic(today)

    print()
    print(coloured(_divider('═'), C.HEADER))
    print(coloured(
        f'  {fmt_cosmic_year(cy)}'.center(WIDTH),
        C.HEADER + C.BOLD,
    ))
    if is_greg_leap(cy + 1):
        print(coloured(
            '  ✦ Leap Year — Feb 29 intercalary in Month III'.center(WIDTH),
            C.DIAMONDS,
        ))
    print(coloured(_divider('═'), C.HEADER))
    print(f'  {"Month":<10}  {"Range":<22}  Suits (card span)')
    print(_divider('─'))

    for m in range(1, 14):
        segs     = MONTH_SEGMENTS[m - 1]
        segs_str = '   '.join(
            f'{coloured(su, SUIT_COLOUR[su])}'
            f'{CARD_VALUES[c_i]}→{CARD_VALUES[c_i + (e - s)]}'
            for su, s, e, c_i in segs
        )
        marker = ''
        if (today_pos and today_pos['type'] in ('regular', 'feb29')
                and today_pos['cy'] == cy and today_pos['month'] == m):
            marker = coloured('  ◀ current month', C.TODAY)

        print(f'  Month {ROMAN[m - 1]:<6}  {MONTH_RANGES[m - 1]:<22}  '
              f'{segs_str}{marker}')

    # Feb 29 intercalary row
    if is_greg_leap(cy + 1):
        feb29    = date(cy + 1, 2, 29)
        f29_mrk  = coloured('  ◀ TODAY', C.TODAY) if feb29 == today else ''
        f29_card = coloured('7♦', C.DIAMONDS)
        print(_divider('·'))
        print(f'  {"✦ Feb 29":<10}  {fmt_date(feb29):<22}  '
              f'{f29_card}  Intercalary (Month III){f29_mrk}')

    ld      = leap_day_date(cy)
    ld_col  = coloured('★ Joker', C.JOKER)
    ld_mrk  = coloured('  ◀ TODAY', C.TODAY) if ld == today else ''
    print(_divider('─'))
    print(f'  {"★ Leap Day":<10}  {fmt_date(ld):<22}  {ld_col}{ld_mrk}')
    print(coloured(_divider('═'), C.HEADER))
    print()


def print_lookup(d: date) -> None:
    """Look up and display a single Gregorian date."""
    info = date_to_cosmic(d)

    print()
    print(coloured(_divider('═'), C.HEADER))
    print(coloured(
        f'  LOOKUP  ·  {d.strftime("%B %d, %Y")}'.center(WIDTH),
        C.HEADER + C.BOLD,
    ))
    print(coloured(_divider('═'), C.HEADER))

    if info is None:
        print(f'  No cosmic position found for {d}.')
        print()
        return

    suit, value = info['card']

    if info['type'] == 'leap_day':
        print(f'  Cosmic Position :  {coloured("Leap Day", C.JOKER)}'
              f'  ·  {fmt_cosmic_year(info["cy"])}')
        print(f'  Card            :  {fmt_card(suit, value)}')

    elif info['type'] == 'feb29':
        print(f'  Cosmic Year     :  {fmt_cosmic_year(info["cy"])}')
        print(f'  Cosmic Position :  '
              f'{coloured("Intercalary Day — Feb 29", C.DIAMONDS)}')
        print(f'  Placement       :  Month III, between Days 16 & 17')
        print(f'  Card            :  {fmt_card(suit, value)}  (Diamonds)')

    else:
        m = info['month']
        print(f'  Cosmic Year     :  {fmt_cosmic_year(info["cy"])}')
        print(f'  Cosmic Month    :  {ROMAN[m - 1]}  ({MONTH_RANGES[m - 1]})')
        print(f'  Cosmic Day      :  {info["day"]}')
        print(f'  Card            :  {fmt_card(suit, value)}'
              f'  ({SUIT_NAME.get(suit, "")})')

    print(coloured(_divider('═'), C.HEADER))
    print()

# ── CLI ────────────────────────────────────────────────────────────────────────

EPILOG = """
examples:
  python cosmic_calendar.py                       today's date
  python cosmic_calendar.py today                 today's date
  python cosmic_calendar.py month 2026 3          Month III, Cosmic Year 2026
  python cosmic_calendar.py year  2026            full year summary
  python cosmic_calendar.py lookup 2028-02-29     look up Feb 29, 2028
  python cosmic_calendar.py lookup 2028-12-18     look up the Leap Day

note:
  Cosmic year label XXXX spans Dec XXXX-1 through December XXXX.
  Pass that same XXXX as the cosmic_year argument.
"""

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='cosmic_calendar.py',
        description='Cosmic Calendar — 13-month playing-card calendar system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    sub = p.add_subparsers(dest='command')

    sub.add_parser('today', help="Show today's cosmic date and card")

    pm = sub.add_parser('month', help='Show a specific cosmic month')
    pm.add_argument('cosmic_year', type=int,
                    help='Cosmic year label XXXX, e.g. 2026 = Dec 2025 – December 2026')
    pm.add_argument('month', type=int, choices=range(1, 14), metavar='MONTH',
                    help='Month number 1–13')

    py = sub.add_parser('year', help='Show all 13 months of a cosmic year')
    py.add_argument('cosmic_year', type=int, help='Cosmic year label XXXX (e.g. 2026)')
    py.add_argument('--full', '-f', action='store_true',
                    help='Also print the day-by-day table for every month')

    pl = sub.add_parser('lookup', help='Look up a Gregorian date (YYYY-MM-DD)')
    pl.add_argument('date', help='Date in YYYY-MM-DD format')

    return p


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    if args.command in ('today', None):
        print_today_info()

    elif args.command == 'month':
        print_month_calendar(args.cosmic_year - 1, args.month)

    elif args.command == 'year':
        cy = args.cosmic_year - 1
        print_year_summary(cy)
        if args.full:
            for m in range(1, 14):
                print_month_calendar(cy, m)
        else:
            ans = input(
                '  Print full day-by-day tables for all months? [y/N] '
            ).strip().lower()
            if ans == 'y':
                for m in range(1, 14):
                    print_month_calendar(cy, m)

    elif args.command == 'lookup':
        try:
            d = date.fromisoformat(args.date)
        except ValueError:
            parser.error(f"invalid date '{args.date}' — use YYYY-MM-DD format")
        print_lookup(d)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
