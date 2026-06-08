
import streamlit as st
import pandas as pd
import re

st.set_page_config(layout="wide", page_title="OKVED Flavor Service v2")

st.title("OKVED Flavor Service v2")

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

    okveds = extract_okved(row)

    for okv in okveds:

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

st.success("Все ОКВЭД входят в разрешенный список")

def clean_text(x):

    if pd.isna(x):
        return ""

    x = str(x).lower()

    x = re.sub(r'[«»\"“”]', '', x)
    x = re.sub(r'\s+', ' ', x)

    return x.strip()

def normalize_flavor(x):

    x = clean_text(x)

    replacements = {
        "cola": "кола",
        "orange": "апельсин",
        "lemon": "лимон",
        "lime": "лайм",
        "apple": "яблоко",
        "cherry": "вишня",
        "mango": "манго",
        "grape": "виноград",

        "апельсиновый": "апельсин",
        "апельсина": "апельсин",
        "апельсинка": "апельсин",

        "лимона": "лимон",
        "лимонный": "лимон",

        "колы": "кола",

        "вишневый": "вишня",
        "яблочный": "яблоко",
    }

    for k, v in replacements.items():
        x = x.replace(k, v)

    x = re.sub(r'\([^)]*\)', '', x)
    x = re.sub(r'[^a-zа-я0-9\s\-]', ' ', x)
    x = re.sub(r'\s+', ' ', x)

    return x.strip().title()

def extract_product_head(text):

    txt = clean_text(text)

    splitters = [
        "со вкусом",
        "вкус",
        "аромат",
        "тип",
        "соус",
    ]

    head = txt

    for s in splitters:

        if s in txt:
            head = txt.split(s)[0]
            break

    return head[:120]

def detect_product_type(row):

    full_txt = " ".join([
        str(row.get("Общее наименование продукции", "")),
        str(row.get("Наименование (обозначение) продукции", ""))
    ])

    head = extract_product_head(full_txt)

    okveds = extract_okved(row)

    if any(x.startswith("11.07") for x in okveds):

        if re.search(r'энергетичес|тонизирующ|energy drink', head):
            return "Энергетики"

        if re.search(r'холодный чай|ice tea|чай', head):
            return "Холодные чаи"

        if re.search(r'изотони', head):
            return "Изотоники"

        return "Газированные напитки"

    if any(x.startswith("10.32") for x in okveds):

        if "морс" in head:
            return "Морсы"

        if "концентрат" in head:
            return "Концентраты"

        return "Соки"

    if any(x.startswith("11.03") for x in okveds):

        if "сидр" in head:
            return "Сидры"

        if "медовух" in head:
            return "Медовуха"

        return "Плодовые вина"

    if any(x.startswith("11.02") for x in okveds):

        if "игрист" in head or "шампан" in head:
            return "Игристые"

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

            if len(flavor) > 1 and len(flavor.split()) <= 5:

                if flavor not in found:
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

    source_name = str(
        row.get("Наименование (обозначение) продукции", "")
    )

    for fl in flavors:

        key = (
            product_type.lower()
            + "|"
            + re.sub(r'[^a-zа-я0-9]+', '', fl.lower())
        )

        rows.append({
            "Вид продукции": product_type,
            "Вкус": fl,
            "Номер ДС": str(row["Регистрационный номер"]),
            "Исходное наименование": source_name,
            "key": key
        })

res = pd.DataFrame(rows)

final = (
    res.groupby("key")
    .agg({
        "Вид продукции": "first",
        "Вкус": "first",
        "Номер ДС": lambda x: ", ".join(sorted(set(x))),
        "Исходное наименование": "first"
    })
    .reset_index(drop=True)
)

final = final.sort_values(["Вид продукции", "Вкус"])

st.dataframe(
    final,
    use_container_width=True,
    height=850
)

csv = final.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Скачать CSV",
    csv,
    file_name="okved_flavors_v2.csv",
    mime="text/csv"
)
