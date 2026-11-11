# Visão geral

## O problema

A operação de digitalização tem meta de cerca de 1 milhão de páginas por mês, perto de
45 mil por dia útil. O controle de qualidade é feito por garantidores e conferentes, que
abrem página por página. Conferir tudo à mão exigiria cerca de 30 páginas por minuto por
pessoa, o dia inteiro.

## O que o sistema faz

Recebe um lote digitalizado e, para cada página, documento e lote:

- detecta defeitos de imagem (sem nitidez, torta, em branco, bordas pretas, exposição,
  resolução baixa, arquivo corrompido, duplicada), de sequência (página faltando, fora de
  ordem, numeração duvidosa) e de completude;
- propõe uma correção para cada defeito, aplicada sempre numa cópia, nunca no original;
- extrai os metadados do Decreto 10.278/2020 e os técnicos (data, equipamento, estação,
  hash, resolução, modo de cor);
- entrega uma fila de revisão só com o que foi sinalizado, um "Corrigir tudo" para o que é
  automático e seguro, o lote corrigido e o relatório do lote com a ordem de retrabalho.

A meta é reduzir em pelo menos metade as páginas que exigem olho humano sem deixar passar
defeito crítico. As metas medidas e os resultados na base sintética estão em
[Demonstração](../guias/demonstracao.md) e em [Testes](../testes/index.md).

## Como é usado

O motor de análise é um serviço com uma API definida em contrato
([referência](../referencia/api.md)). A interface web, a linha de comando e qualquer
sistema futuro falam com ele só por esse contrato
([arquitetura](../arquitetura/index.md)).

| Modo | Onde roda | Como o lote entra | Para quê |
| --- | --- | --- | --- |
| Demonstração em nuvem | Motor num contêiner, servindo também a interface | Lote de demonstração no servidor ou envio pelo navegador | Apresentações, só com documentos sintéticos |
| Linha de comando | Qualquer máquina com Python | Pasta local | Medições, testes e automação |

## Escopo e limites

| Faz | Não faz |
| --- | --- |
| Analisa TIFF, JPEG, PNG e PDF | Não se integra ao software de captura da digitalizadora |
| Defeitos de imagem, sequência e completude | Não gera PDF/A nem assina com ICP-Brasil |
| Correções automáticas na cópia e lote corrigido em TIFF sem perda | Não "melhora" página ilegível: resolução interpolada, nitidez artificial e preenchimento de área cortada são [correções proibidas](../especificacoes/corrections.md) |
| Metadados do Decreto 10.278/2020, com fonte e confiança | Não classifica tipo documental |
| Revisão por teclado, relatório e ordem de retrabalho | Não substitui a decisão humana: [o humano decide](principios.md) |

Limite honesto: os resultados medidos vêm de uma base sintética, em que os defeitos são
mais limpos que os reais. Eles são um teto; só um lote real já conferido decide.
A numeração de folhas hoje vem de um arquivo ao lado do lote (`numbering.json`), não da
imagem ([sequência](../especificacoes/sequencing.md)).
