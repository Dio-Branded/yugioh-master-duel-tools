"""Turn the duel log of a Yu-Gi-Oh! Master Duel match (one JSON file per match) into a readable turn-by-turn play-by-play.

The JSON holds the lists of the duel log that the game itself shows on screen (plays, chains, phases, turns) plus the card
names. The component that captures that log from the game is private and not published.

Usage:  python read_log.py --json ../data/2026-11-23_15-54-44.json
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

# Action and phase codes used by the game's duel log
LOGACTIONTYPE = {"ACTION_NONE": 0, "ACTION_DRAW": 1, "ACTION_SUMMON": 2, "ACTION_SPSUMMON": 3, "ACTION_SPSUMMON_RITUAL": 4,
                 "ACTION_SPSUMMON_FUSION": 5, "ACTION_SPSUMMON_SYNC": 6, "ACTION_SPSUMMON_XYZ": 7, "ACTION_SPSUMMON_PENDULUM": 8,
                 "ACTION_SPSUMMON_LINK": 9, "ACTION_ATTACK": 10, "ACTION_HAPPEN": 11, "ACTION_DISABLE": 12, "ACTION_SETH": 13,
                 "ACTION_SETV": 14, "ACTION_RELEASE": 15, "ACTION_REVERSE": 16, "ACTION_CONFIRM": 17, "ACTION_EXCLUDE": 18,
                 "ACTION_FLIPTOP": 19, "ACTION_EXPLOSION": 20, "ACTION_BREAK": 21, "ACTION_CTRCHANGE": 22, "ACTION_LOCKON": 23,
                 "ACTION_SENDTOGRAVE": 24, "ACTION_DROP": 25, "ACTION_SEARCH": 26, "ACTION_ADDCARD": 27, "ACTION_MOVE": 28,
                 "ACTION_VANISH": 29, "ACTION_EFFECTIMPL": 30, "ACTION_HANDOPEN": 31, "ACTION_REVERSESUMMON": 32,
                 "ACTION_RETURN": 33, "ACTION_REVERSEBACK": 34, "ACTION_SPSUMMONDEF": 35, "ACTION_SPSUMMONSET": 36,
                 "ACTION_ATKTODEFCHANGE": 37, "ACTION_DEFTOATKCHANGE": 38, "ACTION_PUT": 39, "ACTION_ZONESELECT": 40,
                 "CARDCHEAT_ADD": 41, "CARDCHEAT_SET": 42, "CARDCHEAT_PUT": 43, "CARDCHEAT_APPLY": 44, "CARDCHEAT_SEND": 45,
                 "COST_EXCLUDE": 46, "COST_RETURN": 47, "COST_MOVE": 48, "COST_SENDTOGRAVE": 49, "COST_RELEASE": 50,
                 "COST_DROP": 51, "COST_VANISH": 52}
PHASE = {"Draw": 0, "Standby": 1, "Main1": 2, "Battle": 3, "Main2": 4, "End": 5, "Null": 7}
ACTION = {v: k.replace("ACTION_", "").replace("CARDCHEAT_", "CHEAT_") for k, v in LOGACTIONTYPE.items()}
PHASE_NAME = {v: k for k, v in PHASE.items()}

ZONE = {**{i: "M%d" % (i + 1) for i in range(5)}, 5: "EMZ left", 6: "EMZ right", **{i: "S/T%d" % (i - 6) for i in range(7, 12)},
        12: "field zone", 13: "hand", 14: "Extra Deck", 15: "Deck", 16: "GY", 17: "banished", 18: "-"}
VERB = {"HAPPEN": "activates", "SUMMON": "Normal Summon", "SPSUMMON": "Special Summon", "SPSUMMON_FUSION": "Fusion Summon",
        "SPSUMMON_SYNC": "Synchro Summon", "SPSUMMON_XYZ": "Xyz Summon", "SPSUMMON_PENDULUM": "Pendulum Summon",
        "SPSUMMON_LINK": "Link Summon", "SPSUMMON_RITUAL": "Ritual Summon", "SPSUMMONDEF": "Special Summon in DEF",
        "SEARCH": "added (search)", "ADDCARD": "added", "SENDTOGRAVE": "sent to GY", "DROP": "discarded", "EXCLUDE": "banished",
        "BREAK": "destroyed", "EXPLOSION": "destroyed", "RELEASE": "tributed", "RETURN": "returned", "MOVE": "moved",
        "PUT": "placed", "SETH": "set face-down", "SETV": "set", "DRAW": "draws", "ATTACK": "attacks", "DISABLE": "negated",
        "VANISH": "leaves", "CONFIRM": "revealed", "HANDOPEN": "revealed", "LOCKON": "targeted", "EFFECTIMPL": "effect applies",
        "COST_SENDTOGRAVE": "cost: sent to GY", "COST_DROP": "cost: discarded", "COST_EXCLUDE": "cost: banished",
        "COST_RELEASE": "cost: tributed", "COST_RETURN": "cost: returned", "COST_MOVE": "cost: moved", "COST_VANISH": "cost"}

CARD_NAMES = {}   # names provided by the game itself, stored in each JSON under "nombres"


def load_names(r):
    CARD_NAMES.clear()
    CARD_NAMES.update(r.get("nombres") or {})


def card_name(cid):
    if str(cid) in CARD_NAMES:
        return CARD_NAMES[str(cid)]
    return "card %d" % cid if 0 < cid < 30000 else "hidden card"


def my_player(r):
    """My player number in the engine (0 or 1). Taken from the game's own flag when present; otherwise from the owner of the
    first play whose card name carries the local-player mark and is an activation, Normal Summon or draw (those never fail)."""
    me = [k for k, x in enumerate(r.get("rival") or []) if x == 0]
    if me:
        return me[0]
    last, prev = None, None
    for label, i in r["base"]:
        before, prev = prev, label
        if label == "ShowCardName":
            last = r["cardname"][i]
        elif label == "ShowAction" and last and before == "ShowCardName" and last[1] == 1:
            a = r["action"][i]
            if ACTION.get(a["c"][4]) in ("HAPPEN", "SUMMON", "DRAW"):
                return a["r"][3] if (a["r"][0] or a["r"][2]) else a["l"][3]
    return None


def owner(a):
    """Owner of the card in a play = byte 3 of the destination side (or the source side when there is no destination).
    The local-player flag attached to card names is wrong when the opponent summons during my turn, so it is not used here."""
    return a["r"][3] if (a["r"][0] or a["r"][2]) else a["l"][3]


def translate(r):
    load_names(r)
    out = []
    last_name = None
    me = my_player(r)

    def who(p):          # p = engine player number
        if me is None or p not in (0, 1):
            return "P%s" % p
        return "YOU" if p == me else "OPP"

    def who_local(team):  # chain entries carry a local-player flag (1 = me)
        return "YOU" if team == 1 else "OPP"

    prev = None
    for label, i in r["base"]:
        before, prev = prev, label
        if label == "ShowTurn":
            t = r["turn"][i]
            turn_player = int(t[0]) & 0xFFFFFFFF
            last_name = None
            lp = ("YOU %d / OPP %d" % ((t[2], t[3]) if me == 0 else (t[3], t[2]))) if me in (0, 1) else "P0 %d / P1 %d" % (t[2], t[3])
            out.append("\n===== Turn %d (%s)   LP %s =====" % (i + 1, who(turn_player), lp))
        elif label == "ShowPhase":
            out.append("  -- %s" % PHASE_NAME.get(r["phase"][i], r["phase"][i]))
        elif label == "ShowCardName":
            last_name = r["cardname"][i]
        elif label == "ShowAction":
            a = r["action"][i]
            kind = ACTION.get(a["c"][4], a["c"][4])
            if kind == "NONE":
                continue
            cid = a["r"][0] if 0 < a["r"][0] < 30000 else (a["l"][0] if 0 < a["l"][0] < 30000 else
                                                          (last_name[0] if last_name and before == "ShowCardName" and 0 < last_name[0] < 30000 else -1))
            src = ZONE.get(a["l"][2], a["l"][2])
            dst = ZONE.get(a["r"][2], a["r"][2]) if (a["r"][0] or a["r"][2]) else "-"
            material = " [material]" if a["l"][5] or a["r"][5] else ""
            out.append("  %s %s: %s (%s -> %s)%s" % (who(owner(a)), card_name(cid), VERB.get(kind, kind), src, dst, material))
        elif label == "ShowChain":
            c = r["chain"][i]
            out.append("  %s chain link %d: %s (%s)" % ("ACTIVATES" if c[3] == 0 else "resolves", c[1], card_name(c[0]), who_local(c[2])))
        elif label == "ShowTag":
            g = r["tag"][i]
            out.append("    (%s)" % ("target" if g[0] == 0 else "cost"))
        elif label == "CardMoveMulti":
            mm = r["movemulti"][i]
            if mm["acts"]:
                a = mm["acts"][0]
                kind = ACTION.get(a["c"][4])
                out.append("  (%d cards: %s, %s -> %s)" % (len(mm["acts"]), VERB.get(kind, kind), ZONE.get(a["l"][2]), ZONE.get(a["r"][2])))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True)
    args = ap.parse_args()
    r = json.load(open(args.json, encoding="utf-8"))
    text = translate(r)
    target = Path(args.json).with_suffix(".txt")
    target.write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    print()
    print("saved:", target)


if __name__ == "__main__":
    main()
