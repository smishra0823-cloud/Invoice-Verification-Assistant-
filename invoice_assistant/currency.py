"""Detect printed currency evidence without guessing from addresses or IBANs."""
import re
from decimal import Decimal, InvalidOperation

# Display metadata, not exchange rates. No conversion is performed.
CURRENCIES = {
    "INR": ("Indian rupee", "₹"), "USD": ("US dollar", "US$"),
    "EUR": ("Euro", "€"), "GBP": ("Pound sterling", "£"),
    "CAD": ("Canadian dollar", "C$"), "AUD": ("Australian dollar", "A$"),
    "NZD": ("New Zealand dollar", "NZ$"), "SGD": ("Singapore dollar", "S$"),
    "HKD": ("Hong Kong dollar", "HK$"), "JPY": ("Japanese yen", "JP¥"),
    "CNY": ("Chinese yuan", "CN¥"), "KRW": ("South Korean won", "₩"),
    "CHF": ("Swiss franc", "CHF"), "AED": ("UAE dirham", "AED"),
    "SAR": ("Saudi riyal", "SAR"), "KWD": ("Kuwaiti dinar", "KWD"),
    "BHD": ("Bahraini dinar", "BHD"), "OMR": ("Omani rial", "OMR"),
    "JOD": ("Jordanian dinar", "JOD"), "PKR": ("Pakistani rupee", "PKR"),
    "NPR": ("Nepalese rupee", "NPR"), "LKR": ("Sri Lankan rupee", "LKR"),
    "BDT": ("Bangladeshi taka", "BDT"), "IDR": ("Indonesian rupiah", "IDR"),
    "THB": ("Thai baht", "฿"), "VND": ("Vietnamese dong", "₫"),
    "ZAR": ("South African rand", "ZAR"), "RUB": ("Russian ruble", "₽"),
    "TRY": ("Turkish lira", "₺"),
}
NAMES = {
    "INR": r"Indian rupees?", "USD": r"(?:US|U\.S\.|United States|American) dollars?",
    "EUR": r"euros?", "GBP": r"(?:pounds? sterling|British pounds?)",
    "CAD": r"Canadian dollars?", "AUD": r"Australian dollars?",
    "NZD": r"New Zealand dollars?", "SGD": r"Singapore dollars?",
    "HKD": r"Hong Kong dollars?", "JPY": r"(?:Japanese yen|yen)",
    "CNY": r"(?:Chinese yuan|yuan|renminbi)", "CHF": r"Swiss francs?",
    "AED": r"(?:UAE|Emirati) dirhams?", "SAR": r"Saudi riyals?",
    "KWD": r"Kuwaiti dinars?", "BHD": r"Bahraini dinars?",
    "OMR": r"Omani rials?", "JOD": r"Jordanian dinars?",
    "PKR": r"Pakistani rupees?", "NPR": r"Nepalese rupees?",
    "LKR": r"Sri Lankan rupees?", "KRW": r"South Korean won",
}


def currency_precision(code):
    return 0 if code in {"JPY", "KRW", "VND"} else 3 if code in {"KWD", "BHD", "OMR", "JOD"} else 2


def detect_currency(text):
    # Currency-like fragments inside identifiers are not monetary evidence.
    text = re.sub(r"(?im)^\s*(?:(?:invoice|bill)\s*(?:number|no\.?|id|#)(?!\w)\s*[:#\-]?|(?:reference|order number)\s*[:#])\s*\S+", "", text)
    exact, groups, evidence = set(), [], []

    def found(code, value):
        value = " ".join(value.split())
        exact.add(code)
        if value not in evidence:
            evidence.append(value)

    if text.strip().upper() in CURRENCIES:
        found(text.strip().upper(), text.strip())

    for code in CURRENCIES:
        if code == "TRY" and not re.search(r"currency\s*[:=\-]?\s*TRY\b|\bTRY\s*\d|\d\s*TRY\b", text, re.I):
            continue
        # Lowercase words such as "try" and "sar" are not currency evidence.
        pattern = r"(?<![A-Za-z])" + code + r"(?![A-Za-z])"
        for match in re.finditer(pattern, text):
            found(code, match[0])
        for match in re.finditer(r"(?:currency\s*[:=\-]?\s*|(?<=\d)\s*)" + code + r"\b|\b" + code + r"\s*(?=\d)", text, re.I):
            found(code, match[0])
    for code, pattern in NAMES.items():
        for match in re.finditer(r"\b(?:" + pattern + r")\b", text, re.I):
            found(code, match[0])
    remaining = text
    qualified = {"USD": r"(?:US|U\.S\.)\s*\$", "CAD": r"(?:CA|C)\s*\$", "AUD": r"(?:AU|A)\s*\$", "NZD": r"NZ\s*\$", "SGD": r"(?:SG|S)\s*\$", "HKD": r"HK\s*\$", "JPY": r"JP\s*¥", "CNY": r"CN\s*¥"}
    for code, pattern in qualified.items():
        for match in re.finditer(r"(?<![A-Za-z])" + pattern, remaining, re.I):
            found(code, match[0])
        remaining = re.sub(r"(?<![A-Za-z])" + pattern, "", remaining, flags=re.I)
    for symbol, code in {"₹": "INR", "€": "EUR", "£": "GBP", "₩": "KRW", "฿": "THB", "₫": "VND", "₽": "RUB", "₺": "TRY"}.items():
        if symbol in remaining:
            found(code, symbol)
    for pattern, symbol, codes in [
        (r"\$|\bdollars?\b", "$", {"USD", "CAD", "AUD", "NZD", "SGD", "HKD"}),
        (r"¥", "¥", {"JPY", "CNY"}),
        (r"\bRs\.?\b|\brupees?\b", "Rs", {"INR", "PKR", "NPR", "LKR"}),
    ]:
        if re.search(pattern, remaining, re.I):
            groups.append((symbol, codes))
            if symbol not in evidence:
                evidence.append(symbol)
    mixed = len(exact) > 1 or (exact and any(not exact <= codes for _, codes in groups))
    if mixed:
        candidates = exact if len(exact) > 1 else exact | set().union(*(codes for _, codes in groups))
        return dict(currency=None, currency_symbol=None, currency_status="mixed", currency_candidates=sorted(candidates), currency_evidence=evidence[:12])
    if exact:
        code = next(iter(exact))
        return dict(currency=code, currency_symbol=CURRENCIES[code][1], currency_status="detected", currency_candidates=[code], currency_evidence=evidence[:12])
    if groups:
        candidates = set.intersection(*(codes for _, codes in groups))
        return dict(currency=None, currency_symbol=groups[0][0] if candidates else None, currency_status="ambiguous" if candidates else "mixed", currency_candidates=sorted(candidates or set.union(*(codes for _, codes in groups))), currency_evidence=evidence[:12])
    return dict(currency=None, currency_symbol=None, currency_status="unknown", currency_candidates=[], currency_evidence=[])


def set_currency(invoice, text, manual=False):
    values = detect_currency(text)
    if manual and values["currency_status"] == "detected":
        values["currency_status"] = "confirmed"
    for name, value in values.items():
        setattr(invoice, name, value)


def strip_currency(value):
    """Strip printed currency decorations from an individual numeric cell."""
    codes = "|".join(CURRENCIES)
    decoration = r"(?:(?:US|U\.S\.|CA|AU|NZ|SG|HK|C|A|S)\s*\$|(?:JP|CN)\s*¥|₹|\$|€|£|¥|₩|₽|₺|฿|₫|Rs\.?|" + codes + ")"
    value = re.sub(r"^\s*" + decoration + r"\s*", "", str(value), flags=re.I)
    return re.sub(r"\s*" + decoration + r"\s*$", "", value, flags=re.I).strip()


def currency_label(invoice):
    if invoice.currency:
        name, symbol = CURRENCIES.get(invoice.currency, (invoice.currency, invoice.currency))
        return f"{name} ({invoice.currency}) · {symbol}"
    if invoice.currency_status == "mixed":
        return "Multiple currencies detected — separate review needed"
    if invoice.currency_symbol:
        family = {"$": "Dollar", "¥": "Yen / yuan", "Rs": "Rupee"}.get(invoice.currency_symbol, "Currency")
        return f"{family} ({invoice.currency_symbol}) · exact currency not specified"
    return "Currency not read — enter a code or symbol if known"


def format_money(value, invoice):
    if value is None:
        return None
    try:
        amount = Decimal(value)
        if not amount.is_finite():
            return str(value)
        precision = max(currency_precision(invoice.currency), min(6, max(0, -amount.as_tuple().exponent)))
        numeric = f"{amount:,.{precision}f}"
    except (InvalidOperation, ValueError):
        return str(value)
    prefix = CURRENCIES.get(invoice.currency, ("", invoice.currency or ""))[1] if invoice.currency else invoice.currency_symbol or ""
    return f"{prefix} {numeric}".strip()
