# Ajan Yönlendirme Dosyası

Her ajan herhangi bir göreve başlamadan önce bu dosyayı, ardından yalnızca kendisine ait talimat dosyasını okumalıdır.

## Zorunlu başlangıç sırası
1. Ajan kimliğini belirle.
2. Aşağıdaki listeden yalnızca kendi dosyanı aç.
3. Dosyanın `agent_id` bilgisini doğrula.
4. Kendi dosyandaki rolü, izinleri, yasakları, bağımlılıkları, onay koşullarını ve görev listesini oku.
5. İstenen görev izinli görevler listesinde değilse çalıştırma.
6. Bağımlı ajanı yalnızca açıkça tanımlıysa kullan; ilgisiz ajanları etkinleştirme.
7. Kritik işlemlerde onay tamamlanmadan veri değiştirme.
8. Dosya yoksa, okunamıyorsa veya çelişki varsa güvenli biçimde dur ve bildir.

## Ajan talimat dosyaları
| Kimlik | Dosya | Sorumluluk |
|---|---|---|
| `company` | [agents/company.md](agents/company.md) | Firma ve yetkili kayıtları |
| `product` | [agents/product.md](agents/product.md) | Ürün kataloğu ve opsiyonlar |
| `meeting` | [agents/meeting.md](agents/meeting.md) | Görüşmeler ve görüşme ürünleri |
| `quotation` | [agents/quotation.md](agents/quotation.md) | Teklif taslağı ve onay |
| `warehouse` | [agents/warehouse.md](agents/warehouse.md) | Depo ve stok |
| `sales` | [agents/sales.md](agents/sales.md) | Satış koordinasyonu |
| `reporting` | [agents/reporting.md](agents/reporting.md) | Satış raporları |
| `audit` | [agents/audit.md](agents/audit.md) | Ajan ve işlem denetimi |

## Bağlayıcılık
Belge politikası ve uygulamadaki güvenlik kontrolü birlikte sağlanmalıdır. Markdown'da yazması tek başına kodun izin vermediği bir işlemi yetkilendirmez; kodun izin vermesi de ajanın kendi talimatında yasaklanan işi yapmasına izin vermez.