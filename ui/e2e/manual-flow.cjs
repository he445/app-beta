// Segue o manual do conferente (docs/operacao/manual-do-conferente.md) na caixa de
// exemplo do pacote (samples\lote-exemplo): se este roteiro passa, quem nunca viu o
// programa consegue conferir a caixa só com o manual. Mudou a tela? Mude o manual junto.

/** O que o manual manda fazer com cada sinalização da caixa de exemplo. */
const DECISION_BY_RULE = {
  "Inclinação": "c", // Corrigir: o programa endireita a cópia
  "Página em branco": "c", // Corrigir: a folha vazia sai do lote corrigido
  "Desfoque": "r", // Retrabalho: precisa digitalizar de novo
  "Página faltando": "r", // Retrabalho: a folha 3 tem que ser procurada
};

async function conferirCaixaDeExemplo(page, folder, shots) {
  // Passo 1: abrir a caixa.
  await page.getByRole("link", { name: "QA de Digitalização" }).click();
  await page.getByLabel("Pasta do lote").fill(folder);
  await page.getByRole("button", { name: "Analisar lote" }).click();
  await page.waitForURL(/#\/batches\/[0-9a-f-]+$/, { timeout: 30_000 });
  const review = page.getByRole("link", { name: /Revisar \d+ pendente/ });
  await review.waitFor({ timeout: 120_000 });

  // Passo 2: a lista de atalhos (tecla ?).
  await page.keyboard.press("?");
  await page.getByRole("dialog", { name: "Atalhos de teclado" }).waitFor({ timeout: 10_000 });
  if (shots) await page.screenshot({ path: `${shots}/manual-atalhos.png` });
  await page.keyboard.press("Escape");
  await page.getByRole("dialog", { name: "Atalhos de teclado" }).waitFor({ state: "detached", timeout: 10_000 });

  // Passo 3: decidir cada sinalização na Revisão.
  await review.click();
  const progress = page.locator(".queue-progress strong");
  await progress.waitFor({ timeout: 30_000 });
  const seen = [];
  for (let i = 0; i < 30; i++) {
    const text = (await page.locator(".queue-progress").textContent()) ?? "";
    const [, done, total] = /(\d+)\s*de\s*(\d+)\s*decididas/.exec(text) ?? [];
    if (done === total) break;
    const rule = ((await page.locator(".panel h2.inline").first().textContent()) ?? "").trim();
    const key = DECISION_BY_RULE[rule] ?? "a"; // o resto: olhar a página e aprovar se estiver boa
    seen.push(rule);
    await page.keyboard.press(key);
    await page.waitForFunction(
      (before) => document.querySelector(".queue-progress strong")?.textContent !== before,
      done,
      { timeout: 60_000 },
    );
  }
  for (const rule of Object.keys(DECISION_BY_RULE)) {
    if (!seen.includes(rule)) throw new Error(`a caixa de exemplo deveria ter "${rule}"; viu: ${seen.join(", ")}`);
  }
  if (shots) await page.screenshot({ path: `${shots}/manual-revisao.png` });

  // Passo 4: salvar o lote corrigido e conferir o relatório da caixa.
  await page.getByRole("link", { name: "Relatório", exact: true }).click();
  const save = page.getByRole("button", { name: "Salvar na pasta de saída" });
  await save.waitFor({ timeout: 30_000 });
  await page.waitForFunction(() => {
    const b = [...document.querySelectorAll("button")].find((x) => x.textContent === "Salvar na pasta de saída");
    return b && !b.disabled;
  }, null, { timeout: 30_000 });
  await save.click();
  await page.getByText(/Gravado em/).waitFor({ timeout: 120_000 });
  const row = page.locator("tr", { hasText: "CX001" }).first();
  await row.waitFor({ timeout: 30_000 });
  const cells = (await row.locator("td").allTextContents()).map((t) => t.trim());
  // Caixa, Versão, Estado, Processos, Faltando, Ilegíveis
  if (cells[4] !== "1" || cells[5] !== "1") {
    throw new Error(`relatório da caixa CX001 deveria ter 1 faltando e 1 ilegível: ${cells.join(" | ")}`);
  }
  if (shots) await page.screenshot({ path: `${shots}/manual-relatorio.png`, fullPage: true });
  console.log(`manual ok: ${seen.length} decisões (${seen.join(", ")}); caixa CX001 com 1 faltando e 1 ilegível`);
}

module.exports = { conferirCaixaDeExemplo };
