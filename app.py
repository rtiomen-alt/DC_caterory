
import streamlit as st
import pandas as pd
import re

st.set_page_config(layout="wide", page_title="DS Flavor Extractor v5")

st.title("DS Flavor Extractor v5")

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
    x = re.sub(r'\([^)]*\)', '', x)
    x = re.sub(r'\s+', ' ', x)

    return x.strip()

def normalize_flavor(x):

    x = clean_text(x).lower()

    replacements = {
        "cola": "кола",
        "lemon": "лимон",
        "lime": "лайм",
        "orange": "апельсин",
        "bitter": "биттер",
        "spritz": "шприц",
        "aperol": "апероль",
    }

    for k, v in replacements.items():
        x = x.replace(k, v)

    rules = {
        "биттер лемон": "биттер лимон",
        "лимона": "лимон",
        "апельсина": "апельсин",
        "колы": "кола",
        "лайма": "лайм",
    }

    for k, v in rules.items():
        x = x.replace(k, v)

    x = re.sub(r'[^a-zа-я0-9\s\-]', ' ', x)
    x = re.sub(r'\s+', ' ', x)

    return x.strip().title()

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

def extract_flavors(text):

    txt = clean_text(text)

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
                and len(flavor.split()) <= 6
                and flavor not in found
            ):
                found.append(flavor)

    # fallback only for short clean product names
    if not found:

        fallback = normalize_flavor(txt)

        if len(fallback.split()) <= 4:
            found.append(fallback)

    return found

rows = []

for _, row in df.iterrows():

    flavors = extract_flavors(
        row.get("Наименование (обозначение) продукции", "")
    )

    for fl in flavors:

        canonical = re.sub(
            r'[^a-zа-я0-9]+',
            '',
            fl.lower()
        )

        rows.append({
            "Категория": category(row),
            "Вкус": fl,
            "key": category(row).lower() + "|" + canonical,
            "Действие с": pd.to_datetime(row["Действие с"], errors="coerce"),
            "Действие по": pd.to_datetime(row["Действие по"], errors="coerce"),
            "Номер ДС": str(row["Регистрационный номер"])
        })

res = pd.DataFrame(rows)

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

st.dataframe(final, use_container_width=True, height=800)

csv = final.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Скачать CSV",
    csv,
    file_name="ds_flavors_v5.csv",
    mime="text/csv"
)
