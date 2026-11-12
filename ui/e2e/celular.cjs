// Fluxo de demonstração no celular, só com toque (ADR-0010).
// Uso: node e2e/celular.cjs <url-da-interface> [aparelho] [pasta-de-capturas]
//   aparelho: nome do Playwright, ex.: "Pixel 7" (padrão) ou "iPhone 13".
// Requer o motor no ar sem QA_API_TOKEN e com QA_DEMO_DIR (lote de demonstração).
// Falha (código 1) com erro de console, requisição de rede que falhou, resposta 5xx
// ou rolagem horizontal em qualquer tela.
const { chromium, devices } = require('playwright');
const path = require('path');

const UI = process.argv[2] ?? 'http://localhost:8000/';
const DEVICE = process.argv[3] ?? 'Pixel 7';
const SHOTS = process.argv[4] ?? '.';
const slug = DEVICE.toLowerCase().replace(/\s+/g, '-');

(async () => {
  const browser = await chromium.launch();
  const { defaultBrowserType, ...device } = devices[DEVICE];
  const context = await browser.newContext({ ...device, acceptDownloads: true });
  const page = await context.newPage();
  const problems = [];
  // Enquanto o motor acorda, as tentativas de /health falham de propósito: não contam.
  let booting = true;
  page.on('console', (m) => m.type() === 'error' && !booting && problems.push(`console: ${m.text()}`));
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('requestfailed', (r) => {
    if (booting && r.url().endsWith('/health')) return;
    // O fluxo de progresso ao vivo é cancelado pela própria tela quando a análise
    // termina ou quando se sai do painel: não é falha de rede.
    if (r.url().endsWith('/events') && r.failure()?.errorText === 'net::ERR_ABORTED') return;
    problems.push(`rede: ${r.method()} ${r.url()} ${r.failure()?.errorText}`);
  });
  page.on('response', (r) => r.status() >= 500 && problems.push(`HTTP ${r.status()} ${r.url()}`));
  const shot = (name) => page.screenshot({ path: path.join(SHOTS, `${slug}-${name}.png`), fullPage: true });
  const overflow = async (where) => {
    const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    if (wide) problems.push(`rolagem horizontal em ${where}`);
  };
  const t0 = Date.now();

  // Partida (espera o motor acordar) e entrada só com o nome.
  await page.goto(UI);
  await page.waitForTimeout(2500);
  if (await page.getByText('Acordando o motor de análise').count()) await shot('0-acordando');
  await page.getByLabel('Seu nome').waitFor({ timeout: 120000 });
  booting = false;
  console.log(`[${DEVICE}] motor pronto em ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  if (await page.getByLabel('Token de acesso').count()) problems.push('pediu token num motor sem QA_API_TOKEN');
  await overflow('entrada');
  await shot('1-entrada');
  await page.getByLabel('Seu nome').fill('Maria');
  await page.getByRole('button', { name: 'Começar' }).tap();

  // Lote de demonstração: nada é enviado do aparelho.
  const demo = page.getByRole('button', { name: /Analisar lote-demonstracao/ });
  await demo.waitFor({ timeout: 15000 });
  await overflow('envio');
  await shot('2-envio');
  await demo.tap();
  await page.getByText('Dispensam revisão').first().waitFor({ timeout: 180000 });
  await page.waitForTimeout(500);
  await overflow('painel');
  await shot('3-painel');
  console.log(`[${DEVICE}] painel: ${(await page.locator('.stat').first().innerText()).replace(/\s+/g, ' ')}`);

  // Revisão por toque.
  await page.getByRole('link', { name: /Revisar/ }).tap();
  await page.locator('.queue-row').first().waitFor();
  const rows = await page.locator('.queue-row').count();
  await page.locator('.viewer canvas').first().waitFor({ timeout: 20000 });
  await page.waitForTimeout(800);
  await overflow('revisão');
  await shot('4-revisao');
  console.log(`[${DEVICE}] fila de revisão: ${rows} sinalizações (${(await page.locator('.queue-row .rule').allTextContents()).join(', ')})`);

  // Sequência do documento com os quatro casos.
  await page.getByRole('link', { name: 'Sequência', exact: true }).tap();
  await page.locator('.doc-list .mark').first().waitFor({ timeout: 15000 });
  await page.locator('.doc-list a', { hasText: 'DOC0001' }).tap();
  await page.waitForTimeout(800);
  await overflow('sequência (antes)');
  await shot('5-sequencia-antes');
  await page.getByRole('button', { name: 'Corrigir tudo' }).tap();
  await page.locator('.progress-overlay').waitFor({ timeout: 10000 });
  const titles = [];
  for (;;) {
    const t = await page.locator('.progress-overlay h2').textContent({ timeout: 200 }).catch(() => null);
    if (t === null) break;
    if (titles.at(-1) !== t) titles.push(t);
    await page.waitForTimeout(40);
  }
  console.log(`[${DEVICE}] tela de carregamento: ${titles.join(' → ')}`);
  await page.locator('[aria-label="Depois"]').waitFor({ timeout: 15000 });
  await page.waitForTimeout(1500);
  const after = (await page.locator('[aria-label="Depois"] .note-change').allTextContents()).join(' | ');
  const removed = (await page.locator('[aria-label="Antes"] .note-removed').allTextContents()).join(' | ');
  const rescan = (await page.locator('[aria-label="Antes"] .note-rescan').allTextContents()).join(' | ');
  console.log(`[${DEVICE}] depois: ${after} · removidas: ${removed} · redigitalizar: ${rescan}`);
  if (!after.includes('endireitada') || !removed.includes('em branco') || !rescan.toLowerCase().includes('desfoque')) {
    problems.push('resultado do Corrigir tudo incompleto');
  }
  await overflow('sequência (depois)');
  await shot('6-sequencia-depois');

  // Página faltando: Salvar bloqueado até decidir.
  const save = page.getByRole('button', { name: 'Salvar correções' });
  const blocked = await save.isDisabled();
  await page.locator('.missing-card').getByRole('button', { name: /Mandar para retrabalho/ }).tap();
  await page.locator('.missing-card.decided').waitFor({ timeout: 10000 });
  console.log(`[${DEVICE}] Salvar bloqueado com página faltando: ${blocked}; depois de decidir: ${await save.isEnabled()}`);
  if (!blocked || !(await save.isEnabled())) problems.push('bloqueio do Salvar não funcionou');

  // Zoom pelo botão "Ampliar" (toque) e numeração pelo toque na miniatura.
  await page.locator('[aria-label="Depois"] .seq-page.changed .zoom-btn').first().tap();
  await page.getByRole('dialog').waitFor();
  await page.locator('.overlay-loading').waitFor({ state: 'detached', timeout: 20000 });
  await page.waitForTimeout(500);
  await shot('7-zoom');
  const toggle = await page.getByRole('button', { name: 'Original', exact: true }).count();
  await page.getByRole('button', { name: 'Fechar' }).tap();
  await page.getByRole('dialog').waitFor({ state: 'detached' });
  await page.locator('[aria-label="Antes"] .seq-hit').first().tap();
  await page.getByRole('heading', { name: 'Numeração da folha' }).waitFor({ timeout: 3000 });
  await page.getByRole('button', { name: 'Cancelar' }).tap();
  console.log(`[${DEVICE}] zoom com Original/Corrigida: ${toggle > 0}; toque na miniatura abre a numeração: ok`);

  // Salvar e baixar o lote corrigido.
  const download = page.waitForEvent('download', { timeout: 120000 });
  await save.tap();
  const file = await download;
  await file.saveAs(path.join(SHOTS, `${slug}-${file.suggestedFilename()}`));
  console.log(`[${DEVICE}] baixado: ${file.suggestedFilename()}`);
  await page.waitForTimeout(500);
  await shot('8-salvo');

  // As outras telas também cabem na largura do celular.
  for (const [name, link] of [['metadados', 'Metadados'], ['relatorio', 'Relatório'], ['painel', 'Painel']]) {
    await page.getByRole('link', { name: link, exact: true }).first().tap();
    await page.waitForTimeout(1200);
    await overflow(name);
    await shot(`9-${name}`);
  }
  await page.getByRole('link', { name: 'Perfis' }).tap();
  await page.waitForTimeout(800);
  await overflow('perfis');

  console.log(`[${DEVICE}] tempo total: ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  console.log(`[${DEVICE}] problemas: ${problems.length ? '\n  ' + problems.join('\n  ') : 'nenhum'}`);
  if (problems.length) process.exitCode = 1;
  await browser.close();
})().catch((e) => {
  console.error('FALHA', e);
  process.exit(1);
});
