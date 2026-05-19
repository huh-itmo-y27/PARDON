import Link from "next/link";

import { getNotifications } from "../api";

export default async function NotificationsPage({
  searchParams,
}: {
  searchParams?: { page?: string; limit?: string; only_unread?: string };
}) {
  const pageRaw = Number(searchParams?.page ?? "0");
  const limitRaw = Number(searchParams?.limit ?? "30");
  const page = Number.isFinite(pageRaw) && pageRaw >= 0 ? Math.floor(pageRaw) : 0;
  const limit =
    Number.isFinite(limitRaw) && limitRaw >= 1 && limitRaw <= 200
      ? Math.floor(limitRaw)
      : 30;
  const onlyUnread = searchParams?.only_unread === "true";
  const offset = page * limit;
  const rows = await getNotifications(limit, offset, onlyUnread);
  const prevParams = new URLSearchParams();
  const nextParams = new URLSearchParams();
  prevParams.set("page", String(Math.max(0, page - 1)));
  nextParams.set("page", String(page + 1));
  prevParams.set("limit", String(limit));
  nextParams.set("limit", String(limit));
  if (onlyUnread) {
    prevParams.set("only_unread", "true");
    nextParams.set("only_unread", "true");
  }
  return (
    <>
      <h1>Drift notifications</h1>
      <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
        <Link
          href={
            onlyUnread
              ? `/notifications?page=0&limit=${limit}`
              : `/notifications?page=0&limit=${limit}&only_unread=true`
          }
        >
          {onlyUnread ? "Show all" : "Only unread"}
        </Link>
        {page > 0 ? (
          <Link href={`/notifications?${prevParams.toString()}`} aria-label="Previous page">
            ← Prev {limit}
          </Link>
        ) : (
          <span style={{ opacity: 0.5 }}>← Prev {limit}</span>
        )}
        <span>Page {page + 1}</span>
        {rows.length === limit ? (
          <Link href={`/notifications?${nextParams.toString()}`} aria-label="Next page">
            Next {limit} →
          </Link>
        ) : (
          <span style={{ opacity: 0.5 }}>Next {limit} →</span>
        )}
      </div>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Severity</th>
            <th>Title</th>
            <th>Message</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{new Date(row.created_at).toLocaleString()}</td>
              <td>
                <span className={`badge badge-${row.severity}`}>{row.severity}</span>
              </td>
              <td>{row.title}</td>
              <td>{row.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

