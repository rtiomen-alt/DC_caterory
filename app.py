
import streamlit as st
import pandas as pd
import re

st.set_page_config(layout="wide", page_title="DS Flavor Extractor")

st.title("DS Flavor Extractor MVP")

uploaded = st.file_uploader(
    "Загрузить XLS/XLSX/CSV",
    type=["xls", "xlsx", "csv"]
)

if uploaded is None:
    st.stop()

if uploaded.name.endswith(".csv"):
    df = pd.read_csv(uploaded)
elif uploaded.name.endswith(".xls"):
    import subprocess, tempfile, os
    tmpdir = tempfile.mkdtemp()
    src = os.path.join(tmpdir, uploaded.name)

    with open(src, "wb") as f:
        f.write(uploaded.read())

    subprocess.run([
        "libreoffice",
        "--headless",
        "--convert-to",
        "xlsx",
        src,
        "--outdir",
        tmpdir
    ])

    xlsx_path = src + "x"
    df = pd.read_excel(xlsx_path)
else:
    df = pd.read_excel(uploaded)

df.columns = [str(c).strip() for c in df.columns]

df = df[df["Тип заявителя"].astype(str).str.contains("Изготовитель", case=False, na=False)]

def normalize_flavor(flavor):

    if not flavor:
        return ""

    f = str(flavor).lower()

    replacements = {
        "cola": "кола",
        "orange": "апельсин",
        "lemon": "лимон",
        "cherry": "вишня",
        "apple": "яблоко",
        "mango": "манго",
        "grape": "виноград",
        "barbaris": "барбарис"
    }

    for k, v in replacements.items():
        f = f.replace(k, v)

    rules = [
        ("апельсинов", "апельсин"),
        ("апельсина", "апельсин"),
        ("лимона", "лимон"),
        ("вишни", "вишня"),
        ("клубники", "клубника"),
        ("яблока", "яблоко"),
        ("груши", "груша"),
        ("барбариса", "барбарис"),
    ]

    for k, v in rules:
        if k in f:
            return v

    return f.strip().title()

def extract_flavors(text):

    if pd.isna(text):
        return []

    txt = str(text)

    patterns = [
        r'со вкусом ([^",;\n]+)',
        r'вкус ([^",;\n]+)',
        r'аромат ([^",;\n]+)',
        r'тип ([^",;\n]+)',
        r'соус ([^",;\n]+)',
    ]

    results = []

    for p in patterns:
        found = re.findall(p, txt, flags=re.IGNORECASE)

        for f in found:
            nf = normalize_flavor(f)
            if nf and nf not in results:
                results.append(nf)

    if len(results) == 0:

        tm = re.findall(r'«([^»]+)»', txt)

        for x in tm[:1]:
            results.append(normalize_flavor(x))

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
            "Действие с": pd.to_datetime(row["Действие с"]),
            "Действие по": pd.to_datetime(row["Действие по"]),
            "Номер ДС": str(row["Регистрационный номер"])
        })

res = pd.DataFrame(rows)

if len(res) == 0:
    st.warning("Не найдено данных")
    st.stop()

final = (
    res.groupby(["Категория", "Вкус"])
    .agg({
        "Действие с": "min",
        "Действие по": "max",
        "Номер ДС": lambda x: ", ".join(sorted(set(x)))
    })
    .reset_index()
)

final["Действие с"] = final["Действие с"].dt.strftime("%d.%m.%Y")
final["Действие по"] = final["Действие по"].dt.strftime("%d.%m.%Y")

st.dataframe(
    final,
    use_container_width=True,
    height=700
)

csv = final.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Скачать CSV",
    csv,
    file_name="ds_flavors.csv",
    mime="text/csv"
)
