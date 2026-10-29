from html import escape
from typing import Any


def render_quotation_html(quotation: dict[str, Any], company: dict[str, Any] | None) -> str:
    """Render a saved draft quotation as a self-contained, printable HTML document."""
    company_name = escape((company or {}).get("name") or "Firma belirtilmedi")
    website = escape((company or {}).get("website") or "")
    quote_id = escape(str(quotation["id"]))
    created_at = escape(str(quotation["created_at"])[:10])
    currency = escape(str(quotation["currency"]))
    rows = []
    for line in quotation.get("lines", []):
        rows.append(
            "<tr>"
            f"<td>{escape(str(line.get('description', '')))}</td>"
            f"<td class=\"num\">{escape(str(line.get('quantity', '')))}</td>"
            f"<td class=\"num\">{escape(str(line.get('unit_price', '')))} {currency}</td>"
            f"<td class=\"num\">{escape(str(line.get('line_total', '')))} {currency}</td>"
            "</tr>"
        )
    line_rows = "\n".join(rows)
    tax_rate = escape(str((float(quotation.get("tax_rate", 0) or 0) * 100)))
    subtotal = escape(str(quotation.get("subtotal", "0")))
    tax = escape(str(quotation.get("tax_amount", "0")))
    total = escape(str(quotation.get("total", "0")))
    website_row = f"<p>{website}</p>" if website else ""
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Teklif taslağı — {company_name}</title>
<style>
body{{font:14px/1.5 system-ui,sans-serif;color:#17202d;max-width:900px;margin:36px auto;padding:0 24px}}
header{{display:flex;justify-content:space-between;gap:24px;border-bottom:2px solid #17202d;padding-bottom:18px}}
h1{{margin:0 0 8px;font-size:26px}}.muted{{color:#667085}}table{{width:100%;border-collapse:collapse;margin-top:28px}}
th,td{{border-bottom:1px solid #dfe3ea;padding:10px;text-align:left}}th{{background:#f5f6f8}}
.num{{text-align:right;white-space:nowrap}}.totals{{margin:24px 0 0 auto;max-width:340px}}
.total{{font-size:20px;font-weight:750;border-top:2px solid #17202d;padding-top:10px}}
button{{border:0;border-radius:8px;background:#335cff;color:white;padding:10px 16px;font:inherit;cursor:pointer}}
@media print{{body{{margin:0;max-width:none}}.print-action{{display:none}}}}
</style>
</head>
<body>
<div class="print-action"><button onclick="window.print()">Yazdır / PDF olarak kaydet</button>
<p class="muted">Bu belge bir teklif taslağıdır; onaylanmış teklif veya fatura değildir.</p></div>
<header><div><h1>Teklif taslağı</h1><strong>{company_name}</strong>{website_row}</div>
<div><p><strong>Belge no:</strong> {quote_id}</p><p><strong>Tarih:</strong> {created_at}</p><p><strong>Durum:</strong> Taslak</p></div></header>
<table><thead><tr><th>Açıklama</th><th class="num">Miktar</th><th class="num">Birim fiyat</th><th class="num">Tutar</th></tr></thead>
<tbody>{line_rows}</tbody></table>
<div class="totals">
<p>Ara toplam: <strong>{subtotal} {currency}</strong></p>
<p>KDV/vergi (%{tax_rate}): <strong>{tax} {currency}</strong></p>
<p class="total">Genel toplam: {total} {currency}</p>
</div>
</body></html>"""
