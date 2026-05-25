document.addEventListener("DOMContentLoaded", function() {

  /* ---- Theme Toggle ---- */
  const toggle = document.getElementById("theme-toggle");
  const html = document.documentElement;
  const savedTheme = localStorage.getItem("logchecker-theme");

  if (savedTheme) {
    html.setAttribute("data-theme", savedTheme);
  } else if (window.matchMedia("(prefers-color-scheme: light)").matches) {
    html.setAttribute("data-theme", "light");
  }

  toggle.addEventListener("click", function() {
    const current = html.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    localStorage.setItem("logchecker-theme", next);
  });

  /* ---- File Input UX ---- */
  const dropZone = document.getElementById("file-drop-zone");
  const fileInput = document.getElementById("logfile");
  const fileNameEl = document.getElementById("file-selected-name");

  if (fileInput && fileNameEl) {
    fileInput.addEventListener("change", function() {
      if (fileInput.files.length > 0) {
        fileNameEl.textContent = "\u{1F4C4} " + fileInput.files[0].name;
        fileNameEl.classList.add("visible");
      } else {
        fileNameEl.classList.remove("visible");
      }
    });
  }

  if (dropZone) {
    ["dragenter", "dragover"].forEach(evt => {
      dropZone.addEventListener(evt, function(e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add("dragover");
      });
    });
    dropZone.addEventListener("dragleave", function(e) {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("dragover");
    });
    dropZone.addEventListener("drop", function(e) {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("dragover");
      if (e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        fileNameEl.textContent = "\u{1F4C4} " + e.dataTransfer.files[0].name;
        fileNameEl.classList.add("visible");
      }
    });
  }

  /* ---- Load Result ---- */
  const outputContainer = document.getElementById("output-container");
  if (outputContainer) {
    const resultId = outputContainer.getAttribute("data-result-id");
    const rawSubpath = outputContainer.getAttribute("data-subpath") || '';
    const subpath = rawSubpath.replace(/\/+$/, '');
    const resultUrl = (subpath ? subpath : '') + "/result/" + resultId;

    fetch(resultUrl)
      .then(response => response.text())
      .then(data => {
        outputContainer.innerHTML = data;
      })
      .catch(error => {
        outputContainer.innerHTML = '<span style="color:var(--danger-text)">Error loading output. Please try again.</span>';
      });
  }

  /* ---- Log Modal ---- */
  const btnExpand = document.getElementById("btn-expand");
  const logModal = document.getElementById("log-modal");
  const logModalBackdrop = document.getElementById("log-modal-backdrop");
  const logModalBody = document.getElementById("log-modal-body");
  const btnModalClose = document.getElementById("btn-modal-close");

  function openLogModal() {
    if (outputContainer && logModalBody) {
      logModalBody.innerHTML = outputContainer.innerHTML;
    }
    logModal.classList.add("open");
    logModalBackdrop.classList.add("open");
    document.body.style.overflow = "hidden";
  }

  function closeLogModal() {
    logModal.classList.remove("open");
    logModalBackdrop.classList.remove("open");
    document.body.style.overflow = "";
  }

  if (btnExpand) {
    btnExpand.addEventListener("click", openLogModal);
  }
  if (btnModalClose) {
    btnModalClose.addEventListener("click", closeLogModal);
  }
  if (logModalBackdrop) {
    logModalBackdrop.addEventListener("click", closeLogModal);
  }
  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape" && logModal && logModal.classList.contains("open")) {
      closeLogModal();
    }
  });

});
