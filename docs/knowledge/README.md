# LLM Wiki bilgi kaynakları

Bu klasör, Satış Asistanı'nın arayabileceği Ersen Makina teknik bilgi ve satış dokümanları içindir.

- Teknik makine katalogları, kullanım kılavuzları ve teknik föyleri Satış Asistanı ana ekranındaki belge alanından PDF, DOCX, TXT veya MD olarak yükleyin. Kaynak Markdown dosyaları ayrıca bu klasörde tutulabilir.
- Ürün ve opsiyonların güncel adı, SKU ve fiyat bilgisi ürün kataloğundan okunur; kopya fiyat listesi tutmayın.
- Satış kuralları ve ajan yetkileri kök `AGENTS.md`, `AGENT_ARCHITECTURE.md` ve `agents/*.md` dosyalarından alınır.
- Geçmiş görüşmeler, firma adı, tarih, konu, not ve görüşme ürünlerinden; teklifler, teklif satırları ve takip görevleri de yerel SQLite indeksine alınır. Firma iletişim alanları ve vergi numaraları indekslenmez; görüşme notlarında e-posta ve telefon biçimleri maskelenir.
- Wiki araması yerel sözcük eşleştirmesi kullanır; harici embedding isteği veya arka plan LLM çağrısı yapmaz. Yalnızca kullanıcı Satış Asistanı'na soru sorduğunda en alakalı birkaç kayıt modele bağlam olarak gönderilir.
- Satış Asistanı ana ekranındaki belge alanı PDF, DOCX, TXT ve MD dosyalarını kabul eder; metin çıkarılır ve dosyanın kendisi saklanmadan SQLite Wiki indeksine eklenir. 8 MB dosya, 100 sayfalık PDF ve 200.000 karakter sınırı vardır. Daha uzun metinlerde kesilme kullanıcıya bildirilir. Metinsiz/taranmış PDF dosyaları OCR olmadan içeri alınmaz.
