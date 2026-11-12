# Trava por caixa

Dois conferentes não conferem a mesma caixa em máquinas diferentes. A pasta original é
só leitura, então a trava fica na pasta compartilhada de relatórios (`reports_dir`),
que todas as estações já enxergam ([relatório por caixa](relatorio-por-caixa.md)).
Decisão em [ADR-0019](../adr/0019-trava-por-caixa-na-pasta-compartilhada.md).

Vale no programa desktop, para lote aberto por pasta (`box_locks` em `capabilities`).

## Quais caixas o lote trava

As caixas são as mesmas do relatório por caixa (a primeira pasta do documento, ou o
próprio lote quando o documento está na raiz), calculadas pela lista de arquivos antes
da análise, com a regra do [layout do lote](batch-layout.md):

| Arquivo | Documento | Caixa |
| --- | --- | --- |
| `CX0412/PROC-001/0001.tif` | `CX0412/PROC-001` | `CX0412` |
| `CX0414/processo.pdf` ou TIFF multipágina | `CX0414/processo` | `CX0414` |
| `Processo 1/0001.tif` (página única) | `Processo 1` | o lote |
| `0001.tif` na raiz | o lote | o lote |

Arquivos reservados (`numbering.json`, `manifest.csv`, `index.csv`), ocultos e de
formato não aceito não contam.

## A trava

Um arquivo JSON por caixa, `<reports_dir>/travas/<caixa>.lock`, com:

| Campo | Conteúdo |
| --- | --- |
| `box` | Caixa |
| `reviewer` | Conferente (usuário do Windows) |
| `machine` | Nome do computador |
| `since` | Quando a caixa foi aberta |
| `renewed_at` | Última renovação |
| `batch_id` | Lote desta máquina que travou a caixa |
| `program_version` | Versão do programa |
| `taken_over_from` | Só quando a trava foi assumida: quem tinha, onde, desde quando e última renovação |

Criar usa abertura exclusiva: duas máquinas que tentam ao mesmo tempo não ganham as
duas. Renovar e assumir gravam num temporário e renomeiam.

**Dona da trava:** a mesma pessoa na mesma máquina (nome do computador e usuário, sem
diferenciar maiúsculas). Abrir de novo a própria caixa é permitido, mesmo com a trava
antiga; o lote anterior solta a caixa na renovação seguinte.

## Ciclo

1. **Abrir o lote** (`POST /local-batches`): para cada caixa, lê a trava.
   - Sem trava, ou trava própria: trava e segue.
   - Trava de outra pessoa ou máquina, renovada há até dez minutos: **recusa** com 409 e
     a frase "Caixa 0412 em conferência por fulano, na máquina X, desde 14:05 de
     12/11/2026". Nada é aberto. Trava viva nunca é assumida.
   - Trava de outra pessoa sem renovação há **mais de dez minutos**: abandonada (o
     programa fechou ou caiu). Recusa com 409 e `can_take_over`; abrir de novo com
     `take_over` assume a caixa.
   O lote só abre se todas as caixas puderem ser travadas.
2. **Renovar:** a cada minuto, enquanto o programa está aberto, `renewed_at` de cada
   caixa travada é atualizado. Na abertura do programa, a primeira renovação retoma as
   travas de antes.
3. **Concluir:** quando o relatório da caixa é gerado (todas as sinalizações da caixa
   decididas), a trava é apagada. Folha inserida depois numa caixa concluída
   ([folha inserida](folha-inserida.md)) trava a caixa de novo; travada por outra
   máquina, a inserção é recusada com 409.
4. **Fechar o programa** não apaga a trava: sem renovação, ela vira abandonada em dez
   minutos e pode ser assumida. Ao abrir de novo, a máquina retoma a trava se ninguém a
   assumiu.
5. **Lote apagado** pela retenção ou **análise que falhou**: as travas do lote são soltas.

## Trava assumida

Assumir grava a nova trava com `taken_over_from` e registra o fato em três lugares:

- no histórico da máquina que assumiu (`taken_over`, com a trava anterior);
- em `<reports_dir>/travas/historico.jsonl`, uma linha por fato, visível de qualquer
  máquina;
- na máquina que perdeu a caixa: na renovação seguinte ela vê a trava de outra pessoa,
  marca a caixa como **perdida** (`lost`, com quem assumiu) e mostra o aviso no painel
  do lote. As decisões já tomadas lá continuam no banco daquela máquina.

## Sem pasta compartilhada

Sem `reports_dir`, as travas ficam em `<data_dir>/travas` e valem só neste computador; o
painel do lote avisa. Com a pasta configurada mas fora do ar, a trava também é gravada
aqui; quando a pasta volta, a renovação a passa para a pasta compartilhada (ou marca a
caixa como perdida, se outra máquina a travou nesse meio-tempo).

## Rotas

- `POST /local-batches` com `take_over` opcional; 409 no formato
  `box-locked.schema.json` (cada trava em `box-lock.schema.json`).
- `GET /batches/{batch_id}/box-locks` (`box-locks.schema.json`): cada caixa com estado
  (`held`, `lost`, `released`), onde a trava vale (`shared` ou `local`), quem assumiu
  (quando perdida) e o histórico das travas do lote.

## Limites conhecidos

- O tempo de abandono compara o relógio desta máquina com o horário gravado pela outra.
  As estações sincronizam o relógio com o domínio do Windows; uma diferença grande de
  relógio pode adiantar ou atrasar o abandono.
- A trava evita conferência simultânea; ela não junta as decisões de duas máquinas.
