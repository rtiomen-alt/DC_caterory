
import streamlit as st
import pandas as pd
import re

st.set_page_config(layout="wide", page_title="OKVED Flavor Service v4.1")

st.title("OKVED Flavor Service v4.1")

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

def clean_text(x):

    if pd.isna(x):
        return ""

    x = str(x).lower()

    x = re.sub(r'[«»"“”]', '', x)
    x = re.sub(r'\([^)]*\)', '', x)

    x = x.replace("-", " ")
    x = x.replace("/", " ")

    x = re.sub(r'\s+', ' ', x)

    return x.strip()

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
}

MORPH = {
    "биттер лемон": "биттер лимон",
    "вишни": "вишня",
    "вишневый": "вишня",
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
    "апельсиновый": "апельсин",
    "апельсина": "апельсин",
    "апельсинка": "апельсин",
    "колы": "кола",
}

PAIR_RULES = {
    "лимон лайм": "лимон лайм",
    "лимон и лайм": "лимон лайм",
    "манго мангостин": "манго мангостин",
    "манго и мангостин": "манго мангостин",
    "клубника земляника": "клубника земляника",
    "клубника и земляника": "клубника земляника",
    "гуава мята": "гуава мята",
    "гуава и мята": "гуава мята",
}

def normalize_flavor(raw):

    x = clean_text(raw)

    for k, v in EN_RU.items():
        x = x.replace(k, v)

    for k, v in MORPH.items():
        x = x.replace(k, v)

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

def extract_product_head(text):

    txt = clean_text(text)

    splitters = [
        "со вкусом",
        "вкус",
        "аромат",
        "тип",
    ]

    for s in splitters:

        if s in txt:
            txt = txt.split(s)[0]
            break

    return txt[:150]

def detect_product_type(row):

    full_text = " ".join([
        str(row.get("Общее наименование продукции", "")),
        str(row.get("Наименование (обозначение) продукции", ""))
    ])

    full_text = clean_text(full_text)

    head = extract_product_head(full_text)

    okveds = extract_okved(row)

    if any(x.startswith("11.07") for x in okveds):

        # strict energy detection
        if re.search(
            r'энергетичес|тонизирующ|energy drink',
            head
        ):
            return "Энергетические безалкогольные напитки"

        # isotonic detection
        if re.search(
            r'изотони|isotonic|electrolyte',
            full_text
        ):
            return "Спортивные изотонические напитки"

        # tea / coffee detection
        tea_markers = [
            "чай",
            "tea",
            "ice tea",
            "green tea",
            "black tea",
            "чайный напиток",
            "экстракт чая",
            "кофе",
            "coffee",
            "кофейный напиток",
        ]

        for marker in tea_markers:
            if marker in full_text:
                return "Холодные чаи и кофейные напитки"

        return "Газированные и негазированные сладкие напитки"

    if any(x.startswith("10.32") for x in okveds):

        if "морс" in head:
            return "Морсы"

        if "концентрат" in head:
            return "Концентраты"

        return "Фруктовые и овощные соки"

    if any(x.startswith("11.03") for x in okveds):

        if "сидр" in head:
            return "Сидры"

        if "медовух" in head:
            return "Медовуха"

        return "Плодово ягодные напитки"

    if any(x.startswith("11.02") for x in okveds):

        if "игрист" in head or "шампан" in head:
            return "Игристые и шампанское"

        return "Вина"

    return "Прочее"

def extract_flavors(row):

    txt = " ".join([
        str(row.get("Общее наименование продукции", "")),
        str(row.get("Наименование (обозначение) продукции", ""))
    ])

    txt = clean_text(txt)

    patterns = [
        r'со вкусом ([^,.;\n]+)',
        r'вкус ([^,.;\n]+)',
        r'аромат ([^,.;\n]+)',
        r'тип ([^,.;\n]+)',
    ]

    found = []

    for p in patterns:

        matches = re.findall(p, txt, flags=re.IGNORECASE)

        for m in matches:

            flavor = normalize_flavor(m)

            if (
                len(flavor) > 1
                and len(flavor.split()) <= 5
                and flavor not in found
            ):
                found.append(flavor)

    if not found:

        fallback = normalize_flavor(txt)

        if len(fallback.split()) <= 4:
            found.append(fallback)

    return found

rows = []

for _, row in df.iterrows():

    product_type = detect_product_type(row)

    flavors = extract_flavors(row)

    for fl in flavors:

        rows.append({
            "Вид продукции": product_type,
            "Вкус": fl,
            "CanonicalKey": (
                product_type.lower()
                + "|"
                + canonical_key(fl)
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
    file_name="okved_flavors_v41.csv",
    mime="text/csv"
)
