import { useEffect } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PageHeader, Panel } from "../components/ui";
import { useApi } from "../lib/useApi";

/** Must match slugify in tests/unit/test_coaches_meta.py. */
const slugify = (t: string) => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

const textOf = (node: React.ReactNode): string =>
  Array.isArray(node) ? node.map(textOf).join("") : typeof node === "string" ? node : "";

interface Chapter { slug: string; title: string; part: string; summary: string; updated: string }
interface Full extends Chapter {
  markdown: string;
  prev: { slug: string; title: string } | null;
  next: { slug: string; title: string } | null;
}

export default function Knowledge() {
  const { slug } = useParams();
  const nav = useNavigate();
  const location = useLocation();
  const { data: index, error: indexError } =
    useApi<{ chapters: Chapter[] }>("/api/knowledge");
  const chapters = index?.chapters ?? [];
  const { data: doc, error: docError } =
    useApi<Full>(slug ? `/api/knowledge/${slug}` : null);

  // fresh chapter starts at the top
  useEffect(() => { if (doc) window.scrollTo(0, 0); }, [doc]);

  // scroll to #anchor once the chapter markdown is rendered
  useEffect(() => {
    if (!doc || !location.hash) return;
    const id = location.hash.slice(1);
    const t = setTimeout(() => {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        el.classList.add("anchor-flash");
        setTimeout(() => el.classList.remove("anchor-flash"), 2000);
      }
    }, 100);
    return () => clearTimeout(t);
  }, [doc, location.hash]);

  const parts = [...new Set(chapters.map((c) => c.part))];

  if (!slug) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="The NFL Knowledge Book"
          subtitle="Football from first principles — the game, the schemes, the rulebook and the numbers." />
        {indexError && (
          <p className="text-body text-muted">Couldn't load the contents — {indexError}</p>
        )}
        {parts.map((p) => (
          <div key={p}>
            <h2 className="mb-3 text-label font-bold uppercase tracking-[0.14em] text-muted">
              Part {p}
            </h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {chapters.filter((c) => c.part === p).map((c) => (
                <Link key={c.slug} to={`/knowledge/${c.slug}`}
                      className="block rounded-[var(--radius-panel)] border border-border bg-surface p-4 transition-colors hover:border-accent/50 hover:bg-surface-2">
                  <div className="font-semibold text-ink">{c.title}</div>
                  <p className="mt-1 text-label text-muted">{c.summary}</p>
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
        <Link to="/knowledge"
              className="text-label font-bold uppercase tracking-[0.14em] text-accent hover:underline">
          ← contents
        </Link>
        {parts.map((p) => (
          <div key={p}>
            <div className="mb-1 text-micro font-bold uppercase tracking-wider text-muted">{p}</div>
            <ul className="space-y-0.5 text-body">
              {chapters.filter((c) => c.part === p).map((c) => (
                <li key={c.slug}>
                  <Link to={`/knowledge/${c.slug}`}
                        aria-current={c.slug === slug ? "page" : undefined}
                        className={`block rounded-[var(--radius-chip)] px-2 py-1 ${
                          c.slug === slug
                            ? "bg-accent-bg font-semibold text-accent"
                            : "text-muted hover:bg-surface-2 hover:text-ink"}`}>
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
          <Panel>
            <article className="prose-knowledge">
              <ReactMarkdown remarkPlugins={[remarkGfm]}
                components={{
                  h2: ({ children }) => <h2 id={slugify(textOf(children))}>{children}</h2>,
                  h3: ({ children }) => <h3 id={slugify(textOf(children))}>{children}</h3>,
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
            <div className="mt-8 flex border-t border-border pt-4 text-body">
              {doc.prev && (
                <button onClick={() => nav(`/knowledge/${doc.prev!.slug}`)}
                        className="text-accent hover:underline">
                  ← {doc.prev.title}
                </button>
              )}
              {doc.next && (
                <button onClick={() => nav(`/knowledge/${doc.next!.slug}`)}
                        className="ml-auto text-accent hover:underline">
                  {doc.next.title} →
                </button>
              )}
            </div>
          </Panel>
        ) : docError ? (
          <p className="text-body text-muted">Couldn't load this chapter — {docError}</p>
        ) : <p className="text-muted">Loading…</p>}
      </div>
    </div>
  );
}
