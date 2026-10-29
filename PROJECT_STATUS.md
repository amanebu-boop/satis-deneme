# Satış Projesi — Durum ve Devam Dosyası

> Son güncelleme: 2026-10-29  
> Depo: https://github.com/amanebu-boop/satis-deneme  
> Ana dal: `main`  
> İnceleme dalı: `docs/status-audit-2026-10-29`  
> İncelenen ana dal commit'i: `f6089f3bde80ed9429c075f0ca11f759a0651e73`  
> Daha önce paylaşılan canlı adres: https://satis-deneme.onrender.com  
> **Önemli:** Render'da çalışan kodun bu commit ile aynı olduğu doğrulanmadı. Bu oturumda canlıya dağıtım yapılmadı.

Bu dosya ChatGPT ve Codex oturumları arasında proje bağlamını korumak içindir. Kodda veya test çıktısında doğrulanmamış işlevler tamamlanmış sayılmamalıdır.

## 1. Projenin amacı

Firmaları, satış görüşmelerini ve teklif taslaklarını tek bir mobil öncelikli çalışma alanında yönetmek. Teklifler için Word/Excel/PDF belge şablonlarıyla çalışma imkânı sağlamak.

## 2. Mevcut depodan doğrulanabilenler

- Proje Python 3.11+ ve FastAPI kullanıyor; bağımlılıklar `pyproject.toml` içinde tanımlı.
- SQLite varsayılan veritabanı; README'ye göre varsayılan konum `data/sales.db`.
- `app/main.py` tarayıcı akışları için `/api/login`, `/api/logout`, `/api/session`, oturum kontrolü, CSRF kontrolü ve giriş denemesi sınırlaması içeriyor.
- `app/session_store.py` oturum token'ını ham halde değil SHA-256 özetiyle saklıyor ve süre sonu/iptal kontrolü sağlıyor.
- `/api/companies`, `/api/meetings`, `/api/products`, `/api/quotes` ve `/api/templates` gibi uçlar tarayıcı oturumu denetimi kullanıyor.
- `/companies`, `/meetings`, `/products`, `/quotes` gibi eski biçimli uçlar `SALES_API_TOKEN` ortak anahtar kontrolü altında. Bu, kullanıcı bazlı yetkilendirme veya firma/veri izolasyonu değildir.
- Görüşme türü ve konu alanları; görüşme raporunun firma, tarih, tür ve konuyu gösterip not alanını dışarıda bırakması kodda görülüyor. Uçtan uca test yapılmış değil.
- Teklif taslağı saklama ve hesaplama kodu mevcut. Hesaplamada vergi/iskonto oranları kabul ediliyor ve taslak belge çıktısı bir indirim satırı üretiyor.
- `app/template_documents.py` DOCX, XLSX ve doldurulabilir AcroForm PDF için alan keşfi/çıktı üretimi içeriyor. PDF koordinatlarına göre yazma desteklenmiyor.
- `web/index.html` mobil uyumlu bir arayüz ve giriş ekranı içeriyor.
- `app/auth_config.py` Google OIDC yapılandırmasını doğruluyor, fakat kendi açıklamasına göre OIDC uygulaması/rotaları değil, yalnızca yapılandırma kontrolünü sağlıyor.
- README projeyi prototip olarak tanımlıyor; gerçek müşteri verileri veya gerçek ticari teklifler için hazır olduğunu varsaymayın.

**Testlerin çalıştırıldığı veya tüm ekranların uçtan uca doğrulandığı iddia edilmemektedir.**

## 3. Ürün ve tasarım kararları

- Tasarım sade, az renkli; ana renkler lacivert ve beyaz; telefon ekranı öncelikli.
- Giriş ve çalışan işlevler korunmalı; değişiklikler küçük ve hedefli olmalı.
- Ana ekrandaki “Aktif firma”, “Bu hafta görüşme” ve “Taslak teklif” özetlerinin gerçek kayıtlarla çalışması isteniyor.
- Görüşme kaydında tür seçimi: **Telefon görüşmesi** veya **Ziyaret**.
- Görüşme raporu görüşme notlarını/içeriklerini dışarı vermemeli; yalnızca firma, tarih, görüşme şekli ve konu gibi alanları göstermeli.
- Teklif şablonunda satıcı firma: **ERŞEN KALIP VE MAKİNE SANAYİ TİC. LTD.**
- Teklif çıktısında indirim bölümü istenmiyor. Mevcut çıktı kodu bu gereksinimle uyuşmuyor; düzeltme öncesi kabul kriteri netleştirilip test eklenmeli.

Bu gereksinimlerin tamamı uygulanmış veya doğrulanmış değildir.

## 4. İnceleme sonucu: durum sınıflandırması

| Alan | Sonuç | Kanıt / not |
|---|---|---|
| Yerel parola girişi ve oturum altyapısı | Kod mevcut; davranış doğrulanmadı | `app/main.py`, `app/session_store.py`; test çalıştırılmadı |
| Eski API uçlarının erişim kontrolü | Güvenlik incelemesi gerekli | Ortak `SALES_API_TOKEN` anahtarı kullanıcı bazlı erişim değildir |
| Firma CRUD akışı | Kısmen mevcut; uçtan uca doğrulanmadı | `/api/companies` POST/GET/PUT; silme ucu bu incelemede saptanmadı |
| Görüşme kaydı ve raporu | Kod mevcut; uçtan uca doğrulanmadı | `MeetingCreate`, `browser_meeting_report` |
| Teklif taslağı ve hesaplama | Kod mevcut; iş kuralı uyuşmazlığı var | `app/pricing.py`, `app/documents.py` |
| Teklif çıktısında indirim satırı | Gereksinimle uyuşmuyor | `app/documents.py` indirim satırını HTML olarak yazıyor |
| DOCX/XLSX/AcroForm PDF | İşleme altyapısı mevcut; dosya tabanlı test doğrulanmadı | `app/template_documents.py` |
| PDF koordinatlarına göre yazma | Eksik | Kod açıkça desteklenmediğini bildiriyor |
| Google/OIDC | Tamamlanmış değil | `app/auth_config.py` yalnızca yapılandırma doğrulaması yapıyor |
| Gerçek veri izolasyonu / çok kullanıcılı yetki | Tamamlanmış değil | FastAPI açıklaması prototip ve tenant izolasyonunun uygulanmadığını belirtiyor |
| Test paketi | Doğrulanamadı | Depo ağacında `tests/` dizini listelenmiyor; `pytest` çalıştırma ortamı bu oturumda mevcut değil |
| CI | Doğrulanamadı | GitHub Actions runs API'si bu incelemede sıfır workflow run döndürdü |
| Render canlı sürümü/kalıcı disk | Doğrulanamadı | Render yapılandırmasına/dağıtım commit'ine erişim veya doğrulama yok |

## 5. Kanıtlanmış sorunlar ve riskler

1. **Eski rotalar ve ortak API anahtarı:** `app/main.py` middleware'i `/companies`, `/meetings`, `/products`, `/quotes` prefix'lerini API anahtarıyla koruyor. Ancak `/api/...` akışı ayrı browser-session kontrolü yapıyor. Eski rotaları kullanan istemciler belirlenmeden değişiklik yapılmamalı; üretimde kullanıcı bazlı yetkilendirme ve veri izolasyonu mevcut sayılmamalı.
2. **Teklif görünümü gereksinimi:** `app/documents.py` indirim oranı/tutar satırı üretiyor; bu, durum dosyasındaki “indirim bölümü olmasın” kararıyla uyuşmuyor. Hesaplama modeli de iskonto parametresi kabul ediyor; iş kuralı ve çıktı ayrı ayrı ele alınmalı.
3. **Test ve belge referansları:** README kurulum ve güvenlik/yedekleme belgelerine bağlantı veriyor, ancak görülen `main` dosya ağacında `docs/` ve `tests/` dizinleri yer almıyor. İçeriklerin başka dalda/taşınmış olup olmadığı ayrıca kontrol edilmelidir.
4. **Canlı ortam:** Render kalıcı depolama, ortam değişkenleri ve canlı commit eşleşmesi doğrulanmadı. Prototip gerçek müşteri verisiyle kullanılmamalı.

## 6. Bu oturumda yapılanlar

- **Tarih:** 2026-10-29
- **İncelenen dosyalar:** `PROJECT_STATUS.md`, `README.md`, `pyproject.toml`, `.env.example`, `app/main.py`, `app/auth_config.py`, `app/session_store.py`, `app/db.py`, `app/pricing.py`, `app/documents.py`, `app/template_documents.py`, `web/index.html`, `web/manifest.webmanifest`, `web/icon.svg`.
- **Tamamlanan işler:** Yalnızca statik depo incelemesi; kanıtlanmamış işlevler tamamlandı işaretlenmedi.
- **Testler:** `python -m pytest -q` çalıştırılmadı; bu oturumda depo kodu için çalıştırılabilir bir Python checkout/test ortamı yok. Sonuç “başarılı” değildir; “çalıştırılmadı”dır.
- **GitHub Actions:** `GET /repos/amanebu-boop/satis-deneme/actions/runs?per_page=10` yanıtında `total_count: 0`.
- **Dağıtım:** Canlı ortama gönderim yapılmadı; Render'da çalışan commit doğrulanmadı.
- **Dal:** `docs/status-audit-2026-10-29` (inceleme/durum dokümantasyonu için oluşturuldu; `main` değiştirilmedi).
- **Sıradaki tek öncelik:** Python ortamında depo checkout'u sağlayıp test altyapısını ve eski API rotalarının istemci bağımlılıklarını doğrulamak; ardından erişim kontrolü sorununu ayrı ve testli bir PR ile düzeltmek.

## 7. Önerilen sonraki adımlar

1. Depoyu yerel/CI Python 3.11+ ortamında aç; bağımlılıkları `python -m pip install -e ".[test]"` ile kur ve `python -m pytest -q` çalıştır.
2. `tests/` gerçekten yoksa, ilk önce mevcut login, session/CSRF, korumalı rotalar, firma/görüşme/teklif akışları ve şablon işlemleri için regresyon testleri ekle.
3. Eski rotaları hangi istemcilerin kullandığını doğrula. Kullanılmayan eski rotalar kaldırılmalı veya tarayıcı erişimine açılmaları önlenmeli; API istemcisi gerekiyorsa token politikasını ve veri izolasyonunu açıkça tasarla.
4. İndirim bölümünün kaldırılması gereksinimini teklif görünümü/hesaplama davranışına göre kabul testleriyle netleştir.
5. Her değişiklikten sonra hedefli ve tam test paketini çalıştır; gerçek çıktıyı kaydet.
6. Render'da kaynak branch/commit, disk ve ortam değişkenlerini doğrulamadan canlıya dağıtım yapma.

## 8. Her oturum sonunda doldurulacak kısa not

- **İncelenen/değiştirilen dosyalar:**
- **Tamamlanan ve kanıtlanan işler:**
- **Çalıştırılan testler ve sonuçları:**
- **Açık hatalar / riskler:**
- **GitHub dalı ve commit:**
- **Render dağıtım durumu (doğrulandıysa):**
- **Sıradaki tek öncelikli görev:**
