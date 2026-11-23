"""Analysis of my own Yu-Gi-Oh! Master Duel matches (one JSON file per match in ../data).

Produces ../STATS.md: results going first and second, opponent archetype inferred from the cards they revealed, cards I played
and their record, hand traps and responses (who used what against which card, and whether it was negated) and my full
first-turn line in each match.

Usage:  python analysis.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from read_log import ACTION, DATA, card_name, load_names, my_player, owner  # noqa: E402

# Generic staples are ignored when guessing the opponent's archetype
GENERIC = {"Ash Blossom & Joyous Spring", 'Maxx "C"', "Droll & Lock Bird", "Infinite Impermanence", "Effect Veiler",
           "Ghost Ogre & Snow Rabbit", "Ghost Belle & Haunted Mansion", "Nibiru, the Primal Being", "Mulcharmy Fuwalos",
           "Mulcharmy Purulia", "Mulcharmy Meowls", "Called by the Grave", "Crossout Designator", "Triple Tactics Talent",
           "Forbidden Droplet", "Dark Ruler No More", "Harpie's Feather Duster", "Lightning Storm", "Pot of Prosperity",
           "Linkuriboh", "Salamangreat Almiraj", "Crystron Halqifibrax Prism", "Baronne de Fleur", "Charmer Quartet in Bloom",
           "I:P Masquerena", "S:P Little Knight", "Knightmare Unicorn", "Accesscode Talker", "Apollousa, Bow of the Goddess",
           "Super Starslayer TY-PHON - Sky Crisis", "Bystial Druiswurm", "Bystial Magnamhut", "Piri Reis Map"}
PLAYS = {"SUMMON", "SPSUMMON", "SPSUMMON_FUSION", "SPSUMMON_SYNC", "SPSUMMON_XYZ", "SPSUMMON_PENDULUM", "SPSUMMON_LINK",
         "SPSUMMON_RITUAL", "SPSUMMONDEF", "HAPPEN", "SETH", "SETV"}
LINE = {"SUMMON": "Normal", "SPSUMMON": "Special", "SPSUMMONDEF": "Special", "SPSUMMON_FUSION": "Fusion", "SPSUMMON_SYNC": "Synchro",
        "SPSUMMON_XYZ": "Xyz", "SPSUMMON_PENDULUM": "Pendulum", "SPSUMMON_LINK": "Link", "SPSUMMON_RITUAL": "Ritual",
        "HAPPEN": "activates", "SEARCH": "search", "ADDCARD": "add", "SETH": "set", "SETV": "set"}


def events(r, me):
    """Same rules as read_log.translate(), as a list of dicts. Players are engine player numbers."""
    ev, last, prev, turn = [], None, None, 0
    for label, i in r["base"]:
        before, prev = prev, label
        if label == "ShowTurn":
            turn += 1
            last = None
            ev.append({"k": "turn", "turn": turn, "turn_player": int(r["turn"][i][0]) & 0xFFFFFFFF})
        elif label == "ShowCardName":
            last = r["cardname"][i]
        elif label == "ShowAction":
            a = r["action"][i]
            kind = ACTION.get(a["c"][4], a["c"][4])
            if kind == "NONE":
                continue
            cid = a["r"][0] if 0 < a["r"][0] < 30000 else (a["l"][0] if 0 < a["l"][0] < 30000 else
                                                          (last[0] if last and before == "ShowCardName" and 0 < last[0] < 30000 else -1))
            ev.append({"k": "play", "turn": turn, "who": owner(a), "kind": kind, "card": cid, "material": bool(a["l"][5] or a["r"][5])})
        elif label == "ShowChain":
            c = r["chain"][i]
            ev.append({"k": "chain", "turn": turn, "who": me if c[2] == 1 else 1 - me, "card": c[0], "link": c[1], "activates": c[3] == 0})
    return ev


def archetype(cards):
    count = Counter()
    for n in cards:
        if n in GENERIC:
            continue
        for w in set(re.findall(r"[A-Za-z][A-Za-z\-']{3,}", n)):
            if w.lower() not in {"the", "of", "and", "with", "from", "power", "dragon", "lord", "king", "queen"}:
                count[w] += 1
    if not count:
        return "?"
    word, n = count.most_common(1)[0]
    return word if n >= 2 else "?"


def analyse(f):
    r = json.load(open(f, encoding="utf-8"))
    if "lp" not in r:          # partial dump, no end of duel
        return None
    load_names(r)
    me = my_player(r)
    if me is None:
        return None
    opp = 1 - me
    ev = events(r, me)
    turns = [e for e in ev if e["k"] == "turn"]
    first = turns[0]["turn_player"] == me if turns else None
    lp = r.get("lp") or [None, None]
    if None in lp:
        result = "?"
    else:
        result = "win" if lp[opp] <= 0 < lp[me] else ("loss" if lp[me] <= 0 else "?")
    plays = [e for e in ev if e["k"] == "play"]
    mine = [e for e in plays if e["who"] == me and e["card"] > 0]
    theirs = [e for e in plays if e["who"] == opp and e["card"] > 0]
    played = sorted({card_name(e["card"]) for e in mine if e["kind"] in PLAYS})
    seen_from_opp = sorted({card_name(e["card"]) for e in theirs})
    # responses: a chain link >= 2 answers the previous activation of the same chain
    responses, chain = [], []
    for e in ev:
        if e["k"] == "play" and e["kind"] == "HAPPEN" and e["card"] > 0:
            if not chain or chain[-1][0] != e["card"]:
                chain.append((e["card"], e["who"]))
        elif e["k"] == "chain":
            if e["activates"] and e["link"] >= 2:
                target = chain[-1] if chain else (None, None)
                responses.append({"who": e["who"], "card": card_name(e["card"]),
                                  "against": card_name(target[0]) if target[0] else "?", "negated": False})
                chain.append((e["card"], e["who"]))
            elif not e["activates"] and e["link"] == 1:
                chain = []
        elif e["k"] == "play" and e["kind"] == "DISABLE" and responses:
            if responses[-1]["against"] == card_name(e["card"]):
                responses[-1]["negated"] = True
    # my first turn: the line (summons and activations in order)
    my_turn = next((t["turn"] for t in turns if t["turn_player"] == me), None)
    line = ["%s (%s)" % (card_name(e["card"]), LINE[e["kind"]]) for e in mine
            if e["turn"] == my_turn and e["kind"] in LINE and not e["material"]]
    return {"file": f.name, "me": me, "first": first, "result": result, "turns": len(turns), "opponent": archetype(seen_from_opp),
            "played": played, "responses": responses, "line": line}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    matches = [m for m in (analyse(f) for f in sorted(DATA.glob("*.json"))) if m]

    def record(xs):
        w = sum(1 for x in xs if x["result"] == "win")
        lo = sum(1 for x in xs if x["result"] == "loss")
        return "%d-%d%s" % (w, lo, (" (%d%% wins)" % round(100 * w / (w + lo))) if w + lo else "")

    out = ["# My Master Duel matches", "", "Generated by code/analysis.py from data/ (%d complete matches)." % len(matches), "",
           "## Results", "",
           "- Overall: %s" % record(matches),
           "- Going first: %s" % record([x for x in matches if x["first"]]),
           "- Going second: %s" % record([x for x in matches if x["first"] is False]), "",
           "| Match | I went | Opponent | Turns | Result |", "|---|---|---|---|---|"]
    for x in matches:
        out.append("| %s | %s | %s | %d | %s |" % (x["file"][:16], "first" if x["first"] else "second", x["opponent"], x["turns"], x["result"]))
    usage = defaultdict(lambda: [0, 0])
    for x in matches:
        for c in x["played"]:
            usage[c][0] += 1
            usage[c][1] += x["result"] == "win"
    out += ["", "## Cards I played (matches played, matches won)", "", "| Card | Matches | Wins |", "|---|---|---|"]
    for c, (n, w) in sorted(usage.items(), key=lambda kv: -kv[1][0]):
        out.append("| %s | %d | %d |" % (c, n, w))
    out += ["", "## Hand traps and responses", "", "| Match | Who | Card | Against | Negated |", "|---|---|---|---|---|"]
    for x in matches:
        for q in x["responses"]:
            out.append("| %s | %s | %s | %s | %s |" % (x["file"][11:16], "me" if q["who"] == x["me"] else "opponent", q["card"],
                                                     q["against"], "yes" if q["negated"] else ""))
    out += ["", "## My first turn in each match", ""]
    for x in matches:
        out.append("- %s (%s, vs %s, %s): %s" % (x["file"][:16], "first" if x["first"] else "second", x["opponent"], x["result"],
                                                 " -> ".join(x["line"]) or "(nothing)"))
    text = "\n".join(out) + "\n"
    (DATA.parent / "STATS.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
