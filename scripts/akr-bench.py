# /// script
# dependencies = ["openai", "pandas"]
# ///
"""
Automatic evaluator for a custom CSV benchmark.

Usage:
    uv run bench.py benchmark.csv --model qwen2.5:3b
    uv run bench.py benchmark.csv --model gpt-4o \
        --base-url https://api.openai.com/v1 --api-key $OPENAI_API_KEY

Answer formats (strictly enforced):
    sayisal         -> a plain number in base SI units, e.g. 0.4  (no unit, no text)
    coktan_secmeli  -> a single uppercase letter: A, B, C or D
The model must end its reply with one line:  FINAL: <answer>
If the format is invalid, the model is asked ONCE to re-send in the correct
format. If it is still invalid, the question counts as wrong (format_error).

Score: difficulty-weighted accuracy (zorluk 1/2/3 -> weights 1/2/3).
"""
import argparse
import re
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from openai import OpenAI

WEIGHTS = {1: 1, 2: 2, 3: 3}

NUM_RE = re.compile(r"^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$")
MC_RE = re.compile(r"^[ABCD]$")

SYSTEM = {
    "tr": (
        "Soruyu dikkatle çöz. Cevabını EN SONDA, tek bir satırda şu biçimde ver:\n"
        "FINAL: <cevap>\n"
        "Kurallar:\n"
        "- Çoktan seçmeli sorularda <cevap> yalnızca tek bir büyük harf olmalı: A, B, C veya D.\n"
        "- Sayısal sorularda <cevap> yalnızca bir sayı olmalı ve SI temel birimi cinsinden "
        "verilmeli (örn. 400 mV için 0.4, 2 kΩ için 2000). Birim, yüzde işareti, açıklama veya "
        "binlik ayracı yazma; ondalık ayraç olarak nokta kullan. Çok büyük/küçük sayılar için "
        "bilimsel gösterim kullanabilirsin (örn. 4.7e-6).\n"
        "- Soru yüzde (%) istiyorsa cevabı kesir olarak ver (örn. %87.5 için 0.875, %50 için 0.5), "
        "'%' işareti yazma. Soruda SI olmayan bir birim (örn. TL) isteniyorsa o birimde yaz.\n"
        "- FINAL satırında başka hiçbir şey olmasın."
    ),
    "en": (
        "Solve the question carefully. End your reply with a single line in this form:\n"
        "FINAL: <answer>\n"
        "Rules:\n"
        "- For multiple choice, <answer> must be exactly one uppercase letter: A, B, C or D.\n"
        "- For numeric questions, <answer> must be only a number expressed in base SI units "
        "(e.g. 400 mV -> 0.4, 2 kOhm -> 2000). No units, percent signs, words or thousands "
        "separators; use a dot as the decimal separator. Scientific notation is allowed "
        "(e.g. 4.7e-6).\n"
        "- If the question asks for a percentage, give the answer as a fraction "
        "(e.g. 0.875 for 87.5%, 0.5 for 50%), without the % sign. If the question asks for a "
        "quantity in a specific non-SI unit (e.g. TL), answer in the unit the question asks for.\n"
        "- Nothing else may appear on the FINAL line."
    ),
}

RETRY = {
    "tr": "Cevap biçimi geçersiz. Aynı cevabı kurallara uygun olarak yeniden ver. "
          "Yanıtın sadece şu satırdan oluşsun: FINAL: <cevap> "
          "(çoktan seçmeli: tek büyük harf A/B/C/D; sayısal: SI temel biriminde yalnızca sayı).",
    "en": "Invalid answer format. Re-send your answer in the required format. "
          "Reply with only this line: FINAL: <answer> "
          "(multiple choice: one uppercase letter A/B/C/D; numeric: only a number in base SI units).",
}


# ---------- parsing ----------
def clean_reply(text):
    text = text or ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)


def extract_final(text):
    hits = re.findall(r"FINAL\s*:\s*(.+)", clean_reply(text), flags=re.I)
    if not hits:
        return None
    return hits[-1].strip().strip("*`").strip()


def validate(answer, scoring):
    """Return (valid, parsed_value). Strict format check."""
    if answer is None:
        return False, None
    if scoring == "coktan_secmeli":
        return (True, answer) if MC_RE.match(answer) else (False, None)
    # sayisal
    if NUM_RE.match(answer):
        return True, float(answer)
    return False, None


def parse_gold_number(s):
    s = str(s).strip().replace("\u2212", "-").replace(" ", "")
    is_percent = s.endswith("%")
    s = s.rstrip("%")
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    val = float(s)
    return val / 100 if is_percent else val  # percentages are stored as fractions


def parse_tolerance(s):
    if pd.isna(s) or str(s).strip() == "":
        return 0.0
    return float(str(s).replace("%", "").replace(",", ".").strip())


def is_correct(row, pred, scoring):
    gold_raw = row["dogru_cevap"]
    if scoring == "coktan_secmeli":
        return pred == str(gold_raw).strip().upper()[:1]
    gold = parse_gold_number(gold_raw)
    tol = parse_tolerance(row.get("tolerans"))
    if gold == 0:
        return abs(pred) <= 1e-12
    err_pct = abs(pred - gold) / abs(gold) * 100
    return err_pct <= tol


# ---------- progress ----------

class Progress:
    """Thread-safe progress bar showing percentage and the question id(s) in flight."""

    def __init__(self, total):
        self.total, self.done, self.active = total, 0, []
        self.lock = threading.Lock()
        self.draw()

    def start(self, qid):
        with self.lock:
            self.active.append(str(qid))
            self.draw()

    def finish(self, qid):
        with self.lock:
            self.active.remove(str(qid))
            self.done += 1
            self.draw()

    def draw(self):
        width = shutil.get_terminal_size((100, 20)).columns
        pct = self.done / self.total
        bar_len = 30
        filled = int(bar_len * pct)
        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
        now = ", ".join(self.active) if self.active else "-"
        line = f"[{bar}] {pct * 100:5.1f}% ({self.done}/{self.total}) asking: {now}"
        sys.stdout.write("\r\033[K" + line[: width - 1])
        sys.stdout.flush()

    def close(self):
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", default="http://localhost:11434/v1")  # Ollama default
    ap.add_argument("--api-key", default="none")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=4096)
    a = ap.parse_args()

    df = pd.read_csv(a.csv, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    # accept both "doğru_cevap" and "dogru_cevap"
    df = df.rename(columns={"doğru_cevap": "dogru_cevap"})
    # accept the English column names used in questions/ (see README)
    df = df.rename(columns={"question": "soru", "answer": "dogru_cevap", "scoring": "puanlama",
                            "tolerance": "tolerans", "difficulty": "zorluk", "lang": "dil",
                            "domain": "alan", "category": "kategori"})
    df["puanlama"] = df["puanlama"].replace({"multiple_choice": "coktan_secmeli", "numeric": "sayisal"})

    client = OpenAI(base_url=a.base_url, api_key=a.api_key)

    def ask(messages):
        r = client.chat.completions.create(
            model=a.model, temperature=0, max_tokens=a.max_tokens, messages=messages
        )
        return r.choices[0].message.content or ""

    def run(row):
        progress.start(row["id"])
        try:
            return run_one(row)
        finally:
            progress.finish(row["id"])

    def run_one(row):
        lang = row["dil"] if row["dil"] in SYSTEM else "en"
        scoring = str(row["puanlama"]).strip()
        messages = [
            {"role": "system", "content": SYSTEM[lang]},
            {"role": "user", "content": str(row["soru"])},
        ]
        status, pred, correct, reply = "", None, False, ""
        try:
            reply = ask(messages)
            valid, pred = validate(extract_final(reply), scoring)
            if not valid:  # one retry with a format reminder
                messages += [
                    {"role": "assistant", "content": clean_reply(reply)[-2000:] or "(empty)"},
                    {"role": "user", "content": RETRY[lang]},
                ]
                reply2 = ask(messages)
                valid, pred = validate(extract_final(reply2), scoring)
                reply += "\n\n--- RETRY ---\n" + reply2
                status = "retried" if valid else "format_error"
            if valid:
                correct = bool(is_correct(row, pred, scoring))
        except Exception as e:
            status, reply = "api_error", f"ERROR: {e}"

        zorluk = int(row["zorluk"])
        return {
            "id": row["id"], "alan": row.get("alan"), "kategori": row.get("kategori", row.get("kategory")),
            "zorluk": zorluk, "dil": row["dil"], "puanlama": scoring,
            "gold": row["dogru_cevap"], "pred": pred, "correct": correct,
            "weight": WEIGHTS.get(zorluk, 1), "status": status, "reply": reply,
        }

    progress = Progress(len(df))
    with ThreadPoolExecutor(a.workers) as ex:
        results = list(ex.map(run, [r for _, r in df.iterrows()]))
    progress.close()

    res = pd.DataFrame(results)
    res["points"] = res.weight * res.correct
    weighted = res.points.sum() / res.weight.sum() * 100
    raw = res.correct.mean() * 100

    print(f"\nModel: {a.model}")
    print(f"Weighted accuracy: {weighted:.2f}%  ({res.points.sum():.0f}/{res.weight.sum():.0f} points)")
    print(f"Unweighted accuracy: {raw:.2f}%  ({res.correct.sum()}/{len(res)} questions)")
    print(f"Format errors: {(res.status == 'format_error').sum()}  "
          f"Retried OK: {(res.status == 'retried').sum()}  "
          f"API errors: {(res.status == 'api_error').sum()}")
    print("\nBy difficulty (zorluk):")
    print((res.groupby("zorluk").correct.agg(["mean", "count"]) * [100, 1]).round(1)
          .rename(columns={"mean": "acc_%"}))
    missed = res[~res.correct]
    if len(missed):
        print("\nIncorrect / invalid ids: " + ", ".join(
            f"{r.id}" + (f" ({r.status})" if r.status in ("format_error", "api_error") else "")
            for r in missed.itertuples()))


if __name__ == "__main__":
    main()
