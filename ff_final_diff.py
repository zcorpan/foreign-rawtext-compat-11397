"""Per page: SVG/MathML elements of interest whose final state (after scripts) differs between A
and B but not between A and A2, plus JS errors new in B. usage: ff_final_diff.py OUT_DIR..."""
import json, sys

def sig(e):
    return (e["ns"], e["name"], e["text"], tuple(e["kinds"]), e["rules"])

for d in sys.argv[1:]:
    print("==", d)
    for line in open(d + "/results.jsonl"):
        r = json.loads(line)
        A, A2, B = r["A"], r["A2"], r["B"]
        if any("error" in x for x in (A, A2, B)):
            print(r["id"], "ERROR"); continue
        noisy = {i for i, (x, y) in enumerate(zip(A["els"], A2["els"])) if sig(x) != sig(y)}
        diffs = [(x, y) for i, (x, y) in enumerate(zip(A["els"], B["els"])) if i not in noisy and sig(x) != sig(y)]
        base = set(A["errors"]) | set(A2["errors"])
        errs = [e for e in B["errors"] if e not in base and "Cookie" not in e]
        if not diffs and not errs and len(A["els"]) == len(B["els"]):
            print(r["id"], "same"); continue
        kinds = set()
        for x, y in diffs:
            if x["text"] != y["text"]:
                kinds.add(f'{y["name"]} text: {json.dumps(x["text"][:50], ensure_ascii=False)} -> {json.dumps(y["text"][:70], ensure_ascii=False)}')
            elif x["rules"] != y["rules"]:
                kinds.add(f'{y["name"]} cssRules {x["rules"]} -> {y["rules"]}')
            else:
                kinds.add(f'{y["name"]} child nodes {x["kinds"][:3]} -> {y["kinds"][:3]}')
        print(r["id"], r["url"][:50], f"{len(diffs)} el diffs;", "; ".join(sorted(kinds)[:3]), "| new errors:", [e[:70] for e in errs][:2])
