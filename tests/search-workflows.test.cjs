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

test('accent-insensitive matching preserves readable original excerpts', async () => {
  const text = 'Opening '.repeat(30) + 'Café research in Zürich.';
  const result = await search('cafe zurich', [record('Notes', text), record('Other')]);
  assert.deepEqual(result.titles(), ['Notes']);
  assert.match(result.rows()[0].children[1].textContent, /Café research in Zürich/);
  assert.deepEqual((await search('CAFÉ', [record('Cafe\u0301')])).titles(), ['Cafe\u0301']);
});

test('search combines independent words and respects quoted phrases', async () => {
  const records = [record('Alpha', 'Something beta'), record('Alpha beta'), record('Alpha only')];
  assert.deepEqual((await search('alpha beta', records)).titles(), ['Alpha beta', 'Alpha']);
  assert.deepEqual((await search('"alpha beta"', records)).titles(), ['Alpha beta']);
  assert.deepEqual((await search('"alpha beta', records)).titles(), ['Alpha beta']);
  assert.equal((await search('""', records)).titles().length, 3);
});

test('search ranks title matches first and preserves order for ties and empty queries', async () => {
  const records = [record('Background', 'needle'), record('Needle notes'), record('Needle examples')];
  assert.deepEqual((await search('needle', records)).titles(), ['Needle notes', 'Needle examples', 'Background']);
  assert.deepEqual((await search('', records)).titles(), ['Background', 'Needle notes', 'Needle examples']);
});

test('result descriptions and authored topics are searchable and rendered as text', async () => {
  const result = await search('methods', [record('Notes', 'Body', {
    type: 'article', description: 'Research methods <img>', topics: ['Lab notes'], topic_keys: ['lab notes'],
  })]);
  assert.deepEqual(result.titles(), ['Notes']);
  assert.equal(result.rows()[0].children[1].textContent, 'Research methods <img>');
  assert.equal(result.rows()[0].children[2].textContent, 'Writing · Lab notes');
  assert.deepEqual((await search('lab', [record('Notes', '', {topics: ['Lab notes']})])).titles(), ['Notes']);
});
