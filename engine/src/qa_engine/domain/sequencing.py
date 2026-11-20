"""Resolução da numeração de folhas de um documento (``docs/especificacoes/sequencing.md``).

Cada página traz zero ou mais *marcas* (números escritos na região de
numeração), e cada marca traz até três leituras com confiança. Nenhuma leitura
isolada é aceita como verdade: um algoritmo de programação dinâmica escolhe a
sequência vigente mais provável no documento inteiro, premiando incrementos
esperados e penalizando saltos e retrocessos.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

_FOLIO_RE = re.compile(
    r"^\s*(?:fls?\.?\s*)?(?P<n>\d{1,5})"
    r"(?:\s*-?\s*(?P<letter>[A-UW-Za-uw-z]))?"
    r"(?:\s*-?\s*(?P<verso>v(?:erso)?|V))?\s*$"
)


DIGIT_CONFUSIONS: tuple[tuple[str, str], ...] = (
    ("1", "7"),
    ("7", "1"),
    ("2", "9"),
    ("9", "2"),
    ("0", "9"),
    ("9", "0"),
    ("3", "5"),
    ("5", "3"),
    ("7", "9"),
    ("9", "7"),
    ("6", "0"),
    ("0", "6"),
)
"""Trocas de dígito da letra de mão (dígito lido, dígito que pode ser o certo)."""


class NumberingMode(StrEnum):
    """Padrão esperado de numeração no perfil."""

    SIMPLE = "simple"
    """Cada imagem tem um número: 1, 2, 3..."""
    RECTO_VERSO = "recto_verso"
    """Frente e verso: 12, 12v, 13, 13v. O verso costuma vir sem marca."""


class PageNumberingState(StrEnum):
    """Estado da numeração de uma página (``docs/especificacoes/sequencing.md``)."""

    READ = "read"
    INFERRED = "inferred"
    RENUMBERED = "renumbered"
    AMBIGUOUS = "ambiguous"
    ILLEGIBLE = "illegible"
    ABSENT = "absent"


@dataclass(frozen=True, slots=True, order=True)
class Folio:
    """Número de folha: número, letra de intercalação e indicador de verso."""

    number: int
    letter: str = ""
    verso: bool = False

    def __str__(self) -> str:
        """Forma canônica: ``12``, ``12-A``, ``12v``, ``12-Av``."""
        text = str(self.number)
        if self.letter:
            text += f"-{self.letter}"
        if self.verso:
            text += "v"
        return text


@dataclass(frozen=True, slots=True)
class DocumentDoubt:
    """Dúvida sobre a numeração do documento inteiro, que nenhuma página isolada mostra."""

    first: Folio
    last: Folio
    page_id: str
    """Primeira página com valor, onde a sinalização fica."""
    read: str | None = None
    """Dígito comum a todas as folhas que a letra de mão troca (troca sistemática)."""
    alternative: str | None = None
    """Dígito que pode ser o certo."""
    alternative_first: Folio | None = None
    alternative_last: Folio | None = None


def parse_folio(text: str) -> Folio | None:
    """Interpreta uma leitura (``"fls. 12"``, ``"12-v"``, ``"12-A"``) ou retorna ``None``."""
    match = _FOLIO_RE.match(text)
    if match is None:
        return None
    letter = (match.group("letter") or "").upper()
    return Folio(int(match.group("n")), letter, match.group("verso") is not None)


def successor(folio: Folio, mode: NumberingMode) -> Folio:
    """Folha esperada logo depois de ``folio``."""
    if mode is NumberingMode.RECTO_VERSO and not folio.verso:
        return Folio(folio.number, folio.letter, True)
    return Folio(folio.number + 1)


def _ordinal(folio: Folio, mode: NumberingMode) -> int:
    if mode is NumberingMode.RECTO_VERSO:
        return 2 * folio.number + (1 if folio.verso else 0)
    return folio.number


def missing_between(prev: Folio, cur: Folio, mode: NumberingMode) -> list[Folio]:
    """Folhas que deveriam existir entre ``prev`` e ``cur`` (vazio se não há lacuna)."""
    if cur <= prev or cur == successor(prev, mode) or _is_intercalation(prev, cur, mode):
        return []
    missing: list[Folio] = []
    nxt = successor(prev, mode)
    while _ordinal(nxt, mode) < _ordinal(cur, mode) and len(missing) < 1000:
        missing.append(nxt)
        nxt = successor(nxt, mode)
    return missing


def gap_size(prev: Folio, cur: Folio, mode: NumberingMode) -> int:
    """Quantas folhas faltam entre ``prev`` e ``cur``: ``len(missing_between(...))`` sem a lista.

    O sucessor de qualquer folha fica uma posição adiante na ordem (``_ordinal``), então a
    lacuna é a distância menos um, com o mesmo teto de 1000 de :func:`missing_between`.
    """
    if cur <= prev or cur == successor(prev, mode) or _is_intercalation(prev, cur, mode):
        return 0
    return min(max(_ordinal(cur, mode) - _ordinal(prev, mode) - 1, 0), 1000)


def _is_intercalation(prev: Folio, cur: Folio, mode: NumberingMode) -> bool:
    """``12`` → ``12-A`` ou ``12-A`` → ``12-B`` (folhas intercaladas são legítimas)."""
    if cur.number != prev.number or cur.verso or not cur.letter:
        return False
    if mode is NumberingMode.RECTO_VERSO and not prev.verso:
        return False
    return cur.letter > prev.letter


@dataclass(frozen=True, slots=True)
class Reading:
    """Uma leitura possível de uma marca."""

    text: str
    confidence: float


@dataclass(frozen=True, slots=True)
class Mark:
    """Uma marca de numeração encontrada na região da página."""

    readings: tuple[Reading, ...]
    struck: bool = False

    @property
    def top(self) -> Reading | None:
        """Leitura de maior confiança."""
        return max(self.readings, key=lambda r: r.confidence, default=None)


@dataclass(frozen=True, slots=True)
class PageCandidates:
    """Entrada do resolvedor para uma página."""

    page_id: str
    marks: tuple[Mark, ...] = ()


@dataclass(frozen=True, slots=True)
class SequenceParams:
    """Pesos e limiares do resolvedor (``docs/especificacoes/sequencing.md``)."""

    mode: NumberingMode = NumberingMode.SIMPLE
    min_confidence: float = 0.5
    high_confidence: float = 0.85
    w_read: float = 4.0
    w_step: float = 2.0
    w_intercalation: float = 1.0
    w_gap: float = 1.0
    w_gap_max: float = 1.5
    """Teto da penalidade de um salto: uma leitura confiável vence a inferência mesmo
    numa lacuna grande no fim do documento, onde nenhuma página seguinte a confirma."""
    w_back: float = 4.0
    w_repeat: float = 1.0
    """Numeração repetida é penalizada menos que retrocesso: duplicata ou defeito de origem."""
    w_infer: float = 1.0
    confusions: tuple[tuple[str, str], ...] = DIGIT_CONFUSIONS
    """Trocas de dígito do leitor: a checagem de documento procura a troca sistemática."""
    max_first_folio: int | None = None
    """Documento cuja numeração começa depois disto vai para revisão (``None``: desligado)."""
    max_gap_sheets: int = 50
    """Lacuna maior que isto é leitura de numeração duvidosa, não folha faltando. Não muda
    o resolvedor: é lida pelo detector ``sequence`` (``docs/especificacoes/sequencing.md``)."""
    min_implausible_gap: int = 10
    """Lacuna maior que o documento só é implausível a partir deste tamanho (documento curto
    com algumas folhas faltando é comum). Também só é lida pelo detector ``sequence``."""


@dataclass(frozen=True, slots=True)
class PageNumbering:
    """Numeração resolvida de uma página."""

    page_id: str
    state: PageNumberingState
    value: Folio | None
    confidence: float
    previous: tuple[str, ...] = ()
    """Números riscados (numeração anterior), quando há renumeração."""

    @property
    def needs_review(self) -> bool:
        """Ambíguo, ilegível e inferido vão para o revisor."""
        return self.state in {
            PageNumberingState.AMBIGUOUS,
            PageNumberingState.ILLEGIBLE,
            PageNumberingState.INFERRED,
        }


@dataclass(frozen=True, slots=True)
class Gap:
    """Lacuna na numeração entre duas posições consecutivas."""

    after_page_id: str
    before_page_id: str
    missing: tuple[Folio, ...]
    confirmed: bool
    """Verdadeiro quando as leituras dos dois lados são confiáveis."""


@dataclass(frozen=True, slots=True)
class SequenceResult:
    """Resultado da resolução de um documento."""

    pages: tuple[PageNumbering, ...]
    order: tuple[str, ...]
    """Ordem proposta das páginas (igual à original quando não há reordenação)."""
    reordered: bool
    gaps: tuple[Gap, ...] = ()
    repeated: tuple[str, ...] = field(default=())
    """Páginas cuja numeração repete a anterior (possível defeito de origem)."""

    @property
    def has_numbering(self) -> bool:
        """Falso quando nenhuma página tem marca: completude não verificável pela numeração."""
        return any(p.state is not PageNumberingState.ABSENT for p in self.pages)


@dataclass(frozen=True, slots=True)
class _Option:
    value: Folio
    confidence: float
    from_reading: bool


def _options(page: PageCandidates) -> list[_Option]:
    options: list[_Option] = []
    for mark in page.marks:
        if mark.struck:
            continue
        for reading in mark.readings:
            folio = parse_folio(reading.text)
            if folio is not None:
                options.append(_Option(folio, reading.confidence, True))
    return options


def _transition(prev: Folio | None, cur: Folio, p: SequenceParams) -> float:
    if prev is None:
        return 0.0
    if cur == successor(prev, p.mode):
        return p.w_step
    if _is_intercalation(prev, cur, p.mode):
        return p.w_intercalation
    if cur > prev:
        return -min(p.w_gap * gap_size(prev, cur, p.mode), p.w_gap_max)
    if cur == prev:
        return -p.w_repeat
    return -p.w_back


def _confident_value(page: PageCandidates, p: SequenceParams) -> Folio | None:
    live = [m for m in page.marks if not m.struck]
    if len(live) != 1:
        return None
    top = live[0].top
    if top is None or top.confidence < p.high_confidence:
        return None
    return parse_folio(top.text)


def propose_order(pages: Sequence[PageCandidates], p: SequenceParams) -> list[int]:
    """Ordem proposta pela numeração confiável.

    Cada página com leitura confiável abre um bloco; as páginas seguintes sem
    leitura confiável (versos, por exemplo) acompanham o bloco. Os blocos são
    ordenados de forma estável pelo número.
    """
    blocks: list[tuple[Folio | None, list[int]]] = []
    for index, page in enumerate(pages):
        value = _confident_value(page, p)
        if value is not None or not blocks:
            blocks.append((value, [index]))
        else:
            blocks[-1][1].append(index)
    keyed = [b for b in blocks if b[0] is not None]
    if len(keyed) < 2:
        return list(range(len(pages)))
    head = [] if blocks[0][0] is not None else blocks[0][1]
    ordered = sorted(keyed, key=lambda b: b[0] or Folio(0))
    return head + [i for _, idx in ordered for i in idx]


def _viterbi(pages: Sequence[PageCandidates], p: SequenceParams) -> list[_Option | None]:
    # Estado: valor da folha vigente (ou None enquanto nada é conhecido).
    layers: list[dict[Folio | None, tuple[float, Folio | None, _Option | None]]] = []
    current: dict[Folio | None, tuple[float, Folio | None, _Option | None]] = {}
    for index, page in enumerate(pages):
        options = _options(page)
        previous = layers[-1] if layers else {None: (0.0, None, None)}
        current = {}

        def offer(
            state: Folio | None,
            score: float,
            back: Folio | None,
            option: _Option | None,
            table: dict[Folio | None, tuple[float, Folio | None, _Option | None]],
        ) -> None:
            best = table.get(state)
            if best is None or score > best[0]:
                table[state] = (score, back, option)

        infer_cost = 0.0 if not page.marks else -p.w_infer
        for prev_state, (prev_score, _, _) in previous.items():
            for option in options:
                score = prev_score + p.w_read * option.confidence
                score += _transition(prev_state, option.value, p)
                offer(option.value, score, prev_state, option, current)
            if prev_state is None:
                offer(None, prev_score, None, None, current)
            else:
                guess = successor(prev_state, p.mode)
                score = prev_score + p.w_step + infer_cost
                offer(guess, score, prev_state, _Option(guess, 0.0, False), current)
        del index
        layers.append(current)

    if not layers:
        return []
    state: Folio | None = max(layers[-1].items(), key=lambda kv: (kv[1][0], str(kv[0])))[0]
    chosen: list[_Option | None] = []
    for layer in reversed(layers):
        _, back, picked = layer[state]
        chosen.append(picked)
        state = back
    chosen.reverse()
    return chosen


def _classify(page: PageCandidates, option: _Option | None, p: SequenceParams) -> PageNumbering:
    live = [m for m in page.marks if not m.struck]
    struck = [m for m in page.marks if m.struck]
    previous = tuple(m.top.text for m in struck if m.top is not None)
    value = option.value if option else None
    confident_tops = {
        top.text for m in live if (top := m.top) is not None and top.confidence >= p.min_confidence
    }
    if not page.marks:
        return PageNumbering(page.page_id, PageNumberingState.ABSENT, value, 0.0)
    if len(confident_tops) >= 2:
        return PageNumbering(page.page_id, PageNumberingState.AMBIGUOUS, value, 0.0, previous)
    if not confident_tops:
        return PageNumbering(page.page_id, PageNumberingState.ILLEGIBLE, value, 0.0, previous)
    if option is None or not option.from_reading:
        return PageNumbering(page.page_id, PageNumberingState.INFERRED, value, 0.0, previous)
    top = live[0].top if len(live) == 1 else None
    if top is not None and parse_folio(top.text) != option.value:
        return PageNumbering(
            page.page_id, PageNumberingState.INFERRED, value, option.confidence, previous
        )
    state = PageNumberingState.RENUMBERED if struck else PageNumberingState.READ
    return PageNumbering(page.page_id, state, value, option.confidence, previous)


def document_doubt(result: SequenceResult, params: SequenceParams) -> DocumentDoubt | None:
    """Checagem de documento: a numeração inteira pode estar errada do mesmo jeito.

    Um reconhecedor que erra sempre o mesmo dígito (o 2 com laço lido como 9) produz uma
    sequência coerente, e o resolvedor a aceita. Isso só passa calado quando o dígito
    trocado é igual em todas as folhas: trocar um dígito comum a todas soma a mesma
    constante a cada folha, e a sequência alternativa fecha tão bem quanto a lida. Há
    dúvida quando todas as folhas com valor têm o mesmo dígito numa posição e a tabela de
    trocas diz que ele pode ser um dígito **menor** (folha baixa é mais comum que alta:
    todo documento tem fls. 1, poucos têm fls. 1990). Opcionalmente, também quando a
    numeração começa depois de ``max_first_folio``.

    Args:
        result: resolução do documento.
        params: parâmetros do resolvedor (``confusions`` e ``max_first_folio``).

    Returns:
        A dúvida, com a troca e a numeração alternativa quando houver, ou ``None``.
    """
    by_id = {p.page_id: p for p in result.pages}
    valued = [by_id[pid] for pid in result.order if by_id[pid].value is not None]
    if not valued:
        return None
    folios = [p.value for p in valued if p.value is not None]
    first, last = min(folios), max(folios)
    page_id = valued[0].page_id
    numbers = [str(f.number) for f in folios]
    for k in range(min(len(n) for n in numbers)):  # da direita para a esquerda
        digits = {n[-1 - k] for n in numbers}
        if len(digits) != 1:
            continue
        digit = digits.pop()
        leading = any(len(n) == k + 1 for n in numbers)
        for read, alternative in params.confusions:
            if read != digit or alternative >= digit or (leading and alternative == "0"):
                continue
            delta = (int(alternative) - int(digit)) * 10**k
            return DocumentDoubt(
                first,
                last,
                page_id,
                digit,
                alternative,
                Folio(first.number + delta, first.letter, first.verso),
                Folio(last.number + delta, last.letter, last.verso),
            )
    if params.max_first_folio is not None and first.number > params.max_first_folio:
        return DocumentDoubt(first, last, page_id)
    return None


def resolve(pages: Sequence[PageCandidates], params: SequenceParams) -> SequenceResult:
    """Resolve a numeração do documento inteiro.

    Args:
        pages: candidatos por página, na ordem do arquivo.
        params: pesos, limiares e modo de numeração do perfil.

    Returns:
        Estado e valor de cada página, ordem proposta, lacunas e repetições.
    """
    order = propose_order(pages, params)
    ordered = [pages[i] for i in order]
    chosen = _viterbi(ordered, params)
    result = [_classify(page, opt, params) for page, opt in zip(ordered, chosen, strict=True)]

    gaps: list[Gap] = []
    repeated: list[str] = []
    prev: PageNumbering | None = None
    anchored = False  # a última página com valor foi sustentada por leitura confiável?
    for cur in result:
        if cur.value is None:
            continue
        confident = (
            cur.state in {PageNumberingState.READ, PageNumberingState.RENUMBERED}
            and cur.confidence >= params.high_confidence
        )
        if prev is not None and prev.value is not None:
            if cur.value == prev.value:
                repeated.append(cur.page_id)
            missing = missing_between(prev.value, cur.value, params.mode)
            if missing:
                gaps.append(Gap(prev.page_id, cur.page_id, tuple(missing), anchored and confident))
        if confident:
            anchored = True
        elif not (
            cur.state is PageNumberingState.ABSENT and params.mode is NumberingMode.RECTO_VERSO
        ):
            # Verso sem marca no modo frente e verso é esperado e mantém a âncora.
            anchored = False
        prev = cur
    return SequenceResult(
        pages=tuple(result),
        order=tuple(p.page_id for p in ordered),
        reordered=order != list(range(len(pages))),
        gaps=tuple(gaps),
        repeated=tuple(repeated),
    )
