import { useState } from "react";

import { api, ApiError } from "../../api/client";
import type { Report } from "../../api/types";
import { getFeedbackToken, setFeedbackToken } from "../../utils/storage";

export function FeedbackWidget({ report }: { report: Report }) {
  const initial = report.feedback;
  const [rating, setRating] = useState<number | null>(initial.rating);
  const [helpful, setHelpful] = useState<boolean | null>(initial.was_helpful);
  const [comment, setComment] = useState(initial.comment ?? "");
  const [submitted, setSubmitted] = useState(initial.rating !== null);
  const [editing, setEditing] = useState(initial.rating === null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (rating === null || helpful === null) {
      setError("Please choose a rating and answer whether the explanation was helpful.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.sendFeedback(report.public_id, {
        rating,
        was_helpful: helpful,
        comment: comment.trim() || null,
        feedback_token: report.owner === "guest" ? getFeedbackToken(report.public_id) : null,
      });
      if (res.feedback_token) setFeedbackToken(report.public_id, res.feedback_token);
      setSubmitted(true);
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Your rating could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  if (submitted && !editing) {
    return (
      <section className="card" aria-labelledby="feedback-title">
        <h2 id="feedback-title">Thank you for your feedback</h2>
        <p className="mt-1 text-sm text-muted">
          You rated this explanation {rating} out of 5 and said it was {helpful ? "helpful" : "not helpful"}.
        </p>
        <button type="button" className="btn-link mt-2" onClick={() => setEditing(true)}>
          Edit your rating
        </button>
      </section>
    );
  }

  return (
    <form className="card space-y-4" aria-labelledby="feedback-title" onSubmit={submit}>
      <h2 id="feedback-title">Rate this explanation</h2>
      <fieldset>
        <legend className="label">How good was the explanation? (1 = poor, 5 = excellent)</legend>
        <div className="flex gap-1" role="radiogroup">
          {[1, 2, 3, 4, 5].map((n) => (
            <label key={n} className="cursor-pointer">
              <input
                type="radio"
                name="rating"
                value={n}
                className="peer sr-only"
                checked={rating === n}
                onChange={() => setRating(n)}
              />
              <span
                className={`flex h-10 w-10 items-center justify-center rounded-md border text-lg peer-focus-visible:ring-2 peer-focus-visible:ring-blue-700 ${
                  rating !== null && n <= rating
                    ? "border-amber-600 bg-amber-100 text-amber-900"
                    : "border-line"
                }`}
              >
                <span aria-hidden="true">★</span>
                <span className="sr-only">
                  {n} star{n > 1 ? "s" : ""}
                </span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="label">Was this explanation helpful?</legend>
        <div className="flex gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="radio" name="helpful" checked={helpful === true} onChange={() => setHelpful(true)} />{" "}
            Yes
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="helpful"
              checked={helpful === false}
              onChange={() => setHelpful(false)}
            />{" "}
            No
          </label>
        </div>
      </fieldset>
      <div>
        <label htmlFor="feedback-comment" className="label">
          Comment (optional)
        </label>
        <textarea
          id="feedback-comment"
          className="input min-h-[80px]"
          maxLength={2000}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
        <p className="hint">{comment.length} / 2000</p>
      </div>
      {error && (
        <p role="alert" className="text-sm font-semibold text-red-800">
          {error}
        </p>
      )}
      <button type="submit" className="btn-primary" disabled={busy}>
        {busy ? "Sending…" : "Submit rating"}
      </button>
    </form>
  );
}
