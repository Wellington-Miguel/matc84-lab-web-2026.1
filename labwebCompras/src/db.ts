import pg from "pg";

const { Pool } = pg;

export const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

// Retry simples na primeira conexão: postgres pode demorar a subir.
export async function waitForDb(retries = 10, delayMs = 1500): Promise<void> {
  for (let i = 0; i < retries; i++) {
    try {
      await pool.query("SELECT 1");
      return;
    } catch (err) {
      console.log(`[db] indisponível, retry ${i + 1}/${retries}...`);
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  throw new Error("Postgres não respondeu após retries");
}
