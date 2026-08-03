import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import GlassPanel from "../components/GlassPanel";

interface Chapter { slug: string; title: string; part: string; summary: string; updated: string }
interface Full extends Chapter {
  markdown: string;
  prev: { slug: string; title: string } | null;
  next: { slug: string; title: string } | null;
}

export default function Knowledge() {
  const { slug } = useParams();
  const nav = useNavigate();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [doc, setDoc] = useState<Full | null>(null);

  useEffect(() => {
    fetch("/api/knowledge").then((r) => r.json())
      .then((r) => setChapters(r.chapters)).catch(console.error);
  }, []);
  useEffect(() => {
    if (!slug) { setDoc(null); return; }
    setDoc(null);
    fetch(`/api/knowledge/${slug}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => { setDoc(d); window.scrollTo(0, 0); })
      .catch(console.error);
  }, [slug]);

  const parts = [...new Set(chapters.map((c) => c.part))];

  if (!slug) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">The NFL Knowledge Book</h1>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            Football from first principles — the game, the schemes, the rulebook,
            and the numbers. Chapters are plain markdown in docs/knowledge/;
            edit them anytime, no rebuild needed.
          </p>
        </div>
        {parts.map((p) => (
          <div key={p}>
            <h2 className="mb-3 text-sm font-bold uppercase tracking-widest"
                style={{ color: "var(--arc)" }}>Part {p}</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {chapters.filter((c) => c.part === p).map((c) => (
                <Link key={c.slug} to={`/knowledge/${c.slug}`}
                      className="glass block p-4 transition-transform hover:-translate-y-0.5">
                  <div className="font-semibold">{c.title}</div>
                  <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{c.summary}</p>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex gap-8">
      <aside className="sticky top-20 hidden max-h-[80vh] w-56 shrink-0 space-y-4 self-start overflow-y-auto lg:block">
        <Link to="/knowledge" className="text-xs font-bold uppercase tracking-widest hover:underline"
              style={{ color: "var(--arc)" }}>← contents</Link>
        {parts.map((p) => (
          <div key={p}>
            <div className="mb-1 text-[11px] font-bold uppercase tracking-wider"
                 style={{ color: "var(--muted)" }}>{p}</div>
            <ul className="space-y-0.5 text-sm">
              {chapters.filter((c) => c.part === p).map((c) => (
                <li key={c.slug}>
                  <Link to={`/knowledge/${c.slug}`}
                        className={`block rounded px-2 py-1 ${c.slug === slug ? "font-semibold" : "hover:bg-white/5"}`}
                        style={{ color: c.slug === slug ? "var(--arc)" : "var(--text)" }}>
                    {c.title}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </aside>

      <div className="min-w-0 flex-1">
        {doc ? (
          <GlassPanel>
            <article className="prose-knowledge">
              <ReactMarkdown remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ href, children }) =>
                    href?.startsWith("/") && !href.startsWith("/knowledge/") ? (
                      <Link to={href}>{children}</Link>
                    ) : href?.startsWith("/knowledge/") ? (
                      <Link to={href}>{children}</Link>
                    ) : (
                      <a href={href} target="_blank" rel="noreferrer">{children}</a>
                    ),
                }}>
                {doc.markdown}
              </ReactMarkdown>
            </article>
            <div className="mt-8 flex border-t pt-4 text-sm" style={{ borderColor: "var(--stroke)" }}>
              {doc.prev && (
                <button onClick={() => nav(`/knowledge/${doc.prev!.slug}`)}
                        className="hover:underline" style={{ color: "var(--arc)" }}>
                  ← {doc.prev.title}
                </button>
              )}
              {doc.next && (
                <button onClick={() => nav(`/knowledge/${doc.next!.slug}`)}
                        className="ml-auto hover:underline" style={{ color: "var(--arc)" }}>
                  {doc.next.title} →
                </button>
              )}
            </div>
          </GlassPanel>
        ) : <p style={{ color: "var(--muted)" }}>Loading…</p>}
      </div>
    </div>
  );
}
