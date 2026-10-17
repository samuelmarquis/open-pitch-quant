"""FaderScene: the fader family standard (PLAN 2.9) over ControlScene.
Member: fader-desk.

A generator declares ControlScene's attributes plus, where its canon differs
from the family defaults:

  VALUE = 0.5                          default --value
  TAPERS = ("db", "bipolar", "unipolar")
                                       --taper choices (printed marking scales)
  TAPER = "db"                         default --taper

Flags added to the shared vocabulary:
  --value V      cap position along the travel, 0..1 (1 = top)
  --taper T      printed marking scale beside the slot
  --scale S      (shared) physical size: coherent zoom of part and rig

`--scale` with a TAPERS value (`--scale bipolar`) is the pre-family spelling of
`--taper` and is accepted as its alias; a number is the size.

Slots: cap (the grip), panel (the slotted plate), inlay (the strip inset in the
cap); SLOTS declares any subset plus EXTRA_SLOTS.

travel_offset(travel) -> (value - 0.5) * travel: the cap's offset from the
slot centre along +Y.
"""

from .base import Alias
from .control import ControlScene, Flag

FAMILY_SLOTS = ("cap", "panel", "inlay")
FAMILY_SLOT_HELP = {
    "cap": "fader cap (the grip)",
    "panel": "slotted panel plate",
    "inlay": "strip inset in the cap",
}


class FaderScene(ControlScene):
    FAMILY_SLOTS = FAMILY_SLOTS
    FAMILY_SLOT_HELP = FAMILY_SLOT_HELP
    VALUE = 0.5
    TAPERS = ("db", "bipolar", "unipolar")
    TAPER = "db"

    @classmethod
    def family_flags(cls):
        return [
            Flag("--value", float, cls.VALUE, help="cap position along the travel, 0..1 (1 = top)"),
            Flag("--taper", str, cls.TAPER, choices=cls.TAPERS,
                 aliases=[Alias("--scale", values=cls.TAPERS)],
                 help="printed marking scale beside the slot"),
        ]

    def validate(self):
        super().validate()
        if not 0.0 <= self.args.value <= 1.0:
            raise SystemExit(f"{self.COMPONENT}: --value must be in 0..1")

    def travel_offset(self, travel):
        return (self.args.value - 0.5) * travel
