# NEXA-Bench

NEXA Fellowship katılımcılarının birlikte yazdığı, Türkçe ağırlıklı, çok alanlı benchmark.
Her katılımcı kendi alanından en az **50 insan yazımı soru** ekler; sorular PR ile gelir, bir arkadaş ve mentor onaylar.

| Alan | Katkıcı | Tür |
|---|---|---|
| Türkçe özet ve halüsinasyon | Sedat | metin |
| Görsel üretimde sayma ve sahne sadakati | Tuana | görsel |
| Video modellerinde karakter tutarlılığı | Kaan | video |
| Elektrik-elektronik hesapları | Mustafa | metin |
| Ders notlarından sınav | Kutay | metin |

## Yapı

```
sorular/
  _ornek.csv          biçim örneği, sayılmaz
  <github-kullanici-adi>.csv   herkesin kendi dosyası (çakışma olmasın diye)
scripts/dogrula.py    biçim kontrolü, her PR'da otomatik çalışır
```

## Sütunlar

| Sütun | Değerler |
|---|---|
| `id` | `kisaltma-001` (küçük harf, dosya adının ilk 3 harfiyle başlar) |
| `tur` | `metin` · `gorsel` · `video` |
| `alan`, `kategori` | serbest metin; dosya başına en az 3 kategori |
| `zorluk` | `1` tek adım · `2` birkaç adım · `3` uzman |
| `dil` | `tr` · `en` |
| `kaynak` | `insan` · `ai` (AI'a ürettirdiysen mutlaka `ai`) |
| `soru`, `dogru_cevap` | cevap modelleri denemeden önce yazılır |
| `puanlama` | `tam_eslesme` · `coktan_secmeli` · `sayisal` · `kontrol_listesi` · `rubrik` |
| `tolerans` | `sayisal` için zorunlu: `2%` ya da `0.01` |
| `not` | kaynak, çözüm notu, uyarı |

Görsel/video sorularında `soru` prompt'tur, `dogru_cevap` ise `;` ile ayrılmış kontrol maddeleridir.

## Kurallar

1. Açık set burada, gizli set senin reposunda. Kendi 100+ sorundan en az 50'sini buraya koy, kalanı yayınlama (kontaminasyon).
2. İnternetten kopya soru yok. Uyarladıysan `not` sütununa kaynağı yaz.
3. Bir soru tek ve net bir doğru cevaba sahip olmalı. Tartışmalıysa `rubrik` kullan.
4. Herkes yalnızca kendi dosyasını değiştirir.

Katkı adımları: [CONTRIBUTING.md](CONTRIBUTING.md)

## Lisans

MIT. Ayrıntı: [LICENSE](LICENSE)
