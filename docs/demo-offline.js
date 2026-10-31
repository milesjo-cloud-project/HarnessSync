/* Cache only public presentation assets, never demo entries or account data. */
(() => {
  "use strict";
  const status = document.getElementById("offline-status");
  if (location.protocol === "file:") {
    status.textContent = "This local demo works offline. Keep the extracted files together. Full-app links need internet; demo entries reset on reload.";
    return;
  }
  if (!("serviceWorker" in navigator) || !window.isSecureContext) {
    status.textContent = "For offline use in this browser, download the single-file demo below. Hosted offline caching needs HTTPS and service worker support.";
    return;
  }
  status.textContent = "Preparing the demo for offline use… Keep this page open until confirmation.";
  let confirmed = false;
  const timeout = setTimeout(() => {
    if (!confirmed) status.textContent = "Offline preparation is not confirmed. Reconnect and reload, or download the single-file demo below.";
  }, 15000);
  function checkReady() {
    const worker = navigator.serviceWorker.controller;
    if (!worker) return;
    const channel = new MessageChannel();
    channel.port1.onmessage = event => {
      channel.port1.close();
      if (event.data?.type !== "harnesssync-demo-ready" || !event.data.ready) return;
      confirmed = true;
      clearTimeout(timeout);
      status.textContent = "Demo downloaded for offline use. Bookmark this page, then test airplane mode and reload. Full-app links need internet; demo entries reset on reload.";
    };
    worker.postMessage({type: "harnesssync-demo-check"}, [channel.port2]);
  }
  navigator.serviceWorker.addEventListener("controllerchange", checkReady);
  navigator.serviceWorker.register("./demo-sw.js", {scope: "./", updateViaCache: "none"})
    .then(() => navigator.serviceWorker.ready)
    .then(checkReady)
    .catch(() => {
      clearTimeout(timeout);
      status.textContent = "Offline preparation is unavailable. Download the single-file demo below while online.";
    });
})();
