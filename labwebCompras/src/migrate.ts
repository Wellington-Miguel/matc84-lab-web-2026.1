import { runner } from "node-pg-migrate";

// Roda migrations pendentes em processo, no startup.
// Evita o CLI node-pg-migrate, que sai com código 255 mesmo em sucesso
// (Node 24 + node-pg-migrate 7.x) e quebraria chains `&& node ...`.
export async function migrate(): Promise<void> {
  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) throw new Error("DATABASE_URL não definida");

  await runner({
    databaseUrl,
    dir: "migrations",
    direction: "up",
    migrationsTable: "pgmigrations",
    count: Infinity,
    log: (msg) => console.log(`[migrate] ${msg}`),
  });
}
