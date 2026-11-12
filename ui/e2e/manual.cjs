// Segue o manual do conferente (docs/operacao/manual-do-conferente.md) na caixa de exemplo
// do pacote, usando só o que o manual diz: nomes de botão, teclas e textos da tela.
// Uso: node e2e/manual.cjs <link de acesso> <pasta da caixa de exemplo> [pasta de capturas]
const { chromium } = require("playwright");

(async () => {
  const [link, folder, shots] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
  page.on("pageerror", (err) => console.error("erro na página:", err.message));
  await page.goto(link);
  await page.getByRole("heading", { level: 1, name: "Abrir lote" }).waitFor({ timeout: 30_000 });

  // "A qualquer momento, aperte ? para ver a lista de atalhos."
  await page.keyboard.press("?");
  await page.getByRole("dialog", { name: "Atalhos de teclado" }).waitFor();
  await page.keyboard.press("Escape");

  // 1. Abrir a caixa
  await page.getByLabel("Pasta do lote").fill(folder);
  await page.getByRole("button", { name: "Analisar lote" }).click();
  await page.waitForURL(/#\/batches\/[0-9a-f-]+$/, { timeout: 30_000 });
  const batchId = /#\/batches\/([0-9a-f-]+)/.exec(page.url())[1];
  const conferir = page.getByRole("link", { name: "Conferir" }).first();
  const done = page.getByText(/Veredito|Aprovado|Reprovado/).first();
  await Promise.race([conferir.waitFor({ timeout: 120_000 }), done.waitFor({ timeout: 120_000 })]);
  if (await conferir.isVisible()) await conferir.click();
  else await page.goto(page.url().replace(/#.*$/, `#/batches/${batchId}/sequence`));

  // 2. Sequência: a lacuna da folha 3 e "Defeito de origem"
  await page.getByRole("link", { name: "Sequência", exact: true }).click();
  await page.waitForFunction(() => document.body.innerText.includes("Falta fls. 3"), null, { timeout: 120_000 });
  await page.getByRole("button", { name: /Defeito de origem/ }).first().click();
  await page.getByText("Defeito de origem: o papel já veio sem a folha").waitFor({ timeout: 30_000 });
  if (shots) await page.screenshot({ path: `${shots}/manual-sequencia.png`, fullPage: true });

  // 3. Revisão: C endireita / tira a branca, R manda a sem nitidez para retrabalho, A no resto.
  await page.getByRole("link", { name: "Revisão", exact: true }).click();
  await page.getByText("decididas").first().waitFor({ timeout: 30_000 });
  const keyFor = { "Inclinação": "c", "Página em branco": "c", "Desfoque": "r" };
  for (let i = 0; i < 40; i++) {
    if (await page.getByText("Tudo decidido").isVisible()) break;
    const current = page.locator("h2.inline").first();
    if (!(await current.isVisible())) break;
    const rule = (await current.innerText()).trim();
    const before = await page.getByText(/decididas/).first().innerText();
    await page.keyboard.press(keyFor[rule] ?? "a");
    await page.waitForFunction(
      (b) => [...document.querySelectorAll("*")].some((e) => e.childElementCount === 0 && /decididas/.test(e.textContent) && e.textContent !== b),
      before,
      { timeout: 30_000 },
    ).catch(() => {});
  }
  await page.getByText("Tudo decidido").waitFor({ timeout: 30_000 });
  if (shots) await page.screenshot({ path: `${shots}/manual-revisao.png`, fullPage: true });

  // 5. Salvar e relatório da caixa
  await page.getByRole("link", { name: "Relatório", exact: true }).click();
  const save = page.getByRole("button", { name: "Salvar na pasta de saída" });
  await save.waitFor({ timeout: 30_000 });
  await page.waitForFunction(() => {
    const b = [...document.querySelectorAll("button")].find((x) => x.textContent === "Salvar na pasta de saída");
    return b && !b.disabled;
  }, null, { timeout: 60_000 });
  await save.click();
  await page.getByText(/Gravado em/).waitFor({ timeout: 120_000 });
  const boxes = page.getByRole("heading", { name: "Relatórios por caixa" });
  await boxes.waitFor();
  const pending = await page.evaluate(async (id) => {
    const headers = { Authorization: `Bearer ${sessionStorage.getItem("qa.token")}` };
    const findings = await (await fetch(`/batches/${id}/findings`, { headers })).json();
    return findings.filter((f) => !f.decision).map((f) => f.rule);
  }, batchId);
  if (pending.length) throw new Error(`sinalizações sem decisão depois do manual: ${pending}`);
  await page.getByRole("button", { name: "PDF" }).first().waitFor({ timeout: 30_000 });
  if (shots) await page.screenshot({ path: `${shots}/manual-relatorio.png`, fullPage: true });
  await browser.close();
  console.log("manual do conferente ok");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
