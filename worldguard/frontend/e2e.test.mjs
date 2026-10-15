import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import test from 'node:test';
import { chromium } from 'playwright';

const appURL = 'http://127.0.0.1:5173';
const apiURL = process.env.WORLDGUARD_API_URL ?? 'http://127.0.0.1:8520';

async function ready(url, process) {
  for (let attempt = 0; attempt < 60; attempt++) {
    if (process?.exitCode != null) throw new Error(`preview exited: ${process.exitCode}`);
    try { if ((await fetch(url)).ok) return; } catch { /* retry while local server starts */ }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`server not ready: ${url}`);
}

test('dist bundle against real HTTP backend: run, audit, recover, download', { timeout: 120000 }, async () => {
  assert.ok(existsSync('dist/index.html'), 'build dist/ before running e2e');
  const bundle = readdirSync('dist/assets').filter(file => file.endsWith('.js'))
    .map(file => readFileSync(`dist/assets/${file}`, 'utf8')).join('');
  assert.ok(bundle.includes(apiURL), `rebuild dist/ with VITE_WORLDGUARD_API_URL=${apiURL}`);
  await ready(apiURL + '/api/v1/health');
  const preview = spawn('node', ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '5173', '--strictPort'], { stdio: 'pipe' });
  let browser;
  let page;
  const logs = [];
  const errors = [];
  try {
    await ready(appURL, preview);
    browser = await chromium.launch();
    const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 900 } });
    page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { logs.push(`${message.type()}: ${message.text()}`); if (message.type() === 'error') errors.push(message.text()); });
    const apiResponses = [];
    page.on('response', response => { if (response.url().startsWith(apiURL + '/api/v1/')) apiResponses.push(response.url()); });
    const runPosts = [];
    page.on('request', request => {
      if (request.url() === apiURL + '/api/v1/runs' && request.method() === 'POST') runPosts.push(request.url());
    });
    await page.goto(appURL, { waitUntil: 'networkidle' });
    assert.ok(apiResponses.some(url => url.endsWith('/capabilities')), 'capabilities from selected backend');
    await page.locator('#config').selectOption('dual_route_stale');
    await page.getByRole('button', { name: '手动调试', exact: true }).click();
    await page.getByRole('button', { name: /开始测试/ }).click();
    await page.locator('[data-testid="candidates"]').getByRole('button', { name: /block_route_1/ }).waitFor();
    assert.match(page.url(), /\?run=run_/);
    await page.locator('[data-testid="candidates"]').getByRole('button', { name: /block_route_1/ }).click();
    await page.locator('.map-column [data-testid="case-map"]').waitFor();
    assert.ok(await page.locator('.map-column [data-testid="case-map"] rect').count() > 0, 'actual geometry rendered');
    await page.getByRole('button', { name: '运行案例' }).click();
    await page.locator('[data-testid="audit-results"]').getByText('原始路径').waitFor();
    await page.getByRole('button', { name: '审计此路径' }).click();
    await page.getByText('发现路径安全问题', {exact:true}).waitFor();
    assert.match(await page.locator('[data-testid="audit-results"]').innerText(), /规划成功[\s\S]*不通过/);
    await page.getByRole('button', { name: '执行恢复' }).click();
    await page.locator('[data-testid="audit-results"]').getByText('恢复路径').waitFor();
    await page.getByRole('button', { name: '审计此路径' }).click();
    await page.locator('[data-testid="audit-results"]').getByText('通过', { exact: true }).waitFor();
    assert.equal(await page.locator('[data-testid="audit-results"] .path-row.mismatch').count(), 1);
    assert.match(page.url(), /case=block_route_1/);
    const before = await page.locator('[data-testid="candidates"]').innerText();
    const postsBeforeReload = runPosts.length;
    await page.reload({ waitUntil: 'networkidle' });
    assert.equal(runPosts.length, postsBeforeReload, 'reload must not create another run');
    await page.locator('[data-testid="candidates"]').getByRole('button', { name: /block_route_1/ }).waitFor();
    assert.equal(await page.locator('[data-testid="candidates"]').innerText(), before);
    await page.locator('[data-testid="audit-results"] .path-row.mismatch').waitFor();
    assert.match(await page.locator('[data-testid="audit-results"]').innerText(), /原始路径[\s\S]*不通过[\s\S]*恢复路径[\s\S]*通过/);
    await page.getByRole('button', { name: '报告中心', exact: true }).click();
    await page.getByRole('button', { name: '完成运行并生成报告', exact: true }).click();
    await page.getByText('报告已生成').waitFor();
    const [reportDownload] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: '下载报告', exact: true }).first().click()]);
    assert.match(reportDownload.suggestedFilename(), /\.md$/);
    const [zipDownload] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: '证据 ZIP', exact: true }).first().click()]);
    assert.match(zipDownload.suggestedFilename(), /\.zip$/);
    assert.ok((await page.locator('[data-testid="events"]').innerText()).includes('wg_'));
    assert.ok(apiResponses.some(url => url.includes('/candidates')), 'candidates from selected backend');
    const theme = await page.evaluate(() => {
      const relative = color => {
        const [r, g, b] = color.match(/\d+/g).map(Number);
        const channel = c => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
      };
      const body = getComputedStyle(document.body);
      const ratio = (a, b) => {
        const [hi, lo] = [relative(a), relative(b)].sort((x, y) => y - x);
        return (hi + 0.05) / (lo + 0.05);
      };
      return { background: relative(body.backgroundColor), text: ratio(body.color, body.backgroundColor) };
    });
    assert.ok(theme.background < 0.1, `dark theme background, got luminance ${theme.background}`);
    assert.ok(theme.text >= 4.5, `body text contrast must meet WCAG AA, got ${theme.text.toFixed(2)}:1`);
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'mobile overflow');
    await page.getByRole('button', { name: '工作台', exact: true }).click();
    await page.getByLabel('场景配置', { exact: true }).selectOption('labyrinth_stale');
    await page.getByRole('button', { name: /开始测试/ }).click();
    await page.getByRole('button', { name: /disconnect_goal_1/ }).waitFor();
    assert.equal(await page.getByRole('alert').count(), 0, 'cross-map creation does not reuse the old case');
    await page.getByRole('button', { name: '取消任务', exact: true }).click();
    await page.getByText('已取消', { exact: true }).waitFor();
  } finally {
    console.log('pageerror:', errors.filter(Boolean).join('\n') || '(none)');
    console.log('console (all):', logs.join('\n') || '(none)');
    await browser?.close();
    preview.kill('SIGTERM');
    await once(preview, 'exit').catch(() => {});
  }
  assert.deepEqual(errors, [], 'browser errors are failures');
});
