"use strict";
(() => {
  const query = document.querySelector("#query");
  const type = document.querySelector("#page-type");
  const topic = document.querySelector("#topic");
  const results = document.querySelector("#search-results");
  const status = document.querySelector("#search-status");
  const retry = document.querySelector("#search-retry");
  const fallback = Array.from(results.children, node => node.cloneNode(true));
  let indexed = null;
  let loading = false;

  function restoreState() {
    const params = new URL(location.href).searchParams;
    query.value = (params.get("q") || "").slice(0, 200);
    for (const [control, key] of [[type, "type"], [topic, "topic"]]) {
      const value = params.get(key) || "";
      control.value = Array.from(control.options).some(option => option.value === value) ? value : "";
    }
  }

  function saveState(mode) {
    const url = new URL(location.href);
    for (const [key, value] of [["q", query.value.slice(0, 200)], ["type", type.value], ["topic", topic.value]]) {
      if (value) url.searchParams.set(key, value);
      else url.searchParams.delete(key);
    }
    if (url.href !== location.href) history[mode + "State"](null, "", url);
  }

  function search(mode) {
    if (mode) saveState(mode);
    if (!indexed) return;
    const term = query.value.slice(0, 200).trim().toLocaleLowerCase();
    const found = indexed.filter(record => record.terms.includes(term)
      && (!type.value || record.type === type.value)
      && (!topic.value || record.topic_keys.includes(topic.value)));
    const fragment = document.createDocumentFragment();
    for (const record of found) {
      const li = document.createElement("li");
      const link = document.createElement("a");
      link.href = record.url;
      link.textContent = record.title;
      li.append(link);
      if (term) {
        const paragraph = document.createElement("p");
        const match = record.text.toLocaleLowerCase().indexOf(term);
        const start = Math.max(0, match - 60);
        paragraph.textContent = (start ? "…" : "") + record.text.slice(start, start + 180)
          + (record.text.length > start + 180 ? "…" : "");
        li.append(paragraph);
      }
      fragment.append(li);
    }
    results.replaceChildren(fragment);
    status.textContent = found.length ? `${found.length} matching page${found.length === 1 ? "" : "s"}.`
      : "No pages match. Try a shorter phrase or clear search.";
  }

  async function load(isRetry = false) {
    if (loading) return;
    loading = true;
    retry.disabled = true;
    status.textContent = "Loading search. Published page links remain available below.";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch("/search-index.json", { credentials: "omit", cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error("Search index unavailable");
      const text = await response.text();
      if (text.length > 20 * 1024 * 1024) throw new Error("Search index exceeds the limit");
      const records = JSON.parse(text);
      if (!Array.isArray(records) || records.length > 5000 || records.some(record =>
        !record || typeof record.title !== "string" || typeof record.text !== "string" || record.text.length > 100000
        || typeof record.url !== "string" || !/^\/(?!\/)[^\\\s]*$/.test(record.url)
        || !["article", "page"].includes(record.type) || !Array.isArray(record.topic_keys)
        || record.topic_keys.length > 12 || record.topic_keys.some(key => typeof key !== "string" || key.length > 160))) {
        throw new Error("Invalid search index");
      }
      indexed = records.map(record => ({ ...record, terms: (record.title + " " + record.text).toLocaleLowerCase() }));
      retry.hidden = true;
      search();
      if (isRetry) query.focus();
    } catch {
      indexed = null;
      results.replaceChildren(...fallback.map(node => node.cloneNode(true)));
      status.textContent = "Search is unavailable. Browse all published pages below or retry.";
      retry.hidden = false;
    } finally {
      clearTimeout(timeout);
      loading = false;
      retry.disabled = false;
    }
  }

  query.addEventListener("input", () => search("replace"));
  for (const control of [type, topic]) control.addEventListener("change", () => search("push"));
  query.form.addEventListener("submit", event => { event.preventDefault(); search("push"); });
  query.form.addEventListener("reset", event => {
    event.preventDefault(); query.value = ""; type.value = ""; topic.value = ""; search("push"); query.focus();
  });
  retry.addEventListener("click", () => load(true));
  window.addEventListener("popstate", () => { restoreState(); search(); });
  restoreState();
  load();
})();
