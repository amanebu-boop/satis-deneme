# Sales AI Platform

Yerel bilgisayarda tek kullanıcı için geliştirilmekte olan satış çalışma alanı: firma, görüşme, taslak teklif ve Word/Excel/PDF şablonları.

> **Durum:** Deneme prototipi. Google/OIDC girişi yoktur; yerel parola girişi kullanılır. Gerçek müşteri verisi veya gerçek ticari teklifler için henüz kullanmayın. Telefonla aynı Wi-Fi üzerinden denemek için sunucuyu `0.0.0.0` üzerinde başlatabilirsiniz; yalnızca güvendiğiniz ev/özel Wi-Fi ağında kullanın ve internetten erişime açmayın.

## Hızlı başlatma

Adım adım kurulum için [Yerel deneme kılavuzuna](docs/operations/quickstart.md) bakın. Python 3.11+ gerekir.

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
export SALES_LOGIN_PASSWORD='yalnizca-deneme-icin-uzun-bir-parola'
export SALES_API_TOKEN='ayri-uzun-deneme-api-anahtari'
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
$env:SALES_LOGIN_PASSWORD = "yalnizca-deneme-icin-uzun-bir-parola"
$env:SALES_API_TOKEN = "ayri-uzun-deneme-api-anahtari"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Tarayıcıda `http://127.0.0.1:8000/` adresini açın ve belirlediğiniz yerel parolayla giriş yapın. Sunucuyu durdurmak için terminalde `Ctrl+C`.

## Denenebilen alanlar

- **Firmalar, görüşmeler ve teklifler:** aynı tarayıcı oturumundan kullanılabilen yerel çalışma akışları; teklifler taslak olarak kaydedilir. Ersen Makina teklif şablonu Excel olarak indirilebilir; sunucuda LibreOffice Calc kuruluysa aynı şablon PDF’ye de dönüştürülür.
- **Belge şablonları:** `.docx`, `.xlsx` veya doldurulabilir AcroForm `.pdf` yükleyin. Word/Excel alanlarını `{{company_name}}`, `{{quote_total}}` gibi yer tutucularla belirtin; ekranda algılanan alanları doldurup ayrı bir dosya oluşturun.
- **Veri saklama:** SQLite varsayılan olarak `data/sales.db` dosyasına; şablonlar `data/documents/` klasörüne yazılır. İhtiyaç olursa `SALES_DATABASE_PATH` ve `SALES_DOCUMENTS_PATH` ile konumları değiştirin.

Ürün kataloğu ve bazı özet ekranları prototip aşamasında örnek veri gösterebilir. Vergi/iskonto kuralları, teklif onayı, otomatik belge alan eşleştirme ve PDF koordinatlarına göre yazma bu sürümde tamamlanmış değildir.

## Testler

```bash
python -m pytest -q
```

Daha ayrıntılı sınırlar ve yedekleme için [güvenlik notları](docs/security/document-templates.md) ve [yerel çalıştırma/yedekleme](docs/operations/hosting-and-backups.md) sayfalarına bakın. Telefon ve bilgisayar aynı Wi-Fi ağında olmalı. Bilgisayarın yerel IP adresini bulun (`ipconfig` / `hostname -I` / `ipconfig getifaddr en0`) ve telefonda `http://BILGISAYAR_IP:8000/` açın. Bu deneme modu HTTP kullandığından aynı Wi-Fi ağındaki trafik şifrelenmez; halka açık Wi-Fi kullanmayın, modemden port yönlendirmeyin ve gerçek müşteri verisi girmeyin.
