
import streamlit as st
import pandas as pd
import re

st.set_page_config(layout="wide", page_title="DS Flavor Extractor REBUILD")

st.title("DS Flavor Extractor REBUILD")

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

    garbage = [
        "напитки безалкогольные негазированные",
        "торговых марок",
        "торговой марки",
        "радуга",
    ]

    for g in garbage:
        x = re.sub(g, '', x, flags=re.IGNORECASE)

    x = re.sub(r'[.,;:]+', ' ', x)
    x = re.sub(r'\s+', ' ', x)

    return x.strip()

def normalize_flavor(flavor):

    f = clean_text(flavor).lower()

    translit = {
        "cola": "кола",
        "lemon": "лимон",
        "lime": "лайм",
        "orange": "апельсин",
        "bitter": "биттер",
        "mango": "манго",
        "spritz": "шприц",
        "aperol": "апероль",
    }

    for k, v in translit.items():
        f = f.replace(k, v)

    replacements = {
        "биттер лемон": "биттер лимон",
        "bitter лимон": "биттер лимон",
        "лимона": "лимон",
        "лимонный": "лимон",
        "апельсина": "апельсин",
        "колы": "кола",
        "лайма": "лайм",
        "манго-маракуйя": "манго и маракуйя",
        "манго и маракуйи": "манго и маракуйя",
        "манготина": "мангостин",
        "мангостина": "мангостин",
    }

    for k, v in replacements.items():
        f = f.replace(k, v)

    f = re.sub(r'\s+', ' ', f)
    f = f.strip()

    return f.title()

def canonical_key(x):

    x = normalize_flavor(x).lower()

    x = re.sub(r'[^a-zа-я0-9]+', '', x)

    return x

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

    if "лимонад" in txt:
        return "Лимонады"

    if "энерг" in txt:
        return "Энергетики"

    if "сок" in txt:
        return "Соки"

    return "Безалкогольные напитки"

rows = []

for _, row in df.iterrows():

    flavors = extract_flavors(
        row.get("Наименование (обозначение) продукции", "")
    )

    for fl in flavors:

        rows.append({
            "Категория": category(row),
            "Вкус": fl,
            "key": category(row).lower() + "|" + canonical_key(fl),
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

st.dataframe(
    final,
    use_container_width=True,
    height=750
)

csv = final.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Скачать CSV",
    csv,
    file_name="ds_flavors_rebuild.csv",
    mime="text/csv"
)
