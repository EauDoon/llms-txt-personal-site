"use strict";
(async () => {
  const query = document.querySelector("#query");
  const results = document.querySelector("#search-results");
  const status = document.querySelector("#search-status");
  try {
    const response = await fetch("/search-index.json", { credentials: "omit" });
    if (!response.ok) throw new Error("Search index unavailable");
    const records = await response.json();
    if (!Array.isArray(records) || records.length > 5000 || records.some(record =>
      typeof record.title !== "string" || typeof record.text !== "string" ||
      typeof record.url !== "string" || !/^\/(?!\/)[^\\\s]*$/.test(record.url))) {
      throw new Error("Invalid search index");
    }
    const indexed = records.map(record => ({ ...record, terms: (record.title + " " + record.text).toLocaleLowerCase() }));
    function search() {
      const term = query.value.slice(0, 200).trim().toLocaleLowerCase();
      const found = indexed.filter(record => record.terms.includes(term));
      const fragment = document.createDocumentFragment();
      for (const record of found) {
        const li = document.createElement("li");
        const link = document.createElement("a");
        link.href = record.url;
        link.textContent = record.title;
        li.append(link);
        fragment.append(li);
      }
      results.replaceChildren(fragment);
      status.textContent = found.length ? `${found.length} matching page${found.length === 1 ? "" : "s"}.` : "No pages match. Try a shorter phrase or clear search.";
    }
    query.addEventListener("input", search);
    query.form.addEventListener("submit", event => event.preventDefault());
    query.form.addEventListener("reset", () => { query.value = ""; search(); query.focus(); });
    search();
  } catch {
    status.textContent = "Search is unavailable. Browse the published pages below.";
  }
})();
