/**
 * Dev launcher.
 *
 * Runs `next dev` against `.next-dev` instead of `.next`, so a production
 * build can run at the same time without overwriting the running dev server's
 * compiled output. Sharing one directory between the two is the reason a build
 * used to leave `next dev` serving pages that no longer matched the source.
 *
 * The build side keeps `.next`; see the `distDir` note in next.config.mjs.
 *
 * Cross-platform by design: it sets the variable on the child process rather
 * than relying on `VAR=value cmd` shell syntax, which does not work on Windows.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const nextBin = join(root, "node_modules", "next", "dist", "bin", "next");

if (!existsSync(nextBin)) {
  console.error("Next.js is not installed. Run `npm install` first.");
  process.exit(1);
}

const distDir = process.env.NEXT_DIST_DIR || ".next-dev";
const args = ["dev", ...process.argv.slice(2)];

console.log(`next dev -> distDir=${distDir}`);

const child = spawn(process.execPath, [nextBin, ...args], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, NEXT_DIST_DIR: distDir },
});

child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 0);
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}