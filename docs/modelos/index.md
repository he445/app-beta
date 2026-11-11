# Modelos

Esta pasta guarda a ficha (*model card*) de cada modelo de aprendizado de máquina que
vai dentro do programa.

Hoje o motor **não embarca nenhum modelo**: todas as regras usam visão computacional
clássica (OpenCV), e a numeração de folhas vem de um arquivo ao lado do lote.

Quando um modelo entrar, a ficha dele traz, nesta ordem:

| Campo | Conteúdo |
| --- | --- |
| Origem | Quem publicou e de onde o arquivo foi baixado |
| Versão e SHA-256 | O que identifica exatamente o arquivo embarcado |
| Licença | Precisa ser permissiva ([licenças](../seguranca-e-privacidade/licencas.md)) |
| Para que é usado | Qual regra ou etapa depende dele |
| Entrada e saída | Tamanho, normalização e o que cada saída significa |
| Métricas medidas | Na base sintética e, quando houver, em documentos reais |
| Limitações conhecidas | Onde ele erra e o que o sistema faz nesse caso |
