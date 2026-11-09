import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path


class ValidationError(ValueError):
    pass


class Store:
    STATUSES = ('todo', 'progress', 'review', 'done')
    PRIORITIES = ('low', 'medium', 'high')

    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript((Path(__file__).parent / 'schema.sql').read_text(encoding='utf-8'))
            if not db.execute('SELECT 1 FROM projects LIMIT 1').fetchone():
                self.seed(db)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def seed(self, db):
        db.executemany('INSERT INTO projects(name,description,color) VALUES(?,?,?)', [
            ('Запуск платформы', 'От первых макетов до первого релиза', '#8b7cf8'),
            ('Мобильное приложение', 'Продукт, который всегда под рукой', '#f4ae62'),
            ('Маркетинг', 'Рассказываем о том, что делаем', '#61c3ae')])
        tasks = [
            (1,'Собрать референсы для главной','Подобрать примеры навигации, типографики и карточек.','todo','medium','Анна',3),
            (1,'Спроектировать личный кабинет','Профиль, настройки и список проектов.','todo','high','Марк',4),
            (1,'Подготовить API проектов','Описать создание проектов и работу с задачами.','progress','high','Данил',1),
            (1,'Сверстать доску задач','Адаптивные колонки, карточки и состояния загрузки.','progress','medium','Анна',2),
            (1,'Проверить сценарий регистрации','Проверить ошибки ввода и переходы между экранами.','review','high','Марк',0),
            (1,'Настроить структуру проекта','Разделить интерфейс, сервер и хранение данных.','done','low','Данил',-2),
            (1,'Согласовать визуальный стиль','Палитра, шрифты и базовые компоненты.','done','medium','Анна',-1),
            (2,'Нарисовать экран проектов','Показать прогресс и ближайшие задачи.','todo','medium','Марк',7),
            (3,'Подготовить план запуска','Каналы, материалы и даты публикаций.','progress','high','Анна',5)]
        db.executemany('INSERT INTO tasks(project_id,title,description,status,priority,assignee,due_date) VALUES(?,?,?,?,?,?,?)',
            [(*t[:-1], (date.today()+timedelta(days=t[-1])).isoformat()) for t in tasks])
        db.execute("INSERT INTO activity(message) VALUES('Рабочее пространство готово. Можно начинать.')")

    @staticmethod
    def text(data, key, limit, required=False):
        value = data.get(key, '')
        if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
            raise ValidationError(f'Проверьте поле «{key}» (до {limit} символов)')
        return value.strip()

    def state(self):
        with self.connect() as db:
            return {name: [dict(row) for row in db.execute(query)] for name, query in {
                'projects': 'SELECT * FROM projects ORDER BY id',
                'tasks': 'SELECT * FROM tasks ORDER BY id DESC',
                'activity': 'SELECT * FROM activity ORDER BY id DESC LIMIT 20'}.items()}

    def create_project(self, data):
        name = self.text(data, 'name', 80, True)
        description = self.text(data, 'description', 500)
        with self.connect() as db:
            cursor = db.execute('INSERT INTO projects(name,description) VALUES(?,?)', (name, description))
            db.execute('INSERT INTO activity(message) VALUES(?)', (f'Создан проект «{name}»',))
            return dict(db.execute('SELECT * FROM projects WHERE id=?', (cursor.lastrowid,)).fetchone())

    def validate_task(self, data):
        result = {key: self.text(data, key, limit, key == 'title') for key, limit in
                  [('title', 160), ('description', 5000), ('assignee', 80), ('due_date', 10)]}
        result['status'] = data.get('status', 'todo')
        result['priority'] = data.get('priority', 'medium')
        if result['status'] not in self.STATUSES or result['priority'] not in self.PRIORITIES:
            raise ValidationError('Неизвестный статус или приоритет')
        if result['due_date']:
            try:
                date.fromisoformat(result['due_date'])
            except ValueError:
                raise ValidationError('Неверная дата')
        project_id = data.get('project_id')
        if type(project_id) is not int:
            raise ValidationError('Выберите проект')
        result['project_id'] = project_id
        return result

    def create_task(self, data):
        values = self.validate_task(data)
        with self.connect() as db:
            if not db.execute('SELECT id FROM projects WHERE id=?', (values['project_id'],)).fetchone():
                raise ValidationError('Проект не найден')
            keys = ','.join(values)
            cursor = db.execute(f'INSERT INTO tasks({keys}) VALUES({",".join("?" for _ in values)})', tuple(values.values()))
            db.execute('INSERT INTO activity(message) VALUES(?)', (f'Добавлена задача «{values["title"]}»',))
            return dict(db.execute('SELECT * FROM tasks WHERE id=?', (cursor.lastrowid,)).fetchone())

    def update_task(self, task_id, data):
        with self.connect() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
            if not row:
                raise LookupError('Задача не найдена')
            values = self.validate_task({**dict(row), **data})
            if not db.execute('SELECT id FROM projects WHERE id=?', (values['project_id'],)).fetchone():
                raise ValidationError('Проект не найден')
            db.execute(f'UPDATE tasks SET {",".join(k+"=?" for k in values)},updated_at=CURRENT_TIMESTAMP WHERE id=?', (*values.values(), task_id))
            db.execute('INSERT INTO activity(message) VALUES(?)', (f'Обновлена задача «{values["title"]}»',))
            return dict(db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone())

    def delete_task(self, task_id):
        with self.connect() as db:
            row = db.execute('SELECT title FROM tasks WHERE id=?', (task_id,)).fetchone()
            if not row:
                raise LookupError('Задача не найдена')
            db.execute('DELETE FROM tasks WHERE id=?', (task_id,))
            db.execute('INSERT INTO activity(message) VALUES(?)', (f'Удалена задача «{row["title"]}»',))
            return {'deleted': task_id}
