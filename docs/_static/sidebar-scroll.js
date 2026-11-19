document.addEventListener("DOMContentLoaded", () => {
  const SCROLL_KEY = "niblick.sidebar.scroll";
  const CLICK_KEY = "niblick.sidebar.click";
  const sidebar = document.querySelector(".wy-side-scroll");
  if (!sidebar) {
    return;
  }

  const saveScroll = () => {
    sessionStorage.setItem(SCROLL_KEY, String(sidebar.scrollTop));
  };

  sidebar.addEventListener("scroll", saveScroll, { passive: true });

  const menu = document.querySelector(".wy-menu-vertical");
  menu?.addEventListener(
    "click",
    (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }
      if (event.target.closest("a")) {
        saveScroll();
        sessionStorage.setItem(CLICK_KEY, "1");
      }
    },
    true
  );

  if (sessionStorage.getItem(CLICK_KEY) !== "1") {
    return;
  }
  sessionStorage.removeItem(CLICK_KEY);

  const saved = sessionStorage.getItem(SCROLL_KEY);
  if (saved === null) {
    return;
  }

  const originalScrollIntoView = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = function (...args) {
    if (this.closest && this.closest(".wy-side-scroll")) {
      return;
    }
    return originalScrollIntoView.apply(this, args);
  };

  const restore = () => {
    sidebar.scrollTop = Number(saved);
  };
  restore();
  requestAnimationFrame(restore);
  window.addEventListener("load", restore);
});
