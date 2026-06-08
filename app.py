
import streamlit as st
import pandas as pd
import re

st.set_page_config(layout="wide", page_title="OKVED Flavor Service v5.0")

st.title("OKVED Flavor Service v5.0 — SKU-based Classification")

ALLOWED_OKVED = ["11.07", "10.32", "11.03", "11.02"]

uploaded = st.file_uploader(
    "Загрузить XLS/XLSX/CSV",
    type=["xls", "xlsx", "csv"]
)

if uploaded is None:
    st.stop()

if uploaded.name.endswith(".csv"):
    df = pd.read_csv(uploaded)
elif uploaded.name.endswith(".xls"):
    df = pd.read_excel(uploaded, engine="xlrd")
else:
    df = pd.read_excel(uploaded, engine="openpyxl")

df.columns = [str(c).strip() for c in df.columns]

df = df[
    df["Тип заявителя"]
    .astype(str)
    .str.contains("Изготовитель", case=False, na=False)
]

def clean_text(x):

    if pd.isna(x):
        return ""

    x = str(x)

    x = re.sub(r'[«»“”"]', '', x)

    x = x.replace("\n", " ")
    x = x.replace("\r", " ")

    x = re.sub(r'\s+', ' ', x)

    return x.strip()

def extract_okved(row):

    cols = [c for c in df.columns if "оквэд" in c.lower()]

    txt = " ".join([
        str(row.get(c, "")) for c in cols
    ])

    return re.findall(r'\d+\.\d+(?:\.\d+)?', txt)

bad_okveds = set()

for _, row in df.iterrows():

    for okv in extract_okved(row):

        valid = False

        for allowed in ALLOWED_OKVED:
            if okv.startswith(allowed):
                valid = True
                break

        if not valid:
            bad_okveds.add(okv)

if bad_okveds:

    st.error("Обнаружены ОКВЭД вне разрешенного списка")

    st.dataframe(
        pd.DataFrame({
            "Неразрешенные ОКВЭД": sorted(bad_okveds)
        }),
        use_container_width=True
    )

    st.stop()

st.success("Все ОКВЭД разрешены")

EN_RU = {
    "cola": "кола",
    "lemon": "лимон",
    "lime": "лайм",
    "orange": "апельсин",
    "mango": "манго",
    "mangosteen": "мангостин",
    "bitter": "биттер",
    "grapefruit": "грейпфрут",
    "guava": "гуава",
    "mint": "мята",
    "strawberry": "клубника",
    "tea": "чай",
    "coffee": "кофе",
}

MORPH = {
    "биттер лемон": "биттер лимон",
    "вишни": "вишня",
    "грейпфрута": "грейпфрут",
    "гуавы": "гуава",
    "мяты": "мята",
    "зеленого яблока": "зеленое яблоко",
    "клубники": "клубника",
    "земляники": "земляника",
    "лесные ягоды": "лесная ягода",
    "лесных ягод": "лесная ягода",
    "лимона": "лимон",
    "лайма": "лайм",
    "мангостина": "мангостин",
    "манготина": "мангостин",
    "апельсина": "апельсин",
    "апельсиновый": "апельсин",
    "колы": "кола",
}

PAIR_RULES = {
    "лимон лайм": "лимон лайм",
    "лимон и лайм": "лимон лайм",
    "манго мангостин": "манго мангостин",
    "манго и мангостин": "манго мангостин",
    "клубника земляника": "клубника земляника",
    "гуава мята": "гуава мята",
}

def normalize_flavor(x):

    x = clean_text(x).lower()

    for k, v in EN_RU.items():
        x = x.replace(k, v)

    for k, v in MORPH.items():
        x = x.replace(k, v)

    x = x.replace("-", " ")
    x = x.replace("/", " ")
    x = x.replace(" и ", " ")

    x = re.sub(r'[^a-zа-я0-9\s]', ' ', x)
    x = re.sub(r'\s+', ' ', x)

    for k, v in PAIR_RULES.items():
        if k in x:
            x = v

    words = []

    for w in x.split():
        if w not in words:
            words.append(w)

    x = " ".join(words)

    return x.strip().title()

def canonical_key(x):

    x = normalize_flavor(x).lower()

    x = re.sub(r'[^a-zа-я0-9]+', '', x)

    return x

TEA_MARKERS = [
    "чай",
    "ice tea",
    "green tea",
    "black tea",
    "матча",
    "улун",
    "пуэр",
    "каркаде",
]

COFFEE_MARKERS = [
    "кофе",
    "латте",
    "капучино",
    "espresso",
    "эспрессо",
    "cold brew",
    "раф",
]

ENERGY_MARKERS = [
    "энергетичес",
    "energy drink",
    "тонизирующ",
]

ISOTONIC_MARKERS = [
    "изотони",
    "isotonic",
    "electrolyte",
]

def split_into_skus(text):

    text = clean_text(text)

    parts = re.split(r';|•|\n', text)

    result = []

    for p in parts:

        p = p.strip()

        if len(p) < 3:
            continue

        result.append(p)

    return result

def classify_sku(sku, okveds):

    sku_l = sku.lower()

    for m in ENERGY_MARKERS:
        if m in sku_l:
            return "Энергетические безалкогольные напитки"

    for m in ISOTONIC_MARKERS:
        if m in sku_l:
            return "Спортивные изотонические напитки"

    for m in TEA_MARKERS:
        if m in sku_l:
            return "Холодные чаи и кофейные напитки"

    for m in COFFEE_MARKERS:
        if m in sku_l:
            return "Холодные чаи и кофейные напитки"

    if any(x.startswith("11.07") for x in okveds):
        return "Газированные и негазированные сладкие напитки"

    if any(x.startswith("10.32") for x in okveds):

        if "морс" in sku_l:
            return "Морсы"

        if "концентрат" in sku_l:
            return "Концентраты"

        return "Фруктовые и овощные соки"

    if any(x.startswith("11.03") for x in okveds):

        if "сидр" in sku_l:
            return "Сидры"

        if "медовух" in sku_l:
            return "Медовуха"

        return "Плодово ягодные напитки"

    if any(x.startswith("11.02") for x in okveds):

        if "игрист" in sku_l or "шампан" in sku_l:
            return "Игристые и шампанское"

        return "Вина"

    return "Прочее"

def extract_flavor_from_sku(sku):

    txt = sku.lower()

    patterns = [
        r'со вкусом ([^,.;]+)',
        r'вкус ([^,.;]+)',
        r'аромат ([^,.;]+)',
        r'([а-яa-z\s]+чай[а-яa-z\s]*)',
    ]

    for p in patterns:

        matches = re.findall(p, txt, flags=re.IGNORECASE)

        if matches:

            flavor = normalize_flavor(matches[0])

            if len(flavor) > 1:
                return flavor

    txt = re.sub(
        r'напиток|безалкогольный|газированный|негазированный',
        '',
        txt
    )

    txt = normalize_flavor(txt)

    words = txt.split()

    if len(words) > 5:
        txt = " ".join(words[:5])

    return txt

rows = []

for _, row in df.iterrows():

    full_text = " ".join([
        str(row.get("Общее наименование продукции", "")),
        str(row.get("Наименование (обозначение) продукции", ""))
    ])

    skus = split_into_skus(full_text)

    okveds = extract_okved(row)

    for sku in skus:

        product_type = classify_sku(sku, okveds)

        flavor = extract_flavor_from_sku(sku)

        if len(flavor.strip()) < 2:
            continue

        rows.append({
            "Вид продукции": product_type,
            "Вкус": flavor,
            "CanonicalKey": (
                product_type.lower()
                + "|"
                + canonical_key(flavor)
            ),
            "Номер ДС": str(row["Регистрационный номер"])
        })

res = pd.DataFrame(rows)

final = (
    res.groupby("CanonicalKey")
    .agg({
        "Вид продукции": "first",
        "Вкус": "first",
        "Номер ДС": lambda x: ", ".join(sorted(set(x)))
    })
    .reset_index(drop=True)
)

final = final.sort_values(["Вид продукции", "Вкус"])

st.dataframe(
    final,
    use_container_width=True,
    height=900
)

csv = final.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Скачать CSV",
    csv,
    file_name="okved_flavors_v50.csv",
    mime="text/csv"
)
