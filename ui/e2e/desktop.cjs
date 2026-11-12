// Programa desktop sem janela (QA --headless), interface aberta pelo link de acesso de uso
// único: sem tela de entrada, "Abrir lote" por caminho, análise e "Salvar na pasta de saída".
// Com token de administrador, confere também a tela de Diagnóstico com um erro forçado.
// Com a pasta de um lote de três folhas sem número, confere a tela de Sequência: o
// documento resolvido só no teclado e a reordenação indo para o lote corrigido.
// Uso: node e2e/desktop.cjs <link de acesso> <pasta do lote> [capturas] [token de admin] [lote de sequência]
const { chromium } = require("playwright");

(async () => {
  const [link, folder, shots, adminToken, sequenceFolder] = process.argv.slice(2);
  if (!link || !folder) throw new Error("uso: desktop.cjs <link> <pasta do lote> [capturas]");
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1366, height: 860 } });
  page.on("pageerror", (err) => console.error("erro na página:", err.message));
  await page.goto(link);

  await page.getByRole("heading", { level: 1, name: "Abrir lote" }).waitFor({ timeout: 30_000 });
  if (await page.getByText("Seu nome").count()) throw new Error("tela de entrada apareceu no desktop");
  if (await page.getByText("Somente documentos sintéticos").count()) throw new Error("aviso da nuvem no desktop");
  if (new URL(page.url()).hash.includes("code=")) throw new Error("código ficou na URL");
  if (shots) await page.screenshot({ path: `${shots}/desktop-inicio.png` });

  // Configurações: valor inválido é recusado antes de salvar; cada valor diz de onde veio.
  await page.getByRole("link", { name: "Configurações" }).click();
  await page.getByRole("tab", { name: "Digitalizadoras" }).waitFor();
  await page.getByLabel("Ajustar para").selectOption("cg-e3");
  const dark = page.getByLabel("dark_level");
  await dark.waitFor({ timeout: 30_000 });
  if ((await dark.inputValue()) !== "60") throw new Error("dark_level da estação cg-e3 deveria ser 60");
  await dark.fill("-5");
  await page.getByText("mínimo 0").waitFor();
  if (await page.getByRole("button", { name: /Salvar 1 mudança/ }).isEnabled()) throw new Error("salvar liberado com valor inválido");
  await page.getByRole("button", { name: "Descartar" }).click();
  await page.getByRole("tab", { name: "Este computador" }).click();
  const workers = page.getByLabel("Processos de análise");
  await workers.fill("0");
  await page.getByText("mínimo 1").waitFor();
  await workers.fill("2");
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await page.getByText("valem na próxima abertura").waitFor();
  if (shots) await page.screenshot({ path: `${shots}/desktop-configuracoes.png`, fullPage: true });
  await page.getByRole("link", { name: "QA de Digitalização" }).click();

  await page.getByLabel("Pasta do lote").fill(folder);
  await page.getByRole("button", { name: "Analisar lote" }).click();
  await page.waitForURL(/#\/batches\/[0-9a-f-]+$/, { timeout: 30_000 });
  await page.getByRole("link", { name: "Relatório" }).waitFor({ timeout: 120_000 });
  await page.getByText(/Veredito|Aprovado|Reprovado/).first().waitFor({ timeout: 120_000 });
  // Revisão: girar a página pelo teclado (E = 90° à direita) vira decisão auditada.
  await page.getByRole("link", { name: "Revisão" }).click();
  const rotateHeading = page.getByRole("heading", { name: "Girar a página" });
  await page.getByText("decididas").first().waitFor({ timeout: 30_000 });
  for (let i = 0; i < 10 && !(await rotateHeading.isVisible()); i++) await page.keyboard.press("ArrowRight");
  await rotateHeading.waitFor({ timeout: 10_000 });
  await page.keyboard.press("e");
  await page.getByText("Página girada 90° na cópia.").waitFor({ timeout: 30_000 });
  await page.getByText("Na cópia: girada 90° no sentido horário.").waitFor({ timeout: 30_000 });
  if (shots) await page.screenshot({ path: `${shots}/desktop-revisao-girada.png` });
  await page.keyboard.press("q");
  await page.getByText("Página de volta à orientação original.").waitFor({ timeout: 30_000 });
  await page.getByRole("link", { name: "Relatório" }).click();

  const save = page.getByRole("button", { name: "Salvar na pasta de saída" });
  await save.waitFor({ timeout: 30_000 });
  if (!(await save.isEnabled())) {
    // Página faltando sem decisão bloqueia: o conferente manda para retrabalho e salva.
    const batchId = /#\/batches\/([0-9a-f-]+)/.exec(page.url())[1];
    await page.evaluate(async (id) => {
      const headers = { Authorization: `Bearer ${sessionStorage.getItem("qa.token")}`, "Content-Type": "application/json" };
      const findings = await (await fetch(`/batches/${id}/findings?rule=missing_page`, { headers })).json();
      for (const f of findings) {
        await fetch(`/findings/${f.id}/decision`, { method: "POST", headers, body: JSON.stringify({ action: "reject", reviewer: "e2e" }) });
      }
    }, batchId);
    await page.reload();
    await save.waitFor({ timeout: 30_000 });
  }
  await page.waitForFunction(() => {
    const b = [...document.querySelectorAll("button")].find((x) => x.textContent === "Salvar na pasta de saída");
    return b && !b.disabled;
  }, null, { timeout: 30_000 });
  await save.click();
  await page.getByText(/Gravado em/).waitFor({ timeout: 120_000 });
  console.log((await page.getByText(/Gravado em/).textContent())?.trim());
  if (shots) await page.screenshot({ path: `${shots}/desktop-relatorio.png`, fullPage: true });

  if (adminToken) {
    // Erro forçado na interface: vai para o diagnóstico pelo window.onerror.
    await page.evaluate(() => setTimeout(() => { throw new Error("erro forçado pelo teste de ponta a ponta"); }));
    await page.waitForTimeout(1000);
    await page.getByRole("link", { name: "Diagnóstico" }).click();
    await page.getByLabel("Token de administrador").fill(adminToken);
    await page.getByRole("button", { name: "Entrar" }).click();
    await page.getByText("Erros nas últimas 24 h").waitFor({ timeout: 30_000 });
    await page.getByText("erro forçado pelo teste de ponta a ponta").first().waitFor({ timeout: 30_000 });
    await page.getByText("erro forçado pelo teste de ponta a ponta").first().click();
    await page.getByRole("button", { name: "Marcar como resolvido" }).click();
    await page.getByText(/resolvido por/).waitFor({ timeout: 30_000 });
    if (shots) await page.screenshot({ path: `${shots}/desktop-diagnostico.png`, fullPage: true });
    console.log("diagnóstico ok");
  }
  if (sequenceFolder) {
    await sequence(page, sequenceFolder, shots).catch(async (err) => {
      if (shots) await page.screenshot({ path: `${shots}/desktop-sequencia-erro.png`, fullPage: true });
      throw err;
    });
  }
  await browser.close();
  console.log("fluxo desktop ok");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});

/** Tela de Sequência só no teclado: digitar 1, 3, 2; mover com Alt + seta; desfazer; refazer. */
async function sequence(page, folder, shots) {
  await page.getByRole("link", { name: "QA de Digitalização" }).click();
  await page.getByLabel("Pasta do lote").fill(folder);
  await page.getByRole("button", { name: "Analisar lote" }).click();
  await page.waitForURL(/#\/batches\/[0-9a-f-]+$/, { timeout: 30_000 });
  await page.getByRole("link", { name: "Relatório" }).waitFor({ timeout: 120_000 });
  await page.getByText(/Veredito|Aprovado|Reprovado/).first().waitFor({ timeout: 120_000 });
  const batchId = /#\/batches\/([0-9a-f-]+)/.exec(page.url())[1];
  await page.goto(page.url().replace(/#.*$/, `#/batches/${batchId}/sequence`));
  const field = (n) => page.getByLabel(`Numeração da página na posição ${n}`);
  await field(1).waitFor({ timeout: 30_000 });
  // O foco já está na primeira folha com dúvida: digitar e Enter, três vezes.
  await page.waitForFunction(() => document.activeElement?.getAttribute("aria-label")?.includes("posição 1"), null, { timeout: 10_000 });
  // Digitado de uma vez, sem esperar a gravação: nada se perde.
  for (const value of ["1", "3", "2"]) {
    await page.keyboard.type(value);
    await page.keyboard.press("Enter");
  }
  const typed = () =>
    page.evaluate(async (id) => {
      const headers = { Authorization: `Bearer ${sessionStorage.getItem("qa.token")}` };
      const report = await (await fetch(`/batches/${id}/report`, { headers })).json();
      return report.documents[0].page_ids.map((pid) => report.pages.find((p) => p.id === pid).numbering?.typed ?? "").join();
    }, batchId);
  for (let i = 0; i < 60 && (await typed()) !== "1,3,2"; i++) await page.waitForTimeout(500);
  if ((await typed()) !== "1,3,2") throw new Error(`numeração gravada: ${await typed()}`);
  const values = async () => Promise.all([1, 2, 3].map((n) => field(n).inputValue()));
  if ((await values()).join() !== "1,3,2") throw new Error(`numeração digitada: ${await values()}`);
  // A folha 2 está na posição 3: Alt + seta para a esquerda a traz para a posição 2.
  await field(3).focus();
  await page.keyboard.press("Alt+ArrowLeft");
  await page.getByRole("heading", { name: /ordem escolhida pelo revisor/i }).waitFor({ timeout: 30_000 });
  await page.waitForFunction(() => [...document.querySelectorAll(".seq-input")].map((i) => i.value).join() === "1,2,3", null, { timeout: 30_000 });
  // Desfazer volta a ordem do arquivo; mover de novo.
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("Control+z");
  await page.waitForFunction(() => [...document.querySelectorAll(".seq-input")].map((i) => i.value).join() === "1,3,2", null, { timeout: 30_000 });
  await field(3).focus();
  await page.keyboard.press("Alt+ArrowLeft");
  await page.getByRole("heading", { name: /ordem escolhida pelo revisor/i }).waitFor({ timeout: 30_000 });
  if (shots) await page.screenshot({ path: `${shots}/desktop-sequencia.png`, fullPage: true });
  const plan = await page.evaluate(async (id) => {
    const headers = { Authorization: `Bearer ${sessionStorage.getItem("qa.token")}` };
    return (await fetch(`/batches/${id}/corrected-plan`, { headers })).json();
  }, batchId);
  const doc = plan.documents[0];
  const moved = doc.pages.filter((p) => p.moved).map((p) => `${p.old_position}->${p.new_position}`).sort();
  if (!doc.reordered || moved.join() !== "2->3,3->2") throw new Error(`lote corrigido sem a ordem manual: ${moved}`);
  console.log("sequência ok:", moved.join(", "));
}
