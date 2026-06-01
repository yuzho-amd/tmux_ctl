/* Keep terminal chords from triggering browser shortcuts (e.g. Ctrl+Shift+C → DevTools). */
(function () {
  function isCtrlShiftC(event) {
    return (
      event.type === "keydown" &&
      event.ctrlKey &&
      event.shiftKey &&
      !event.altKey &&
      !event.metaKey &&
      (event.code === "KeyC" || event.key === "c" || event.key === "C")
    );
  }

  function blockBrowserShortcut(event) {
    if (!isCtrlShiftC(event)) return;
    event.preventDefault();
    event.stopPropagation();
  }

  window.addEventListener("keydown", blockBrowserShortcut, true);
  document.addEventListener("keydown", blockBrowserShortcut, true);

  function attachTermHandler() {
    const term = window.term;
    if (!term || typeof term.attachCustomKeyEventHandler !== "function") {
      return false;
    }
    term.attachCustomKeyEventHandler((event) => {
      if (isCtrlShiftC(event)) {
        event.preventDefault();
        event.stopPropagation();
      }
      return true;
    });
    return true;
  }

  if (attachTermHandler()) return;

  const timer = window.setInterval(() => {
    if (attachTermHandler()) window.clearInterval(timer);
  }, 50);
  window.setTimeout(() => window.clearInterval(timer), 10000);
})();
