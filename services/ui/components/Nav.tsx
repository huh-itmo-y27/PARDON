import Link from "next/link";

export function Nav() {
  return (
    <nav style={{ display: "flex", gap: 12, padding: "12px 24px", borderBottom: "1px solid #1e293b" }}>
      <Link href="/">Dashboard</Link>
      <Link href="/predictions">Recent predictions</Link>
      <Link href="/experiments">Experiments</Link>
      <Link href="/notifications">Drift notifications</Link>
    </nav>
  );
}

