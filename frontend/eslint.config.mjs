// Next 16's eslint-config-next ships native flat configs, so they are imported
// directly — no FlatCompat shim required.
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const eslintConfig = [
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    // `.next-dev` is the dev server's distDir (see next.config.mjs). Linting it
    // scans thousands of generated files and drowns the real signal.
    ignores: [
      "node_modules/**",
      ".next/**",
      ".next-dev/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
    ],
  },
  {
    rules: {
      // This rule fires whenever setState is *reachable* from an effect body,
      // including through an async function. In this app the flagged cases are
      // client-side data fetches whose setState happens after `await`, so there
      // is no synchronous cascade. Kept as a warning to keep it visible rather
      // than silenced, and to catch the real variant if one is introduced.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
];

export default eslintConfig;