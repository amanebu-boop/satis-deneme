# Hostinger teknik kurulum runbook'u

**Kapsam:** Bu belge hazırlık ve staging runbook'udur. Hostinger hesabında işlem, satın alma, VPS kurulumu, DNS/canlı değişiklik ve gerçek veri taşıma bu aşamada yapılmaz.

## 1. Hazırlanan servisler

- FastAPI uygulaması: Python 3.11, Uvicorn; Docker içinde root olmayan kullanıcı.
- PostgreSQL 16: yalnızca Compose iç ağına açık.
- RustFS: S3 uyumlu nesne depolama; 9000/9001 portları host'a yayınlanmaz.
- Nginx: ters proxy; test aşamasında yalnızca `127.0.0.1:8080` üzerinden erişilir.
- Günlük yedekleme: PostgreSQL dump + RustFS nesne arşivi; AES-256-GCM/PBKDF2 ile şifreli, 14 günlük yerel saklama.

RustFS imajı `.env.hostinger.example` içinde resmi dokümanlardaki x86 musl `v2.3.1` örneğine sabitlenmiştir. Satın alma/kurulum öncesi mimari ve daha yeni güvenlik sürümü yeniden kontrol edilmelidir.

## 2. Staging başlatma (yalnızca ayrıca onaylanmış VPS veya geliştirici makinesi)

1. `.env.hostinger.example` dosyasını `.env` olarak kopyalayın.
2. `POSTGRES_PASSWORD`, `RUSTFS_ACCESS_KEY`, `RUSTFS_SECRET_KEY`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `SALES_API_TOKEN`, `SALES_LOGIN_PASSWORD` ve `BACKUP_ENCRYPTION_PASSPHRASE` alanlarını güçlü, benzersiz sırlarla değiştirin. RustFS yönetici access key'i yalnızca büyük harf/rakam kullanmalı; PostgreSQL parolasını URL güvenli karakterlerle üretin.
3. `.env` dosyasını Git'e eklemeyin.
4. `docker compose config --quiet` ile yapılandırmayı doğrulayın.
5. Önce yalnızca RustFS'i başlatın: `docker compose up -d rustfs`.
6. Yönetim konsolu host üzerinde yalnızca `127.0.0.1:9001` adresine bağlıdır. Yönetici bilgisayarından SSH tüneli açın (`ssh -L 9001:127.0.0.1:9001 kullanici@sunucu`) ve `http://127.0.0.1:9001` üzerinden bağlanın.
7. RustFS yönetici hesabıyla bucket'ı oluşturun; uygulama için yalnızca bu bucket üzerinde gerekli listeleme/okuma/yazma/silme izinleri olan ayrı bir servis hesabı oluşturun. `S3_ACCESS_KEY` ve `S3_SECRET_KEY` alanlarına bu servis hesabını yazın. Yönetici anahtarları uygulama konteynerine aktarılmaz.
8. `docker compose build` ve `docker compose up -d` çalıştırın.
9. Uygulama migration'ları başlangıçta Alembic ile çalıştırır ve önceden oluşturulmuş bucket erişimini doğrular.
10. `curl http://127.0.0.1:8080/health` sonucu `status=ok`, `database=postgresql`, `storage=s3` olmalıdır.
11. `docker compose ps` ve logları kontrol edin. PostgreSQL ve RustFS host üzerinde doğrudan port yayınlamamalıdır.

Bu yapılandırma HTTP test proxy'sidir; genel internete açılmaya veya canlı yayına hazır değildir. Domain, TLS sertifikası, HTTPS yönlendirmesi ve firewall kuralları ayrı hazırlık/onay kapısında yapılacaktır.

## 3. Günlük yedekleme

- `docs/hosting/hostinger-daily-backup.cron` içindeki cron satırını gerçek kurulum dizinine göre düzenleyin.
- Hostinger VPS üzerinde günlük snapshot/backup özelliğini ayrıca etkinleştirin; panelde sıklık ve saklama süresini doğrulayın.
- Mantıksal yedek `pg_dump` ve RustFS bucket içeriğini kapsar; `/backups` Docker volume'ünde şifreli tutulur.
- Şifreleme parolası yedeklerle aynı klasöre veya Git'e yazılmaz; ayrı güvenli yerde saklanır.
- Yedek işi günlük loglanır. Başarısızlıkta cron logu incelenir; yedek dosyası oluştu diye başarı varsayılmaz.
- En az bir kez temiz bir test veritabanı ve boş test bucket'ına geri yükleme yapılmadan yedek kabul edilmez.

## 4. Geri yükleme güvenliği

`restore.sh` veritabanı nesnelerini temizleyip yeniden oluşturabilir. Yalnızca ayrı test hedefinde çalıştırın. Önce backup timestamp ve checksum doğrulanır. Komut `RESTORE_CONFIRM=YES` olmadan çalışmaz; hedef RustFS bucket doluysa varsayılan olarak durur. Dolu bucket üzerine birleştirme yalnızca ayrı inceleme sonrası `RESTORE_ALLOW_NONEMPTY_BUCKET=YES` ile yapılmalıdır.

## 5. Açık üretim engelleri

- Uygulamada gerçek kullanıcı giriş/OIDC akışı ve üretim düzeyi rol/erişim kontrolleri henüz tamamlanmış değildir.
- HTTPS/TLS ve public Nginx port eşlemesi bu aşamada yoktur.
- RustFS tek VPS/tek disk üzerinde çalışırsa yüksek erişilebilirlik sağlamaz; Hostinger snapshot/backup bağımsız geri dönüş katmanı olarak doğrulanmalıdır.
- RustFS yönetici anahtarları yalnızca RustFS servisine verilir; uygulama ve yedekleme araçları bucket ile sınırlandırılmış servis hesabını kullanır.
- PostgreSQL CI smoke testi vardır; tüm iş akışlarının PostgreSQL üzerinde tam kabul testi ve dosya depolama uçtan uca testi henüz tamamlanmamıştır.
- Mevcut SQLite verisi ve belgeler taşınmamıştır. Gerçek veri taşıma için dry-run, checksum ve kayıt mutabakatı ayrıca gerekir.

Bu maddeler kapanmadan canlı geçiş yapılmaz.

## 6. SQLite ve belge taşıma provası

1. Önce PostgreSQL şemasının Alembic ile kurulduğunu ve hedef tabloların boş olduğunu doğrulayın.
2. SQLite veri raporu: `python scripts/migrate_sqlite_to_postgres.py --source data/sales.db`.
3. Yerel belge raporu: RustFS ortam değişkenlerini ayarladıktan sonra `python scripts/migrate_local_documents_to_s3.py --source data/documents`.
4. Dry-run raporundaki tablo sayıları, SHA-256 özetleri, dosya sayıları ve byte toplamlarını kaynakla karşılaştırın.
5. Gerçek taşıma gerekiyorsa ayrı bakım penceresi, geri dönüş yedeği ve açık onaydan sonra yalnızca hedef ortamda `--apply` kullanın. Bu araçlar kaynak veriyi silmez.
6. Taşıma sonrası firma/görüşme/teklif sayıları, ürün ilişkileri, dosya indirme ve Excel/PDF çıktıları kullanıcı kabul testinden geçirilmelidir.
