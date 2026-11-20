"""NEXA-Bench soru dosyalarını doğrular. Sadece standart kütüphane.

Kullanım:
  python scripts/dogrula.py                 # tüm sorular/*.csv
  python scripts/dogrula.py sorular/x.csv   # tek dosya
Hata varsa çıkış kodu 1 olur; GitHub Actions PR'ı kırmızı gösterir.
"""
import csv, re, sys, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIN_INSAN = 50
COLS = ["id", "tur", "alan", "kategori", "zorluk", "dil", "kaynak", "soru", "dogru_cevap", "puanlama", "tolerans", "not"]
ENUM = {
    "tur": {"metin", "gorsel", "video"},
    "zorluk": {"1", "2", "3"},
    "dil": {"tr", "en"},
    "kaynak": {"insan", "ai"},
    "puanlama": {"tam_eslesme", "coktan_secmeli", "sayisal", "kontrol_listesi", "rubrik"},
}
ID_RE = re.compile(r"^[a-z0-9]+-\d{3}$")


def norm(t):
    return re.sub(r"\W+", " ", t.casefold()).strip()


def check(path, seen_ids, seen_q):
    errs, warns = [], []
    stem = path.stem
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames != COLS:
            return [f"{path.name}: başlık satırı şu olmalı:\n    {','.join(COLS)}\n  bulunan:\n    {','.join(r.fieldnames or [])}"], warns, collections.Counter()
        cnt = collections.Counter()
        for n, row in enumerate(r, start=2):
            where = f"{path.name}:{n}"
            rid = (row["id"] or "").strip()
            if not ID_RE.match(rid):
                errs.append(f"{where}: id '{rid}' biçimi 'kisaltma-001' olmalı (küçük harf, tire, 3 hane)")
            elif not stem.startswith("_") and not rid.startswith(stem.split("-")[0].lower()[:3]):
                warns.append(f"{where}: id '{rid}' dosya adıyla aynı önekle başlamıyor")
            if rid in seen_ids:
                errs.append(f"{where}: id '{rid}' tekrar ediyor (ilk: {seen_ids[rid]})")
            seen_ids.setdefault(rid, where)
            for k, allowed in ENUM.items():
                v = (row[k] or "").strip()
                if v not in allowed:
                    errs.append(f"{where}: {k}='{v}' geçersiz. İzin verilen: {', '.join(sorted(allowed))}")
            for k in ("alan", "kategori", "soru", "dogru_cevap"):
                if not (row[k] or "").strip():
                    errs.append(f"{where}: '{k}' boş olamaz")
            p, tol = (row["puanlama"] or "").strip(), (row["tolerans"] or "").strip()
            if p == "sayisal":
                if not re.match(r"^\d+([.,]\d+)?%?$", tol):
                    errs.append(f"{where}: sayisal puanlamada tolerans gerekli (ör. 2% ya da 0.01)")
                if not re.search(r"\d", row["dogru_cevap"] or ""):
                    errs.append(f"{where}: sayisal sorunun doğru cevabında sayı yok")
            if p == "coktan_secmeli" and not re.match(r"^[A-Ea-e]$", (row["dogru_cevap"] or "").strip()):
                errs.append(f"{where}: coktan_secmeli cevabı tek harf olmalı (A–E)")
            if p == "kontrol_listesi" and ";" not in (row["dogru_cevap"] or ""):
                errs.append(f"{where}: kontrol_listesi maddeleri ';' ile ayrılmalı (en az 2 madde)")
            if (row["tur"] or "") in {"gorsel", "video"} and p not in {"kontrol_listesi", "rubrik"}:
                errs.append(f"{where}: görsel/video sorusu kontrol_listesi ya da rubrik ile puanlanır")
            q = norm(row["soru"] or "")
            if q and q in seen_q:
                errs.append(f"{where}: aynı soru zaten var ({seen_q[q]})")
            seen_q.setdefault(q, where)
            cnt[(row["kaynak"] or "").strip()] += 1
            cnt["zorluk" + (row["zorluk"] or "").strip()] += 1
            cnt["kat:" + (row["kategori"] or "").strip()] += 1
    if not stem.startswith("_"):
        if cnt["insan"] < MIN_INSAN:
            warns.append(f"{path.name}: {cnt['insan']} insan sorusu var, teslim için en az {MIN_INSAN} gerekli")
        if len([k for k in cnt if k.startswith("kat:")]) < 3:
            warns.append(f"{path.name}: en az 3 kategori olmalı")
        if len([k for k in ("zorluk1", "zorluk2", "zorluk3") if cnt[k]]) < 3:
            warns.append(f"{path.name}: 3 zorluk seviyesinin hepsinden soru olmalı")
    return errs, warns, cnt


def main():
    files = [pathlib.Path(a) for a in sys.argv[1:]] or sorted((ROOT / "sorular").glob("*.csv"))
    seen_ids, seen_q, all_errs = {}, {}, []
    print(f"{'dosya':<28}{'insan':>7}{'ai':>5}{'z1':>5}{'z2':>5}{'z3':>5}")
    for f in files:
        errs, warns, c = check(f, seen_ids, seen_q)
        print(f"{f.name:<28}{c['insan']:>7}{c['ai']:>5}{c['zorluk1']:>5}{c['zorluk2']:>5}{c['zorluk3']:>5}")
        for w in warns:
            print("  ! " + w)
        all_errs += errs
    if all_errs:
        print("\nHATALAR:")
        for e in all_errs:
            print("  ✕ " + e)
        sys.exit(1)
    print("\n✓ Biçim hatası yok.")


if __name__ == "__main__":
    main()
