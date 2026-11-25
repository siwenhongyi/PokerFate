/* Views behind one address, so the browser's back button works: #table, #money, ...
 *
 *   PFViews.start({ name: [refresh, everyMs], ... }, { covered, onRoute })
 *
 * The page has one <section id="view-NAME"> per view and one <a class="tab" data-tab="NAME">.
 * Only the view on screen is polled; the first one named is where an unknown address lands.
 *   covered(view)      true while something lies over the view and nothing behind needs redrawing
 *   onRoute(view, arg) after every address change; `arg` is what follows the slash in #name/arg
 */
(() => {
  function start(views, { covered = () => false, onRoute = () => {} } = {}) {
    const names = Object.keys(views);
    let view = "";
    let timer = 0;
    let run = 0;
    async function tick() {
      clearTimeout(timer);
      const mine = ++run;
      const [refresh, every] = views[view];
      if (!document.hidden && !covered(view)) {
        try { await refresh(); } catch (_) { /* keep the last frame; the next tick tries again */ }
      }
      if (mine === run) timer = setTimeout(tick, every);      // a view change meanwhile started its own loop
    }
    function route() {
      const [name, arg] = location.hash.replace(/^#/, "").split("/");
      const next = views[name] ? name : names[0];
      if (next !== view) {
        view = next;
        for (const key of names) document.getElementById(`view-${key}`).hidden = key !== view;
        document.querySelectorAll(".tab").forEach((tab) => {
          if (tab.dataset.tab === view) tab.setAttribute("aria-current", "page");
          else tab.removeAttribute("aria-current");
        });
        window.scrollTo(0, 0);
        tick();
      }
      onRoute(view, arg);
    }
    window.addEventListener("hashchange", route);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) tick(); });
    route();
  }
  window.PFViews = { start };
})();
