import Editor, { type OnMount } from "@monaco-editor/react";
import { useEffect, useRef } from "react";

import { EDITOR_LANGUAGE } from "../../utils/monacoSetup";

type MonacoEditor = Parameters<OnMount>[0];

/** Read-only Monaco viewer that highlights a line range and scrolls to it. */
export function CodeViewer({
  code,
  language,
  highlight,
  height = "100%",
}: {
  code: string;
  language: string;
  highlight: [number, number] | null;
  height?: string;
}) {
  const editorRef = useRef<MonacoEditor | null>(null);
  const decorations = useRef<string[]>([]);

  function apply() {
    const editor = editorRef.current;
    if (!editor) return;
    if (!highlight) {
      decorations.current = editor.deltaDecorations(decorations.current, []);
      return;
    }
    const [start, end] = highlight;
    decorations.current = editor.deltaDecorations(decorations.current, [
      {
        range: { startLineNumber: start, startColumn: 1, endLineNumber: end, endColumn: 1 },
        options: {
          isWholeLine: true,
          className: "xai-line-highlight",
          linesDecorationsClassName: "xai-line-glyph",
        },
      },
    ]);
    editor.revealLinesInCenterIfOutsideViewport(start, end);
  }

  useEffect(apply, [highlight]);

  return (
    <Editor
      height={height}
      language={EDITOR_LANGUAGE[language] ?? "plaintext"}
      value={code}
      onMount={(editor) => {
        editorRef.current = editor;
        apply();
      }}
      options={{
        readOnly: true,
        domReadOnly: true,
        minimap: { enabled: false },
        fontSize: 13,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        renderLineHighlight: "none",
        ariaLabel: "Submitted code (read only)",
      }}
    />
  );
}
