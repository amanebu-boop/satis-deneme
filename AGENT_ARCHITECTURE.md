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
| Satış | Süreç koordinasyonu ve ajanlar arası iş akışı | Koordinatör rolü tanımlı; yürütülebilir koordinasyon henüz geliştirilmedi |
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
- Harici yapay zekâ çağrıları ve otomatik iş verisi yazımı, ilgili güvenlik kuralları ayrıca tasarlanıp test edilene kadar kapalı kalır.

## Uygulama sırası

1. Görevlerin doğru ajana bağlanması ve arayüz etiketlerinin açıklığa kavuşturulması.
2. Açık bağımlılıkların otomatik etkinleştirilmesi.
3. Satış Ajanı koordinasyon akışının geliştirilmesi.
4. Raporlama ve Denetim kapsamlarının genişletilmesi.
5. İşlem ajanlarının gerçek iş akışlarının tamamlanması ve test edilmesi.

Bu belgedeki "mevcut" ifadeleri yalnızca tabloda belirtilen kodlanmış kapsamı ifade eder; henüz geliştirilmemiş görevler tamamlandı kabul edilmez.
