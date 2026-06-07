
import streamlit as st
import pandas as pd
import re

st.set_page_config(layout="wide", page_title="DS Flavor Extractor v4")

st.title("DS Flavor Extractor v4")

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

    x = re.sub(r'[«»"“”]', '', x)
    x = re.sub(r'\s+', ' ', x)
    x = re.sub(r'[.,;:]+$', '', x)

    return x.strip()

def canonical_flavor(x):

    x = clean_text(x).lower()

    translit = {
        "cola": "кола",
        "lemon": "лимон",
        "lime": "лайм",
        "bitter": "биттер",
        "orange": "апельсин",
    }

    for k, v in translit.items():
        x = x.replace(k, v)

    # normalize variants
    replacements = [
        ("биттер лимон", "биттер лимон"),
        ("биттер lemon", "биттер лимон"),
        ("bitter лимон", "биттер лимон"),
        ("лимон-лайма", "лимон-лайм"),
        ("лимон лайма", "лимон-лайм"),
        ("колы", "кола"),
        ("апельсина", "апельсин"),
    ]

    for k, v in replacements:
        x = x.replace(k, v)

    # remove generic product garbage
    garbage = [
        "напитки безалкогольные негазированные",
        "торговых марок",
        "радуга",
    ]

    for g in garbage:
        x = x.replace(g, "")

    x = re.sub(r'\([^)]*\)', '', x)
    x = re.sub(r'[^a-zа-я0-9\s\-]', '', x)
    x = re.sub(r'\s+', ' ', x)

    return x.strip().title()

def extract_flavor(text):

    txt = clean_text(text)

    patterns = [
        r'со вкусом ([^,;\n]+)',
        r'вкус ([^,;\n]+)',
        r'аромат ([^,;\n]+)',
        r'тип ([^,;\n]+)',
    ]

    for p in patterns:
        found = re.findall(p, txt, flags=re.IGNORECASE)

        if found:
            return canonical_flavor(found[0])

    return canonical_flavor(txt)

def category(row):

    txt = " ".join([
        str(row.get("ОКВЭД название", "")),
        str(row.get("Группа продукции", "")),
        str(row.get("Общее наименование продукции", "")),
        str(row.get("Наименование (обозначение) продукции", ""))
    ]).lower()

    if "лимонад" in txt:
        return "Лимонады"

    if "энерг" in txt:
        return "Энергетики"

    if "сок" in txt:
        return "Соки"

    return "Безалкогольные напитки"

rows = []

for _, row in df.iterrows():

    flavor = extract_flavor(
        row.get("Наименование (обозначение) продукции", "")
    )

    rows.append({
        "Категория": category(row),
        "Вкус": flavor,
        "Действие с": pd.to_datetime(row["Действие с"], errors="coerce"),
        "Действие по": pd.to_datetime(row["Действие по"], errors="coerce"),
        "Номер ДС": str(row["Регистрационный номер"])
    })

res = pd.DataFrame(rows)

res["key"] = (
    res["Категория"].str.lower().str.strip()
    + "|"
    + res["Вкус"]
        .str.lower()
        .str.replace(r'[^a-zа-я0-9]+', '', regex=True)
)

final = (
    res.groupby("key")
    .agg({
        "Категория": "first",
        "Вкус": "first",
        "Действие с": "min",
        "Действие по": "max",
        "Номер ДС": lambda x: ", ".join(sorted(set(x)))
    })
    .reset_index(drop=True)
)

final["Действие с"] = final["Действие с"].dt.strftime("%d.%m.%Y")
final["Действие по"] = final["Действие по"].dt.strftime("%d.%m.%Y")

final = final.sort_values(["Категория", "Вкус"])

st.dataframe(final, use_container_width=True, height=750)

csv = final.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Скачать CSV",
    csv,
    file_name="ds_flavors_v4.csv",
    mime="text/csv"
)
