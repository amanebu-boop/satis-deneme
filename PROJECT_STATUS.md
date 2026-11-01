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


- Render dağıtımı: son commit `5ef9aa5e050e4d0a343c525978d9a42053e5ec60` test servisine başarıyla dağıtıldı; deploy `dep-dbjfge12tl4s73efvekg` `live` (2026-11-01 08:29:56 UTC). Servis dalı `feature/agent-foundation` olarak doğrulandı.
- Açılış doğrulaması: Render loglarında `Application startup complete`, `Uvicorn running` ve `GET /` yanıtı `200 OK` görüldü. Uygulama loglarında bu dağıtım aralığında `error`/`warn` seviyesinde kayıt bulunmadı.
- Sınır: Bu yalnızca servis açılış/HTTP kök yolu doğrulamasıdır. Denetim Ajanı görevini gerçek kullanıcı arayüzünde çalıştırma doğrulaması henüz yapılmadı. GitHub Actions workflow run görünmediği için otomatik test sonucu da yoktur.
- Sıradaki adım: test ortamında Denetim Ajanı kartını etkinleştirip “Denetim kayıtları özeti” görevini çalıştırmak ve sonuç ekranını kontrol etmek. `main` ve canlı Render servisine dokunulmadı.


## 12. 2026-11-01 — Onaylı ajan mimarisinin görev sınırları ve bağımlılıkları

- Kullanıcının daha önce onayladığı mimari esas alındı; yeniden tasarım onayı istenmedi.
- `AGENT_ARCHITECTURE.md` eklendi: işlem ajanları kendi alanlarında, Satış Ajanı koordinatör, Raporlama Ajanı analiz, Denetim Ajanı denetim sorumluluğunda.
- `AGENT_DEPENDENCIES` tanımlandı: Satış Ajanı etkinleştirildiğinde Firma, Ürün, Görüşme ve Teklif ajanları atomik biçimde otomatik etkinleştirilir.
- Denetim Ajanı bağımsız denetim yaptığı için etkinleştirilmesi Teklif Ajanı'nı veya diğer işlem ajanlarını açmaz. Böylece kullanıcının gördüğü teklif taslağı akışı ile Denetim Ajanı'nın görevi ayrıştırıldı.
- Bağımlılık ajanları koordinatör kapatıldığında otomatik kapatılmaz; başka akışlarca kullanılıyor olabilir.
- Otomatik etkinleştirmeler `agent_auto_enabled` denetim kaydı üretir.
- Ajan ekranındaki görüşmeden teklif taslağı panelinin başlığı ve açıklaması, işlemin Teklif Ajanı'na ait olduğunu ve Denetim Ajanı'ndan bağımsız olduğunu belirtecek şekilde düzeltildi.
- Bağımlılık davranışı için üç regresyon testi eklendi: Satış Ajanı bağımlılıkları açar, Denetim Ajanı ilgisiz ajanları açmaz, koordinatör kapatılınca bağımlılıklar kapanmaz.
- Testler henüz çalıştırılmadı; GitHub Actions workflow sonucu ve Render dağıtımı bekleniyor. Bu nedenle otomatik test başarısı iddia edilmez.
- Çalışma dalı `feature/agent-foundation`; `main` ve canlı Render değiştirilmedi.
- Sıradaki iş: test dağıtımını doğrulamak, sonra görev ekranındaki gerçek akışları ajan kartları altında tutarlı hale getirmek ve Satış Ajanı koordinasyon görevini geliştirmek.


## 13. 2026-11-01 — Ajan talimat dosyaları ve çalışma öncesi yönlendirme

- Kök `AGENTS.md` yönlendirme dosyası oluşturuldu. Sekiz ajanın her biri için `agents/{agent_id}.md` talimat dosyası eklendi: company, product, meeting, quotation, warehouse, sales, reporting, audit.
- Her dosyada rol, başlangıç sırası, yapabilecekleri, yapamayacakları, görev izinleri ve güvenlik kuralları tanımlandı.
- `app/agent_instructions.py` eklendi. Çalışma zamanı önce kök yönlendirme dosyasını, sonra yalnızca ilgili ajanın kendi dosyasını okur; yönlendirme hedefini, agent_id kimliğini ve istenen görevin izinli görev listesinde bulunmasını doğrular.
- `app/agent_runtime.py` her görev çalıştırılmadan önce bu doğrulamayı zorunlu kılar. Belge eksik/bozuksa veya görev izinli değilse görev başlatılmaz.
- Belge politikası uygulama kodunun güvenlik kontrollerinin yerine geçmez; iki katman birlikte gereklidir. Satış Ajanı ve Depo Ajanı için henüz çalıştırılabilir görev tanımlanmadı.
- Talimat yükleme ve izinli/izinsiz görev senaryoları için testler eklendi; testler henüz çalıştırılmadı.
- Çalışma dalı `feature/agent-foundation`. `main` ve canlı Render'a dokunulmadı.
- Sıradaki adım: dosyaların GitHub'da tam olduğunu doğrulamak, test dalında dağıtımı ve çalışma zamanı davranışını kontrol etmek.


- Çalışma zamanı talimat kontrolü eklendi: `app/agent_instructions.py` önce `AGENTS.md`, sonra ilgili ajan dosyasını okur; rota, kimlik ve izinli görev listesini doğrular. `app/agent_runtime.py` bu kontrolü her görevden önce zorunlu kılar.
- Sekiz ajanın tamamında `Çalıştırılabilir görevler` bölümü standartlaştırıldı. Satış ve Depo ajanlarının izinli görev listesi boş; bu ajanlar henüz görev çalıştıramaz.
- Testler eklendi ancak henüz çalıştırılmadı. GitHub Actions sonucu doğrulanmadı; otomatik test başarısı iddia edilmez.
- Son kod commit'i: `0b83737f4e51f6accd85a1b37d5f85d3dfa3824f`. `main` ve canlı Render değiştirilmedi.


## 2026-11-01 — Ajan talimatları için test altyapısı ve test dağıtımı

- `.github/workflows/python-tests.yml` eklendi. `feature/agent-foundation` dalına push, `main` hedefine PR ve manuel çalıştırma tetikleyicileriyle Python 3.12 üzerinde `python -m pip install -e ".[test]"` ve `python -m pytest -q` çalıştırır.
- Test ortamı Render dağıtımı commit `a2ed70171a0201e7fd2ce2670b2f2d1438e467ec` için `live` oldu. Build başarılı, uygulama başlangıcı tamamlandı ve Render sağlık isteği `GET /` için `200 OK` döndü.
- GitHub Actions test sonucunu mevcut bağlantı üzerinden doğrulayamadım: commit workflow sorgusu yalnızca PR tetiklemeli çalışmaları döndürüyor; commit status sorgusunda da henüz kontrol sonucu görünmüyor. Bu nedenle pytest testleri geçti denemez. Test workflow dosyası eklendi, fakat test koşum sonucu beklemede/doğrulanamadı.
- Test servisi: `https://satis-deneme-test.onrender.com`. `main` ve canlı Render'a dokunulmadı.


## 2026-11-01 — OpenAI API sohbet entegrasyonu (ilk uygulama aşaması)

- Kullanıcı tercihi: uygulama içine OpenAI API entegrasyonu; tanımlı güvenli işlemler otomatik, kritik işlemler kullanıcı onayıyla.
- Test dalında `app/agent_chat.py` eklendi. `POST /api/assistant/chat` uç noktası mevcut uygulama oturumu ve CSRF doğrulamasının arkasında çalışır; tarayıcıya OpenAI anahtarı verilmez.
- Resmi OpenAI Python SDK ve Responses API kullanılır. Model `OPENAI_MODEL` ile sunucu tarafında seçilir; varsayılan `gpt-5.5`.
- Ajan görev akışı profil-önceliklidir: model önce `read_agent_profile` aracını çağırır; sunucu önce `AGENTS.md`, sonra seçilen ajanın kendi MD dosyasını okur ve içeriği modele verir. Ardından `run_agent_task` çağrısı, aynı turda profil okunmuşsa, izin listesi uygunsa ve ajan etkinse çalışır. Çalışma zamanı ayrıca kendi MD dosyasındaki görev iznini tekrar doğrular.
- Modelin kullanabildiği görevler mevcut salt-okunur özetler ve görüşmeden teklif hazırlama önizlemesidir. Teklif önizlemesi kayıt oluşturmaz. Firma/ürün/görüşme/teklif oluşturma, değiştirme veya silme araçları modele açılmadı.
- Kritik işlemler için model çağrısı veya modelin kendi beyanı onay sayılmaz. Uygulamanın mevcut onay akışı ve sunucu tarafı doğrulamaları zorunludur.
- `pyproject.toml` içine `openai>=2.0,<3.0` bağımlılığı eklendi. `tests/test_agent_chat.py` içinde sohbet yanıtı, MD profilini önce okuma, izinli görev, profil okunmadan görev reddi ve araç çağrısı sınırı testleri eklendi.
- Gerekli Render test ortamı değişkenleri: `OPENAI_API_KEY` (kullanıcının kendi API anahtarı; gizli ortam değişkeni) ve isteğe bağlı `OPENAI_MODEL`. API anahtarı henüz Render'a eklenmedi; canlı OpenAI çağrısı yapılandırılmadı/doğrulanmadı.
- OpenAI API kullanımı ChatGPT aboneliğinden ayrıdır ve API hesabında ayrıca ücretlendirilir.
- Testler bu aşamada henüz çalıştırılmadı; başarı iddiası yoktur. Render dağıtımı ve GitHub Actions test sonucu ayrıca doğrulanmalıdır.
- Çalışma dalı `feature/agent-foundation`; `main` ve canlı Render servisine dokunulmadı.
