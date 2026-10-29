# Teklif şablonu doğrulama kılavuzu

Bu kontrol, `feature/quote-template-file` dalındaki Excel teklif çıktısını doğrulamak içindir. **Canlı sürüm ve `main` dalı değiştirilmez.** Render'daki mevcut `satis-deneme` hizmeti yalnızca `main` dalını izliyor ve PR önizlemesi kapalı; bu nedenle bu değişiklikler canlı URL'de görünmez. Gerçek müşteri bilgileri girmeyin.

## 1. Otomatik test sonucu

GitHub Actions, bu dalda commit olduğunda ve `main` hedefine PR açıldığında otomatik testleri çalıştırır. PR içindeki **Checks** sekmesinde `Quote template validation` işinin yeşil olmasını bekleyin.

Testler şunları denetler:
- Şablondaki müşteri/teklif alanlarının doldurulması ve özgün satıcı/ticari koşulların korunması
- Miktar, birim fiyat, KDV formülleri ve toplamın yazıyla gösterimi
- İndirimli teklif ve 15 kalemi aşan teklif için açık hata
- Türkçe tutar yazımı

## 2. Bilgisayarda arayüz testi

Python 3.11 veya üzeri kurulu bilgisayarda:

1. GitHub'dan `feature/quote-template-file` dalını ZIP olarak indirin: https://github.com/amanebu-boop/satis-deneme/archive/refs/heads/feature/quote-template-file.zip
2. ZIP'i açın; klasörde terminal/PowerShell açın.
3. Kurulum:
   - Windows: `py -3.11 -m venv .venv` ardından `.\.venv\Scripts\Activate.ps1`
   - macOS/Linux: `python3 -m venv .venv` ardından `source .venv/bin/activate`
4. `python -m pip install -e ".[test]"` çalıştırın.
5. Deneme parolası ve API anahtarı belirleyin:
   - PowerShell: `$env:SALES_LOGIN_PASSWORD = "yalnizca-deneme-icin-parola"` ve `$env:SALES_API_TOKEN = "ayri-deneme-api-anahtari"`
   - macOS/Linux: `export SALES_LOGIN_PASSWORD='yalnizca-deneme-icin-parola'` ve `export SALES_API_TOKEN='ayri-deneme-api-anahtari'`
6. Önce `python -m pytest -q` çalıştırın. Testler geçerse `uvicorn app.main:app --host 127.0.0.1 --port 8000` başlatın.
7. Tarayıcıda http://127.0.0.1:8000 adresini açın. Az önce belirlediğiniz parola ile giriş yapın.

## 3. Uygulama içinde kontrol

1. **Firmalar** bölümünde gerçek olmayan bir test firması ekleyin (ör. “Örnek Sanayi A.Ş.”); adres, vergi dairesi/no, yetkili, telefon ve e-posta alanlarını doldurun.
2. **Teklifler** bölümünde bu test firmasına bağlı bir teklif oluşturun. İki kalem ekleyin; örneğin 2 × 100 EUR ve 1 × 50 EUR. Vergiyi %20, indirimi %0 bırakın.
3. Teklifi kaydedin.
4. Teklif listesinde **Önizle / PDF** bağlantısının açıldığını ve **Excel teklif** bağlantısının `.xlsx` dosyası indirdiğini doğrulayın.
5. İndirilen Excel dosyasını açın; firma bilgileri, tarih, kalemler, miktar/fiyat, ara toplam, KDV ve genel toplamı kontrol edin. Excel hesaplamayı açılışta yeniden yapabilir.
6. İndirim oranını sıfırdan farklı yapıp tekrar deneyin: Excel çıktısının indirim sessizce atlanmadan anlaşılır hata vermesi beklenir.
7. En fazla 15 kalem desteklenir; 16 kalemlik denemede açık hata beklenir.

## 4. Tamamlandı saymak için

- [ ] GitHub Actions testleri yeşil
- [ ] Deneme firması ve teklif kaydedilebildi
- [ ] Excel dosyası indirilebildi ve açıldı
- [ ] Excel alanları ve hesaplamalar kontrol edildi
- [ ] İndirim uyarısı beklenen şekilde çalıştı
- [ ] `main` ve canlı sürümün değişmediği doğrulandı

Bir kontrol başarısız olursa indirdiğiniz Excel dosyasını ve hata mesajını paylaşın; gerçek müşteri verilerini paylaşmayın.
