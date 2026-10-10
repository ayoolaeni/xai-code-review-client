import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CodeEditor } from "../../src/components/CodeEditor";
import { FileUploadButton } from "../../src/components/InputControls";

describe("FileUploadButton (FR1, FR3)", () => {
  it("rejects unsupported file types with an inline error", async () => {
    const user = userEvent.setup({ applyAccept: false });
    const onLoaded = vi.fn();
    render(<FileUploadButton onLoaded={onLoaded} filename={null} />);
    await user.upload(
      screen.getByTestId("file-input"),
      new File(["puts 1"], "script.rb", { type: "text/plain" }),
    );
    expect(await screen.findByTestId("upload-error")).toHaveTextContent("not a supported file type");
    expect(onLoaded).not.toHaveBeenCalled();
  });

  it("loads a .java file and reports its language", async () => {
    const user = userEvent.setup();
    const onLoaded = vi.fn();
    render(<FileUploadButton onLoaded={onLoaded} filename={null} />);
    await user.upload(
      screen.getByTestId("file-input"),
      new File(["class A {}"], "A.java", { type: "text/x-java" }),
    );
    await vi.waitFor(() => expect(onLoaded).toHaveBeenCalled());
    expect(onLoaded.mock.calls[0][0]).toEqual({ name: "A.java", text: "class A {}", language: "java" });
  });

  it("rejects files larger than 1 MB", async () => {
    const user = userEvent.setup();
    render(<FileUploadButton onLoaded={vi.fn()} filename={null} />);
    const big = new File(["x".repeat(1024 * 1024 + 1)], "big.py", { type: "text/x-python" });
    await user.upload(screen.getByTestId("file-input"), big);
    expect(await screen.findByTestId("upload-error")).toHaveTextContent("larger than 1 MB");
  });
});

describe("CodeEditor line counter (FR3)", () => {
  it("shows the live count", () => {
    render(
      <CodeEditor
        value={"a\nb\nc"}
        onChange={() => undefined}
        language="auto"
        maxLines={400}
        maxChars={40000}
      />,
    );
    expect(screen.getByTestId("line-counter")).toHaveTextContent("Lines: 3 / 400");
  });

  it("turns red when over the limit", () => {
    const code = Array.from({ length: 6 }, (_, i) => `x${i} = ${i}`).join("\n");
    render(
      <CodeEditor value={code} onChange={() => undefined} language="python" maxLines={5} maxChars={40000} />,
    );
    const counter = screen.getByTestId("line-counter");
    expect(counter).toHaveTextContent("Lines: 6 / 5");
    expect(counter).toHaveTextContent("too long");
    expect(counter.className).toContain("text-red-800");
  });
});
