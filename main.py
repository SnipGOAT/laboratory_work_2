import sqlite3
import re
import os

# ------------------------------------------------------------
# 1. Создание баз и таблиц
# ------------------------------------------------------------
def create_databases():
    for db in ["source1.db", "source2.db", "datawarehouse.db"]:
        if os.path.exists(db):
            os.remove(db)

    # Источник 1: проекты
    with sqlite3.connect("source1.db") as conn:
        conn.execute('''
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                role TEXT,
                project_name TEXT,
                tech_stack TEXT
            )
        ''')

    # Источник 2: резюме
    with sqlite3.connect("source2.db") as conn:
        conn.execute('''
            CREATE TABLE resumes (
                id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                competencies TEXT,
                salary REAL,
                bonus REAL
            )
        ''')

    # Хранилище данных
    with sqlite3.connect("datawarehouse.db") as conn:
        conn.execute('''
            CREATE TABLE unified_employee (
                id INTEGER PRIMARY KEY,
                normalized_name TEXT UNIQUE,
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
    print("Базы данных и таблицы созданы.")

# ------------------------------------------------------------
# 2. Заполнение источников данными (5 вариаций ФИО)
# ------------------------------------------------------------
def populate_sources():
    # Данные для source1: (ФИО, роль, проект, стек)
    data1 = [
        ("Иванов Иван Иванович", "Team Lead", "Платформа аналитики", "Python, SQL, Airflow"),
        ("петров петр петрович", "Developer", "Мобильное приложение", "Kotlin, Android SDK"),
        ("СидорОВ СИДОР Сидорович", "QA Engineer", "Тестирование API", "Postman, JMeter"),
        ("Алексей Козлов", "DevOps", "Облачная инфраструктура", "Terraform, AWS"),
        ("мария смирнова", "Analyst", "BI-отчётность", "Tableau, Excel")
    ]
    with sqlite3.connect("source1.db") as conn:
        for full_name, role, project, stack in data1:
            conn.execute(
                "INSERT INTO projects (full_name, role, project_name, tech_stack) VALUES (?, ?, ?, ?)",
                (full_name, role, project, stack)
            )
    print("source1 заполнен (5 записей).")

    # Данные для source2: (ФИО, компетенции, зарплата, премия)
    data2 = [
        ("иванов иван иванович", "Python, SQL, DWH", 120000, 15000),
        ("Петр Петрович Петров", "Kotlin, CI/CD", 110000, 12000),
        ("Сидорович СИДОР сидоров", "Postman, SQL", 95000, 8000),
        ("Козлов Алексей", "Terraform, AWS", 130000, 20000),
        ("СМИРНОВА МАРИЯ", "Tableau, Python", 105000, 10000)
    ]
    with sqlite3.connect("source2.db") as conn:
        for full_name, comp, salary, bonus in data2:
            conn.execute(
                "INSERT INTO resumes (full_name, competencies, salary, bonus) VALUES (?, ?, ?, ?)",
                (full_name, comp, salary, bonus)
            )
    print("source2 заполнен (5 записей).")

# ------------------------------------------------------------
# 3. Функция нормализации ФИО
# ------------------------------------------------------------
def normalize_name(name: str) -> str:
    """
    Приводит ФИО к каноническому виду:
    - удаляет знаки препинания
    - переводит в нижний регистр
    - разбивает на слова, сортирует их
    - соединяет пробелом
    Пример: "Петр Петрович Петров" -> "петр петрович петров"
    """
    clean = re.sub(r'[^\w\s]', '', name)  # убираем точки, запятые и т.п.
    words = clean.lower().split()
    words.sort()
    return " ".join(words)

# ------------------------------------------------------------
# 4. ETL процесс: чтение, нормализация, объединение, запись в ХД
# ------------------------------------------------------------
def run_etl():
    with sqlite3.connect("source1.db") as conn1, \
         sqlite3.connect("source2.db") as conn2, \
         sqlite3.connect("datawarehouse.db") as dw:

        # Читаем source1
        rows1 = conn1.execute("SELECT full_name, role, project_name, tech_stack FROM projects").fetchall()
        # Читаем source2
        rows2 = conn2.execute("SELECT full_name, competencies, salary, bonus FROM resumes").fetchall()

        merged = {}  # ключ = нормализованное ФИО

        # Загружаем данные из source1
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
                # Обновляем (на случай дубликатов в одном источнике – но у нас их нет)
                merged[norm]["original_src1"] = full_name
                merged[norm]["role"] = role
                merged[norm]["project_name"] = project
                merged[norm]["tech_stack"] = stack

        # Загружаем данные из source2 (добавляем или объединяем)
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

        # Вставка / обновление в ХД
        for norm, data in merged.items():
            try:
                dw.execute('''
                    INSERT INTO unified_employee (
                        normalized_name, original_name_src1, original_name_src2,
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
                # Если уже есть такой normalized_name, обновляем
                dw.execute('''
                    UPDATE unified_employee SET
                        original_name_src1 = COALESCE(original_name_src1, ?),
                        original_name_src2 = COALESCE(original_name_src2, ?),
                        role = COALESCE(role, ?),
                        project_name = COALESCE(project_name, ?),
                        tech_stack = COALESCE(tech_stack, ?),
                        competencies = COALESCE(competencies, ?),
                        salary = COALESCE(salary, ?),
                        bonus = COALESCE(bonus, ?)
                    WHERE normalized_name = ?
                ''', (
                    data["original_src1"], data["original_src2"],
                    data["role"], data["project_name"], data["tech_stack"],
                    data["competencies"], data["salary"], data["bonus"],
                    norm
                ))
        dw.commit()
    print("ETL выполнен. Данные объединены в datawarehouse.db")

# ------------------------------------------------------------
# 5. Показать результат
# ------------------------------------------------------------
def show_result():
    with sqlite3.connect("datawarehouse.db") as conn:
        cursor = conn.execute("SELECT * FROM unified_employee")
        rows = cursor.fetchall()
        print("\n=== Содержимое Хранилища данных ===")
        for row in rows:
            print(f"normalized_name: {row[1]}")
            print(f"  src1: {row[2]}")
            print(f"  src2: {row[3]}")
            print(f"  role: {row[4]}, project: {row[5]}, stack: {row[6]}")
            print(f"  competencies: {row[7]}, salary: {row[8]}, bonus: {row[9]}\n")

# ------------------------------------------------------------
# Главный блок
# ------------------------------------------------------------
if __name__ == "__main__":
    create_databases()
    populate_sources()
    run_etl()
    show_result()