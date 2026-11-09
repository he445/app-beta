const { chromium } = require('playwright');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
// Uso: node e2e/fluxo-completo.cjs <lote.zip> [pasta-de-capturas] [pasta-do-lote-original]
// Requer o motor (QA_API_TOKEN=demo-token) e o vite dev (npm run dev) no ar.
// Com a pasta do lote original, confere no fim que nenhum arquivo dela mudou (SHA-256).
const ZIP = process.argv[2];
const S = process.argv[3] ?? '.';
const LOT = process.argv[4];

function shaTree(dir) {
  const out = {};
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else out[path.relative(dir, p)] = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
    }
  };
  walk(dir);
  return out;
}

async function progressTitles(page, timeout = 120000) {
  // Lê a tela de carregamento enquanto ela existir: o progresso vem do motor.
  const seen = [];
  const end = Date.now() + timeout;
  await page.locator('.progress-overlay').waitFor({ timeout: 10000 });
  while (Date.now() < end) {
    const t = await page.locator('.progress-overlay h2').textContent({ timeout: 200 }).catch(() => null);
    if (t === null) break;
    if (seen[seen.length - 1] !== t) seen.push(t);
    await page.waitForTimeout(50);
  }
  return seen;
}
const UI = process.env.QA_UI_URL ?? 'http://localhost:5173/';
const TOKEN = process.env.QA_TOKEN ?? 'demo-token';
(async () => {
  const originalBefore = LOT ? shaTree(LOT) : null;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  await page.goto(UI);
  // Entrada: só o nome; o token aparece só se o motor exigir (QA_API_TOKEN, ADR-0010).
  await page.getByLabel('Seu nome').waitFor({ timeout: 120000 });
  await page.getByLabel('Seu nome').fill('Garantidor 1');
  if (await page.getByLabel('Token de acesso').count()) await page.getByLabel('Token de acesso').fill(TOKEN);
  await page.getByRole('button', { name: 'Começar' }).click();
  await page.getByRole('heading', { name: 'Enviar lote' }).waitFor();
  await page.screenshot({ path: `${S}/1-envio.png` });
  await page.locator('input[accept^=".zip"]').setInputFiles(`${ZIP}`);
  await page.getByRole('button', { name: 'Analisar lote', exact: true }).click();
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
  // Decisão pelo teclado e Ctrl+Z (o "Corrigir tudo" vem depois, sobre o estado original).
  const t1 = Date.now();
  await page.keyboard.press('a');
  await page.waitForFunction((n) => document.querySelectorAll('.queue-row').length === n - 1, before, { timeout: 5000 });
  console.log('decisão pelo teclado (ms):', Date.now() - t1);
  await page.getByRole('status').filter({ hasText: 'aprovada' }).waitFor({ timeout: 5000 });
  await page.keyboard.press('Control+z');
  await page.waitForFunction((n) => document.querySelectorAll('.queue-row').length === n, before, { timeout: 5000 });
  console.log('após Ctrl+Z a fila voltou a', await page.locator('.queue-row').count());
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
  // ---- Corrigir tudo (documento) --------------------------------------------------
  await page.getByRole('link', { name: 'Sequência', exact: true }).click();
  await page.locator('.doc-list a').first().waitFor();
  await page.locator('.doc-list .mark').first().waitFor({ timeout: 5000 }).catch(() => undefined);
  const missingDoc = page.locator('.doc-list a', { has: page.locator('.mark-missing') }).first();
  const docLink = (await missingDoc.count()) ? missingDoc : page.locator('.doc-list a').first();
  const docName = (await docLink.textContent()).trim().split(' ')[0];
  await docLink.click();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${S}/5-sequencia-antes.png`, fullPage: true });
  await page.getByRole('button', { name: 'Corrigir tudo' }).click();
  console.log(`Corrigir tudo (${docName}):`, await progressTitles(page));
  await page.waitForTimeout(800);
  console.log('resultado:', (await page.locator('p.small.muted', { hasText: 'Corrigir tudo' }).first().textContent()).trim());

  // ---- Corrigir o lote inteiro (painel) ---------------------------------------------
  await page.getByRole('link', { name: 'Painel', exact: true }).click();
  await page.getByRole('button', { name: 'Corrigir o lote inteiro' }).click();
  console.log('Corrigir o lote inteiro:', await progressTitles(page));
  await page.waitForTimeout(1500);
  const docs = page.locator('.doc-list a');
  const summary = { endireitadas: 0, removidas: 0, movidas: 0, redigitalizar: 0, depois: 0 };
  for (let i = 0; i < await docs.count(); i++) {
    await docs.nth(i).click();
    await page.waitForTimeout(1500);
    const after = page.locator('[aria-label="Depois"]');
    if (await after.count()) summary.depois += 1;
    summary.endireitadas += await page.locator('[aria-label="Depois"] .note-change', { hasText: 'endireitada' }).count();
    summary.movidas += await page.locator('[aria-label="Depois"] .note-change', { hasText: 'movida' }).count();
    summary.removidas += await page.locator('[aria-label="Antes"] .seq-page.removed').count();
    summary.redigitalizar += await page.locator('[aria-label="Antes"] .note-rescan').count();
    await page.screenshot({ path: `${S}/6-sequencia-doc${i + 1}.png`, fullPage: true });
  }
  console.log('resultado na sequência:', summary);

  // ---- Página faltando: Salvar bloqueado até decidir --------------------------------------
  const saveButton = page.getByRole('button', { name: 'Salvar correções' });
  const blocked = await page.locator('.mark-missing').count();
  if (blocked) {
    await page.locator('.doc-list a', { has: page.locator('.mark-missing') }).first().click();
    await page.waitForTimeout(800);
    console.log('Salvar bloqueado com página faltando:', await saveButton.isDisabled(), '|', (await page.locator('.blocked-reason').first().textContent()).trim());
    if (!(await saveButton.isDisabled())) process.exitCode = 1;
    while (await page.locator('.doc-list a .mark-missing').count()) {
      await page.locator('.doc-list a', { has: page.locator('.mark-missing') }).first().click();
      await page.waitForTimeout(500);
      await page.locator('.missing-card').getByRole('button', { name: /Mandar para retrabalho/ }).first().click();
      await page.waitForTimeout(800);
    }
    await page.screenshot({ path: `${S}/7-faltando-decidida.png`, fullPage: true });
  }
  console.log('Salvar liberado depois da decisão:', await saveButton.isEnabled());

  // ---- Zoom com duplo clique e teclado ---------------------------------------------------
  const corrected = page.locator('[aria-label="Depois"] .seq-page.changed');
  if (!(await corrected.count())) {
    for (let i = 0; i < await docs.count(); i++) {
      await docs.nth(i).click();
      await page.waitForTimeout(600);
      if (await corrected.count()) break;
    }
  }
  const card = (await corrected.count()) ? corrected.first() : page.locator('.strip .seq-page').first();
  const thumb = card.locator('.seq-hit');
  await thumb.dblclick();
  await page.getByRole('dialog').waitFor();
  await page.waitForTimeout(400);
  const numberingAlsoOpened = await page.getByRole('heading', { name: 'Numeração da folha' }).count();
  const label1 = await page.locator('.zoom-head strong').textContent();
  await page.keyboard.press('ArrowRight');
  const label2 = await page.locator('.zoom-head strong').textContent();
  await page.keyboard.press('ArrowLeft');
  await page.locator('.overlay-loading').waitFor({ state: 'detached', timeout: 15000 });
  await page.waitForTimeout(500);
  const toggle = await page.getByRole('button', { name: 'Original', exact: true }).count();
  await page.screenshot({ path: `${S}/8-zoom-corrigida.png` });
  if (toggle) {
    await page.getByRole('button', { name: 'Original', exact: true }).click();
    await page.locator('.overlay-loading').waitFor({ state: 'detached', timeout: 15000 });
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${S}/8-zoom-original.png` });
    await page.getByRole('button', { name: 'Corrigida', exact: true }).click();
  }
  console.log('zoom: alternância Original/Corrigida presente:', toggle > 0);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);
  console.log('zoom: abriu sem a numeração:', numberingAlsoOpened === 0, '| seta trocou a página:', label1 !== label2, '| Esc fechou:', (await page.getByRole('dialog').count()) === 0);
  if (numberingAlsoOpened || label1 === label2 || await page.getByRole('dialog').count()) process.exitCode = 1;
  await thumb.click();
  await page.getByRole('heading', { name: 'Numeração da folha' }).waitFor({ timeout: 2000 });
  await page.keyboard.press('Escape');
  await thumb.focus();
  await page.keyboard.press('z');
  await page.getByRole('dialog').waitFor({ timeout: 2000 });
  await page.keyboard.press('Escape');
  await thumb.focus();
  await page.keyboard.press('Enter');
  await page.getByRole('heading', { name: 'Numeração da folha' }).waitFor({ timeout: 2000 });
  await page.keyboard.press('Escape');
  console.log('teclado: Z abre o zoom, Enter abre a numeração, Esc fecha: ok');

  // ---- Salvar correções e baixar o zip ------------------------------------------------------
  const zipDownload = page.waitForEvent('download');
  await saveButton.click();
  const zipFile = await zipDownload;
  const zipPath = path.join(S, zipFile.suggestedFilename());
  await zipFile.saveAs(zipPath);
  console.log('lote corrigido baixado:', zipFile.suggestedFilename());
  const check = execFileSync('python3', ['-I', '-c', `
import io, json, sys, zipfile
from PIL import Image
z = zipfile.ZipFile(sys.argv[1])
m = json.loads(z.read("manifest.json"))
tifs = [n for n in z.namelist() if n.endswith(".tif")]
comp = {Image.open(io.BytesIO(z.read(n))).tag_v2[259] for n in tifs}
print(json.dumps({"tifs": len(tifs), "totals": m["totals"], "compressao": sorted(comp),
  "mudancas": [c["text"] for d in m["documents"] for p in d["pages"] for c in p["changes"]],
  "faltando": [(d["name"], g["missing"], g["decision"]["action"]) for d in m["documents"] for g in d["missing"]]}, ensure_ascii=False))
`, zipPath]).toString().trim();
  console.log('manifesto:', check);
  if (!check.includes('"compressao": [8]')) process.exitCode = 1;
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${S}/9-salvo.png`, fullPage: true });

  await page.getByRole('link', { name: 'Metadados', exact: true }).first().click();
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: 'Editar' }).first().click();
  await page.locator('td.value input').fill('Contrato de locação');
  await page.getByRole('button', { name: 'Salvar' }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${S}/10-metadados.png`, fullPage: true });
  await page.getByRole('link', { name: 'Relatório', exact: true }).click();
  await page.getByRole('heading', { name: 'Ordem de retrabalho' }).waitFor();
  await page.waitForTimeout(1000);
  console.log('relatório: "Baixar lote corrigido" habilitado:', await page.getByRole('button', { name: 'Baixar lote corrigido' }).isEnabled());
  await page.screenshot({ path: `${S}/11-relatorio.png`, fullPage: true });
  const dl = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Ordem de retrabalho (CSV)' }).click();
  console.log('download:', (await dl).suggestedFilename());
  await page.getByRole('link', { name: 'Perfis' }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${S}/12-perfis.png` });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(page.url().replace(/#.*/, '') + '#/');
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${S}/13-celular.png`, fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  console.log('rolagem horizontal no celular:', overflow);
  if (originalBefore) {
    const same = JSON.stringify(shaTree(LOT)) === JSON.stringify(originalBefore);
    console.log('arquivos originais intactos (SHA-256):', same);
    if (!same) process.exitCode = 1;
  }
  console.log('erros de console:', errors.length ? errors : 'nenhum');
  if (errors.length || overflow) process.exitCode = 1;
  await browser.close();
})().catch(e => { console.error('FALHA', e); process.exit(1); });
