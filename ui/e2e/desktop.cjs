// Programa desktop sem janela (QA --headless), interface aberta pelo link de acesso de uso
// único: sem tela de entrada, "Abrir lote" por caminho, análise e "Salvar na pasta de saída".
// Uso: node e2e/desktop.cjs <link de acesso> <pasta do lote> [pasta de capturas]
const { chromium } = require("playwright");

(async () => {
  const [link, folder, shots] = process.argv.slice(2);
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

  await page.getByLabel("Pasta do lote").fill(folder);
  await page.getByRole("button", { name: "Analisar lote" }).click();
  await page.waitForURL(/#\/batches\/[0-9a-f-]+$/, { timeout: 30_000 });
  await page.getByRole("link", { name: "Relatório" }).waitFor({ timeout: 120_000 });
  await page.getByText(/Veredito|Aprovado|Reprovado/).first().waitFor({ timeout: 120_000 });
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
  await browser.close();
  console.log("fluxo desktop ok");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
