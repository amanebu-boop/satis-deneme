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
| Firma | Firma ve yetkili kayıtları | Rehber özeti + eksik sektör/şehir/adres/telefon ve yinelenen ad kalite kontrolü |
| Ürün | Ürün kataloğu ve opsiyonlar | Katalog özeti + açıklama/tam sayı fiyat/para birimi/opsiyon bağlantısı kalite kontrolü |
| Görüşme | Görüşme ve görüşme ürünleri | Görüşme özeti + gecikmiş ve 7 gün içindeki açık takip görevleri + katalog bağlantısı/miktar/fiyat/para birimi kontrolü |
| Teklif | Görüşmeden teklif taslağı, teklif süreci ve onaylı teklif oluşturma | Taslak önizleme + onaylı oluşturma akışı + firma/satır/ara toplam/KDV/genel toplam bütünlük kontrolü + teklif süreci özeti |
| Depo | Stok ve depo süreçleri | Kullanılabilir görev yok; etkinleştirilmez |
| Satış | Süreç koordinasyonu ve ajanlar arası iş akışı | İzinli görev kataloğuyla salt-okunur koordinasyon mevcut; üst çalışma kaydı alt görevleri parent_run_id ile ilişkilendirir |
| Raporlama | Satış raporları ve performans analizi | Genel özet + tarih aralığında görüşme/teklif sayıları ve para birimine göre teklif toplamları |
| Denetim | Ajan ve onay kayıtlarının denetimi | Toplu özet + başarısız/engellenmiş görev ve süresi geçmiş onay anomalileri |

## Bağımlılık ve otomatik etkinleştirme

- Bir ajanın başka bir ajana gerçekten ihtiyaç duyduğu bağımlılık, `AGENT_DEPENDENCIES` içinde açıkça tanımlanır.
- Satış Ajanı koordinatör olduğu için Firma, Ürün, Görüşme, Teklif ve Raporlama ajanları etkinleştirilirken otomatik etkinleştirilir.
- Denetim Ajanı diğer ajanların kayıtlarını okuyarak denetim yapar; diğer ajanların etkin olmasına ihtiyaç duymaz. Bu nedenle Denetim Ajanı etkinleştirildiğinde Teklif Ajanı veya diğer işlem ajanları otomatik açılmaz.
- Bir koordinatör kapatıldığında, başka iş akışlarının da kullanabileceği bağımlılık ajanları otomatik kapatılmaz.
- Her otomatik etkinleştirme `agent_auto_enabled` denetim olayıyla kaydedilir.
- Bağımlılıkların tamamı aynı veritabanı işlemi içinde etkinleştirilir; kısmi etkinleştirme yapılmaz.

## Güvenlik sınırları

- Güvenli ve açıkça tanımlanmış işlemler otomatik yürütülebilir.
- Teklif oluşturma gibi kritik iş etkisi olan adımlar mevcut onay akışından geçer.
- Ajanların etkin olması tek başına onay gerektiren bir işlemi onaysız yapma yetkisi vermez.
- Harici yapay zekâ çağrıları sunucu tarafında yapılandırılmış izin bayrağı ve API anahtarıyla sınırlandırılır; API anahtarı yoksa çağrı yapılmaz.
- Kullanıcının ana ekrandan açıkça başlattığı firma/görüşme kaydı arka plan otomasyonu değildir; işlem atomik olmalı ve tamamlanmış dış ajan işi + denetim izi üretmelidir. `automatic_business_writes_enabled` kapalıyken arka plan/insansız iş verisi yazma görevi yoktur; ana ekranın açık kullanıcı eylemi ayrı tutulur.
- Kritik iş etkisi olan değişiklikler uygulamanın onay akışından geçer; sohbet modelinin çıktısı tek başına onay sayılmaz.

## Kalan geliştirme sırası

1. Depo ajanını ancak gerçek stok kartı, depo hareketi ve stok bakiyesi veri modeli eklendiğinde etkinleştirmek.
2. Raporlama için dönüşüm oranı ve satış hedefi raporlarını, kaynak veri alanları doğrulandıktan sonra eklemek.
3. Wiki semantik retrieval ihtiyacını ancak gerçek sorgu kalitesi ve veri hacmi ölçümleri bunu gerektirirse değerlendirmek; mevcut yerel FTS5/BM25 ve sınırlandırılmış lexical yedek arama korunur.

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
- Modelin araç çağrısı doğrudan veritabanına erişmez. `run_agent_task` sunucu tarafında sabit izin listesine, ajanın etkin olmasına, görev kaydına ve `AGENTS.md` + ajana ait talimat dosyasına bağlıdır. Ajan talimatı bir önceki model turunda okunmadan aynı turda görev çalıştırılamaz.
- Asistanın tek kullanıcı arayüzü ana ekrandadır. Ayrı `/assistant` sayfası kaldırılmıştır; sohbet API'si yalnızca ana ekrandaki arayüz tarafından çağrılır.
- İzinli özet/rapor görevleri, görüşmeden teklif önizlemesi ve yerel LLM Wiki araması açılır. Teklifin kalıcı oluşturulması ayrı, onaylı işlem akışıdır. Firma/ürün/görüşme/teklif silme araçları modele sunulmaz.
- LLM Wiki; ürün kataloğu ve bağlı opsiyonları, firma temel bilgileri, görüşme geçmişi, teklif satırları, takip görevleri ve Markdown satış/ajan dokümanlarını SQLite FTS5 üzerinde BM25 sıralamasıyla indeksler; FTS5 kullanılamazsa sözcüksel yedek arama kullanılır. Ana ekrandan PDF/DOCX/TXT/MD belge alır ve uzun belgeleri parçalara böler. Sadece en alakalı en fazla üç sonuç, belge başına en fazla 900 karakterle modele bağlam olarak verilir; arka plan LLM çağrısı veya harici embedding isteği yapılmaz. Tam indeks uzlaştırması en fazla 180 saniyede bir yapılır ve eşzamanlı yenileme kilitlenir.
- İndeks, silinen ürün/firma/görüşme/teklif/takip kayıtlarını arama dışı bırakır. Firma iletişim alanları Wiki indeksine alınmaz; görüşme notlarında e-posta, telefon, IBAN ve 10–11 haneli vergi/kimlik numarası biçimleri maskelenir.
- Kritik işlemler için modelin onayı yeterli değildir. Uygulamanın mevcut onay kaydı, kullanıcı incelemesi, onay süresi ve onaylanan içerik özeti doğrulaması tamamlanmadan işlem yürütülmez. Mevcut görüşmeden teklif oluşturma onay akışı bu ayrımı örnekler.
- Gerçek OpenAI bağlantısının çalıştığı, yalnızca Render test servisine anahtar eklendikten ve uçtan uca çağrı başarıyla tamamlandıktan sonra doğrulanmış sayılır. Kaynak kodda anahtar bulunmaz.
- API kullanımı ChatGPT aboneliğinden ayrıdır ve OpenAI API hesabında ayrıca ücretlendirilir.


## OpenAI API anahtarı — Render gizli değişkeni ve ek korumalar

- Anahtar yalnızca test servisi Render Dashboard → Environment içindeki `OPENAI_API_KEY` gizli değişkeninde tutulur. Anahtar GitHub'a, kaynak koda, tarayıcıya, sohbet yanıtına veya loglara konmaz.
- OpenAI için ayrı bir API Project ve yalnızca bu uygulamaya ait, mümkün olan en dar izinli ve harcama limiti izlenen bir Project API key kullanılmalıdır. ChatGPT aboneliği API ücretini kapsamaz.
- Anahtar kullanıcı tarafından Render arayüzüne girilir; sohbet veya destek mesajı üzerinden paylaşılmaz. Anahtar yenilenirse eski anahtar iptal edilir.
- Asistan uç noktası mevcut oturum + same-origin + CSRF kontrollerini korur; oturum başına süreç belleğinde dakikada en fazla 10 istek kabul eder.
- `previous_response_id` yalnızca aynı tarayıcı oturumunun sunucuda saklanan son yanıt kimliğiyle eşleşirse kabul edilir; istemci başka oturumun yanıt kimliğini kullanamaz. Sunucu yeniden başlatılırsa sohbet devamlılığı sıfırlanır.
- Kullanıcı mesajı 6.000 karakterle, model çıktısı 700 tokenla, araç çağrıları kullanıcı isteği başına 8 ile sınırlandırılır; konuşma geçmişi en fazla 8 kullanıcı turuyla sınırlandırılır. Görüşme kayıt isteği modeline tüm katalog yerine metinle ilişkili en fazla 12 firma ve 20 ürün adayı gönderilir; ilişkili ana/alt ürünler de korunur. OpenAI istemcisi 30 saniye zaman aşımı ve otomatik yeniden deneme olmadan çalışır.
- Araç hatalarının iç ayrıntıları modele iletilmez; API anahtarı veya ham sağlayıcı hata metni kullanıcıya döndürülmez.
- İsteğe bağlı günlük harcama sınırı `OPENAI_DAILY_BUDGET_USD` Render gizli değişkeniyle belirlenir; sınır aşıldığında veya günlük kayıtlarda fiyatı bilinmeyen istek varsa yeni OpenAI çağrısı durdurulur. Bu değişken ayarlanmazsa uygulama içi günlük harcama freni etkin değildir. Dakikalık sınır süreç belleğindedir; tek Render instance için koruyucu katmandır, dağıtık/çok instance limit garantisi değildir. Kalıcı ve çok instance limitleri gerekirse ortak depolama tabanlı rate limiter ayrıca eklenmelidir.
- Bu önlemler anahtarın Render hesap yetkileri ihlal edilirse açığa çıkma riskini ortadan kaldırmaz. Render hesap erişimi MFA ile korunmalı, erişim yalnızca gerekli kişilerle sınırlandırılmalı ve anahtar düzenli yenilenmelidir.
