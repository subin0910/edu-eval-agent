"""Extract per-question answer and points from uploaded answer PDFs. No hardcoded key."""
import re
from dataclasses import dataclass
from io import BytesIO
import fitz

CIRCLED = {c: i for i, c in enumerate('①②③④⑤⑥⑦⑧⑨⑩', 1)}

@dataclass(frozen=True)
class KeyItem:
    number: int
    answer: int
    points: float


def _tokens(line: str):
    line = line.replace('｜', ' ').replace('|', ' ')
    line = re.sub(r'(?<=\d)[\u2460-\u2469]', lambda m: ' ' + m.group(), line)
    line = re.sub(r'[\u2460-\u2469](?=\d)', lambda m: m.group() + ' ', line)
    return line.split()


def _answer(value: str):
    value = value.strip('()[]{}.,')
    if value in CIRCLED:
        return CIRCLED[value]
    if value.isdigit() and 1 <= int(value) <= 5:
        return int(value)
    return None


def _extract_lines(page):
    # Spatial grouping preserves the PDF table's parallel columns.
    words = page.get_text('words', sort=True)
    rows = []
    for x0, y0, x1, y1, word, *_ in sorted(words, key=lambda w: (round(w[1] / 3), w[0])):
        mid = (y0 + y1) / 2
        group = next((row for row in rows if abs(row[0] - mid) <= 3.5), None)
        if group is None:
            rows.append([mid, [(x0, word)]])
        else:
            group[1].append((x0, word))
    return [' '.join(v for _, v in sorted(items)) for _, items in sorted(rows, key=lambda r:r[0])]


def parse_answer_pdf(pdf_bytes: bytes) -> dict[int, KeyItem]:
    if not pdf_bytes or not pdf_bytes.startswith(b'%PDF'):
        raise ValueError('정답지는 PDF 형식이어야 합니다.')
    extracted = {}
    duplicates = set()
    with fitz.open(stream=pdf_bytes, filetype='pdf') as pdf:
        for page in pdf:
            for line in _extract_lines(page):
                values = _tokens(line)
                # Each table row is one or more triples: number / answer / score.
                i = 0
                while i + 2 < len(values):
                    n, a, p = values[i:i+3]
                    parsed_answer = _answer(a)
                    valid = n.isdigit() and parsed_answer is not None and bool(re.fullmatch(r'\d+(?:\.\d+)?', p))
                    if valid:
                        number, points = int(n), float(p)
                        if number > 0 and 0 < points <= 100:
                            item = KeyItem(number, parsed_answer, points)
                            if number in extracted:
                                duplicates.add(number)
                            extracted[number] = item
                            i += 3
                            continue
                    i += 1
    if duplicates:
        raise ValueError(f'정답표에서 중복된 문항 번호가 발견되었습니다: {sorted(duplicates)}')
    if not extracted:
        raise ValueError('PDF에서 문항 번호·정답·배점 조합을 추출하지 못했습니다. 스캔본이거나 지원하지 않는 표 형식일 수 있습니다.')
    numbers = sorted(extracted)
    expected = list(range(1, numbers[-1] + 1))
    if numbers != expected:
        missing = sorted(set(expected) - set(numbers))
        raise ValueError(f'정답표에 누락된 문항이 있습니다: {missing}. 원본 PDF를 확인해 주세요.')
    return dict(sorted(extracted.items()))
