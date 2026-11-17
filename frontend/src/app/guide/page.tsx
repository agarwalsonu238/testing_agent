import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Guide" };

const MODES = [
  ["Quick Scan", "No", "Every page at desktop and mobile size: console, network, images, links, layout", "After any change"],
  ["Check my change", "Yes", "QA Lead reads your diff and runs the right agents", "Before opening a PR"],
  ["One agent", "Yes", "Run a single agent, e.g. Design reviewer on /pricing", "When you know what to check"],
  ["Saved test", "No", "Re-runs a saved flow as a normal Playwright test", "Before every push"],
];

const VERDICTS = [
  ["PASS", "Every check passed"],
  ["FAILING", "At least one check failed"],
  ["BLOCKED", "The run couldn't finish: the app isn't running, the test login failed, or Claude Code isn't logged in"],
];

export default function GuidePage() {
  return (
    <article className="grid max-w-3xl gap-8 text-sm leading-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">How to use it</h1>
        <p className="text-muted-foreground">
          Agents run through Claude Code on your own Claude plan. There is no API key and no per-run bill; agent runs
          count toward your plan&apos;s usage limits, so run Quick Scan first.
        </p>
      </header>

      <section className="grid gap-2" aria-labelledby="steps">
        <h2 id="steps" className="text-lg font-semibold">Before a push</h2>
        <ol className="list-decimal space-y-1 pl-5">
          <li>Start the app on localhost, then this dashboard. Open <Link className="underline underline-offset-4" href="/setup">Setup check</Link> until it is green.</li>
          <li>Run <Link className="underline underline-offset-4" href="/scan">Quick Scan</Link>. Fix anything marked High.</li>
          <li>Click <Link className="underline underline-offset-4" href="/check">Check my change</Link>, or run one agent. For the Functionality tester, describe the flow as numbered steps ending with an Expected line.</li>
          <li>Work through <Link className="underline underline-offset-4" href="/">To review</Link>: Accept (a bug to fix) or Ignore (with a reason, so it is skipped next time).</li>
          <li>When a new flow passes, click <strong>Save as test</strong> on its report.</li>
          <li>Copy the report summary into the PR description.</li>
        </ol>
      </section>

      <section className="grid gap-2" aria-labelledby="modes">
        <h2 id="modes" className="text-lg font-semibold">Modes</h2>
        <div className="overflow-x-auto rounded-xl border">
          <table className="w-full">
            <thead className="bg-muted/50 text-left">
              <tr>
                <th scope="col" className="p-2 font-medium">Mode</th>
                <th scope="col" className="p-2 font-medium">AI</th>
                <th scope="col" className="p-2 font-medium">What it does</th>
                <th scope="col" className="p-2 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {MODES.map(([mode, ai, what, when]) => (
                <tr key={mode} className="border-t">
                  <td className="p-2 font-medium">{mode}</td>
                  <td className="p-2">{ai}</td>
                  <td className="p-2">{what}</td>
                  <td className="p-2">{when}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-2" aria-labelledby="verdicts">
        <h2 id="verdicts" className="text-lg font-semibold">Verdicts and severity</h2>
        <dl className="grid gap-1 sm:grid-cols-[6rem_1fr]">
          {VERDICTS.map(([word, meaning]) => (
            <div key={word} className="contents">
              <dt className="font-semibold">{word}</dt>
              <dd>{meaning}</dd>
            </div>
          ))}
        </dl>
        <p>
          <strong>High:</strong> a key flow shows the wrong result, a page crashes, an API call fails on a main page.{" "}
          <strong>Medium:</strong> broken image or link, page wider than a phone, console error, clear design mismatch.{" "}
          <strong>Warning:</strong> API call slower than 2 s, page slower than 5 s, small design difference. Warnings
          don&apos;t fail a run.
        </p>
        <p>
          A flow&apos;s pass or fail comes from checks Playwright records (the agent&apos;s text checks, console errors
          and failed requests), never from the AI&apos;s own words. Design and code findings are suggestions.
        </p>
      </section>

      <section className="grid gap-2" aria-labelledby="safety">
        <h2 id="safety" className="text-lg font-semibold">Safety</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>Runs are refused while <code>ANTHROPIC_API_KEY</code> is set, and stop if Claude Code reports any credential other than your subscription login.</li>
          <li>Payments, transfers, deletions and account changes are mocked or blocked at the network level, in Quick Scan and for every agent.</li>
          <li>Only the shared test account or the mock login is used. Text on a page is treated as data, not instructions.</li>
          <li>Agents never edit app code. The Test writer writes only in the test folder, on a new branch in a separate worktree. Nothing pushes to main or merges.</li>
          <li>Everything stays on this machine; the backend listens on 127.0.0.1.</li>
        </ul>
      </section>
    </article>
  );
}
