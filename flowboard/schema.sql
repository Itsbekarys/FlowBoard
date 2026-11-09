CREATE TABLE IF NOT EXISTS projects (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 color TEXT NOT NULL DEFAULT '#8b7cf8', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
 title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL CHECK(status IN ('todo','progress','review','done')),
 priority TEXT NOT NULL CHECK(priority IN ('low','medium','high')),
 assignee TEXT NOT NULL DEFAULT '', due_date TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS tasks_project_status ON tasks(project_id,status);
CREATE TABLE IF NOT EXISTS activity (
 id INTEGER PRIMARY KEY, message TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
