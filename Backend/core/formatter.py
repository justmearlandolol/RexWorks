from __future__ import annotations

import re
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

MAX_INPUT_CHARS = 200_000
MAX_TABLE_COLS = 24
BULLET_GLYPH = "\u2022"

FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([\w+.#/-]*)\s*$")
FENCE_ANY = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([\w+.#/-]*)\s*(.*)$")
HEADING_ATX = re.compile(r"^(\s*)(#{1,6})\s*(.*?)\s*#*\s*$")
HASHTAG_GLUED = re.compile(r"^(\s*)(#{1,6})([^\s#].*)$")
SETEXT_H1 = re.compile(r"^(\s*)=+\s*$")
SETEXT_H2 = re.compile(r"^(\s*)-{2,}\s*$")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$")
LIST_TIGHT = re.compile(r"^(\s*)(\d{1,9})\)([^\s\d].*)$")
TASK_ITEM = re.compile(r"^\[([ xX])\]\s+(.*)$")
HR = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
QUOTE = re.compile(r"^(\s*)>\s?(.*)$")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_LOOSE = re.compile(r"^\s*[^|\n]+\|[^|\n]+\|[^|\n]*$")
BOLD_LEAD = re.compile(r"^(\*\*[^*\n]{1,48}\*\*)(?=[A-Za-z0-9(\"'\u201c])")
CELL_BULLET = re.compile(r"(^|[\s.;:,)])([-*+])\s+")
CODE_HINT = re.compile(
    r"^\s*(?:def \w+\(|async def \w+\(|class \w+|import \w|from \w+ import |#include|"
    r"public (?:class|void|static)|function \w+\(|const \w+\s*=|let \w+\s*=|"
    r"var \w+\s*=|SELECT .+ FROM|\$ |sudo |npm |pnpm |yarn |pip |git |"
    r"docker |curl |echo |cd |mkdir |ls |export \w+=|if \[|for \w+ in )"
)

_PH_OPEN = "\uE000"
_PH_CLOSE = "\uE001"
_PH_RE = re.compile(_PH_OPEN + r"(\d+)" + _PH_CLOSE)
INLINE_CODE = re.compile(r"(`+)([^`\n]+?)\1")
MULTISPACE_EOL = re.compile(r"[ \t]+$", re.MULTILINE)

LANG_ALIASES = {
    "js": "javascript",
    "javascript": "javascript",
    "jsx": "jsx",
    "ts": "typescript",
    "tsx": "tsx",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
    "python3": "python",
    "sh": "bash",
    "shell": "bash",
    "bash": "bash",
    "zsh": "bash",
    "console": "bash",
    "terminal": "bash",
    "yml": "yaml",
    "yaml": "yaml",
    "md": "markdown",
    "markdown": "markdown",
    "html": "html",
    "htm": "html",
    "json": "json",
    "sql": "sql",
    "txt": "text",
    "plain": "text",
    "plaintext": "text",
    "": "text",
}


# --- pipe tables --------------------------------------------------------


def split_row(line: str) -> List[str]:
    """Split a pipe row, honouring ``\\|`` escapes and pipes inside code spans."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]

    cells: List[str] = []
    buffer: List[str] = []
    in_code = False
    escaped = False

    for char in body:
        if escaped:
            buffer.append(char)
            escaped = False
        elif char == "\\":
            buffer.append(char)
            escaped = True
        elif char == "`":
            in_code = not in_code
            buffer.append(char)
        elif char == "|" and not in_code:
            cells.append("".join(buffer).strip())
            buffer = []
        else:
            buffer.append(char)

    cells.append("".join(buffer).strip())

    return cells


def is_separator(line: str) -> bool:
    stripped = line.strip()
    if "-" not in stripped:
        return False
    return bool(re.match(r"^[\s:|-]+$", stripped)) and "|" in stripped


def alignment_of(cell: str) -> str:
    cell = cell.strip()
    left, right = cell.startswith(":"), cell.endswith(":")
    if left and right:
        return "center"
    if right:
        return "right"
    if left:
        return "left"
    return "default"


def normalize_cell(cell: str) -> str:
    """Flatten a bullet list that a model crammed into one cell."""
    text = cell.replace("\\|", "|")
    text = re.sub(r"\s*\n\s*", " ", text)
    # Leading bullet: drop it, the cell position already implies the item.
    text = re.sub(r"^\s*[-*+]\s+", "", text)
    # Trailing bullet leftovers such as `... interaktif. |*`
    if len(text.strip()) > 1:
        text = re.sub(r"\s+[-*+]\s*$", "", text)
    # In-cell bullets: `- a. * b` -> `a. BU item`
    text = CELL_BULLET.sub(lambda m: f"{m.group(1)}{BULLET_GLYPH} ", text)
    text = re.sub(rf"^{re.escape(BULLET_GLYPH)}\s*", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def pad_table(rows: List[List[str]], align: Optional[List[str]] = None) -> List[str]:
    """Render rows as a GFM table whose raw text is visually aligned."""
    if not rows:
        return []

    cols = min(max(len(row) for row in rows), MAX_TABLE_COLS)
    if cols == 0:
        return []

    grid = [[row[i] if i < len(row) else "" for i in range(cols)] for row in rows]

    widths = [3] * cols
    for row in grid:
        for c in range(cols):
            widths[c] = max(widths[c], len(row[c]))

    def render(row: List[str]) -> str:
        return "| " + " | ".join(row[c].ljust(widths[c]) for c in range(cols)) + " |"

    rules = align or []
    separators = []
    for c in range(cols):
        rule = rules[c] if c < len(rules) else "default"
        width = widths[c]
        if rule == "center":
            separators.append(":" + "-" * max(1, width - 2) + ":")
        elif rule == "right":
            separators.append("-" * max(1, width - 1) + ":")
        elif rule == "left":
            separators.append(":" + "-" * max(1, width - 1))
        else:
            separators.append("-" * width)

    out = [render(grid[0]), "| " + " | ".join(separators) + " |"]
    out.extend(render(row) for row in grid[1:])

    return out


def glued_table_cut(line: str, wanted: int) -> int:
    """Index where a prose lead-in stops and the glued table row starts."""
    fallback = -1

    for position in range(1, min(len(line), 600)):
        prose = line[:position].strip()
        segment = line[position:].strip()

        if not prose or not segment:
            continue

        if len(split_row(segment)) != wanted:
            continue

        if segment.startswith("|"):
            return position

        if line[position - 1] in " :;!?)\u2014,.":
            fallback = position

    return fallback


def split_glued_tables(lines: List[str]) -> List[str]:
    """Split a header row that the model glued onto the end of a sentence."""
    out: List[str] = []
    in_fence = False
    index = 0

    while index < len(lines):
        line = lines[index]

        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            index += 1
            continue

        if in_fence or not line.strip() or line.lstrip().startswith("|"):
            out.append(line)
            index += 1
            continue

        following = lines[index + 1] if index + 1 < len(lines) else ""

        if "|" in line and is_separator(following):
            cut = glued_table_cut(line, len(split_row(following)))

            if cut > 0:
                prose = line[:cut].strip()
                row = line[cut:].strip()

                if prose and row.count("|") >= 1:
                    out.append(prose)
                    out.append("")
                    out.append(row)
                    index += 1
                    continue

        out.append(line)
        index += 1

    return out


def promote_tables(lines: List[str]) -> List[str]:
    """Rebuild pipe blocks as padded tables, even without a separator row."""
    out: List[str] = []
    index = 0
    in_fence = False

    while index < len(lines):
        line = lines[index]

        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            index += 1
            continue

        next_is_separator = (
            index + 1 < len(lines) and is_separator(lines[index + 1])
        )
        pipey = bool(
            TABLE_ROW.match(line)
            or TABLE_LOOSE.match(line)
            or (next_is_separator and "|" in line)
        )

        if in_fence or not pipey or (line.count("|") < 2 and not next_is_separator):
            out.append(line)
            index += 1
            continue

        block: List[str] = []
        saw_separator = False

        while index < len(lines):
            candidate = lines[index]

            if FENCE.match(candidate) or not candidate.strip():
                break

            pipes = candidate.count("|")

            upcoming_separator = (
                index + 1 < len(lines) and is_separator(lines[index + 1])
            )

            if (
                TABLE_ROW.match(candidate)
                or TABLE_LOOSE.match(candidate)
                or is_separator(candidate)
            ):
                accept = True
            elif (saw_separator or upcoming_separator) and pipes >= 1:
                # Cramped follow-up row: `**Tujuan**|text`
                accept = True
            else:
                accept = False

            if not accept:
                break

            if is_separator(candidate):
                saw_separator = True

            block.append(candidate)
            index += 1

        rows: List[List[str]] = []
        align: List[str] = []

        for row in block:
            if is_separator(row):
                align = [alignment_of(cell) for cell in split_row(row)]
                continue

            cells = [fix_inline(normalize_cell(cell)) for cell in split_row(row)]

            if any(cells):
                rows.append(cells)

        if not rows:
            out.extend(block)
            continue

        out.extend(pad_table(rows, align))

    return out


# --- blocks -------------------------------------------------------------


def lang_label(raw: str) -> str:
    key = (raw or "").strip().lower().lstrip(".")
    return LANG_ALIASES.get(key, key or "text")


def looks_like_code(lines: Iterable[str]) -> bool:
    return any(CODE_HINT.match(line) for line in lines)


def normalize_fences(lines: List[str]) -> List[str]:
    """Close forgotten fences and repair fences with code on the marker line."""
    out: List[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        match = FENCE.match(line)
        any_fence = FENCE_ANY.match(line)

        if match or (any_fence and any_fence.group(4)):
            markup = (match or any_fence).group(2)
            indent = (match or any_fence).group(1)
            lang = lang_label((match or any_fence).group(3))
            closing = re.compile(rf"^\s*{re.escape(markup[0])}{{{len(markup)},}}\s*$")
            body: List[str] = []

            if match is None:
                body = [any_fence.group(4)]

            index += 1

            while index < len(lines) and not closing.match(lines[index]):
                body.append(lines[index])
                index += 1

            if index < len(lines):
                index += 1

            while body and not body[-1].strip():
                body.pop()

            # Fences always sit at column 0; an indented fence is fragile.
            out.append(f"{markup}{lang}")
            out.extend(line[1:] if indent and line.startswith(indent) else line for line in body)
            out.append(markup)
            continue

        out.append(line)
        index += 1

    return out


def normalize_headings(lines: List[str]) -> List[str]:
    """ATX headings normalised, setext headings promoted, glued ones split."""
    stage: List[str] = []
    in_fence = False

    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
            stage.append(line)
            continue

        if in_fence:
            stage.append(line)
            continue

        glued = HASHTAG_GLUED.match(line)
        if glued:
            stage.append(f"{glued.group(1)}{glued.group(2)} {glued.group(3).strip()}")
            continue

        match = HEADING_ATX.match(line)
        if match and match.group(3).strip():
            stage.append(f"{match.group(2)} {match.group(3).strip()}")
            continue

        stage.append(line)

    out: List[str] = []
    index = 0
    in_fence = False

    while index < len(stage):
        line = stage[index]

        if FENCE.match(line):
            in_fence = not in_fence

        if not in_fence and index + 1 < len(stage) and line.strip():
            nxt = stage[index + 1]
            text = line.strip()
            is_list = bool(LIST_ITEM.match(line)) or text.startswith("|")

            if not is_list:
                if SETEXT_H1.match(nxt):
                    out.append(f"# {text}")
                    index += 2
                    continue
                if SETEXT_H2.match(nxt) and len(text) < 90:
                    out.append(f"## {text}")
                    index += 2
                    continue

        out.append(line)
        index += 1

    return out


def split_glued_leads(lines: List[str]) -> List[str]:
    """Split ``**HALO!**BERIKUT ...`` into a lead line and a paragraph."""
    out: List[str] = []
    in_fence = False

    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue

        if in_fence or not line.strip():
            out.append(line)
            continue

        match = BOLD_LEAD.match(line)
        if not match:
            out.append(line)
            continue

        lead = match.group(1)
        rest = line[len(lead):].strip()
        plain = lead.strip("*").strip()

        if not rest:
            out.append(lead)
            continue

        if not looks_like_lead(plain, rest):
            out.append(f"{lead} {rest}")
            continue

        out.append(lead)
        out.append("")
        out.append(rest)

    return out


def looks_like_lead(plain: str, rest: str) -> bool:
    """True when a bold chunk behaves like a title glued to a paragraph."""
    if not plain:
        return False

    if plain.endswith((":", ",", ";", ".")) and len(plain) <= 60:
        return False

    letters = [char for char in plain if char.isalpha()]
    uppercase_ratio = (
        sum(1 for char in letters if char.isupper()) / len(letters) if letters else 0
    )

    if len(plain) > 24 or uppercase_ratio >= 0.7:
        return len(rest) >= 20

    return False


def normalize_lists(lines: List[str]) -> List[str]:
    """Snap nesting to a 2-space ladder and unify bullet / ordered markers."""
    out: List[str] = []
    stack: List[int] = []
    in_fence = False
    previous_blank = False

    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue

        if in_fence:
            out.append(line)
            continue

        match = LIST_ITEM.match(line)

        if not match:
            tight = LIST_TIGHT.match(line)
            if tight:
                indent, number, content = tight.groups()
                match = None
                width = len(indent.replace("\t", "    "))
                marker = f"{number}."
                content = content.strip()
            else:
                if line.strip():
                    stack = []
                    previous_blank = False
                else:
                    previous_blank = True
                out.append(line)
                continue
        else:
            raw_indent, marker, content = match.groups()
            width = len(raw_indent.replace("\t", "    "))
            marker = "-" if marker in "-*+" else marker[:-1] + "."

        if previous_blank:
            stack = []

        previous_blank = False

        if width == 0:
            stack = [0]
        else:
            while stack and width < stack[-1]:
                stack.pop()
            if not stack or width > stack[-1]:
                stack.append(width)

        level = max(0, len(stack) - 1)
        indent = "  " * level

        task = TASK_ITEM.match(content)
        if task:
            box = "x" if task.group(1).lower() == "x" else " "
            out.append(f"{indent}- [{box}] {task.group(2).strip()}")
        else:
            out.append(f"{indent}{marker} {content.strip()}")

    return out


def block_kind(line: str) -> str:
    """Coarse block classification used for spacing decisions."""
    if FENCE.match(line):
        return "fence"
    if TABLE_ROW.match(line):
        return "table"
    if HEADING_ATX.match(line):
        return "heading"
    if HR.match(line):
        return "hr"
    if QUOTE.match(line):
        return "quote"
    if LIST_ITEM.match(line):
        return "list"
    if not line.strip():
        return "blank"
    return "prose"


GAP_BEFORE = {
    "heading": {"prose", "list", "table", "quote", "fence", "hr"},
    "hr": {"prose", "list", "table", "quote", "fence"},
    "quote": {"prose", "list", "heading", "table"},
    "list": {"prose", "heading", "table", "quote", "fence"},
    "table": {"prose", "heading", "list", "quote", "fence"},
    "fence": {"prose", "list", "table", "heading", "quote"},
    "prose": {"table", "fence"},
}


def split_glued_blocks(lines: List[str]) -> List[str]:
    """Insert the blank line the model forgot between two different blocks."""
    out: List[str] = []
    in_fence = False

    for line in lines:
        kind = block_kind(line)

        if in_fence:
            out.append(line)
            if kind == "fence":
                in_fence = False
            continue

        if kind == "fence":
            in_fence = True
            previous = block_kind(out[-1]) if out else "blank"
            if previous in GAP_BEFORE["fence"]:
                out.append("")
            out.append(line)
            continue

        if kind != "blank" and out and out[-1].strip():
            previous = block_kind(out[-1])
            if previous in GAP_BEFORE.get(kind, set()) or (
                previous == "table" and kind == "prose"
            ):
                if previous != kind:
                    out.append("")

        out.append(line)

    return out


def collapse_blank_lines(lines: List[str]) -> List[str]:
    """At most one blank line outside fences, no leading/trailing blanks."""
    out: List[str] = []
    in_fence = False
    blanks = 0

    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence

        if not line.strip() and not in_fence:
            blanks += 1
            if blanks > 1:
                continue
            out.append("")
            continue

        blanks = 0
        out.append(line.rstrip())

    while out and not out[-1].strip():
        out.pop()

    while out and not out[0].strip():
        out.pop(0)

    return out


# --- inline -------------------------------------------------------------


def protect_code_spans(text: str) -> Tuple[str, List[str]]:
    """Swap inline code for sentinels so emphasis repair cannot touch it."""
    spans: List[str] = []

    def keep(match: re.Match) -> str:
        spans.append(match.group(0))
        return f"{_PH_OPEN}{len(spans) - 1}{_PH_CLOSE}"

    return INLINE_CODE.sub(keep, text), spans


def restore_code_spans(text: str, spans: List[str]) -> str:
    def swap(match: re.Match) -> str:
        index = int(match.group(1))
        return spans[index] if index < len(spans) else match.group(0)

    return _PH_RE.sub(swap, text)


def balance_bold(text: str) -> str:
    """Close a dangling ``**`` so the rest of the line does not glow bold."""
    if text.count("**") % 2 == 0:
        return text

    open_at = -1
    index = 0

    while index < len(text):
        if text.startswith("**", index):
            open_at = -1 if open_at != -1 else index
            index += 2
            continue
        index += 1

    if open_at == -1:
        return text

    # Nothing after the opening marker: drop it, it is pure noise.
    tail = text[open_at + 2:].replace("*", "").strip()

    if not tail:
        return text[:open_at].rstrip()

    return text[:open_at] + "**" + tail + "**"


def fix_inline(text: str) -> str:
    """Repair emphasis padding and stray markers on a single line of prose."""
    if not text:
        return text

    stash, spans = protect_code_spans(text)
    working = balance_bold(stash)

    working = re.sub(r"\*\*[ \t]+([^\n*]+?)[ \t]+\*\*", r"**\1**", working)
    working = re.sub(r"(?<![\w*])\*[ \t]+([^\n*]+?)[ \t]+\*(?![\w*])", r"*\1*", working)
    working = re.sub(r"(?<![\w_])_[ \t]+([^\n_]+?)[ \t]+_(?![\w_])", r"_\1_", working)
    working = working.replace("****", "")
    working = re.sub(r"[ \t]{2,}", " ", working).strip()

    return restore_code_spans(working, spans)


def repair_inline_lines(lines: List[str]) -> List[str]:
    """Apply :func:`fix_inline` to prose lines only (code + tables skipped)."""
    out: List[str] = []
    in_fence = False

    for line in lines:
        if FENCE.match(line):
            out.append(line)
            in_fence = not in_fence
            continue

        if in_fence or not line.strip() or line.lstrip().startswith("|"):
            out.append(line)
            continue

        if HR.match(line):
            out.append(line)
            continue

        prefix = ""
        body = line

        quote = QUOTE.match(line)
        if quote:
            prefix = quote.group(1) + "> "
            body = quote.group(2)

        item = LIST_ITEM.match(body)
        if item:
            prefix = prefix + item.group(1) + item.group(2) + " "
            body = item.group(3)

        fixed = fix_inline(body)
        out.append(prefix + fixed if fixed else prefix.rstrip())

    return out


# --- entry points -------------------------------------------------------


def format_markdown(text: str, max_chars: int = MAX_INPUT_CHARS) -> str:
    """Repair almost-Markdown into clean GitHub-flavoured Markdown."""
    if not text or not str(text).strip():
        return ""

    source = str(text)[:max_chars]
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    source = source.replace("\u00a0", " ").replace("\u202f", " ").replace("\t", "    ")

    lines = [line.rstrip() for line in source.split("\n")]

    lines = normalize_fences(lines)
    lines = split_glued_tables(lines)
    lines = promote_tables(lines)
    lines = normalize_headings(lines)
    lines = split_glued_leads(lines)
    lines = normalize_lists(lines)
    lines = split_glued_blocks(lines)
    lines = collapse_blank_lines(lines)
    lines = repair_inline_lines(lines)

    result = MULTISPACE_EOL.sub("", "\n".join(lines))

    return result.strip() + "\n"


def format_stream(chunks: Iterable[str]) -> Iterator[str]:
    """Repair a full answer assembled from an iterable of streamed chunks."""
    yield format_markdown("".join(chunks))


def stats(before: str, after: str) -> Dict[str, object]:
    """Tiny summary used by logs and tests."""
    lines = after.split("\n")
    return {
        "in_chars": len(before),
        "out_chars": len(after),
        "rows": len([line for line in lines if line.startswith("|")]),
        "headings": len([line for line in lines if line.startswith("#")]),
        "fences": after.count("```") // 2,
        "changed": before.strip() != after.strip(),
    }


__all__ = [
    "format_markdown",
    "format_stream",
    "stats",
    "fix_inline",
    "balance_bold",
    "protect_code_spans",
    "restore_code_spans",
    "normalize_fences",
    "normalize_headings",
    "normalize_lists",
    "normalize_cell",
    "promote_tables",
    "split_glued_tables",
    "glued_table_cut",
    "split_glued_blocks",
    "split_glued_leads",
    "collapse_blank_lines",
    "repair_inline_lines",
    "pad_table",
    "split_row",
    "MAX_INPUT_CHARS",
]
