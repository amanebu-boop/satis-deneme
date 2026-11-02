# Satış Projesi — Durum ve Devam Dosyası

> Son güncelleme: 2026-11-02  
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
- **Kesin iş kuralı: Teklifte indirim bölümü hiçbir yerde olmayacak.** İndirim oranı/tutarı teklif arayüzünde, API istek/yanıtlarında, hesaplama modelinde, veritabanı alanlarında ve üretilen belgelerde yer almamalı. Vergi/KDV ayrı bir hesaplama olarak ele alınmalı. Mevcut `QuoteRequest`, `calculate_quote`, teklif tablosu şeması ve `app/documents.py` çıktısı bu kurala göre birlikte düzenlenmeli; veri tabanı geçişi gerekiyorsa mevcut kayıtlar korunarak yapılmalı ve regresyon testleri eklenmeli.

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
2. **Teklif iş kuralı ihlali:** İndirim hiçbir yerde olmayacak. `app/documents.py` indirim oranı/tutar satırı üretiyor; `QuoteRequest` ve `app/pricing.py` iskonto oranını kabul ediyor; veritabanında `discount_rate` ve `discount_amount` alanları bulunuyor. Yalnızca HTML satırını kaldırmak yeterli değildir: API modeli, hesaplama, kalıcılık ve çıktı birlikte düzeltilmeli; mevcut kayıtları kaybetmeyecek bir geçiş ve testler hazırlanmalı.
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
4. İndirim bölümünü tüm teklif akışından kaldır: API şeması, hesaplama, veritabanı, arayüz ve çıktı. Kabul testleri indirim alanlarının yokluğunu ve indirim olmadan doğru toplamı doğrulamalı.
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


## 9. Hostinger yayın mimarisi ve uygulama hazırlığı (2026-11-02)

**Kullanıcı tarafından onaylanan hedef:** Yayın sağlayıcısı tamamen Hostinger; uygulama Hostinger Linux VPS; veritabanı PostgreSQL; belgeler kalıcı depolama; günlük yedekleme. Mevcut Render servisi geçiş ve kabul testleri tamamlanana kadar geri dönüş noktası olarak korunur.

### Geliştirme dalında oluşturulan altyapı
- `infra/hostinger-migration-prep` dalında PostgreSQL bağlantısı için SQLAlchemy 2 + psycopg uyumluluk katmanı eklendi. SQLite yerel geliştirme varsayılanı olarak korundu.
- Alembic yapılandırması, başlangıç şema migration köprüsü ve uygulama başlangıcında migration çalıştırma eklendi. İlk migration mevcut idempotent şema kurulumunu çağırır; sonraki şema değişiklikleri gerçek Alembic `op` migration'ları olarak yazılmalıdır.
- Yerel dosya sistemi ve S3 uyumlu RustFS için depolama katmanı eklendi. Şablon yükleme/listeleme ve üretilen dosyaların S3'e yazılması uyarlandı.
- Dockerfile: Python 3.11, LibreOffice, PostgreSQL istemci araçları, root olmayan uygulama kullanıcısı.
- Docker Compose: FastAPI, PostgreSQL 16, RustFS ve Nginx. Nginx test portu yalnızca `127.0.0.1:8080` adresine bağlıdır; HTTPS/public port açılmadı.
- Sağlık kontrolü veritabanı ve depolama bağımlılıklarını doğrular.
- Günlük PostgreSQL + RustFS yedekleme betikleri, AES-256-GCM/PBKDF2 tabanlı şifreleme, 14 günlük yerel saklama ve kontrollü geri yükleme betiği eklendi.
- SQLite → PostgreSQL taşıma aracı, SQLite Backup API ile tutarlı geçici kaynak kopyası alır; şema yükseltmelerini yalnızca kopyada çalıştırır ve kaynak dosyayı değiştirmez. Taşıma varsayılan olarak dry-run'dır.
- Günlük 02.00 cron şablonu eklendi. Hostinger VPS panelindeki otomatik snapshot yedeği ayrıca etkinleştirilmeli ve doğrulanmalıdır.
- GitHub Actions: SQLite regresyonu, PostgreSQL smoke testi, Python derleme, shell syntax ve Docker Compose yapılandırma doğrulaması.

### Son doğrulama kaydı
- GitHub Actions son başarılı koşu: 2 Kasım 2026, commit `e2bdf8574c7e0fba0ee80f3fb5e8bcada9d6b2a1`, workflow run `41412761295`. SQLite: **29 passed, 3 skipped, 1 warning**; PostgreSQL: **6 passed**.
- Aynı koşuda Python compileall, backup/restore shell syntax, Docker Compose config ve Docker image build başarılı.
- Son migration iyileştirmesi (SQLite kaynak DB'yi değiştirmeden geçici kopyada schema upgrade) bu koşuda doğrulandı.
- RustFS gerçek servis uçtan uca testi, tüm PostgreSQL iş akışı regresyonu ve günlük backup/restore tatbikatı henüz yapılmadı.
- Hostinger satın alma/VPS kurulumu, DNS, canlı değişiklik, Render değişikliği ve gerçek müşteri verisi taşıma yapılmadı.

### Canlı geçişi engelleyen açık işler
1. [x] Son CI yeşil: SQLite 29 passed / 3 skipped; PostgreSQL 6 passed; Docker build, Compose config, compileall ve shell syntax başarılı.
2. [ ] Docker Compose servislerinin birlikte çalıştırılması ve gerçek servis health kontrolü (staging gerekli).
3. [ ] PostgreSQL üzerinde firma, görüşme, ürün, teklif numarası, teklif/Excel/PDF ve KDV akışlarının tam regresyonu.
4. [ ] RustFS gerçek S3 API put/get/head/list/delete ve yeniden başlatma kalıcılığı uçtan uca testi.
5. [ ] Şifreli PostgreSQL + nesne yedeği üretimi ve temiz DB/bucket'a tam restore tatbikatı.
6. [ ] Gerçek kullanıcı girişi/OIDC, rol ve erişim kontrolleri; HTTPS/TLS, firewall ve güvenlik taraması.
7. [ ] Yük, disk doluluğu, servis kesintisi, yeniden başlatma ve rollback testleri.
8. [ ] SQLite → PostgreSQL ve yerel dosya → RustFS taşıma provası, checksum ve kayıt mutabakatı.
9. [ ] Hostinger satın alma, VPS staging, gerçek veri taşıma ve canlı DNS için ayrı onay kapıları.

**İşlem sınırı:** Bütün geliştirme bu dalda kalır. `main`, Render, Hostinger hesabı, DNS ve gerçek veri değiştirilmez. Satın alma, sunucu kurulumu, gerçek veri taşıma ve canlı geçiş için ayrıca açık onay gerekir.

**Draft PR:** https://github.com/amanebu-boop/satis-deneme/pull/33 (main'e birleştirilmedi).\n\n**Sıradaki öncelik:** Son SQLite kaynak-kopya migration değişikliğinin CI sonucunu doğrula; ardından Docker/RustFS staging ve güvenlik/backup kabul testlerini tamamla.


### Son test kaydı — 2026-11-02
- Dal: `infra/hostinger-migration-prep`
- Commit: `e2bdf8574c7e0fba0ee80f3fb5e8bcada9d6b2a1`
- Workflow run: `41412761295` — başarılı.
- SQLite: 29 passed, 3 skipped, 1 warning.
- PostgreSQL: 6 passed.
- Docker image build, Compose config, Python compileall ve backup/restore shell syntax: başarılı.
- PR #33 açık, draft ve merge edilmedi. `main`, Render, DNS, Hostinger hesabı ve gerçek müşteri verisi değiştirilmedi.
- Staging gerektiren RustFS E2E, tam iş akışı, restore drill, TLS/auth, yük ve rollback testleri henüz yapılmadı.


## Agent / LLM Wiki integration status
- Safe deterministic agent foundation, Sales Assistant, LLM Wiki, meeting capture and AI usage modules are included from the verified agent feature branch.
- PostgreSQL compatibility adapter is integrated for the shared business database. Agent registry, runs, approvals, audit and Wiki metadata use the same configured database connection.
- LLM Wiki FTS5 is SQLite-specific; PostgreSQL uses the lexical fallback until a PostgreSQL-native full-text implementation is separately tested.
- Hostinger CI must include PostgreSQL tests for agent initialization, `INSERT OR IGNORE` translation, AI usage identity columns and Wiki fallback before main readiness.
- Live migration, DNS cutover and VPS activation remain separate approvals.
