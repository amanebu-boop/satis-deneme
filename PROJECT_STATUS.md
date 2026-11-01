# Satış Projesi — Durum ve Devam Dosyası

> Son güncelleme: 2026-10-29  
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

## 9. 2026-11-01 — Ajan kartları (test dalı)

- Çalışma dalı: `feature/agent-foundation`. `main` ve canlı Render servisine gönderim yapılmadı.
- `web/agents.html`: ajan kartları masaüstünde 3 sütun, mobilde 2 sütun olacak şekilde düzenlendi; kartlar kare oranında.
- Ajanın durumu artık kartın kendisine dokunarak açılıp kapatılacak şekilde bağlandı. Klavyeden Enter/Space ile de değiştirilebilir.
- Ayrı “Etkinleştir / Devre dışı bırak” düğmesi ve durum değişikliği öncesi onay penceresi kaldırıldı.
- Etkin kart, mevcut arayüz paletine uygun altın tonlu kenarlık ve açık zeminle ayırt ediliyor; pasif kart nötr görünüyor.
- Durum değişikliği mevcut `/api/agents/{id}/status` uç noktasına kaydediliyor; ekran her değişiklikten sonra `/api/agents` verisini yeniden yükleyerek sunucuda kayıtlı durumu gösteriyor. Bu, uygulamanın mevcut kalıcı ajan durum alanını kullanır.
- Etkin ajanların görev düğmeleri korunmuştur. Bu düğmelere tıklamak kartın aç/kapa davranışını tetiklemez.
- Değişiklik commit'leri: `5e3127b` (kart yerleşimi/stil), `1355156` (kart tıklama ve onay kaldırma), `e3726ef` (kart içi görev düğmelerini koruyarak erişilebilir klavye etkileşimi).
- Dağıtım: Render test servisi `srv-dbhssmd9el5s738cnr9g` üzerinde `064ce4a5ae64478697db60b4a0e4055923501da7` commit’i `live` durumuna geçti (deploy `dep-dbjfb3i9249c738fs47g`, 2026-11-01 08:18 UTC). Render loglarında uygulama başlangıcı ve “Your service is live” kaydı görüldü. Canlı servis ve `main` değiştirilmedi.
- Test: GitHub commit durum kontrolünde kontrol sonucu bulunmadı; commit için workflow run da görünmedi. Bu nedenle otomatik test başarılı olarak raporlanamaz. Kullanıcı, Render test ortamında ajan kartlarını kontrol ederek istenen davranışların çalıştığını doğruladı: kare kartlar, masaüstünde yan yana üç kart, kart üzerinden aç/kapa, ayrı etkinleştirme düğmesi/onayı olmaması ve durumun korunması. Bu, kullanıcı tarafından yapılan arayüz doğrulamasıdır; otomatik test sonucu değildir.
- Render test servisi için `b0a7c7f` dokümantasyon commit’ini içeren sonraki dağıtım da `dep-dbjfc3qvcj2c73eu2jrg` kimliğiyle `live` oldu (2026-11-01 08:20 UTC).
- Sonraki adım: bu ajan arayüzü işi kullanıcı doğrulamasıyla tamamlandı. Otomatik test altyapısı/sonuçları ayrıca doğrulanmadıkça test başarısı iddia edilmemeli.


## 10. 2026-11-01 — Kullanıcı doğrulaması

- Kullanıcı, görüşme takviminde geçmiş tarih seçiminin düzeldiğini doğruladı.
- Kullanıcı, teklif PDF sayfa yerleşimini doğruladı.
- Bu iki iş, kullanıcı tarafından test ortamında kontrol edilerek tamamlandı kabul edildi; otomatik test sonucu olarak değerlendirilmez.

## 11. 2026-11-01 — Denetim ajanı (test dalı)

- Sonraki ajan geliştirme adımı olarak Denetim Ajanı için salt-okunur audit_overview görevi eklendi.
- Görev yalnızca denetim olayları, ajan görevleri ve onay durumlarının sayısal dağılımını döndürür; aktör kimlikleri, olay ayrıntıları veya müşteri verileri rapora çıkarılmaz.
- Denetim ajanı etkinleştirme izin listesine ve Ajan Yönetimi görev düğmelerine eklendi.
- Regresyon testi eklendi; test sonucu ve Render dağıtımı henüz doğrulanmadı.
- Çalışma dalı: feature/agent-foundation. main ve canlı Render servisine dokunulmadı.
