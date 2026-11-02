# Hostinger Yayın Geçişi — Test ve Kabul Planı

**Durum:** Plan hazırlandı; testlerin çalıştırıldığı anlamına gelmez.  
**Ortam:** İlk aşama yalnızca geliştirici makinesi/CI. Hostinger sunucusu kurulmayacak, Render canlısına dokunulmayacak, gerçek veri taşınmayacak.

## 1. Test ilkeleri

- Testler sentetik/fake verilerle yürütülecek; gerçek müşteri ve teklif verisi kullanılmayacak.
- Test sonuçları komut, ortam, tarih, başarı/başarısızlık ve hata özetiyle kaydedilecek.
- Mevcut test tabanı önce çalıştırılacak; mevcut başarısızlıklar yeni değişikliklerden ayrılacak.
- PostgreSQL hedef veritabanıdır. Yalnızca SQLite üzerinde yeşil test, geçiş kabulü için yeterli değildir.
- Her veri taşıma komutu dry-run, tekrar çalıştırılabilirlik ve hata halinde güvenli durma kriterlerini karşılamalıdır.
- Hiçbir test otomatik olarak canlıya dağıtım, DNS güncelleme veya gerçek veri taşıma yapmamalıdır.

## 2. Aşama 0 — Mevcut durum ve test tabanı

| Test | Yöntem | Kabul kriteri |
|---|---|---|
| Kaynak tabanı | `git status`, branch ve commit kontrolü | Başlangıç commit'i kaydedilmiş; kullanıcı değişiklikleri ezilmemiş |
| Bağımlılıklar | Temiz Python 3.11+ ortamında kurulum | Kurulum hatasız |
| Mevcut testler | `python -m pytest -q` | Sonuç ve mevcut başarısızlıklar raporlanmış |
| Uygulama başlangıcı | Uvicorn test ortamında başlatma | Başlangıç hatası yok |
| Health endpoint | HTTP sağlık kontrolü | Beklenen durum ve bağımlılık bilgisi doğru |
| Dosya ağacı/şablon | Şablon, test ve migration dosyalarını inceleme | Kullanılan ve kullanılmayan dosyalar ayrılmış |

## 3. Aşama 1 — PostgreSQL uyumluluğu

- [ ] PostgreSQL temiz veritabanı oluşturma ve migration çalıştırma.
- [ ] Migration ikinci kez çalıştırıldığında veri kaybı veya şema bozulması olmaması.
- [ ] Firma oluşturma, listeleme, arama, güncelleme ve silme.
- [ ] Görüşme oluşturma, güncelleme, firma ilişkisi ve ürün satırları.
- [ ] Teklif taslağı oluşturma, güncelleme, silme ve doğru firmaya bağlı kalma.
- [ ] Teklif numarası/sequence eşzamanlı isteklerde çakışmamalı.
- [ ] Bir transaction ortasında hata olduğunda kısmi kayıt bırakılmamalı.
- [ ] Tarih/saat ve timezone dönüşümleri doğru olmalı.
- [ ] JSON alanları ve boş/null değerler doğru saklanmalı.
- [ ] Türkçe karakterli firma, kişi, ürün ve adres alanları kayıpsız olmalı.
- [ ] PostgreSQL bağlantısı kesildiğinde kontrollü hata; sır veya SQL detayı kullanıcıya/loga sızmamalı.
- [ ] Bağlantı havuzu sınırı ve yeniden bağlanma davranışı test edilmeli.

**Kabul:** Kritik iş akışlarının tamamı PostgreSQL üzerinde geçer; veri bütünlüğü ve transaction testleri yeşildir.

## 4. Aşama 2 — Dosya depolama ve belge üretimi

- [ ] Şablon yükleme, listeleme, indirme ve silme.
- [ ] Teklif Excel çıktısı ve formül koruması.
- [ ] PDF önizleme/çıktı üretimi ve KDV gösterimi.
- [ ] İndirim satırı/bölümü hiçbir çıktıda bulunmamalı.
- [ ] Miktar ve birim fiyat tam sayı kuralı korunmalı.
- [ ] Dosya adı çakışması, aynı dosyanın yeniden yüklenmesi ve metadata tutarlılığı.
- [ ] Uygulama konteyneri yeniden oluşturulduğunda dosyalar kalmalı.
- [ ] RustFS PoC seçilirse S3 put/get/head/list/delete ve büyük dosya/yarım yükleme testleri.
- [ ] Depolama servisi erişilemezken uygulama kontrollü hata vermeli; DB kaydı ile dosya tutarsızlığı yönetilmeli.
- [ ] Yetkisiz kullanıcı başka belgeyi indiremiyor olmalı.
- [ ] Yasak uzantı, sahte MIME, aşırı büyük dosya ve bozuk arşiv reddedilmeli.

**Kabul:** Dosyalar konteyner yaşam döngüsünden bağımsız kalıcı olmalı; belge çıktıları mevcut teklif kurallarını bozmamalı.

## 5. Aşama 3 — Güvenlik

- [ ] HTTPS ve HTTP'den HTTPS'e yönlendirme.
- [ ] PostgreSQL, RustFS S3 API ve yönetim konsolu internetten erişilemez olmalı.
- [ ] SSH yalnızca anahtar tabanlı ve sınırlandırılmış erişim.
- [ ] Eksik/yanlış API token ve oturumla korunan API'lere erişim reddedilmeli.
- [ ] CSRF koruması ve cookie güvenlik bayrakları.
- [ ] Oturum süresi dolması, çıkış ve oturum iptali.
- [ ] Yetkisiz firma/teklif/belge erişimi.
- [ ] Brute-force/rate-limit ve parola politikası değerlendirmesi.
- [ ] Gizli değerler kaynak kodda, image katmanında, loglarda veya hata sayfalarında görünmemeli.
- [ ] Container kullanıcıları root olmamalı (gereken servis istisnaları belgelenmeli).
- [ ] Bağımlılık güvenlik taraması ve işletim sistemi güncelleme prosedürü.

**Kabul:** Kritik/yüksek güvenlik bulgusu açık kalmamalı; bilinen sınırlamalar yazılı risk kabulü olmadan üretime taşınmamalı.

## 6. Aşama 4 — Günlük yedekleme ve felaket kurtarma

- [ ] Günlük PostgreSQL mantıksal yedeği oluşturuluyor.
- [ ] Belge dosyaları ve metadata yedeğe dahil.
- [ ] Yedek şifreli ve yetkisiz erişime kapalı.
- [ ] Yedekleme başarısız olduğunda alarm/log üretiliyor.
- [ ] Yedek dosyası bütünlük kontrolünden geçiyor.
- [ ] Temiz test ortamına PostgreSQL restore.
- [ ] Temiz test ortamına belge restore.
- [ ] Restore sonrası firma, görüşme, teklif ve dosya sayıları mutabık.
- [ ] Excel/PDF örnek çıktıları restore edilen veriyle tekrar üretilebiliyor.
- [ ] Hostinger günlük VPS yedeği ayrıca etkin ve panelde doğrulanmış (bu adım satın alma sonrası).
- [ ] Tam VPS restore tatbikatı; süre ölçümü ve uygulama sağlık kontrolü (bu adım staging VPS kurulumu ve ayrıca onay sonrası).

**Kabul:** En az bir tam mantıksal geri yükleme tatbikatı başarılı; RPO hedefi 24 saat veya daha iyi; gerçek RTO ölçülüp kaydedilmiş.

## 7. Aşama 5 — Performans ve dayanıklılık

- [ ] Eşzamanlı kullanıcı ve istek yükü için başlangıç yük testi.
- [ ] Büyük Excel/PDF ve belge yükleme.
- [ ] PostgreSQL bağlantı havuzu ve yavaş sorgular.
- [ ] RAM, CPU ve disk kullanımı.
- [ ] Disk doluluğu ve log büyümesi.
- [ ] Uygulama, DB veya dosya depolama konteyneri yeniden başlatıldığında toparlanma.
- [ ] DB bağlantısı kaybı ve dosya depolama kesintisi.
- [ ] Container image güncelleme/rollback.
- [ ] Sağlık kontrolü ve alarm davranışı.

**Kabul:** Seçilecek VPS kaynakları altında test yükü kararlı; disk/RAM için operasyonel güvenlik payı var.

## 8. Aşama 6 — Kullanıcı kabul testleri

Sentetik verilerle aşağıdaki gerçek iş akışları uçtan uca denenmeli:

1. Firma ekle, düzenle, ara ve firma detayını aç.
2. Telefon görüşmesi ve ziyaret kaydı oluştur.
3. Görüşme içinde katalogdan ürün seç ve kaydet.
4. Görüşmedeki ürünleri teklif taslağına aktar.
5. Teklifin tek bir firmaya ait olduğunu doğrula.
6. Çoklu ürün satırı, tam sayı miktar/birim fiyat ve doğru toplamları doğrula.
7. Ersen Makina Excel şablonuyla teklif oluştur; renk paleti ve formüller korunmalı.
8. PDF çıktısında KDV ve genel toplam doğru görünmeli.
9. İndirim alanı hiçbir ekranda/çıktıda bulunmamalı.
10. Hatalı teklif silme onayıyla sil; iptal edildiğinde kayıt kalmalı.
11. Mobil ekranda firma, görüşme, teklif ve belge akışlarını tamamla.

## 9. Aşama 7 — Staging, taşıma provası ve canlıya geçiş kapıları

Bu aşamalar bu hazırlık dalında yapılmayacak; ayrıca onay gerektirir.

- **Kapı A — Satın alma:** VPS planı, lokasyon, yenileme bedeli, günlük yedek fiyatı ve saklama süresi kullanıcıya sunulup onay alınır.
- **Kapı B — Sunucu kurulumu:** Hostinger VPS ve staging ortamı kurulur; canlı DNS'e dokunulmaz.
- **Kapı C — Taşıma provası:** Yalnızca sentetik/anonimleştirilmiş örnek veri ile dry-run ve mutabakat.
- **Kapı D — Gerçek veri taşıma:** Kaynak yedek, checksum, kayıt sayıları ve geri dönüş planı kullanıcıya sunulur; açık onay alınır.
- **Kapı E — Canlı yayın:** DNS/SSL ve kullanıcı kabul testi için ayrıca açık onay alınır.
- **Kapı F — Render kapatma:** Hostinger'da kararlı çalışma ve geri dönüş süresi tamamlanmadan Render kapatılmaz.

## 10. Test raporu şablonu

Her test koşusunda aşağıdaki alanlar doldurulmalı:

- Tarih / commit / dal:
- Test ortamı ve sürümler:
- Çalıştırılan komut:
- Sonuç: PASS / FAIL / BLOCKED / NOT RUN
- Başarısız test ve hata özeti:
- Etkilenen işlev:
- Güvenlik/veri riski:
- Düzeltme veya takip işi:
- Testi tekrar çalıştıran kişi/tarih:

## 11. Canlıya geçiş için engelleyici koşullar

Aşağıdakilerden biri varsa canlıya geçilmez:
- PostgreSQL üzerinde kritik iş akışı testlerinden biri başarısız.
- Yedekten geri yükleme başarıyla denenmemiş.
- Gerçek kullanıcı erişim/yetkilendirme ve dosya erişim kontrolleri tamamlanmamış.
- Belge/teklif hesapları veya Excel/PDF çıktıları hatalı.
- Günlük yedekleme etkinliği ve başarısı doğrulanmamış.
- Kritik/yüksek güvenlik bulgusu açık.
- Render geri dönüş planı ve kullanıcı onayı yok.


## 12. Geliştirme dalı uygulama/test durumu

- [x] SQLAlchemy/psycopg PostgreSQL adaptörü eklendi.
- [x] Alembic başlangıç migration köprüsü eklendi.
- [x] Yerel ve RustFS S3 depolama adaptörü eklendi.
- [x] Dockerfile, Compose, Nginx loopback proxy ve ortam değişkeni örneği eklendi.
- [x] PostgreSQL SQL çeviri, repository ve sentetik SQLite → PostgreSQL taşıma testleri eklendi.
- [x] Yerel belge → RustFS dry-run/checksum taşıma aracı ve testleri eklendi.
- [x] AES-GCM şifreli günlük backup/restore betikleri, checksum ve cron şablonu eklendi.
- [x] CI Docker image build, Compose config, Python compile ve shell syntax kontrolleri geçti.
- [x] Son SQLite kaynak-kopya migration iyileştirmesi için CI sonucu doğrulandı (commit `e2bdf8574c7e0fba0ee80f3fb5e8bcada9d6b2a1`).
- [ ] RustFS servis uçtan uca testi.
- [ ] PostgreSQL üzerinde tüm iş akışları regresyonu.
- [ ] Şifreli backup/restore tatbikatı.
- [ ] TLS, kimlik doğrulama/yetkilendirme ve güvenlik sertleştirmesi.
- [ ] Gerçek veri taşıma provası.

**Son başarılı CI (2 Kasım 2026, commit `e2bdf8574c7e0fba0ee80f3fb5e8bcada9d6b2a1`, workflow run `41412761295`):** SQLite 29 passed, 3 skipped, 1 warning; PostgreSQL 6 passed. Python compileall, backup/restore shell syntax, Docker Compose config ve Docker image build başarılı. Son PR doğrulama workflow'u da aynı commit için başarılı. Sonraki migration kaynak-kopya değişikliği ayrıca test bekliyor.


## 13. 2 Kasım 2026 — Son CI doğrulaması ve kalan gerçek ortam testleri

**PASS — CI'da kanıtlandı (commit `e2bdf8574c7e0fba0ee80f3fb5e8bcada9d6b2a1`):**
- SQLite regresyonu: 29 passed, 3 skipped, 1 warning.
- PostgreSQL adaptör + smoke + SQLite→PostgreSQL sentetik migration: 6 passed.
- Python compileall, backup/restore shell syntax, Docker Compose config ve Docker image build: başarılı.
- PR doğrulama workflow'u: başarılı.

**NOT RUN / BLOCKED — CI yeşil olsa da tamamlanmış sayılmaz:**
- RustFS gerçek S3 servisiyle put/get/head/list/delete ve kalıcılık uçtan uca testi.
- PostgreSQL üzerinde tüm firma/görüşme/ürün/teklif/Excel/PDF/KDV iş akışı regresyonu.
- Şifreli PostgreSQL + nesne yedeğinin gerçek üretimi ve temiz hedefe tam restore tatbikatı.
- TLS/HTTPS, firewall, gerçek kullanıcı/rol yetkilendirmesi ve güvenlik taraması.
- Yük, disk doluluğu, servis kesintisi ve rollback testleri.
- Hostinger VPS ortamı olmadan VPS'e özgü snapshot, cron ve restore testi.

**Sonuç:** Kod/CI doğrulaması başarılıdır; teknik kabul testlerinin tamamı henüz bitmemiştir. Bu engelleyici testler gerçek Hostinger staging ortamı gerektirir. Satın alma/VPS kurulumu için ayrı onay alınmadan bu ortam testleri yapılamaz.
