/** The phone's database, opened once and brought up to date. */
import { openDatabaseSync } from "expo-sqlite";
import { migrate, type Sql } from "./db";

let db: Sql | null = null;

export function getDb(): Sql {
  if (!db) {
    db = openDatabaseSync("nada.db") as unknown as Sql;
    migrate(db);
  }
  return db;
}

export const now = () => Math.floor(Date.now() / 1000);

export function setting(key: string, fallback: string): string {
  return getDb().getFirstSync<{ value: string }>("SELECT value FROM setting WHERE key = ?", key)?.value ?? fallback;
}

export function setSetting(key: string, value: string): void {
  getDb().runSync("INSERT INTO setting(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", key, value);
}
