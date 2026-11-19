document.addEventListener("DOMContentLoaded", () => {
  const SCROLL_KEY = "niblick.sidebar.scroll";
  const sidebar = document.querySelector(".wy-side-scroll");
  if (!sidebar) {
    return;
  }

  let userScrolled = false;
  const markUserScroll = () => {
    userScrolled = true;
  };
  sidebar.addEventListener("wheel", markUserScroll, { passive: true });
  sidebar.addEventListener("touchstart", markUserScroll, { passive: true });
  sidebar.addEventListener("pointerdown", markUserScroll, { passive: true });
  sidebar.addEventListener("keydown", markUserScroll);
  sidebar.addEventListener("scroll", () => {
    sessionStorage.setItem(SCROLL_KEY, String(sidebar.scrollTop));
  }, { passive: true });

  const saved = sessionStorage.getItem(SCROLL_KEY);
  if (saved === null) {
    sessionStorage.setItem(SCROLL_KEY, String(sidebar.scrollTop));
    return;
  }

  // The theme calls scrollIntoView() on the active sidebar link after every
  // navigation. Keep the sidebar where the reader left it instead.
  const originalScrollIntoView = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = function (...args) {
    if (this.closest && this.closest(".wy-side-scroll")) {
      return;
    }
    return originalScrollIntoView.apply(this, args);
  };

  const restore = () => {
    if (!userScrolled) {
      sidebar.scrollTop = Number(saved);
    }
  };
  restore();
  requestAnimationFrame(restore);
  window.addEventListener("pageshow", restore);
  window.addEventListener("load", restore);
});
