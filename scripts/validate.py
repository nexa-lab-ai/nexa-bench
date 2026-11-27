"""Validate NEXA-Bench contributions. Standard library only.

Usage:
  python scripts/validate.py                        # everything in questions/, chats/, finetune/
  python scripts/validate.py questions/alice.csv    # one or more files

Errors make the exit code 1 (the PR check turns red). Lines starting with "!" are
warnings: they do not block the PR, but fix them before your final submission.
"""
import collections
import csv
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- questions/*.csv
Q_MIN_HUMAN = 50
Q_COLS = ["id", "type", "domain", "category", "difficulty", "lang", "source",
          "question", "answer", "scoring", "tolerance", "notes"]
Q_ENUM = {
    "type": {"text", "image", "video"},
    "difficulty": {"1", "2", "3"},
    "lang": {"tr", "en"},
    "source": {"human", "ai"},
    "scoring": {"exact_match", "multiple_choice", "numeric", "checklist", "rubric"},
}
ID_RE = re.compile(r"^[a-z0-9]+-\d{3}$")


def norm(t):
    return re.sub(r"\W+", " ", t.casefold()).strip()


def check_questions(path, seen):
    errs, warns, cnt = [], [], collections.Counter()
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames != Q_COLS:
            return [f"{path.name}: header must be\n    {','.join(Q_COLS)}\n  found\n    {','.join(r.fieldnames or [])}"], warns, cnt
        prefix = path.stem.split("-")[0].lower()[:3]
        for n, row in enumerate(r, start=2):
            row = {k: (v or "").strip() for k, v in row.items() if k}
            at = f"{path.name}:{n}"
            rid = row["id"]
            if not ID_RE.match(rid):
                errs.append(f"{at}: id '{rid}' must look like 'abc-001' (lowercase, dash, 3 digits)")
            elif not path.stem.startswith("_") and not rid.startswith(prefix):
                warns.append(f"{at}: id '{rid}' should start with '{prefix}' (first 3 letters of the file name)")
            if rid in seen["id"]:
                errs.append(f"{at}: duplicate id '{rid}' (first at {seen['id'][rid]})")
            seen["id"].setdefault(rid, at)
            for k, allowed in Q_ENUM.items():
                if row[k] not in allowed:
                    errs.append(f"{at}: {k}='{row[k]}' is invalid. Allowed: {', '.join(sorted(allowed))}")
            for k in ("domain", "category", "question", "answer"):
                if not row[k]:
                    errs.append(f"{at}: '{k}' cannot be empty")
            s, ans = row["scoring"], row["answer"]
            if s == "numeric":
                if not re.match(r"^\d+([.,]\d+)?%?$", row["tolerance"]):
                    errs.append(f"{at}: numeric scoring needs a tolerance (e.g. 2% or 0.01)")
                if not re.search(r"\d", ans):
                    errs.append(f"{at}: numeric answer contains no number")
            if s == "multiple_choice" and not re.match(r"^[A-Ea-e]$", ans):
                errs.append(f"{at}: multiple_choice answer must be a single letter (A-E)")
            if s == "checklist" and ";" not in ans:
                errs.append(f"{at}: checklist items must be separated by ';' (at least 2)")
            if row["type"] in {"image", "video"} and s not in {"checklist", "rubric"}:
                errs.append(f"{at}: image/video questions are scored with checklist or rubric")
            q = norm(row["question"])
            if q and q in seen["q"]:
                errs.append(f"{at}: same question already exists ({seen['q'][q]})")
            seen["q"].setdefault(q, at)
            cnt[row["source"]] += 1
            cnt["d" + row["difficulty"]] += 1
            cnt["cat:" + row["category"]] += 1
    if not path.stem.startswith("_"):
        if cnt["human"] < Q_MIN_HUMAN:
            warns.append(f"{path.name}: {cnt['human']} human-written questions, at least {Q_MIN_HUMAN} needed")
        if sum(1 for k in cnt if k.startswith("cat:")) < 3:
            warns.append(f"{path.name}: needs at least 3 categories")
        if not all(cnt[d] for d in ("d1", "d2", "d3")):
            warns.append(f"{path.name}: needs questions at all 3 difficulty levels")
    summary = f"{cnt['human']} human, {cnt['ai']} ai, difficulty 1/2/3 = {cnt['d1']}/{cnt['d2']}/{cnt['d3']}"
    return errs, warns, summary


# ---------------------------------------------------------------- chats/*.jsonl
C_MIN_HUMAN, C_MIN_TOTAL, C_MIN_TOOLS, C_MIN_TOOL_RATIO = 30, 280, 3, 0.40
C_KEYS = {"messages", "tools", "source", "review"}
C_SOURCE = {"human", "ai"}
C_REVIEW = {"ok", "fixed", "-"}
C_SPLIT = {"train", "test"}
ROLES = {"system", "user", "assistant", "tool"}
MOJIBAKE = re.compile(r"Ã.|Ä.|Å.|�")
JSON_TYPES = {"string": str, "number": (int, float), "integer": int, "boolean": bool,
              "object": dict, "array": list}


def tool_schemas(tools, at, errs):
    out = {}
    if not isinstance(tools, list):
        errs.append(f"{at}: 'tools' must be a list")
        return out
    for t in tools:
        fn = t.get("function", t) if isinstance(t, dict) else None
        if not isinstance(fn, dict) or not fn.get("name"):
            errs.append(f"{at}: every tool needs a function name")
            continue
        out[fn["name"]] = fn.get("parameters") or {}
    return out


def check_args(args, schema, name, at, errs):
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            errs.append(f"{at}: arguments of '{name}' are not valid JSON")
            return
    if not isinstance(args, dict):
        errs.append(f"{at}: arguments of '{name}' must be an object")
        return
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        if req not in args:
            errs.append(f"{at}: '{name}' is missing required argument '{req}'")
    for k, v in args.items():
        if props and k not in props:
            errs.append(f"{at}: '{name}' has unknown argument '{k}'")
            continue
        typ = JSON_TYPES.get(props.get(k, {}).get("type"))
        if typ and (not isinstance(v, typ) or (isinstance(v, bool) and typ is not bool)):
            errs.append(f"{at}: '{name}.{k}' should be {props[k]['type']}")


def check_chats(path, seen):
    errs, warns, cnt = [], [], collections.Counter()
    tool_names = set()
    with path.open(encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    for n, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        at = f"{path.name}:{n}"
        try:
            chat = json.loads(line)
        except json.JSONDecodeError as e:
            errs.append(f"{at}: invalid JSON ({e.msg})")
            continue
        if not isinstance(chat, dict) or not C_KEYS <= chat.keys():
            errs.append(f"{at}: each line needs keys {', '.join(sorted(C_KEYS))}")
            continue
        src, rev, split = chat["source"], chat["review"], chat.get("split", "train")
        if src not in C_SOURCE:
            errs.append(f"{at}: source='{src}' is invalid. Allowed: human, ai")
        if rev not in C_REVIEW:
            errs.append(f"{at}: review='{rev}' is invalid. Allowed: ok, fixed, - (delete rejected chats)")
        if split not in C_SPLIT:
            errs.append(f"{at}: split='{split}' is invalid. Allowed: train, test")
        schemas = tool_schemas(chat["tools"], at, errs)
        tool_names |= schemas.keys()
        msgs = chat["messages"]
        if not isinstance(msgs, list) or not msgs:
            errs.append(f"{at}: 'messages' must be a non-empty list")
            continue
        has_call = False
        for m in msgs:
            role = m.get("role") if isinstance(m, dict) else None
            if role not in ROLES:
                errs.append(f"{at}: unknown role '{role}'")
                continue
            for call in m.get("tool_calls") or []:
                has_call = True
                fn = call.get("function", {}) if isinstance(call, dict) else {}
                name = fn.get("name")
                if name not in schemas:
                    errs.append(f"{at}: calls undefined tool '{name}'")
                else:
                    check_args(fn.get("arguments", {}), schemas[name], name, at, errs)
            if role == "tool" and m.get("name") and m["name"] not in schemas:
                errs.append(f"{at}: tool result from undefined tool '{m['name']}'")
            if MOJIBAKE.search(json.dumps(m, ensure_ascii=False)):
                errs.append(f"{at}: broken Turkish characters (encoding problem, e.g. 'Ã¼')")
        if msgs[-1].get("role") != "assistant" or not msgs[-1].get("content"):
            warns.append(f"{at}: chat should end with an assistant text reply")
        key = norm(" ".join(str(m.get("content") or "") for m in msgs if m.get("role") == "user"))
        if key and key in seen["chat"]:
            errs.append(f"{at}: duplicate chat (same user turns as {seen['chat'][key]})")
        seen["chat"].setdefault(key, at)
        cnt[src] += 1
        cnt["call"] += has_call
        cnt["review_" + rev] += src == "ai"
        cnt[split] += 1
    total = cnt["human"] + cnt["ai"]
    ratio = cnt["call"] / total if total else 0
    if not path.stem.startswith("_"):
        if cnt["human"] < C_MIN_HUMAN:
            warns.append(f"{path.name}: {cnt['human']} human chats, at least {C_MIN_HUMAN} needed")
        if total < C_MIN_TOTAL:
            warns.append(f"{path.name}: {total} chats in total, at least {C_MIN_TOTAL} needed")
        if len(tool_names) < C_MIN_TOOLS:
            warns.append(f"{path.name}: {len(tool_names)} tools defined, at least {C_MIN_TOOLS} needed")
        if total and ratio < C_MIN_TOOL_RATIO:
            warns.append(f"{path.name}: {ratio:.0%} of chats use a tool, at least {C_MIN_TOOL_RATIO:.0%} needed")
        reviewed = cnt["review_ok"] + cnt["review_fixed"]
        if cnt["ai"] and reviewed < 0.2 * cnt["ai"]:
            warns.append(f"{path.name}: {reviewed}/{cnt['ai']} AI chats reviewed by hand, at least 20% needed")
        if not cnt["test"]:
            warns.append(f"{path.name}: no chats with \"split\": \"test\" (keep ~10% human chats for testing)")
    summary = (f"{cnt['human']} human, {cnt['ai']} ai, {ratio:.0%} tool-call, "
               f"{len(tool_names)} tools, {cnt['test']} test")
    return errs, warns, summary


# ---------------------------------------------------------------- finetune/*.csv
F_COLS = ["date", "base_model", "method", "hf_link", "r", "lora_alpha", "learning_rate", "epochs",
          "max_seq_length", "train_minutes", "gpu", "bench_base", "bench_ft", "format_err_base",
          "format_err_ft", "tool_acc_base", "tool_acc_ft", "arg_acc_ft", "notes"]
F_REQUIRED = ["date", "base_model", "method", "hf_link", "learning_rate", "epochs", "gpu",
              "bench_base", "bench_ft"]
F_NUMERIC = ["r", "lora_alpha", "learning_rate", "epochs", "max_seq_length", "train_minutes",
             "bench_base", "bench_ft", "format_err_base", "format_err_ft", "tool_acc_base",
             "tool_acc_ft", "arg_acc_ft"]
F_METHOD = {"full", "lora", "qlora"}


def check_finetune(path, seen):
    errs, warns = [], []
    rows, families = 0, set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames != F_COLS:
            return [f"{path.name}: header must be\n    {','.join(F_COLS)}\n  found\n    {','.join(r.fieldnames or [])}"], warns, ""
        for n, row in enumerate(r, start=2):
            row = {k: (v or "").strip() for k, v in row.items() if k}
            at = f"{path.name}:{n}"
            rows += 1
            for k in F_REQUIRED:
                if not row[k]:
                    errs.append(f"{at}: '{k}' cannot be empty")
            if row["date"] and not re.match(r"^\d{4}-\d{2}-\d{2}$", row["date"]):
                errs.append(f"{at}: date must be YYYY-MM-DD")
            if row["method"] and row["method"] not in F_METHOD:
                errs.append(f"{at}: method='{row['method']}' is invalid. Allowed: full, lora, qlora")
            if row["method"] in {"lora", "qlora"} and not (row["r"] and row["lora_alpha"]):
                errs.append(f"{at}: lora/qlora runs need r and lora_alpha")
            if row["hf_link"] and not row["hf_link"].startswith("https://huggingface.co/"):
                errs.append(f"{at}: hf_link must start with https://huggingface.co/")
            for k in F_NUMERIC:
                if row[k]:
                    try:
                        float(row[k])
                    except ValueError:
                        errs.append(f"{at}: '{k}'='{row[k]}' must be a number (no % sign)")
            families.add(re.split(r"[-_.\d]", row["base_model"].split("/")[-1].lower())[0])
    if not path.stem.startswith("_") and len(families) < 2:
        warns.append(f"{path.name}: fine-tune at least 2 different model families")
    return errs, warns, f"{rows} runs, {len(families)} families"


# ---------------------------------------------------------------- main
CHECKERS = {"questions": check_questions, "chats": check_chats, "finetune": check_finetune}
PATTERNS = {"questions": "*.csv", "chats": "*.jsonl", "finetune": "*.csv"}


def main():
    if sys.argv[1:]:
        files = [pathlib.Path(a).resolve() for a in sys.argv[1:]]
    else:
        files = [p for d, pat in PATTERNS.items() for p in sorted((ROOT / d).glob(pat))]
    seen = collections.defaultdict(dict)
    all_errs = []
    for f in files:
        kind = f.parent.name
        if kind not in CHECKERS:
            all_errs.append(f"{f.name}: put it in questions/, chats/ or finetune/")
            continue
        errs, warns, summary = CHECKERS[kind](f, seen)
        print(f"{kind + '/' + f.name:<36} {summary}")
        for w in warns:
            print("  ! " + w)
        all_errs += errs
    if all_errs:
        print("\nERRORS:")
        for e in all_errs:
            print("  x " + e)
        sys.exit(1)
    print("\nOK: no format errors.")


if __name__ == "__main__":
    main()
