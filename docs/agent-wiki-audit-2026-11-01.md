# Ajan ve LLM Wiki denetim düzeltmeleri — 2026-11-01

Kapsam: yalnızca feature/agent-foundation. main ve canlı Render servisine değişiklik gönderilmedi.

1. SAFE_TASKS, agent_runtime.HANDLERS ile hizalandı. Firma veri kalitesi, katalog sağlığı, görüşme takip incelemesi, dönem raporu ve denetim anomalisi görevleri asistanın izin listesine eklendi.
2. Görüşme Ajanı talimatı, mevcut metin tabanlı AI yakalama akışıyla tutarlı hale getirildi; ses kaydı, ses yükleme ve transkripsiyon olmadığı açıkça belirtildi.
3. LLM Wiki tam kaynak yenilemesi her aramada değil, 30 saniyelik aralıkla yapılır. Değişmeyen kayıtlar içerik hash'iyle yeniden yazılmaz.
4. Uzun asistan sohbetleri 8 kullanıcı turuyla sınırlandı; yeni sohbet gerektiren 409 yanıtı verilir. Araç çağrısı sınırı koordinatör görevleri için 8'e çıkarıldı.
5. Görüşme yakalama AI kullanım metaverisi, kalıcı firma/görüşme kaydından önce ölçülür.
6. Asistan ve görüşme yakalama akışında kullanım ölçümü başarısız veya eksikse işlem fail-closed davranır; asistan yeni araç/model turuna devam etmez, görüşme kaydı oluşturulmaz.
7. LLM Wiki araması SQLite FTS5/BM25 kullanır; FTS5 olmayan sistemlerde yerel sözcük eşleştirmesine döner. Harici embedding çağrısı yoktur.
8. İlgili satış/ürün/teknik/takip sorularında Wiki araması model API çağrısından önce sunucu tarafında yapılır. Wiki araması için ayrı model turu kaldırılmıştır.

Doğrulama:
- Python CI: 131 passed, 1 skipped, 1 warning. Uyarı Starlette TestClient/httpx deprecation uyarısıdır.
- Teklif şablonu / LibreOffice / Docker CI, son kontrol anında Docker image build adımındaydı; tamamlandı olarak işaretlenmedi.
- Render test servisi srv-dbhssmd9el5s738cnr9g, commit 0eba7d0e3a57986c5dd440cc21b1832a9911b9d9 için live.
- Gerçek OpenAI API çağrısı yapılmadı; token ölçümü otomatik testlerde sahte yanıtlarla doğrulandı.
- PR #11 açık/draft. main ve production Render değiştirilmedi.
