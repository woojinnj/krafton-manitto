const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const vm = require("node:vm");

const source = readFileSync(resolve(__dirname, "../static/js/dashboard.js"), "utf8");

function setup(fetch) {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, {
      hidden: false, textContent: "", open: false, focused: false,
      showModal() { this.open = true; },
      close() { this.open = false; },
      focus() { this.focused = true; },
    });
    return elements.get(id);
  };
  const redirects = [];
  const context = vm.createContext({
    Headers, URLSearchParams, AbortController, TypeError, fetch,
    window: { setTimeout, clearTimeout, location: { assign: (path) => redirects.push(path) } },
    document: { cookie: "csrf_access_token=sample-token", addEventListener() {}, getElementById: element },
  });
  vm.runInContext(source, context);
  return { context, element, redirects, run: (code) => vm.runInContext(code, context) };
}

test("profile writes send the CSRF token and preserve submitted content", async () => {
  let request;
  const app = setup(async (url, options) => {
    request = { url, options };
    return { ok: true, status: 200, json: async () => ({ result: "success" }) };
  });
  await app.run('apiRequest("/dashboard/side/update", { method: "PUT", body: new URLSearchParams({ name: "새이름" }) })');
  assert.equal(request.url, "/dashboard/side/update");
  assert.equal(request.options.headers.get("X-CSRF-TOKEN"), "sample-token");
  assert.equal(request.options.body.get("name"), "새이름");
});

test("both expired and malformed authentication redirect to login", async () => {
  for (const status of [401, 422]) {
    const app = setup(async () => ({ status }));
    await assert.rejects(app.run('apiRequest("/api/likes")'), /Authentication required/);
    assert.deepEqual(app.redirects, ["/login"]);
  }
});

test("API errors preserve the server explanation even on HTTP 200", async () => {
  for (const status of [200, 403]) {
    const app = setup(async () => ({
      status, ok: status === 200,
      json: async () => ({ result: "false", message: "이미 별점을 등록했습니다." }),
    }));
    await assert.rejects(app.run('apiRequest("/api/likes")'), /이미 별점을 등록했습니다/);
  }
});

test("non-JSON server failures provide a readable error", async () => {
  const app = setup(async () => ({ status: 503, ok: false, json: async () => { throw new SyntaxError(); } }));
  await assert.rejects(app.run('apiRequest("/api/likes")'), /서버 응답을 확인할 수 없습니다/);
});

test("offline and timeout failures provide recovery guidance", async () => {
  const offline = setup(async () => { throw new TypeError("Failed to fetch"); });
  await assert.rejects(offline.run('apiRequest("/api/likes")'), /연결을 확인/);
  const timeout = setup(async () => { const error = new Error(); error.name = "AbortError"; throw error; });
  await assert.rejects(timeout.run('apiRequest("/api/likes")'), /새로고침해 결과를 확인/);
});

test("cancelling reassignment never executes the operation", () => {
  const app = setup();
  app.run('globalThis.executed = 0; showAlert("배정 변경", () => executed++, true); closeModal(false);');
  assert.equal(app.context.executed, 0);
  assert.equal(app.element("custom-modal").open, false);
  assert.equal(app.element("modal-cancel").focused, true);
});

test("confirming reassignment executes exactly once", () => {
  const app = setup();
  app.run('globalThis.executed = 0; showAlert("배정 변경", () => executed++, true); closeModal(true); closeModal(true);');
  assert.equal(app.context.executed, 1);
});
