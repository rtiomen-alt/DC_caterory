import pandas as pd
import json
import re
import time
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential

# -------------------------------------------------------------------
#  НАСТРОЙКИ (измените под себя)
# -------------------------------------------------------------------
FILE_PATH = "declarations.xls"          # путь к вашему файлу
SHEET_NAME = 0                          # номер или имя листа
OUTPUT_CSV = "unique_product_flavor.csv"

# Выберите движок: "openai" или "ollama"
ENGINE = "ollama"      # "openai" или "ollama"

# Параметры OpenAI (если ENGINE == "openai")
OPENAI_API_KEY = "sk-..."               # ваш ключ
OPENAI_MODEL = "gpt-3.5-turbo"          # или gpt-4

# Параметры Ollama (если ENGINE == "ollama")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"                 # или "qwen:7b", "mistral" и др.

# Колонки в файле (возможные варианты названий)
COLUMN_MAPPING = {
    "group": ["Группа продукции", "Группа", "Категория"],
    "general_name": ["Общее наименование продукции", "Общее наименование", "Наименование общее"],
    "detailed_name": ["Наименование (обозначение) продукции", "Наименование продукции", "Наименование", "Продукция"]
}

# -------------------------------------------------------------------
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# -------------------------------------------------------------------
def find_column(df: pd.DataFrame, possible_names: List[str]) -> str:
    """Ищет реальное имя колонки по списку возможных вариантов."""
    for name in possible_names:
        if name in df.columns:
            return name
    raise KeyError(f"Не найдена ни одна из колонок: {possible_names}")

def build_context(row: pd.Series, group_col: str, general_col: str, detailed_col: str) -> str:
    """Формирует текст для LLM из трёх колонок."""
    parts = []
    if pd.notna(row[group_col]):
        parts.append(f"Группа продукции: {row[group_col]}")
    if pd.notna(row[general_col]):
        parts.append(f"Общее наименование продукции: {row[general_col]}")
    if pd.notna(row[detailed_col]):
        parts.append(f"Наименование (обозначение) продукции: {row[detailed_col]}")
    return "\n".join(parts)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_openai(prompt: str) -> str:
    """Отправка запроса к OpenAI API."""
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"}  # упрощает парсинг
    )
    return response.choices[0].message.content

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_ollama(prompt: str) -> str:
    """Отправка запроса к локальному Ollama."""
    import requests
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json"   # просим JSON
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data.get("response", "")

def parse_llm_output(raw_text: str) -> Tuple[Optional[str], Optional[str]]:
    """Извлекает поля product и flavor из JSON-ответа."""
    try:
        # Пытаемся найти в ответе JSON (бывает, что модель добавляет пояснения)
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(raw_text)
        product = data.get("product")
        flavor = data.get("flavor")
        if flavor == "null" or flavor is None:
            flavor = None
        return product, flavor
    except Exception as e:
        print(f"Ошибка парсинга JSON: {e}\nОтвет: {raw_text[:200]}")
        return None, None

def extract_pair(context: str) -> Tuple[Optional[str], Optional[str]]:
    """Формирует промпт, вызывает LLM и возвращает (product, flavor)."""
    prompt = f"""Ты — экспертный парсер пищевых деклараций.

На основе контекста определи:
- вид продукции (например, "йогурт", "сок", "конфета", "напиток", "вода", "чипсы")
- вкус (если указан). Если вкуса нет или он не определяется, верни flavor: null.

Правила:
- Если в названии перечислено несколько вкусов (клубника-банан), верни их как есть.
- Используй дополнительную информацию из групп продукции, если основное название неоднозначно.
- Ответ дай строго в формате JSON: {{"product": "...", "flavor": ...}}

Контекст:
{context}

Ответ:
"""
    try:
        if ENGINE == "openai":
            raw = call_openai(prompt)
        else:
            raw = call_ollama(prompt)
        return parse_llm_output(raw)
    except Exception as e:
        print(f"Ошибка при вызове LLM: {e}")
        return None, None

# -------------------------------------------------------------------
#  ОСНОВНОЙ ПРОЦЕСС
# -------------------------------------------------------------------
def main():
    # 1. Загрузка файла
    print(f"Загрузка файла {FILE_PATH}...")
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, dtype=str)
    print(f"Всего строк: {len(df)}")

    # 2. Определяем реальные имена колонок
    try:
        group_col = find_column(df, COLUMN_MAPPING["group"])
        general_col = find_column(df, COLUMN_MAPPING["general_name"])
        detailed_col = find_column(df, COLUMN_MAPPING["detailed_name"])
        print(f"Колонки: группа='{group_col}', общее='{general_col}', детальное='{detailed_col}'")
    except KeyError as e:
        print(f"Ошибка: {e}. Доступные колонки: {list(df.columns)}")
        return

    # 3. Формируем контекст для каждой строки
    df["context"] = df.apply(
        lambda row: build_context(row, group_col, general_col, detailed_col),
        axis=1
    )

    # 4. Дедупликация по контексту (чтобы не слать повторные запросы)
    unique_contexts = df["context"].drop_duplicates().tolist()
    print(f"Уникальных текстов для обработки: {len(unique_contexts)}")

    # 5. Кэш: текст -> (product, flavor)
    cache = {}
    for i, ctx in enumerate(unique_contexts):
        if not ctx.strip():
            cache[ctx] = (None, None)
            continue
        print(f"Обработка {i+1}/{len(unique_contexts)}...")
        product, flavor = extract_pair(ctx)
        cache[ctx] = (product, flavor)
        time.sleep(0.5)  # пауза, чтобы не перегружать LLM

    # 6. Применяем кэш к исходному DataFrame и собираем уникальные пары
    df["product"] = df["context"].apply(lambda x: cache[x][0])
    df["flavor"] = df["context"].apply(lambda x: cache[x][1])

    # 7. Формируем результирующий массив уникальных пар (игнорируем None-продукты)
    pairs = df[["product", "flavor"]].drop_duplicates()
    pairs = pairs[pairs["product"].notna()]

    # 8. Сохраняем
    pairs.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"Готово! Найдено уникальных пар: {len(pairs)}")
    print(f"Результат сохранён в {OUTPUT_CSV}")
    print("\nПримеры:")
    print(pairs.head(10).to_string(index=False))

if __name__ == "__main__":
    main()