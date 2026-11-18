# 0022: Checagem de documento na resolução da sequência

Status: aceito · Data: 2026-11-18 · Decisores: Everton Ferreira

## Contexto

No relatório de testes de 18/11/2026, seis datas do mesmo livro, 1920 a 1925, foram lidas
como 1990 a 1995 com confiança de 0,94 a 1,00. Com `w_read` = 4 e leituras acima de
`high_confidence`, o erro consistente do reconhecedor vence a inferência: o resolvedor
aceita a sequência sem sinalizar nada. Nenhuma página isolada mostra o problema; só o
documento inteiro.

## Opções consideradas

1. Troca sistemática: dúvida quando todas as folhas têm um dígito em comum que a tabela
   de trocas diz poder ser outro.
2. Salto: dúvida quando a numeração começa longe de fls. 1.
3. Rebaixar a confiança do reconhecedor (calibração) até a leitura deixar de vencer.

## Decisão

Opção 1 ligada, só para troca por um dígito **menor**, e opção 2 disponível no perfil
(`numbering.max_first_folio`), desligada por padrão. Trocar um dígito comum a todas as
folhas soma a mesma constante a cada uma, então a sequência alternativa fecha tão bem
quanto a lida: a evidência não decide, e o que desempata é que folha baixa é mais comum
que alta. Documento que começa em fls. 1 nunca tem dígito comum a todas as folhas, então a
checagem não toca no caso mais comum. A opção 2 pega erro fora da tabela, mas sinaliza
todo volume que continua outro e todo trecho de documento (os casos de conformidade já
começam em fls. 11 a 16); fica para a operação ligar se todo documento começar perto de
fls. 1. A opção 3 não resolve sozinha: com confiança 1,00 no erro, só uma calibração muito
agressiva tiraria a leitura do topo.

## Consequências

- O documento em dúvida ganha `numbering_review` (alto) na primeira página com valor, com
  a numeração alternativa na mensagem ("fls. 1990 a 1995 também fecha como fls. 1920 a
  1925").
- Volume que continua outro com todas as folhas na mesma centena e dígito trocável por
  um menor (fls. 901 a 950) vai para revisão uma vez.
- Caso de conformidade `erro-sistematico-de-digito`; regras de sequência na versão 1.2.0;
  contrato do perfil ganha `numbering.max_first_folio` (opcional).
