
import streamlit as st
import pandas as pd
import re

st.set_page_config(layout="wide", page_title="DS Flavor Extractor v3")

st.title("DS Flavor Extractor v3")

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
    x = re.sub(r'\s*\(\s*', ' (', x)
    x = re.sub(r'\s*\)\s*', ') ', x)

    x = re.sub(r'[.,;:]+$', '', x)
    x = re.sub(r'\s+', ' ', x)

    return x.strip()

def normalize_flavor(flavor):

    f = clean_text(flavor).lower()

    replacements = {
        "cola": "кола",
        "orange": "апельсин",
        "lemon": "лимон",
        "lime": "лайм",
        "mango": "манго",
        "mangosteen": "мангостин",
        "spritz": "шприц",
        "aperol": "апероль",
    }

    for k, v in replacements.items():
        f = f.replace(k, v)

    rules = [
        ("апельсинов", "апельсин"),
        ("апельсина", "апельсин"),
        ("лимона", "лимон"),
        ("лимонный", "лимон"),
        ("лимон-лайма", "лимон-лайм"),
        ("лимон лайма", "лимон-лайм"),
        ("колы", "кола"),
        ("лайма", "лайм"),
        ("манготина", "мангостин"),
        ("мангостина", "мангостин"),
        ("манго-маракуйя", "манго и маракуйя"),
        ("манго и маракуйи", "манго и маракуйя"),
    ]

    for k, v in rules:
        if k in f:
            f = f.replace(k, v)

    f = re.sub(r'\s+', ' ', f)
    f = re.sub(r'\s+\)', ')', f)
    f = re.sub(r'\(\s+', '(', f)

    return f.strip().title()

def extract_flavors(text):

    txt = clean_text(text)

    patterns = [
        r'со вкусом ([^,;\n]+)',
        r'вкус ([^,;\n]+)',
        r'аромат ([^,;\n]+)',
        r'тип ([^,;\n]+)',
        r'соус ([^,;\n]+)',
    ]

    results = []

    for p in patterns:

        found = re.findall(p, txt, flags=re.IGNORECASE)

        for item in found:

            nf = normalize_flavor(item)

            if nf and nf not in results:
                results.append(nf)

    if len(results) == 0:

        fallback = normalize_flavor(txt)

        if fallback:
            results.append(fallback)

    return results

def category(row):

    txt = " ".join([
        str(row.get("ОКВЭД название", "")),
        str(row.get("Группа продукции", "")),
        str(row.get("Общее наименование продукции", "")),
        str(row.get("Наименование (обозначение) продукции", ""))
    ]).lower()

    if "энерг" in txt:
        return "Энергетики"

    if "лимонад" in txt:
        return "Лимонады"

    if "сок" in txt:
        return "Соки"

    if "напит" in txt:
        return "Безалкогольные напитки"

    return "Прочее"

rows = []

for _, row in df.iterrows():

    flavors = extract_flavors(
        row.get("Наименование (обозначение) продукции", "")
    )

    for fl in flavors:

        rows.append({
            "Категория": category(row),
            "Вкус": fl,
            "Действие с": pd.to_datetime(row["Действие с"], errors="coerce"),
            "Действие по": pd.to_datetime(row["Действие по"], errors="coerce"),
            "Номер ДС": str(row["Регистрационный номер"])
        })

res = pd.DataFrame(rows)

# Canonical key for duplicate collapse
res["dup_key"] = (
    res["Категория"].astype(str).str.lower().str.strip()
    + "|"
    + res["Вкус"]
        .astype(str)
        .str.lower()
        .str.replace(r'[^a-zA-Zа-яА-Я0-9]+', '', regex=True)
)

final = (
    res.groupby("dup_key")
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

st.dataframe(
    final,
    use_container_width=True,
    height=750
)

csv = final.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Скачать CSV",
    csv,
    file_name="ds_flavors_v3.csv",
    mime="text/csv"
)
