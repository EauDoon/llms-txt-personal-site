const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function search(query, records, response) {
  const element = () => ({
    children: [], value: '', options: [{ value: '' }], listeners: {},
    append(child) { this.children.push(child); },
    replaceChildren(...children) { this.children = children; },
    addEventListener(name, fn) { this.listeners[name] = fn; },
    focus() { this.focused = true; },
    cloneNode() { return this; },
  });
  const controls = Object.fromEntries(['query', 'page-type', 'topic', 'search-results', 'search-status', 'search-retry', 'search-more']
    .map(id => ['#' + id, element()]));
  controls['#query'].form = element();
  const fallback = element();
  controls['#search-results'].children = [fallback];
  const location = { href: 'https://example.test/search.html?q=' + encodeURIComponent(query) };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../template/search.js'), 'utf8'), {
    document: { querySelector: id => controls[id], createElement: element, createDocumentFragment: element },
    location, history: { pushState(_, __, url) { location.href = url.href; }, replaceState(_, __, url) { location.href = url.href; } },
    window: { addEventListener() {} }, URL, AbortController, TextDecoder, setTimeout, clearTimeout,
    fetch: async () => response || new Response(JSON.stringify(records)),
  });
  await new Promise(resolve => setImmediate(resolve));
  return {
    controls, fallback,
    rows: () => controls['#search-results'].children[0].children,
    titles: () => controls['#search-results'].children[0].children.map(row => row.children[0].textContent),
  };
}
const record = (title, text = '', extra = {}) => ({title, text, url: '/' + encodeURIComponent(title) + '.html', type: 'page', topic_keys: [], ...extra});

test('oversized streamed search responses stop reading and preserve fallback', async () => {
  for (const length of [undefined, '1', String(21 * 1024 * 1024)]) {
    let reads = 0, cancelled = false;
    const body = new ReadableStream({
      pull(controller) { reads++; controller.enqueue(new Uint8Array(1024 * 1024)); },
      cancel() { cancelled = true; },
    }, { highWaterMark: 0 });
    const result = await search('', [], new Response(body, { headers: length ? { 'Content-Length': length } : {} }));
    assert.equal(reads, 21);
    assert.equal(cancelled, true);
    assert.equal(result.controls['#search-results'].children[0], result.fallback);
    assert.equal(result.controls['#search-retry'].hidden, false);
    assert.match(result.controls['#search-status'].textContent, /Search is unavailable/);
  }
});

test('streamed UTF-8 split across chunks remains searchable', async () => {
  const bytes = new TextEncoder().encode(JSON.stringify([record('Café')]));
  const offset = bytes.indexOf(0xc3) + 1;
  const body = new ReadableStream({ start(controller) {
    controller.enqueue(bytes.slice(0, offset)); controller.enqueue(bytes.slice(offset)); controller.close();
  } });
  assert.deepEqual((await search('cafe', [], new Response(body))).titles(), ['Café']);
});

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

test('exact phrases stay within each authored search field', async () => {
  const records = [record('Alpha', 'Beta', {description:'Research', topics:['Methods', 'Practice']}),
    record('Whole phrase', 'Alpha beta', {description:'Research methods', topics:['Methods practice']})];
  for (const phrase of ['alpha beta', 'research methods', 'methods practice']) {
    assert.deepEqual((await search('"' + phrase + '"', records)).titles(), ['Whole phrase']);
    assert.equal((await search(phrase, records)).titles().length, 2);
  }
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

test('large result sets expand in bounded batches and reset on a new query', async () => {
  const result = await search('', Array.from({length: 60}, (_, i) => record('Note ' + i)));
  assert.equal(result.rows().length, 25);
  const more = result.controls['#search-more'];
  assert.equal(more.hidden, false);
  more.listeners.click();
  assert.equal(result.rows().length, 50);
  assert.equal(result.rows()[25].children[0].focused, true);
  more.listeners.click();
  assert.equal(result.rows().length, 60);
  assert.equal(more.hidden, true);
  result.controls['#query'].value = 'Note 59';
  result.controls['#query'].listeners.input();
  assert.equal(result.rows().length, 1);
  result.controls['#query'].form.listeners.reset({preventDefault() {}});
  assert.equal(result.rows().length, 25);
  assert.equal(result.controls['#query'].focused, true);
});
