const { chromium } = require('playwright');
// Uso: node e2e/fluxo-completo.cjs <lote.zip> [pasta-de-capturas]
// Requer o motor (QA_API_TOKEN=demo-token) e o vite dev (npm run dev) no ar.
const ZIP = process.argv[2];
const S = process.argv[3] ?? '.';
const UI = process.env.QA_UI_URL ?? 'http://localhost:5173/';
const TOKEN = process.env.QA_TOKEN ?? 'demo-token';
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  await page.goto(UI);
  await page.getByLabel('Seu nome').fill('Garantidor 1');
  await page.getByLabel('Token de acesso').fill(TOKEN);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await page.getByRole('heading', { name: 'Enviar lote' }).waitFor();
  await page.screenshot({ path: `${S}/1-envio.png` });
  await page.locator('input[accept=".zip"]').setInputFiles(`${ZIP}`);
  await page.getByRole('button', { name: 'Analisar lote' }).click();
  const t0 = Date.now();
  await page.getByText('Dispensam revisão').first().waitFor({ timeout: 120000 });
  console.log('análise até o painel (s):', ((Date.now() - t0) / 1000).toFixed(1));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${S}/2-painel.png`, fullPage: true });
  await page.getByRole('link', { name: /Revisar/ }).first().click();
  await page.locator('.queue-row').first().waitFor();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${S}/3-revisao.png` });
  const before = await page.locator('.queue-row').count();
  // Decisões pelo teclado: tempo por decisão.
  const t1 = Date.now();
  for (const k of ['a', 'r', 'o']) { await page.keyboard.press(k); await page.waitForTimeout(250); }
  console.log('3 decisões (ms):', Date.now() - t1);
  const after = await page.locator('.queue-row').count();
  console.log('fila', before, '->', after);
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(600);
  console.log('após Ctrl+Z', await page.locator('.queue-row').count());
  // Correção automática: filtrar médio (inclinação) e aplicar C.
  await page.keyboard.press('3');
  await page.waitForTimeout(300);
  const skew = page.locator('.queue-row', { hasText: 'Inclinação' }).first();
  if (await skew.count()) {
    await skew.click();
    await page.waitForTimeout(800);
    await page.keyboard.press('c');
    await page.waitForFunction(() => (document.querySelector('[role=status]')?.textContent ?? '').includes('cópia'), null, { timeout: 15000 });
    console.log('toast:', await page.getByRole('status').textContent());
    await page.locator('.queue-row', { hasText: 'Inclinação' }).count();
  }
  await page.keyboard.press('3');
  await page.locator('label.check input').uncheck();
  await page.waitForTimeout(300);
  const fixed = page.locator('.queue-row.decided', { hasText: 'Inclinação' }).first();
  if (await fixed.count()) { await fixed.click(); await page.waitForTimeout(1500); await page.screenshot({ path: `${S}/4-correcao-depois.png` }); }
  await page.getByRole('link', { name: 'Sequência', exact: true }).click();
  await page.waitForTimeout(300);
  // documento com sinalização de sequência
  const docs = page.locator('.doc-list a');
  const n = await docs.count();
  for (let i = 0; i < n; i++) {
    await docs.nth(i).click(); await page.waitForTimeout(200);
    if (await page.locator('.gap, .seq-page.moved, .seq-page.doubt').count()) break;
  }
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${S}/5-sequencia.png`, fullPage: true });
  await page.getByRole('link', { name: 'Metadados', exact: true }).first().click();
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: 'Editar' }).first().click();
  await page.locator('td.value input').fill('Contrato de locação');
  await page.getByRole('button', { name: 'Salvar' }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${S}/6-metadados.png`, fullPage: true });
  await page.getByRole('link', { name: 'Relatório', exact: true }).click();
  await page.getByRole('heading', { name: 'Ordem de retrabalho' }).waitFor();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${S}/7-relatorio.png`, fullPage: true });
  const dl = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Ordem de retrabalho (CSV)' }).click();
  console.log('download:', (await dl).suggestedFilename());
  await page.getByRole('link', { name: 'Perfis' }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${S}/8-perfis.png` });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(page.url().replace(/#.*/, '') + '#/');
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${S}/9-celular.png`, fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  console.log('rolagem horizontal no celular:', overflow);
  console.log('erros de console:', errors.length ? errors : 'nenhum');
  if (errors.length || overflow) process.exitCode = 1;
  await browser.close();
})().catch(e => { console.error('FALHA', e); process.exit(1); });
