# Ajan Mimarisi ve Görev Sınırları

Bu belge, Satış projesinde kabul edilmiş ajan rol modelini ve görev sınırlarını tanımlar.

## Temel mimari

- **İşlem ajanları** kendi iş alanlarının işlemlerini yürütür: Firma, Ürün, Görüşme, Teklif ve ileride Depo.
- **Satış Ajanı** koordinatördür. Satış sürecindeki ihtiyacı belirler ve ilgili işlem ajanlarını sıralı biçimde görevlendirir.
- **Raporlama Ajanı** satış performansı ve süreç sonuçlarını analiz eder. İşlem ajanlarının yerine işlem yapmaz.
- **Denetim Ajanı** ajan çalıştırmalarını, yetki değişikliklerini, onayları ve güvenlik kayıtlarını denetler. İşlem ajanlarının yerine teklif/firma/ürün işlemi yapmaz.

## Görev kataloğu

| Ajan | Sorumluluk | Mevcut uygulama durumu |
|---|---|---|
| Firma | Firma ve yetkili kayıtları | Şimdilik salt-okunur firma rehberi özeti |
| Ürün | Ürün kataloğu ve opsiyonlar | Şimdilik salt-okunur katalog özeti |
| Görüşme | Görüşme ve görüşme ürünleri | Şimdilik salt-okunur görüşme özeti |
| Teklif | Görüşmeden teklif taslağı, teklif süreci ve onaylı teklif oluşturma | Taslak önizleme + onaylı oluşturma akışı mevcut; teklif süreci özeti mevcut |
| Depo | Stok ve depo süreçleri | Kullanılabilir görev yok; etkinleştirilmez |
| Satış | Süreç koordinasyonu ve ajanlar arası iş akışı | İzinli görev kataloğuyla salt-okunur koordinasyon mevcut; her alt görev ayrı yetki/etkinlik kontrolünden geçer |
| Raporlama | Satış raporları ve performans analizi | Salt-okunur genel satış özeti mevcut |
| Denetim | Ajan ve onay kayıtlarının denetimi | Salt-okunur toplu denetim özeti mevcut |

## Bağımlılık ve otomatik etkinleştirme

- Bir ajanın başka bir ajana gerçekten ihtiyaç duyduğu bağımlılık, `AGENT_DEPENDENCIES` içinde açıkça tanımlanır.
- Satış Ajanı koordinatör olduğu için Firma, Ürün, Görüşme ve Teklif ajanları etkinleştirilirken otomatik etkinleştirilir.
- Denetim Ajanı diğer ajanların kayıtlarını okuyarak denetim yapar; diğer ajanların etkin olmasına ihtiyaç duymaz. Bu nedenle Denetim Ajanı etkinleştirildiğinde Teklif Ajanı veya diğer işlem ajanları otomatik açılmaz.
- Bir koordinatör kapatıldığında, başka iş akışlarının da kullanabileceği bağımlılık ajanları otomatik kapatılmaz.
- Her otomatik etkinleştirme `agent_auto_enabled` denetim olayıyla kaydedilir.
- Bağımlılıkların tamamı aynı veritabanı işlemi içinde etkinleştirilir; kısmi etkinleştirme yapılmaz.

## Güvenlik sınırları

- Güvenli ve açıkça tanımlanmış işlemler otomatik yürütülebilir.
- Teklif oluşturma gibi kritik iş etkisi olan adımlar mevcut onay akışından geçer.
- Ajanların etkin olması tek başına onay gerektiren bir işlemi onaysız yapma yetkisi vermez.
- Harici yapay zekâ çağrıları sunucu tarafında yapılandırılmış izin bayrağı ve API anahtarıyla sınırlandırılır; API anahtarı yoksa çağrı yapılmaz.
- Kullanıcının ana ekrandan açıkça başlattığı firma/görüşme kaydı arka plan otomasyonu değildir; işlem atomik olmalı ve ajan denetim izi üretmelidir.
- Kritik iş etkisi olan değişiklikler uygulamanın onay akışından geçer; sohbet modelinin çıktısı tek başına onay sayılmaz.

## Uygulama sırası

1. Görevlerin doğru ajana bağlanması ve arayüz etiketlerinin açıklığa kavuşturulması.
2. Açık bağımlılıkların otomatik etkinleştirilmesi.
3. Satış Ajanı koordinasyon akışının geliştirilmesi.
4. Raporlama ve Denetim kapsamlarının genişletilmesi.
5. İşlem ajanlarının gerçek iş akışlarının tamamlanması ve test edilmesi.

Bu belgedeki "mevcut" ifadeleri yalnızca tabloda belirtilen kodlanmış kapsamı ifade eder; henüz geliştirilmemiş görevler tamamlandı kabul edilmez.


## Ajan talimatlarının başlangıç kaynağı

- Bütün ajanlar için ilk okunacak dosya kök dizindeki `AGENTS.md` yönlendirme dosyasıdır.
- Yönlendirme dosyası her ajanı kendi `agents/{agent_id}.md` talimat dosyasına gönderir.
- Çalışma zamanı bu sırayı `app.agent_instructions.load_agent_instructions` ile uygular; kendi dosyasında izinli olmayan görev çalıştırılmaz.
- Her ajanın rol, yetki, yapabilecekleri, yapamayacakları ve görev listesi kendi dosyasında tutulur.


## OpenAI API entegrasyonu — ilk aşama

- Uygulama içi asistan, sunucu tarafında OpenAI Responses API ve resmi Python SDK üzerinden çalışır. Tarayıcı OpenAI API'sine doğrudan bağlanmaz.
- İstek yolu: oturum açmış arayüz → `POST /api/assistant/chat` → sunucu oturum/CSRF kontrolü → OpenAI Responses API → yalnızca uygulamanın tanımladığı araçlar → ajan yönlendiricisi ve ilgili ajanın Markdown talimatları → yanıt.
- `OPENAI_API_KEY` yalnızca Render ortam değişkeninde tutulur; kaynak kod, tarayıcı, GitHub ve loglara yazılmaz. `OPENAI_MODEL` model seçimini sunucu tarafında belirler; varsayılan `gpt-5.5`.
- Modelin araç çağrısı doğrudan veritabanına erişmez. `run_agent_task` sunucu tarafında sabit izin listesine, ajanın etkin olmasına, görev kaydına ve `AGENTS.md` + ajana ait talimat dosyasına bağlıdır.
- İlk aşamada yalnızca mevcut özet/rapor görevleri ve görüşmeden teklif hazırlama önizlemesi açılır. Teklif oluşturma önizlemedir; kalıcı teklif kaydı oluşturmaz. Firma/ürün/görüşme/teklif silme veya değiştirme araçları modele sunulmaz.
- Kritik işlemler için modelin onayı yeterli değildir. Uygulamanın mevcut onay kaydı, kullanıcı incelemesi, onay süresi ve onaylanan içerik özeti doğrulaması tamamlanmadan işlem yürütülmez. Mevcut görüşmeden teklif oluşturma onay akışı bu ayrımı örnekler.
- API anahtarı henüz Render'a eklenmedi. Bu nedenle canlı OpenAI çağrısı henüz yapılandırılmış veya doğrulanmış değildir. Anahtar kullanıcı tarafından Render test servisine güvenli biçimde eklendikten sonra uçtan uca bağlantı testi yapılmalıdır.
- API kullanımı ChatGPT aboneliğinden ayrıdır ve OpenAI API hesabında ayrıca ücretlendirilir.


## OpenAI API anahtarı — Render gizli değişkeni ve ek korumalar

- Anahtar yalnızca test servisi Render Dashboard → Environment içindeki `OPENAI_API_KEY` gizli değişkeninde tutulur. Anahtar GitHub'a, kaynak koda, tarayıcıya, sohbet yanıtına veya loglara konmaz.
- OpenAI için ayrı bir API Project ve yalnızca bu uygulamaya ait, mümkün olan en dar izinli ve harcama limiti izlenen bir Project API key kullanılmalıdır. ChatGPT aboneliği API ücretini kapsamaz.
- Anahtar kullanıcı tarafından Render arayüzüne girilir; sohbet veya destek mesajı üzerinden paylaşılmaz. Anahtar yenilenirse eski anahtar iptal edilir.
- Asistan uç noktası mevcut oturum + same-origin + CSRF kontrollerini korur; oturum başına süreç belleğinde dakikada en fazla 10 istek kabul eder.
- `previous_response_id` yalnızca aynı tarayıcı oturumunun sunucuda saklanan son yanıt kimliğiyle eşleşirse kabul edilir; istemci başka oturumun yanıt kimliğini kullanamaz. Sunucu yeniden başlatılırsa sohbet devamlılığı sıfırlanır.
- Kullanıcı mesajı 6.000 karakterle, model çıktısı 900 tokenla, araç çağrıları tur başına 6 ile sınırlandırılır. OpenAI istemcisi 30 saniye zaman aşımı ve bir yeniden deneme kullanır.
- Araç hatalarının iç ayrıntıları modele iletilmez; API anahtarı veya ham sağlayıcı hata metni kullanıcıya döndürülmez.
- Dakikalık sınır süreç belleğindedir; tek Render instance için koruyucu katmandır, dağıtık/çok instance limit garantisi değildir. Kalıcı ve çok instance limitleri gerekirse ortak depolama tabanlı rate limiter ayrıca eklenmelidir.
- Bu önlemler anahtarın Render hesap yetkileri ihlal edilirse açığa çıkma riskini ortadan kaldırmaz. Render hesap erişimi MFA ile korunmalı, erişim yalnızca gerekli kişilerle sınırlandırılmalı ve anahtar düzenli yenilenmelidir.
