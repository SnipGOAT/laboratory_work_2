import sqlite3
import re
import os

# -------------------------------------------------------------------
# 1. Словари и правила нормализации (синонимы, инициалы)
# -------------------------------------------------------------------
SYNONYMS = {
    'георгий': 'егор',
    'гавриил': 'гаврила',
    'дмитрий': 'дима',
    'алексей': 'алёша',
    'анна': 'аня',
    'екатерина': 'катя'
}

INITIALS_MAP = {
    'а.':   'алексей',
    'а.а.': 'алексей алексеевич',
    'с.с.': 'сергей сергеевич',
    'п.п.': 'петр петрович',
    'в.':   'владимир',
    'в.в.': 'владимир владимирович',
    'и.и.': 'иван иванович'
}

# -------------------------------------------------------------------
# 2. Функция нормализации (расширенная)
# -------------------------------------------------------------------
def normalize_name(name: str) -> str:
    """
    Приводит ФИО к каноническому виду:
    - очистка от лишних символов (оставляем буквы, пробелы, точки)
    - нижний регистр
    - разбивка на токены (слова + инициалы)
    - замена инициалов по словарю
    - замена синонимов
    - сортировка токенов
    - склейка
    """
    # 1) Очистка: удаляем всё, кроме букв, пробелов, точек
    cleaned = re.sub(r'[^\w\s\.]', '', name)
    # 2) Нижний регистр
    lowercased = cleaned.lower()
    # 3) Разделяем на токены (слова и инициалы с точками)
    tokens = re.findall(r'[\w\.]+', lowercased)
    
    expanded_tokens = []
    for token in tokens:
        # 4) Обработка инициалов: если токен похож на "а." или "а.а."
        if re.match(r'^[а-я]\.$', token) or re.match(r'^[а-я]\.[а-я]\.$', token):
            expanded = INITIALS_MAP.get(token, token)
            # разворачиваем в одно или несколько слов
            expanded_tokens.extend(expanded.split())
        else:
            # 5) Замена синонимов
            canonical = SYNONYMS.get(token, token)
            expanded_tokens.append(canonical)
    
    # 6) Сортировка
    expanded_tokens.sort()
    # 7) Склейка
    return ' '.join(expanded_tokens)


# -------------------------------------------------------------------
# 3. Создание баз данных и таблиц (с денормализованным ХД)
# -------------------------------------------------------------------
def create_databases():
    for db in ["source1.db", "source2.db", "datawarehouse.db"]:
        if os.path.exists(db):
            os.remove(db)

    # source1: проекты
    conn = sqlite3.connect("source1.db")
    conn.execute('''
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            role TEXT,
            project_name TEXT,
            tech_stack TEXT
        )
    ''')
    conn.close()

    # source2: резюме
    conn = sqlite3.connect("source2.db")
    conn.execute('''
        CREATE TABLE resumes (
            id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            competencies TEXT,
            salary REAL,
            bonus REAL
        )
    ''')
    conn.close()

    # Хранилище данных (денормализованная таблица + правила нормализации)
    conn_dw = sqlite3.connect("datawarehouse.db")
    conn_dw.execute('''
        CREATE TABLE unified_employee (
            id INTEGER PRIMARY KEY,
            normalized_key TEXT UNIQUE,
            original_name_src1 TEXT,
            original_name_src2 TEXT,
            role TEXT,
            project_name TEXT,
            tech_stack TEXT,
            competencies TEXT,
            salary REAL,
            bonus REAL
        )
    ''')
    # Таблица правил нормализации (можно заполнить из словарей)
    conn_dw.execute('''
        CREATE TABLE normalization_rules (
            rule_id INTEGER PRIMARY KEY,
            original_form TEXT,
            canonical_form TEXT,
            rule_type TEXT
        )
    ''')
    # Заполним таблицу правил (пример)
    rules = [
        (1, 'георгий', 'егор', 'synonym'),
        (2, 'с.с.', 'сергей сергеевич', 'initials'),
        (3, 'п.п.', 'петр петрович', 'initials'),
        (4, 'а.а.', 'алексей алексеевич', 'initials'),
    ]
    conn_dw.executemany(
        "INSERT INTO normalization_rules (rule_id, original_form, canonical_form, rule_type) VALUES (?,?,?,?)",
        rules
    )
    conn_dw.commit()
    conn_dw.close()


# -------------------------------------------------------------------
# 4. Заполнение источников тестовыми данными (7 вариаций)
# -------------------------------------------------------------------
def populate_sources():
    # 7 разных вариаций ФИО для демонстрации всех случаев
    data_source1 = [
        ("Петров С.С.", "Team Lead", "Платформа аналитики", "Python, SQL"),
        ("Георгий Иванов", "Developer", "Мобильное приложение", "Kotlin"),
        ("Дмитрий А.А.", "QA", "Тестирование API", "Postman"),
        ("Алексей Козлов", "DevOps", "Облако", "Terraform"),
        ("Козлов Алексей", "Analyst", "BI", "Tableau"),
        ("Анна В.В.", "Manager", "Проект А", "Jira"),
        ("Алексей Смирнов", "Architect", "Архитектура", "UML")
    ]

    data_source2 = [
        ("Петров Сергей Сергеевич", "Python, SQL", 120000, 15000),
        ("Иванов Георгий", "Kotlin, CI/CD", 110000, 12000),
        ("АЛЕКСЕЙ АЛЕКСЕЕВИЧ", "Postman, SQL", 95000, 8000),
        ("козлов алексей", "Terraform, AWS", 130000, 20000),
        ("Алексей Козлов", "Tableau, Python", 105000, 10000),
        ("Владимирова Анна", "Jira, Confluence", 90000, 5000),
        ("Смирнов Алексей", "UML, ArchiMate", 140000, 25000)
    ]

    conn1 = sqlite3.connect("source1.db")
    for full_name, role, proj, stack in data_source1:
        conn1.execute(
            "INSERT INTO projects (full_name, role, project_name, tech_stack) VALUES (?,?,?,?)",
            (full_name, role, proj, stack)
        )
    conn1.commit()
    conn1.close()

    conn2 = sqlite3.connect("source2.db")
    for full_name, comp, sal, bonus in data_source2:
        conn2.execute(
            "INSERT INTO resumes (full_name, competencies, salary, bonus) VALUES (?,?,?,?)",
            (full_name, comp, sal, bonus)
        )
    conn2.commit()
    conn2.close()


# -------------------------------------------------------------------
# 5. ETL процесс: чтение, нормализация, объединение, запись
# -------------------------------------------------------------------
def etl():
    conn1 = sqlite3.connect("source1.db")
    conn2 = sqlite3.connect("source2.db")
    conn_dw = sqlite3.connect("datawarehouse.db")

    # Читаем source1
    cur1 = conn1.execute("SELECT full_name, role, project_name, tech_stack FROM projects")
    rows1 = cur1.fetchall()
    # Читаем source2
    cur2 = conn2.execute("SELECT full_name, competencies, salary, bonus FROM resumes")
    rows2 = cur2.fetchall()

    merged = {}

    # Обработка source1
    for full_name, role, project, stack in rows1:
        norm = normalize_name(full_name)
        if norm not in merged:
            merged[norm] = {
                "original_src1": full_name,
                "original_src2": None,
                "role": role,
                "project_name": project,
                "tech_stack": stack,
                "competencies": None,
                "salary": None,
                "bonus": None
            }
        else:
            # Обновляем (если вдруг дубли в одном источнике)
            merged[norm]["original_src1"] = full_name
            merged[norm]["role"] = role
            merged[norm]["project_name"] = project
            merged[norm]["tech_stack"] = stack

    # Обработка source2
    for full_name, comp, salary, bonus in rows2:
        norm = normalize_name(full_name)
        if norm not in merged:
            merged[norm] = {
                "original_src1": None,
                "original_src2": full_name,
                "role": None,
                "project_name": None,
                "tech_stack": None,
                "competencies": comp,
                "salary": salary,
                "bonus": bonus
            }
        else:
            merged[norm]["original_src2"] = full_name
            merged[norm]["competencies"] = comp
            merged[norm]["salary"] = salary
            merged[norm]["bonus"] = bonus

    # Запись в ХД (денормализованную таблицу)
    for norm, data in merged.items():
        try:
            conn_dw.execute('''
                INSERT INTO unified_employee (
                    normalized_key, original_name_src1, original_name_src2,
                    role, project_name, tech_stack,
                    competencies, salary, bonus
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                norm,
                data["original_src1"],
                data["original_src2"],
                data["role"],
                data["project_name"],
                data["tech_stack"],
                data["competencies"],
                data["salary"],
                data["bonus"]
            ))
        except sqlite3.IntegrityError:
            # Обновляем существующую запись
            conn_dw.execute('''
                UPDATE unified_employee SET
                    original_name_src1 = COALESCE(original_name_src1, ?),
                    original_name_src2 = COALESCE(original_name_src2, ?),
                    role = COALESCE(role, ?),
                    project_name = COALESCE(project_name, ?),
                    tech_stack = COALESCE(tech_stack, ?),
                    competencies = COALESCE(competencies, ?),
                    salary = COALESCE(salary, ?),
                    bonus = COALESCE(bonus, ?)
                WHERE normalized_key = ?
            ''', (
                data["original_src1"], data["original_src2"],
                data["role"], data["project_name"], data["tech_stack"],
                data["competencies"], data["salary"], data["bonus"],
                norm
            ))

    conn_dw.commit()
    conn1.close()
    conn2.close()
    conn_dw.close()


# -------------------------------------------------------------------
# 6. Функция вывода результатов
# -------------------------------------------------------------------
def show_results():
    conn = sqlite3.connect("datawarehouse.db")
    cursor = conn.execute("SELECT * FROM unified_employee")
    rows = cursor.fetchall()
    print("\n=== Хранилище данных (денормализованная таблица) ===")
    for row in rows:
        print(f"ID: {row[0]}")
        print(f"Нормализованный ключ: {row[1]}")
        print(f"Исходное из source1: {row[2]}")
        print(f"Исходное из source2: {row[3]}")
        print(f"Роль: {row[4]}, Проект: {row[5]}, Стек: {row[6]}")
        print(f"Компетенции: {row[7]}, Зарплата: {row[8]}, Премия: {row[9]}")
        print("-" * 50)
    conn.close()


# -------------------------------------------------------------------
# 7. Демонстрация работы нормализации на тестовых примерах
# -------------------------------------------------------------------
def demo_normalization():
    test_cases = [
        "Петров С.С.",
        "Георгий Иванов",
        "Дмитрий А.А.",
        "Алексей Козлов",
        "Козлов Алексей",
        "Анна В.В.",
        "Алексей Смирнов",
        "Смирнов Алексей"
    ]
    print("\n=== Демонстрация нормализации ===")
    for name in test_cases:
        norm = normalize_name(name)
        print(f"{name:25} -> {norm}")


# -------------------------------------------------------------------
# 8. Главный блок
# -------------------------------------------------------------------
if __name__ == "__main__":
    print("1. Создание баз данных...")
    create_databases()
    print("2. Заполнение источников (7 вариаций ФИО)...")
    populate_sources()
    print("3. Демонстрация нормализации...")
    demo_normalization()
    print("4. Запуск ETL...")
    etl()
    print("5. Результат объединения:")
    show_results()
