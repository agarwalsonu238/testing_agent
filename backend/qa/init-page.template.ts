// Playwright MCP `--init-page` for QA agent runs. The backend fills in __RULES__ and __LOG_PATH__
// for each run, so this is the same risky-endpoint list and mocks that Quick Scan uses.
//
// 1. Network guard: mocked endpoints are answered here; risky endpoints are aborted. Agents can't
//    route or unroute (the network capability isn't enabled), so they can't switch the guard off.
// 2. Recorder: console errors, page crashes, failed requests and 4xx/5xx responses are appended to
//    a JSONL log. Flow verdicts come from this log and Playwright checks, not from the model.

type Rule = { url: string; method?: string | null };
type Mock = Rule & { status: number; body: string; headers: Record<string, string> };

const RULES: { mocks: Mock[]; risky: Rule[] } = __RULES__;
const LOG_PATH: string = __LOG_PATH__;

function globToRegExp(pattern: string): RegExp {
  const escaped = pattern
    .split('*')
    .map((part) => part.replace(/[.+?^${}()|[\]\\]/g, '\\$&'))
    .join('.*');
  return new RegExp(`^${escaped}$`);
}

function matches(rule: Rule, url: string, method: string): boolean {
  if (rule.method && rule.method.toUpperCase() !== method.toUpperCase()) return false;
  return globToRegExp(rule.url.replace(/\*\*/g, '*')).test(url);
}

export default async ({ page }: { page: any }) => {
  const fs = await import('node:fs');
  const log = (entry: Record<string, unknown>) => {
    try {
      fs.appendFileSync(LOG_PATH, JSON.stringify({ at: Date.now(), ...entry }) + '\n');
    } catch {
      // The recorder must never break the page under test.
    }
  };

  const context = page.context();
  if (context.__qaGuardInstalled) return;
  context.__qaGuardInstalled = true;

  await context.route('**/*', async (route: any) => {
    const request = route.request();
    const url: string = request.url();
    const method: string = request.method();
    const mock = RULES.mocks.find((m) => matches(m, url, method));
    if (mock) {
      await route.fulfill({ status: mock.status, body: mock.body, headers: mock.headers });
      return;
    }
    if (RULES.risky.some((r) => matches(r, url, method))) {
      log({ type: 'blocked', method, url });
      await route.abort('blockedbyclient');
      return;
    }
    await route.fallback();
  });

  const watch = (p: any) => {
    p.on('console', (msg: any) => {
      if (msg.type() === 'error') log({ type: 'console', text: msg.text(), page: p.url() });
    });
    p.on('pageerror', (err: any) => log({ type: 'pageerror', text: String(err), page: p.url() }));
    p.on('requestfailed', (req: any) =>
      log({
        type: 'requestfailed',
        method: req.method(),
        url: req.url(),
        resourceType: req.resourceType(),
        failure: req.failure()?.errorText,
      }),
    );
    p.on('response', (res: any) => {
      if (res.status() >= 400) {
        const req = res.request();
        log({
          type: 'response',
          status: res.status(),
          method: req.method(),
          url: res.url(),
          resourceType: req.resourceType(),
        });
      }
    });
  };
  watch(page);
  context.on('page', watch);
};
