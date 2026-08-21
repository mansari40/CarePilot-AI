import { useEffect, useState } from "react";

type Health = { status: string; service: string };

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then((data: Health) => setHealth(data))
      .catch((err) => setError(String(err)));
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-800">
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-semibold text-teal-700">AgentCare</h1>
        <p className="mt-2 text-sm text-slate-500">
          Agentic AI for patient administration and care coordination.
        </p>
        <p className="mt-6 text-xs text-slate-400">
          {error
            ? `Backend unreachable: ${error}`
            : health
              ? `Backend: ${health.status} (${health.service})`
              : "Checking backend…"}
        </p>
      </div>
    </div>
  );
}