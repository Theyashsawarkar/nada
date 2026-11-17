// node:sqlite behind the same small interface as expo-sqlite, so tests run the
// app's real SQL on the laptop.
import { DatabaseSync } from "node:sqlite";
import { migrate, type Param, type Sql } from "../src/core/db";

export function memoryDb(): Sql {
  const d = new DatabaseSync(":memory:");
  const db: Sql = {
    execSync: (sql) => d.exec(sql),
    runSync: (sql, ...p: Param[]) => {
      const r = d.prepare(sql).run(...p);
      return { changes: Number(r.changes), lastInsertRowId: Number(r.lastInsertRowid) };
    },
    getAllSync: <T>(sql: string, ...p: Param[]) => d.prepare(sql).all(...p) as T[],
    getFirstSync: <T>(sql: string, ...p: Param[]) => (d.prepare(sql).get(...p) as T | undefined) ?? null,
  };
  migrate(db);
  return db;
}
