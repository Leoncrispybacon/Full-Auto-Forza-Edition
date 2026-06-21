document.addEventListener("DOMContentLoaded", () => {
  const isZh = document.documentElement.lang.toLowerCase().startsWith("zh");

  document.querySelectorAll(".screenshot img").forEach((img) => {
    const openFullSize = () => {
      const opened = window.open(img.currentSrc || img.src, "_blank", "noopener,noreferrer");
      if (opened) opened.opener = null;
    };

    img.tabIndex = 0;
    img.setAttribute("role", "link");
    img.setAttribute(
      "aria-label",
      `${img.alt || (isZh ? "教學圖片" : "Tutorial image")} — ${isZh ? "開啟完整尺寸" : "open full size"}`,
    );
    img.addEventListener("click", openFullSize);
    img.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openFullSize();
      }
    });
  });

  const guides = [
    ["first-time-setup", "First-time Setup", "首次設定"],
    ["race-auto-grind", "AFK Races", "自動掛機刷技術點"],
    ["auto-unlock-spin-wheel-mastery-tree", "Auto Unlock Wheelspins from the Mastery Tree", "從熟練度樹自動解鎖幸運轉盤"],
    ["auto-buy-cars-in-batch", "Auto Buy Cars in Batch", "批次自動購車"],
    ["delete-used-cars", "Delete Used Cars", "刪除已使用車輛"],
    ["auto-wheelspin", "Auto Wheelspins", "自動轉輪"],
    ["troubleshooting", "Troubleshooting", "疑難排解"],
    ["game-overlay", "Game Overlay", "遊戲浮層"],
    ["reporting-bugs", "Reporting Bugs", "回報問題"],
    ["settings", "Settings", "設定說明"],
    ["mechanics", "How FAFE Works", "機制說明"],
  ];

  const slug = location.pathname.match(/\/guides\/([^/]+)\//)?.[1];
  const current = guides.findIndex(([guideSlug]) => guideSlug === slug);
  if (current < 0) return;

  const overview = ["forza-horizon-6-farming-guide", "Complete Farming Guide", "掛機刷錢與技能點指南"];
  const previous = current > 0 ? guides[current - 1] : overview;
  const next = current < guides.length - 1 ? guides[current + 1] : overview;
  const labelIndex = isZh ? 2 : 1;
  const nav = document.createElement("nav");
  nav.className = "guide-pagination";
  nav.setAttribute("aria-label", isZh ? "指南導覽" : "Guide navigation");
  nav.innerHTML = `
    <a href="../${previous[0]}/"><span>${isZh ? "上一篇" : "Previous"}</span><strong>← ${previous[labelIndex]}</strong></a>
    <a href="../${next[0]}/"><span>${isZh ? "下一篇" : "Next"}</span><strong>${next[labelIndex]} →</strong></a>
  `;

  const sections = document.querySelectorAll("main > section");
  const allGuides = sections[sections.length - 1];
  if (allGuides) allGuides.before(nav);
});
