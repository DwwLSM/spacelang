/**
 * Keep a documentation sidebar aware of the article it points at.
 *
 * Both the /docs table of contents and the article body are rendered on the
 * server from the same Markdown pass, so every anchor already exists. This
 * module only adds the scrolling niceties: mark the section currently under
 * the fold and smooth in-page jumps. It is shared by /docs and /tutorial.
 */

export function initDocNavigation() {
  const body = document.querySelector(".doc-body");
  const toc = document.querySelector("nav.doc-toc");
  if (!body || !toc) return;

  const links = new Map();
  for (const link of toc.querySelectorAll('a[href^="#"]')) {
    const id = decodeURIComponent(link.hash.slice(1));
    if (id) links.set(id, link);
  }
  if (links.size === 0) return;

  const headings = [...body.querySelectorAll("h2[id], h3[id]")].filter((heading) =>
    links.has(heading.id)
  );
  if (headings.length === 0) return;

  let activeId = "";
  const setActive = (id) => {
    if (id === activeId) return;
    const previous = links.get(activeId);
    if (previous) {
      previous.classList.remove("is-active");
      previous.removeAttribute("aria-current");
    }
    const current = links.get(id);
    if (current) {
      current.classList.add("is-active");
      current.setAttribute("aria-current", "true");
    }
    activeId = id;
  };

  // The article is its own scroll container, so the viewport rects are
  // compared against the article's top edge, not the window's.
  const update = () => {
    const threshold = body.getBoundingClientRect().top + 24;
    let current = headings[0];
    for (const heading of headings) {
      if (heading.getBoundingClientRect().top > threshold) break;
      current = heading;
    }
    setActive(current.id);
  };

  let frame = 0;
  const schedule = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      update();
    });
  };

  body.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule);
  update();
}
