/* Poll only the latest snapshot. Expiry also runs when the network is down. */
(() => {
  let expiresAt = 0;
  let cleared = false;
  const label = document.getElementById("live-freshness");
  function clear() {
    if (cleared) return;
    cleared = true;
    window.PFLiveTable.render({__available: true, seats: [], board: [], feed: []});
    document.getElementById("live-conn").textContent = "● 数据已中断";
    document.getElementById("live-empty").textContent = "等待实时数据恢复…";
    label.textContent = "暂无有效实时数据";
  }
  async function refresh() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2500);
    const started = performance.now();
    try {
      const response = await fetch("/api/live", {cache: "no-store", signal: controller.signal});
      if (response.status === 401) {
        clear();
        window.location.replace("/login");
        return;
      }
      if (!response.ok) throw new Error("Live data unavailable");
      const data = await response.json();
      const remaining = Number(data.expires_in_sec || 0);
      if (!data.ok || data.stale || !data.live || remaining <= 0) {
        expiresAt = 0;
        clear();
      } else {
        expiresAt = started + Math.min(15, remaining) * 1000;
        if (performance.now() >= expiresAt) { clear(); return; }
        window.PFLiveTable.render({...data.live, __available: true});
        cleared = false;
        label.textContent = "实时同步 · " + new Date().toLocaleTimeString();
      }
    } catch (_) {
      if (performance.now() >= expiresAt) clear();
      else label.textContent = "连接中断，正在重新获取…";
    } finally {
      clearTimeout(timeout);
      setTimeout(refresh, 700);
    }
  }
  setInterval(() => { if (performance.now() >= expiresAt) clear(); }, 250);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && performance.now() >= expiresAt) clear();
  });
  clear();
  refresh();
})();
