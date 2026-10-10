import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  window.localStorage.clear();
});

// Monaco cannot run in jsdom: replace the editors with simple elements.
vi.mock("@monaco-editor/react", () => ({
  default: ({
    value,
    onChange,
    options,
  }: {
    value: string;
    onChange?: (v: string) => void;
    options?: { ariaLabel?: string };
  }) =>
    createElement("textarea", {
      "aria-label": options?.ariaLabel ?? "editor",
      value,
      readOnly: !onChange,
      onChange: (e: { target: { value: string } }) => onChange?.(e.target.value),
    }),
  DiffEditor: ({ original, modified }: { original: string; modified: string }) =>
    createElement("div", { "data-testid": "monaco-diff" }, `${original}\n---\n${modified}`),
  loader: { config: () => undefined },
}));
vi.mock("../src/utils/monacoSetup", () => ({
  EDITOR_LANGUAGE: { auto: "plaintext", python: "python", javascript: "javascript", java: "java" },
}));
