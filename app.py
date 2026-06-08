import streamlit as st
import pandas as pd
import re

st.set_page_config(layout="wide", page_title="OKVED Flavor Service")

st.title("OKVED Flavor Service")

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

    st.error("Обнаружены ОКВЭД вне списка")

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

    x = re.sub(r'[«»\"“”]', '', x)
    x = re.sub(r'\([^)]*\)', '', x)
    x = re.sub(r'\s+', ' ', x)

    return x.strip()

def normalize_flavor(x):

    x = clean_text(x)

    repl = {
        "cola": "кола",
        "orange": "апельсин",
        "lemon": "лимон",
        "lime": "лайм",
        "apple": "яблоко",
        "апельсиновый": "апельсин",
        "апельсина": "апельсин",
        "апельсинка": "апельсин",
        "лимона": "лимон",
        "колы": "кола",
    }

    for k, v in repl.items():
        x = x.replace(k, v)

    x = re.sub(r'[^a-zа-я0-9\s\-]', ' ', x)
    x = re.sub(r'\s+', ' ', x)

    return x.strip().title()

def product_type(row):

    txt = " ".join([
        str(row.get("Общее наименование продукции", "")),
        str(row.get("Наименование (обозначение) продукции", ""))
    ]).lower()

    okveds = extract_okved(row)

    if any(x.startswith("10.32") for x in okveds):

        if "морс" in txt:
            return "Морсы"

        return "Соки"

    if any(x.startswith("11.03") for x in okveds):

        if "сидр" in txt:
            return "Сидры"

        if "медовух" in txt:
            return "Медовуха"

        return "Плодовые вина"

    if any(x.startswith("11.02") for x in okveds):

        if "игрист" in txt or "шампан" in txt:
            return "Игристые"

        return "Вина"

    if any(x.startswith("11.07") for x in okveds):

        if "энерг" in txt:
            return "Энергетики"

        if "чай" in txt:
            return "Холодные чаи"

        if "изотони" in txt:
            return "Изотоники"

        if "квас" in txt:
            return "Квас"

        return "Газированные напитки"

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

            f = normalize_flavor(m)

            if len(f) > 1 and f not in found:
                found.append(f)

    if not found:

        fallback = normalize_flavor(txt)

        if len(fallback.split()) <= 5:
            found.append(fallback)

    return found

rows = []

for _, row in df.iterrows():

    flavors = extract_flavors(row)

    for fl in flavors:

        rows.append({
            "Вид продукции": product_type(row),
            "Вкус": fl,
            "Номер ДС": str(row["Регистрационный номер"])
        })

res = pd.DataFrame(rows)

if len(res) == 0:
    st.warning("Вкусы не найдены")
    st.stop()

res["key"] = (
    res["Вид продукции"].str.lower()
    + "|"
    + res["Вкус"]
        .str.lower()
        .str.replace(r'[^a-zа-я0-9]+', '', regex=True)
)

final = (
    res.groupby("key")
    .agg({
        "Вид продукции": "first",
        "Вкус": "first",
        "Номер ДС": lambda x: ", ".join(sorted(set(x)))
    })
    .reset_index(drop=True)
)

final = final.sort_values(["Вид продукции", "Вкус"])

st.dataframe(final, use_container_width=True, height=800)

csv = final.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Скачать CSV",
    csv,
    file_name="okved_flavors.csv",
    mime="text/csv"
)
