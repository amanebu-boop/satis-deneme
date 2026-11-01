# LLM Wiki bilgi kaynakları

Bu klasör, Satış Asistanı'nın arayabileceği Ersen Makina teknik bilgi ve satış dokümanları içindir.

- Teknik makine katalogları, kullanım kılavuzları ve teknik föyleri Markdown biçiminde bu klasöre ekleyin.
- Ürün ve opsiyonların güncel adı, SKU ve fiyat bilgisi ürün kataloğundan okunur; kopya fiyat listesi tutmayın.
- Satış kuralları ve ajan yetkileri kök `AGENTS.md`, `AGENT_ARCHITECTURE.md` ve `agents/*.md` dosyalarından alınır.
- Geçmiş görüşmeler, firma adı, tarih, konu, not ve görüşme ürünlerinden yerel SQLite indeksine alınır. İletişim bilgileri ve vergi numaraları Wiki indeksine eklenmez.
- Wiki araması yerel sözcük eşleştirmesi kullanır; harici embedding isteği veya arka plan LLM çağrısı yapmaz. Yalnızca kullanıcı Satış Asistanı'na soru sorduğunda en alakalı birkaç kayıt modele bağlam olarak gönderilir.
- Henüz PDF/DOCX dosyalarını otomatik ayrıştırma veya yükleme arayüzü yoktur. Bu tür teknik dokümanlar Markdown'a dönüştürülerek buraya eklenmelidir; otomatik belge alımı ayrı bir geliştirme adımıdır.
