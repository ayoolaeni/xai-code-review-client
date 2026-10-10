import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "../api/client";

export function AboutPage() {
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: 5 * 60_000 });
  useEffect(() => {
    document.title = "About · Explainable AI Code Review Assistant";
  }, []);
  const hours = meta.data?.guest_retention_hours ?? 24;

  return (
    <article className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1>About this assistant</h1>
        <p className="mt-2 text-muted">
          The Explainable AI Code Review Assistant explains source code in plain language and shows, for every
          problem it reports, where the problem is, why it matters, how to fix it, how serious it is and how
          confident the system is — so you can decide for yourself whether the code is safe to use.
        </p>
      </header>

      <section className="card space-y-2">
        <h2>How it works</h2>
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          <li>Your code is checked (size, type) and the language is detected.</li>
          <li>Passwords, API keys and other secrets are masked.</li>
          <li>
            Rule-based static analysis tools (Semgrep, Bandit, ESLint, PMD) look for known weaknesses. The
            code is only read — it is never run.
          </li>
          <li>
            An AI model explains the code, reviews the tool findings, lists further problems and suggests an
            improved version, following a fixed answer format.
          </li>
          <li>A second, independent AI review checks the first one for consistency.</li>
          <li>
            Findings from the tools and the AI are combined. Severity and confidence are assigned with fixed
            rules, and the system decides whether a human expert should review the code.
          </li>
          <li>The improved code is syntax-checked and scanned again before it is shown to you.</li>
        </ol>
      </section>

      <section className="card space-y-2">
        <h2>How to read confidence</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            <strong>High</strong> — found by both static analysis and the AI, or consistently by two
            independent AI reviews with a recognised weakness category.
          </li>
          <li>
            <strong>Medium</strong> — found by a static analysis rule, or by the AI consistently but without a
            recognised category.
          </li>
          <li>
            <strong>Low</strong> — the AI was uncertain, the issue did not appear in the second review, or the
            AI judged a tool finding to be a false positive.
          </li>
        </ul>
      </section>

      <section className="card space-y-2">
        <h2>Privacy</h2>
        {meta.data && <p className="text-sm">{meta.data.privacy_notice}</p>}
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>Detected secrets are replaced with placeholders before anything is sent to the AI service.</li>
          <li>Guest reports and code are deleted automatically after {hours} hours.</li>
          <li>
            Registered users decide whether their code is kept in their history. If not, only a copy with
            secrets masked is kept so the report keeps working.
          </li>
          <li>Passwords are stored as salted hashes. API keys never leave the server.</li>
        </ul>
      </section>

      <section className="card space-y-2">
        <h2>Limitations</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            The code is analysed as text only. Behaviour that depends on runtime data, other files or external
            services cannot be checked.
          </li>
          <li>
            AI explanations can be incomplete or wrong, and the AI&apos;s stated reasoning may not reflect how
            it produced its answer.
          </li>
          <li>Static analysis tools can miss real problems and can report problems that are not real.</li>
          <li>Only single files of Python, JavaScript or Java are supported.</li>
          <li>
            A clean report does not prove the code is safe. You remain responsible for the code you use.
          </li>
        </ul>
      </section>
    </article>
  );
}
