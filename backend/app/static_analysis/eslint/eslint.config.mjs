import security from "eslint-plugin-security";
import globals from "globals";

export default [
  {
    files: ["**/*.js", "**/*.mjs", "**/*.cjs"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: { ...globals.node, ...globals.browser },
    },
  },
  security.configs.recommended,
  {
    rules: {
      "security/detect-object-injection": "off", // too many false positives
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "eqeqeq": "warn",
      "no-unused-vars": "warn",
      "no-undef": "warn",
      "no-empty": "warn",
      "no-unreachable": "error",
      "no-dupe-keys": "error",
      "no-constant-condition": "warn",
      "require-await": "warn",
      "no-async-promise-executor": "error",
      "no-prototype-builtins": "warn"
    },
  },
];
