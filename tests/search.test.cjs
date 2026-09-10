const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('title-only search results omit unrelated body excerpts', async () => {
  const element = () => ({
    children: [], value: '', options: [{ value: '' }],
    append(child) { this.children.push(child); },
    replaceChildren(...children) { this.children = children; },
    addEventListener() {},
  });
  const controls = Object.fromEntries(['query', 'page-type', 'topic', 'search-results', 'search-status', 'search-retry']
    .map(id => ['#' + id, element()]));
  controls['#query'].form = element();
  const records = [
    { title: 'Needle title', text: 'Unrelated opening.', url: '/title.html', type: 'page', topic_keys: [] },
    { title: 'Body match', text: 'Contains needle in the body.', url: '/body.html', type: 'page', topic_keys: [] },
  ];
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../template/search.js'), 'utf8'), {
    document: { querySelector: id => controls[id], createElement: element, createDocumentFragment: element },
    location: { href: 'https://example.test/search.html?q=needle' }, history: {},
    window: { addEventListener() {} }, URL, AbortController, setTimeout, clearTimeout,
    fetch: async () => ({ ok: true, text: async () => JSON.stringify(records) }),
  });
  await new Promise(resolve => setImmediate(resolve));
  const results = controls['#search-results'].children[0].children;
  assert.equal(results.length, 2);
  assert.equal(results[0].children.length, 1);
  assert.equal(results[0].children[0].textContent, 'Needle title');
  assert.equal(results[1].children[1].textContent, 'Contains needle in the body.');
});
