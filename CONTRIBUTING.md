# Nasıl katkı verilir (PR akışı)

Organizasyonun üyesisin, fork gerekmez: repoyu klonla, kendi branch'inde çalış, PR aç.

## 1. Bir kez: klonla

```bash
git clone https://github.com/nexa-lab-ai/nexa-bench.git
cd nexa-bench
```

## 2. Her PR için: branch aç

```bash
git switch main
git pull                       # başkalarının merge edilen işini al
git switch -c sedat/ozet-ilk-10   # <adin>/<ne-ekliyorsun>
```

## 3. Dosyanı düzenle, kontrol et

`sorular/_ornek.csv`'nin başlık satırını kopyala, `sorular/<github-kullanici-adin>.csv` oluştur.

```bash
python scripts/dogrula.py sorular/foqunty.csv
```

`✓ Biçim hatası yok` görmeden push etme. `!` ile başlayan satırlar uyarıdır, son PR'a kadar düzelmeli.

## 4. Küçük commit'ler at

```bash
git add sorular/foqunty.csv
git commit -m "Add 10 Turkish summary questions on sports news"
git push -u origin sedat/ozet-ilk-10
```

Commit mesajı ne eklediğini söylesin. `update`, `fix`, `asdf` olmaz.

## 5. PR aç

GitHub'da çıkan **Compare & pull request** butonuna bas. Şablondaki kontrol listesini doldur.
İlk PR'ı **Draft** olarak açabilirsin: erken geri bildirim almak için.

## 6. Review

- Sana atanan arkadaşın PR'ına bak: en az 5 soruyu kendin çöz, cevap anahtarıyla karşılaştır.
- Yorumu satıra bırak (**Files changed** → satır numarasının yanındaki **+**). Somut ol: "Bu sorunun iki doğru cevabı var: …".
- Sana gelen yorumu aynı branch'e yeni commit atarak düzelt, sonra **Resolve conversation**.
- Arkadaşın onaylar (**Approve**), mentor merge eder. Kendi PR'ını kendin merge etme.

## 7. Çakışma (conflict) çıkarsa

```bash
git switch main && git pull
git switch sedat/ozet-ilk-10
git merge main
# dosyayı düzelt, sonra:
git add . && git commit && git push
```

Herkes kendi dosyasında çalıştığı için çakışma nadirdir.
