import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-xl py-10 text-center">
      <h1>Page not found</h1>
      <p className="mt-2 text-muted">The page you are looking for does not exist.</p>
      <Link to="/" className="btn-primary mt-6 no-underline">
        Go to the code analyser
      </Link>
    </div>
  );
}
