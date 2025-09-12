// publishing/static/publishing/admin_autopopulate.js
(function () {
  function byId(id) { return document.getElementById(id); }

  function setIfEmpty(el, jsonValue) {
    if (!el) return;
    const v = (el.value || "").trim();
    if (!v || v === "[]" || v === "{}") {
      el.value = JSON.stringify(jsonValue);
    }
  }

  async function populateFromDataset(datasetId) {
    const dimsEl = byId("id_default_group_dims");
    const metsEl = byId("id_default_metrics");
    const visEl  = byId("id_visible_filters");
    if (!datasetId || !(dimsEl && metsEl && visEl)) return;

    const url = `/admin/publishing/datasetview/suggest_from_dataset/${datasetId}/`;
    try {
      const res = await fetch(url, { credentials: "same-origin" });
      if (!res.ok) return;
      const data = await res.json();
      setIfEmpty(dimsEl, data.default_group_dims);
      setIfEmpty(metsEl, data.default_metrics);
      setIfEmpty(visEl,  data.visible_filters);
    } catch (e) {
      // ignore
    }
  }

  function init() {
    const dsSel = byId("id_dataset");
    if (!dsSel) return;
    if (dsSel.value) { populateFromDataset(dsSel.value); }
    dsSel.addEventListener("change", function (e) {
      populateFromDataset(e.target.value);
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
