import "./style.css";

const loadingMessage = document.getElementById("loading-message");
const loadingTitle = document.querySelector<HTMLElement>(".loading-title");

function showFailure(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  if (loadingTitle !== null) {
    loadingTitle.textContent = "Failed to start Niblick";
  }
  if (loadingMessage !== null) {
    loadingMessage.textContent = message;
  }
  console.error(error);
}

requestAnimationFrame(() => {
  if (loadingMessage !== null) {
    loadingMessage.textContent = "Loading editor and compiler";
  }
  void import("./app").catch(showFailure);
});
