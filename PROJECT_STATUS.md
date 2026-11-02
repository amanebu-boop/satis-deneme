# Satış Projesi — Durum ve Devam Dosyası

> Son güncelleme: 2026-11-02  
> Depo: https://github.com/amanebu-boop/satis-deneme  
> Ana dal: `main`  
> Daha önce paylaşılan canlı adres: https://satis-deneme.onrender.com  
> **Önemli:** Canlı Render sürümünün GitHub `main` ile aynı kodu çalıştırdığı bu dosya oluşturulurken doğrulanmadı. Değişiklikten önce depo ve dağıtım durumu kontrol edilmelidir.

Bu dosya ChatGPT ve Codex oturumları arasında proje bağlamını korumak içindir. Kodda doğrulanmamış işlevler tamamlanmış olarak işaretlenmemelidir.

## 1. Projenin amacı

Firmaları, satış görüşmelerini ve teklif taslaklarını tek bir mobil öncelikli çalışma alanında yönetmek. Teklifler için Word/Excel/PDF belge şablonlarıyla çalışma imkânı sağlamak.

## 2. Mevcut depodan doğrulanabilenler

- Proje Python 3.11+ ve FastAPI kullanıyor.
- Bağımlılıklar `pyproject.toml` içinde tanımlı; test komutu `python -m pytest -q`.
- SQLite varsayılan veritabanı olarak kullanılıyor; README'ye göre varsayılan konum `data/sales.db`.
- README; firma, görüşme ve teklif akışlarını prototip olarak tanımlıyor.
- Word/Excel şablonları ve doldurulabilir PDF belgeleri için belge işleme altyapısı bulunuyor.
- `app/main.py` içinde `/companies`, `/meetings`, `/products` ve `/quotes` yolları için `SALES_API_TOKEN` ortam değişkenine bağlı API anahtarı kontrolü mevcut.
- Kod açıklaması, kullanıcı bazlı yetkilendirme, kiracı/veri ayrımı ve üretim ortamı güvenlik sertleştirmesinin tamamlanmadığını belirtiyor.
- Depodaki `web/index.html` lacivert-beyaz, sade ve mobil uyumlu bir arayüz yaklaşımı kullanıyor.
- README, ürün kataloğu ve bazı özet ekranlarında örnek veri olabileceğini; otomatik belge alan eşleştirme ve PDF koordinatlarına göre yazma gibi bazı işlevlerin tamamlanmadığını belirtiyor.

**Bu liste, tüm testlerin çalıştırıldığı veya her ekranın uçtan uca doğrulandığı anlamına gelmez.**

## 3. Ürün ve tasarım kararları

Önceki proje görüşmelerinde belirtilen gereksinimler:

- Tasarım sade, az renkli; ana renkler lacivert ve beyaz.
- Öncelik telefon ekranı.
- Giriş sistemi ve mevcut çalışan işlevler korunmalı; değişiklikler mevcut yapıyı bozmamalı.
- Ana ekrandaki “Aktif firma”, “Bu hafta görüşme” ve “Taslak teklif” özetlerinin gerçek verilerle çalışması isteniyor.
- Görüşme kaydında görüşme türü seçilebilmeli: **Telefon görüşmesi** veya **Ziyaret**.
- Görüşme raporunda görüşme içerikleri gösterilmemeli; yalnızca görüşme kayıtları ve görüşme konusu raporlanmalı.
- Teklif alanı geliştirilecek.
- Teklif şablonu için bildirilen satıcı firma: **ERŞEN KALIP VE MAKİNE SANAYİ TİC. LTD.**
- Teklif şablonunda indirim bölümü istenmiyor.

Bu gereksinimler konuşma geçmişinden alınmıştır; her birinin güncel kodda uygulandığı henüz doğrulanmış değildir.

## 4. Kesinlikle doğrulanması gerekenler

Aşağıdaki maddeler, kod ve test incelemesi yapılmadan “tamamlandı” kabul edilmemeli:

- [ ] Giriş ve oturum akışı; yetkisiz erişim testleri.
- [ ] Firma oluşturma, listeleme, düzenleme ve silme işlemleri.
- [ ] Görüşme oluşturma; telefon/ziyaret türü ve görüşme konusu kaydı.
- [ ] Görüşme raporunun istenen kapsamı göstermesi ve görüşme içeriğini dışarı sızdırmaması.
- [ ] Ana ekran sayaçlarının örnek veri yerine gerçek kayıtları kullanması.
- [ ] Teklif oluşturma, taslak kaydetme, düzenleme ve firma ile ilişkilendirme.
- [ ] Teklif toplamlarının ve ürün satırı hesaplamalarının doğru olması.
- [ ] Teklif çıktısında indirim bölümünün bulunmaması.
- [ ] Word/Excel/PDF şablonlarının yüklenmesi ve çıktıların açılabilir/doğru olması.
- [ ] Telefon ekranında menüler, formlar ve tabloların kullanılabilirliği.
- [ ] Veritabanı ve yüklenen belgeler için yedekleme/geri yükleme planı.
- [ ] Render yapılandırması, kalıcı disk/veritabanı durumu, ortam değişkenleri ve canlı sürümün commit'i.
- [ ] Gerçek müşteri verisi kullanılmadan önce güvenlik ve erişim kontrolü incelemesi.

## 5. Bilinen riskler ve sınırlamalar

- README mevcut projeyi prototip olarak tanımlıyor; gerçek müşteri verileri veya gerçek ticari teklifler için hazır olduğunu varsaymayın.
- README yerel parola girişi olduğunu ve Google/OIDC girişinin olmadığını söylüyor. Canlı uygulamadaki giriş akışı ayrıca kontrol edilmelidir.
- API anahtarı kontrolü, tek başına kullanıcı bazlı yetkilendirme veya firma/veri izolasyonu anlamına gelmez.
- Yerel SQLite dosyasının Render ortamında kalıcı olup olmadığı ve dağıtımlar arasında korunup korunmadığı doğrulanmalıdır.
- Canlı ortamda sırlar kaynak koda yazılmamalı; Render ortam değişkenlerinde tutulmalıdır.
- Testler çalıştırılmadan, test çıktısı görülmeden “testler başarılı” denmemelidir.
- Ana dala veya canlı ortama gönderimden önce değişiklikler gözden geçirilmeli ve mümkünse ayrı dal/PR üzerinden doğrulanmalıdır.

## 6. Önerilen çalışma sırası

1. **Başlangıç incelemesi:** `main` dalındaki dosya ağacını, README'yi, yapılandırmayı ve mevcut testleri incele.
2. **Test tabanı:** `python -m pytest -q` çalıştır; başarısızlıkları ve mevcut kapsamı raporla.
3. **İşlev kontrol listesi:** Yukarıdaki maddeleri kod ve test kanıtlarıyla “Çalışıyor / Eksik / Hatalı / Doğrulanamadı” olarak sınıflandır.
4. **Öncelikli düzeltmeler:** Önce veri kaybı, yetkisiz erişim ve temel kayıt akışlarını; sonra raporları, teklifleri ve görsel ayrıntıları ele al.
5. **Küçük değişiklikler:** Her görevde amaç, değişen dosyalar, testler ve sonuçları açıkça belirt.
6. **Dağıtım kontrolü:** GitHub commit'i ile Render'da çalışan sürümü eşleştir; dağıtım ve canlı test sonuçlarını kaydet.
7. **Bu dosyayı güncelle:** Yalnızca kod veya test kanıtı olan tamamlanmış işleri işaretle; tarih ve sıradaki işi güncelle.

## 7. ChatGPT ve Codex için çalışma talimatı

Bu dosyayı ve ilgili kaynak kodu okumadan projede değişiklik yapmaya başlama.

Her görevde:

1. Önce mevcut davranışı ve ilgili dosyaları incele.
2. İstenen sonucu ve kabul kriterlerini yaz.
3. İlgisiz dosyalara dokunma; mevcut giriş ve çalışan işlevleri koru.
4. Güvenlik açıklarını, sırları veya müşteri verilerini loglara yazma.
5. Uygun testleri ekle/çalıştır ve gerçek çıktıyı bildir.
6. Yapılmayan testleri açıkça belirt; tahminle başarı iddia etme.
7. Canlı ortama gönderim öncesinde değişiklik özetini ve riskleri bildir.
8. İş bitince bu dosyanın “doğrulanabilenler”, kontrol listesi ve sıradaki iş bölümlerini güncelle.

## 8. Her oturum sonunda doldurulacak kısa not

- **Tarih:**
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
- Günlük 02.00 cron şablonu eklendi. Hostinger VPS panelindeki otomatik snapshot yedeği ayrıca etkinleştirilmeli ve doğrulanmalıdır.
- GitHub Actions: SQLite regresyonu, PostgreSQL smoke testi, Python derleme, shell syntax ve Docker Compose yapılandırma doğrulaması.

### Son doğrulama kaydı
- GitHub Actions başarılı koşu: commit `040dca21f2e38ab48b35a00e6b35eacabcc2b9f8` üzerinde SQLite: **28 passed, 2 skipped, 1 warning**; PostgreSQL: **5 passed**. Python compileall, backup/restore shell syntax ve Docker Compose config kontrolleri de geçti.
- Bu koşu AES-GCM yedekleme testlerini ve Compose YAML doğrulamasını içerir; Docker image build adımı daha sonra eklendi. Ardından uygulama healthcheck/restore guard ve CI image-build adımı değişti; bunların son CI sonucu ayrıca bekleniyor.
- RustFS gerçek uçtan uca testi ve Docker image build sonucu henüz doğrulanmış değil.
- Hostinger satın alma/VPS kurulumu, DNS, canlı değişiklik, Render değişikliği ve gerçek müşteri verisi taşıma yapılmadı.

### Canlı geçişi engelleyen açık işler
1. Son CI koşusunun yeşil olması; gerekirse düzeltme.
2. Docker imajının gerçek build ve Compose servislerinin yerel/staging ortamda çalıştırılması.
3. PostgreSQL üzerinde firma, görüşme, ürün, teklif numarası, teklif/Excel/PDF ve KDV akışlarının tam regresyonu.
4. RustFS yükleme, listeleme, indirme, çıktı üretme ve yeniden başlatma kalıcılığı için uçtan uca test.
5. Yedek üretimi ve boş test veritabanı/bucket'a geri yükleme tatbikatı.
6. Gerçek kullanıcı girişi/OIDC, rol ve erişim kontrolleri; HTTPS/TLS ve firewall.
7. SQLite → PostgreSQL ve yerel dosya → RustFS taşıma provası, checksum ve kayıt mutabakatı.
8. Hostinger satın alma, VPS staging, gerçek veri taşıma ve canlı DNS için ayrı onay kapıları.

**İşlem sınırı:** Bütün geliştirme bu dalda kalır. `main`, Render, Hostinger hesabı, DNS ve gerçek veri değiştirilmez. Satın alma, sunucu kurulumu, gerçek veri taşıma ve canlı geçiş için ayrıca açık onay gerekir.

**Sıradaki öncelik:** Son CI koşusunu incele; tüm kontroller geçtikten sonra draft PR hazırla. Ardından Docker/RustFS staging ve güvenlik/backup kabul testlerini tamamla.
