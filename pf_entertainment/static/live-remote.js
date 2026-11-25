/* VPS viewer: the table and the money view, each read from what the bot last uploaded.
 *
 *   #table   /api/live   the latest snapshot only; it expires on this page too, also when the network is down
 *   #money   /api/money  the figures, and the hands this page does not hold yet
 */
(() => {
  const T = window.PFLiveTable, M = window.PFMoney;
  const label = document.getElementById("live-freshness");
  const time = () => new Date().toLocaleTimeString("zh-CN", {hour12: false});
  let shown = "";                 // the view on screen: only it writes the label in the top bar

  // A read that gives up, and that sends an expired sign-in back to the sign-in page.
  async function read(path, patience) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), patience);
    try {
      const response = await fetch(path, {cache: "no-store", signal: controller.signal});
      if (response.status === 401) {
        window.location.replace("/login");
        return null;
      }
      if (!response.ok) throw new Error("Live data unavailable");
      return await response.json();
    } finally {
      clearTimeout(timeout);
    }
  }

  // ── the table ───────────────────────────────────────────────────────────────
  let expiresAt = 0;
  let cleared = false;
  T.mount(document.getElementById("live-root"));
  function clear() {
    if (shown === "table") label.textContent = "没有收到直播数据";
    if (cleared) return;
    cleared = true;
    T.render({__available: true, __stale: true, seats: [], board: []});
  }
  async function refreshTable() {
    const started = performance.now();
    try {
      const data = await read("/api/live", 2500);
      if (!data) return clear();
      const remaining = Number(data.expires_in_sec || 0);
      if (!data.ok || data.stale || !data.live || remaining <= 0) {
        expiresAt = 0;
        clear();
      } else {
        expiresAt = started + Math.min(15, remaining) * 1000;
        if (performance.now() >= expiresAt) { clear(); return; }
        T.render({...data.live, __available: true});
        cleared = false;
        label.textContent = "同步于 " + time();
      }
    } catch (_) {
      if (performance.now() >= expiresAt) clear();
      else label.textContent = "网络中断，正在重试";
    }
  }
  // Behind the money view the table is not read, so it is not judged either.
  setInterval(() => { if (shown === "table" && performance.now() >= expiresAt) clear(); }, 250);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && performance.now() >= expiresAt) clear();
  });
  clear();

  // ── money ───────────────────────────────────────────────────────────────────
  // Figures stay on screen when the upload or the network stops, with the time they are from.
  let held = {epoch: "", points: []};
  let heldAt = "";                // when the figures on screen arrived; "" = none on screen
  M.mount(document.getElementById("money-root"));
  function moneyStopped(what, nothing) {
    if (heldAt) M.notice(`${what}，下面是 ${heldAt} 收到的数字`, {keep: true});
    else M.notice(nothing);
  }
  async function refreshMoney() {
    let data;
    try {
      data = await read(`/api/money?from=${held.points.length}&epoch=${encodeURIComponent(held.epoch)}`, 8000);
    } catch (_) {
      label.textContent = "网络中断，正在重试";
      return moneyStopped("网络中断", "网络中断，正在重试。");
    }
    if (!data) return;
    if (!data.money) {
      held = {epoch: "", points: held.points};        // what comes next is a new list
      if (data.stale) {
        label.textContent = "没有收到直播数据";
        return moneyStopped("上传中断", "没有收到资金数据：bot 没在运行，或上传中断。");
      }
      label.textContent = "同步于 " + time();
      heldAt = "";
      return M.notice("运行中的 bot 版本较旧，重启后显示资金。");
    }
    const next = M.hold(held, data.money);
    if (!next) { held = {epoch: "", points: []}; return; }      // out of step: the next read starts from 0
    held = next;
    heldAt = time();
    label.textContent = "同步于 " + heldAt;
    M.render({...data.money.facts, hand_points: held.points});
  }

  window.PFViews.start({table: [refreshTable, 700], money: [refreshMoney, 2000]},
    {onRoute(view) {
      if (view === shown) return;
      shown = view;
      label.textContent = "正在连接";
      // Back on the table: what was drawn stays for the one read it takes to replace it.
      if (view === "table" && !cleared) expiresAt = Math.max(expiresAt, performance.now() + 3000);
    }});
})();
