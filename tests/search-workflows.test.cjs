const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function search(query, records) {
  const element = () => ({
    children: [], value: '', options: [{ value: '' }], listeners: {},
    append(child) { this.children.push(child); },
    replaceChildren(...children) { this.children = children; },
    addEventListener(name, fn) { this.listeners[name] = fn; },
    focus() { this.focused = true; },
  });
  const controls = Object.fromEntries(['query', 'page-type', 'topic', 'search-results', 'search-status', 'search-retry', 'search-more']
    .map(id => ['#' + id, element()]));
  controls['#query'].form = element();
  const location = { href: 'https://example.test/search.html?q=' + encodeURIComponent(query) };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../template/search.js'), 'utf8'), {
    document: { querySelector: id => controls[id], createElement: element, createDocumentFragment: element },
    location, history: { pushState(_, __, url) { location.href = url.href; }, replaceState(_, __, url) { location.href = url.href; } },
    window: { addEventListener() {} }, URL, AbortController, setTimeout, clearTimeout,
    fetch: async () => ({ ok: true, text: async () => JSON.stringify(records) }),
  });
  await new Promise(resolve => setImmediate(resolve));
  return {
    controls,
    rows: () => controls['#search-results'].children[0].children,
    titles: () => controls['#search-results'].children[0].children.map(row => row.children[0].textContent),
  };
}
const record = (title, text = '', extra = {}) => ({title, text, url: '/' + encodeURIComponent(title) + '.html', type: 'page', topic_keys: [], ...extra});

test('search combines independent words and respects quoted phrases', async () => {
  const records = [record('Alpha', 'Something beta'), record('Alpha beta'), record('Alpha only')];
  assert.deepEqual((await search('alpha beta', records)).titles(), ['Alpha', 'Alpha beta']);
  assert.deepEqual((await search('"alpha beta"', records)).titles(), ['Alpha beta']);
  assert.deepEqual((await search('"alpha beta', records)).titles(), ['Alpha beta']);
  assert.equal((await search('""', records)).titles().length, 3);
});
