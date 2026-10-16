/**
 * Production start for `output: "standalone"`.
 *
 * `next start` refuses to run when standalone output is enabled, and the
 * standalone server does not include `public/` or `.next/static` inside its own
 * folder. Both are copied in here, then the traced server is launched.
 *
 * The Dockerfile relies on the same layout, so this mirrors what it does.
 */
import { cpSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const standalone = join(root, ".next", "standalone");

if (!existsSync(join(standalone, "server.js"))) {
  console.error(
    "No standalone build found. Run `npm run build` before `npm start`.",
  );
  process.exit(1);
}

const copies = [
  [join(root, ".next", "static"), join(standalone, ".next", "static")],
  [join(root, "public"), join(standalone, "public")],
];

for (const [from, to] of copies) {
  if (!existsSync(from)) continue;
  cpSync(from, to, { recursive: true });
  console.log(`copied ${from.replace(root, ".")} -> ${to.replace(root, ".")}`);
}

const server = spawn(process.execPath, [join(standalone, "server.js")], {
  stdio: "inherit",
  env: { ...process.env, PORT: process.env.PORT ?? "3000" },
});

server.on("exit", (code) => process.exit(code ?? 0));
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.kill(signal));
}