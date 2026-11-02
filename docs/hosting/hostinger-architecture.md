# Hostinger Yayın Mimarisi — Teknik Hazırlık

**Durum:** Tasarım kararı onaylandı; teknik hazırlık aşamasında. Satın alma, sunucu kurulumu, canlı değişiklik ve veri taşıma yapılmadı.  
**Hedef:** Satış uygulamasını, PostgreSQL veritabanını ve kalıcı belge depolamasını tek sağlayıcı olarak Hostinger üzerinde çalıştırmak.  
**Yedekleme kararı:** Günlük (daily).

## 1. Onaylanmış kararlar ve sınırlar

- Uygulama, veritabanı ve dosyalar Hostinger üzerinde barındırılacak.
- Uygulama Python/FastAPI olduğu için Hostinger VPS kullanılacak; Web/Cloud hosting bu uygulama için hedef değil. Hostinger Python kurulumunu root erişimi nedeniyle VPS ile sınırlandırıyor.
- Veritabanı PostgreSQL olacak.
- Kullanıcı tarafından yüklenen şablonlar ve üretilen belgeler kalıcı depolamada tutulacak.
- Günlük yedekleme hedeflenecek.
- Mevcut Render servisi geçiş ve kabul testleri tamamlanana kadar geri dönüş seçeneği olarak korunacak.
- Bu dalda yalnızca teknik dokümantasyon, kod uyarlaması ve yerel/CI test hazırlığı yapılabilir. Hostinger hesabında işlem, satın alma, DNS değişikliği, Render yapılandırması veya gerçek veri taşıma yapılmayacak.

## 2. Hedef topoloji

```text
Kullanıcı / Tarayıcı
        |
      HTTPS
        |
Hostinger VPS (tercihen Almanya veri merkezi)
        |
      Nginx
        |
 FastAPI / Uvicorn
   |          |
   |          +---- Kalıcı belge depolama
   |                (önce depolama arayüzü; S3 uyumlu RustFS
   |                 teknik doğrulama sonrasında seçilebilir)
   |
 PostgreSQL
        |
 Günlük yedekleme + geri yükleme doğrulaması
```

Tek VPS başlangıçta işletim maliyetini sadeleştirir; ancak uygulama, PostgreSQL ve dosya depolaması aynı makinenin CPU/RAM/disk kaynaklarını paylaşır ve makine tek hata noktasıdır. Kaynak kullanımı ve disk doluluğu izlenmelidir. Büyüme veya yüksek erişilebilirlik ihtiyacında bileşenleri ayırma kararı ayrıca alınmalıdır.

## 3. Sunucu ve işletim sistemi

- İlk teknik hedef: Hostinger Linux VPS; Almanya lokasyonu tercih edilecek. VPS lokasyonu ilk kurulumdan sonra değiştirilemediği için satın alma öncesi tekrar teyit edilmeli.
- KVM2 sınıfı kaynaklar yalnızca başlangıç planlama varsayımıdır; gerçek kaynak ihtiyacı yük testi ve fiyat/yenileme koşulları kontrol edilerek satın alma öncesi kesinleştirilecek.
- Docker Engine ve Docker Compose ile servisler birbirinden ayrılacak.
- Konteynerler sabit sürüm etiketleriyle çalıştırılacak; üretimde `latest` etiketi kullanılmayacak.
- Hostinger VPS self-managed olduğundan işletim sistemi güncellemeleri, firewall, SSH, Docker, log rotasyonu, izleme ve kurtarma sorumluluğu proje işletimindedir.

## 4. Uygulama katmanı

- Mevcut FastAPI uygulaması korunacak; uygulama konteyner içinde Uvicorn ile çalışacak.
- Nginx yalnızca 80/443 portlarını dışarı açacak; FastAPI, PostgreSQL ve nesne depolama yönetim portları internete doğrudan açılmayacak.
- HTTPS sertifikası otomatik yenileme ile yönetilecek.
- Gizli bilgiler Git'e yazılmayacak. Uygulama sırları Hostinger VPS üzerinde dosya izinleri kısıtlı environment/secrets dosyasında tutulacak; loglarda veya hata mesajlarında gösterilmeyecek.
- Sağlık kontrolü uygulama, PostgreSQL ve dosya depolama bağımlılıklarını ayrı ayrı doğrulayacak.

## 5. PostgreSQL'e geçiş hazırlığı

Mevcut kod SQLite `sqlite3` API'sine ve SQLite'a özgü SQL davranışlarına bağlı. Bu nedenle yalnızca bağlantı adresini değiştirmek yeterli değildir.

Hazırlık işleri:
1. Veritabanı erişimini tek bir repository/connection katmanında toplamak.
2. SQLite'a özgü `PRAGMA`, `sqlite3.Row`, placeholder ve conflict davranışlarını belirlemek.
3. PostgreSQL sürücüsünü ve bağlantı havuzunu eklemek; bağlantı bilgilerini environment değişkenlerinden okumak.
4. Şema oluşturma ve yükseltmeleri tekrarlanabilir migration dosyalarına taşımak.
5. Tarih/saat, boolean, JSON alanları, transaction ve unique sequence davranışlarını PostgreSQL ile eşdeğer kılmak.
6. Testlerde SQLite ve PostgreSQL için aynı işlevsel kabul kriterlerini çalıştırmak; üretim hedefi PostgreSQL'dir.
7. Şema ve veri taşıma komutlarını ayrı, tekrar çalıştırılabilir ve dry-run destekli hazırlamak. Gerçek veriye dokunulmayacak.

İlk etapta SQLAlchemy/Alembic veya mevcut yapıya en az müdahaleli bir migration yaklaşımı teknik prototiple karşılaştırılacak; seçim kod incelemesi ve test kolaylığına göre yapılacak.

## 6. Kalıcı belge depolama

Mevcut uygulama `SALES_DOCUMENTS_PATH` üzerinden yerel dosya sistemine yazıyor. Konum değişkeni tek başına kalıcı depolama garantisi sağlamaz.

- Uygulama kodu depolama sağlayıcısından ayrıştırılacak: kaydet, oku, listele, sil ve metadata işlemleri bir arayüz üzerinden yapılacak.
- İlk uyumluluk adımı, Docker volume ile kalıcı dosya sistemi sağlayıcısını desteklemek.
- S3 uyumlu RustFS, Hostinger VPS üzerinde ayrı konteyner ve kalıcı volume olarak teknik PoC'ye alınabilir. RustFS'in tek düğüm/tek disk kurulumu veri yedekliliği sağlamaz; bu nedenle tek başına yedekleme sayılmayacak ve üretim kararı restore/backup testinden önce verilmeyecek.
- Dosya erişimi uygulama üzerinden yetkilendirilecek; bucket/console portları internete açılmayacak.
- Yükleme boyutu, MIME/uzantı doğrulaması, dosya adı normalizasyonu, zararlı/arşiv içeriği kontrolü ve yetkisiz dosya indirme testleri korunacak.
- Şablon kaynak dosyaları, teklif çıktıları ve metadata birlikte yedeklenebilir/geri yüklenebilir olmalı.

## 7. Güvenlik ve işletim

- SSH anahtar tabanlı erişim; parola ile root SSH kapalı.
- Firewall: yalnızca 80/443 ve yönetim için sınırlandırılmış SSH erişimi.
- PostgreSQL ve RustFS yalnızca özel Docker ağı üzerinden erişilebilir.
- Yönetici/uygulama parolaları ve API tokenları güçlü, ayrı ve döndürülebilir olacak.
- Oturum, CSRF, yetkilendirme ve rol/erişim kontrolleri üretim öncesi ayrıca denetlenecek. Mevcut tek kullanıcı prototip akışı, üretim güvenliği tamamlandı anlamına gelmez.
- Güvenlik güncellemeleri, container image güncellemeleri, disk doluluk alarmı, servis sağlık kontrolü ve log rotasyonu prosedürü hazırlanacak.
- Müşteri verisi içeren loglar ve yedekler erişim kontrollü ve şifreli tutulacak.

## 8. Günlük yedekleme standardı

Günlük yedekleme kullanıcı tarafından onaylanmış gereksinimdir; ücretli VPS günlük yedekleme seçeneğinin fiyatı ve saklama süresi satın alma öncesi Hostinger panelinde teyit edilecek.

Yedek kapsamı:
- PostgreSQL tutarlı mantıksal yedeği (ör. `pg_dump`).
- Yüklenmiş şablonlar, teklif belgeleri ve dosya metadata'sı.
- Gerekli uygulama yapılandırması (sırlar yedek dosyalarına düz metin dahil edilmeyecek).
- VPS otomatik günlük yedeği; Hostinger dokümanına göre sunucudan ayrı saklanır. Güncel dokümanda en fazla iki günlük ve iki haftalık yedek tutulduğu belirtiliyor; satın alma ekranında tekrar doğrulanmalı.

Kurallar:
- Yedekler şifreli olmalı; erişim yalnızca yetkili işleticiye açık olmalı.
- Yedek işi başarılı/başarısız durumunu, dosya boyutunu ve zaman damgasını kaydetmeli; başarısızlık görünür alarm üretmeli.
- Yedek üretildi diye başarılı kabul edilmeyecek; periyodik geri yükleme testi zorunlu.
- Hedef RPO: en fazla 24 saatlik veri kaybı (günlük yedek varsayımı). Hedef RTO, gerçek restore tatbikatıyla ölçülüp belirlenecek.
- Aynı VPS üzerindeki ikinci kopya tek başına yedek değildir. Hostinger'ın sunucudan ayrı tuttuğu backup katmanı doğrulanmalı.
- Sağlayıcı tekliği tercihi nedeniyle off-provider yedekleme varsayılan kapsamda değil; bunun sağlayıcı/hesap düzeyinde ortak risk yarattığı açıkça kabul edilmeli.

## 9. Geçiş ve yayın sırası

1. Bu dalda kod ve test hazırlığı.
2. Yerel Docker Compose üzerinde FastAPI + PostgreSQL + kalıcı dosya depolama testi.
3. Güvenlik, yedekleme ve geri yükleme kabul testleri.
4. Kod incelemesi ve kullanıcı onayı.
5. **Ayrı onaydan sonra** Hostinger satın alma ve VPS oluşturma.
6. **Ayrı onaydan sonra** Hostinger ortam kurulumu ve staging testi.
7. **Ayrı onaydan sonra** veri/dosya taşıma provası ve mutabakat.
8. **Ayrı onaydan sonra** DNS/canlı geçiş.
9. Render, geri dönüş süresi ve kullanıcı kabulü tamamlanana kadar kapatılmayacak.

## 10. Resmî teknik referanslar

- Hostinger — Python yalnızca VPS üzerinde desteklenir: https://www.hostinger.com/support/3648030-is-python-supported-at-hostinger
- Hostinger — VPS yedekleme ve geri yükleme: https://www.hostinger.com/support/1583232-how-to-back-up-or-restore-a-vps-at-hostinger/
- Hostinger — VPS lokasyonları: https://www.hostinger.com/support/1583267-where-are-hostinger-servers-located/
- RustFS — Docker kurulumu ve tek düğüm/tek disk sınırlaması: https://docs.rustfs.com/en/installation/container


## 11. Geliştirme dalındaki teknik uygulama

Aşağıdaki bileşenler `infra/hostinger-migration-prep` dalına eklendi:
- SQLAlchemy 2 + psycopg PostgreSQL erişim adaptörü; SQLite yerel backend olarak korunur.
- Alembic başlangıç migration köprüsü. İlk sürüm mevcut idempotent şema oluşturucuyu çağırır; bundan sonraki şema değişiklikleri gerçek Alembic revision dosyalarıyla yapılmalıdır.
- `app/storage.py`: yerel/S3 depolama seçimi. RustFS için path-style S3, başlangıçta bucket kontrolü ve oluşturma.
- `template_documents.py`: şablon metadata/kaynaklarının RustFS'e kaydı, listeleme ve oluşturulan belge nesnelerinin saklanması.
- Dockerfile ve Compose: FastAPI, PostgreSQL 16, RustFS, Nginx. Nginx yalnızca loopback `127.0.0.1:8080` test erişimi sağlar.
- Sağlık kontrolü PostgreSQL/SQLite ve seçilen depolama backend'ini sorgular.
- Günlük mantıksal yedek: PostgreSQL dump + RustFS nesneleri; AES-256-GCM ve PBKDF2 ile şifreli; 14 gün saklama. Cron şablonu 02.00 UTC değil, sunucunun yerel saatine göre 02.00 çalışır.

Bu altyapı kod hazırlığıdır; gerçek Hostinger kurulumu veya yedek/restore tatbikatı yapılmış değildir.


## 12. Veri taşıma araçları

- `scripts/migrate_sqlite_to_postgres.py`: SQLite tabloları için önce dry-run raporu ve SHA-256 özetleri üretir. Hedef şemanın önceden Alembic ile kurulmuş ve tüm uygulama tablolarının boş olması gerekir. Yazma yalnızca `--apply` ile yapılır; kayıt sayısı ve tablo checksum'ları transaction içinde doğrulanır. Ürün opsiyon ebeveyn ilişkileri üstten alta kopyalanır; döngü tespit edilirse işlem durur.
- `scripts/migrate_local_documents_to_s3.py`: yerel `.source`, `.json` ve `.output.*` dosyalarını RustFS anahtarlarına eşler; varsayılan dry-run'dır. `--apply` sırasında SHA-256 doğrulaması yapar ve mevcut farklı nesnenin üzerine yazmaz.
- Her iki araç da kaynak SQLite dosyasını veya yerel dosyaları silmez. Dry-run raporu, kayıt mutabakatı ve ayrıca kullanıcı onayı olmadan gerçek müşteri verisi taşınmaz.
