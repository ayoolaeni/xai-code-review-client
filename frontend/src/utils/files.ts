import type { LanguageId } from "../api/types";

export const ACCEPTED_EXTENSIONS = [".py", ".js", ".mjs", ".cjs", ".java"];
export const MAX_FILE_BYTES = 1024 * 1024;

const EXTENSION_LANGUAGE: Record<string, LanguageId> = {
  ".py": "python",
  ".js": "javascript",
  ".mjs": "javascript",
  ".cjs": "javascript",
  ".java": "java",
};

export function extensionOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}

export function languageForFile(name: string): LanguageId | null {
  return EXTENSION_LANGUAGE[extensionOf(name)] ?? null;
}

export class FileRejected extends Error {}

export interface LoadedFile {
  name: string;
  text: string;
  language: LanguageId;
}

/** Read an uploaded source file as text (FR1) after checking its type and size (FR3). */
export function readSourceFile(file: File): Promise<LoadedFile> {
  const language = languageForFile(file.name);
  if (!language) {
    return Promise.reject(
      new FileRejected(
        `"${file.name}" is not a supported file type. Please choose a .py, .js, .mjs, .cjs or .java file.`,
      ),
    );
  }
  if (file.size > MAX_FILE_BYTES) {
    return Promise.reject(
      new FileRejected(`"${file.name}" is larger than 1 MB. Please choose a smaller file.`),
    );
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({ name: file.name, text: String(reader.result ?? ""), language });
    reader.onerror = () => reject(new FileRejected(`"${file.name}" could not be read.`));
    reader.readAsText(file);
  });
}
