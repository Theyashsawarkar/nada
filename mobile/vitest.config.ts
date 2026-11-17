import { defineConfig } from "vitest/config";

// `pnpm test` never touches the network; `pnpm live` asks YouTube for real.
export default defineConfig({ test: { include: process.env.LIVE ? [`scripts/${process.env.LIVE === "1" ? "live-check" : process.env.LIVE}.test.ts`] : ["test/**/*.test.ts"] } });
