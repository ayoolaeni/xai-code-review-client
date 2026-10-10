// Bundle Monaco locally (no CDN) so the strict Content-Security-Policy works (spec Section 12.5).
import { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import "monaco-editor/esm/vs/basic-languages/java/java.contribution";
import "monaco-editor/esm/vs/basic-languages/javascript/javascript.contribution";
import "monaco-editor/esm/vs/basic-languages/python/python.contribution";

self.MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};

loader.config({ monaco });

export const EDITOR_LANGUAGE: Record<string, string> = {
  auto: "plaintext",
  python: "python",
  javascript: "javascript",
  java: "java",
};
