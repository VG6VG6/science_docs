import pandas as pd
import sqlite3  # Или psycopg2 для PostgreSQL
import os

def update_science_docs_db():
    total_in_db = 0

    conn = sqlite3.connect('science_docs.db')

    for YEAR in range(2020, 2024+1):
        # 1. Загружаем данные из CSV, который мы скачали со Scimago
        # В этом файле УЖЕ есть Title, ISSN, SJR и Квартили для ВСЕХ журналов
        file_name = f'scimagojr {YEAR}.csv'
        if not os.path.exists(file_name):
            print(f"⚠️ Файл {file_name} не найден, пропускаю.")
            continue

        # Пробуем прочитать файл. Если ошибка в разделителе - pandas скажет
        try:
            df = pd.read_csv(file_name, sep=';')
            if len(df.columns) < 5:  # Если колонок слишком мало, значит разделитель скорее всего запятая
                df = pd.read_csv(file_name, sep=',')
        except Exception as e:
            print(f"❌ Ошибка чтения {file_name}: {e}")
            continue

        # 2. Очистка данных
        # Нам нужны только колонки: Название, ISSN, Квартиль, SJR, Страна
        df_cleaned = df[['Title', 'Issn', 'SJR Best Quartile', 'SJR', 'Country', 'H index']].copy()  # Добавлен .copy()

        # Разделяем ISSN (в файле они могут быть через запятую)
        # Нам важно, чтобы для поиска в будущем ISSN был чистым
        df_cleaned.loc[:, 'Issn'] = df_cleaned['Issn'].str.split(',').str[0]  # Используем .loc

        # Добавляем колонку Год (так как файл за 2023 год)
        df_cleaned.loc[:, 'Year'] = YEAR  # Используем .loc

        print(f"Загружено {len(df_cleaned)} журналов с квартилями!")

        # 3. "Загнать в БД" (Пример для SQLite, для Postgres принцип тот же)
        mode = 'replace' if YEAR == 2020 else 'append'
        df_cleaned.to_sql('journals_ranks', conn, if_exists=mode, index=False)

        total_in_db += len(df_cleaned)

    print(f"✅ Данные успешно импортированы в базу данных!\n {total_in_db} записей")

    # --- ДОБАВЬТЕ ЭТО ДЛЯ ПРОВЕРКИ ---

    # 4. Проверочный запрос прямо из кода
    print("\n📊 Проверка содержимого базы 'science_docs.db':")
    check_df = pd.read_sql("SELECT Year, COUNT(*) as Count FROM journals_ranks GROUP BY Year ORDER BY Year", conn)
    print(check_df)

    # 5. Обязательно закрываем соединение, чтобы сохранить файл на диск
    conn.close()


if __name__ == "__main__":
    import argparse

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-u", "--update", help="Обновить базу данных статей.")

    args = arg_parser.parse_args()
    if args.update:
        print("Обновляем базу данных.")
        update_science_docs_db()
        print("Готово.")

