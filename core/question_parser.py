"""Conservative, column-aware source-page crop for model-assisted question creation."""
import re
import fitz


def locate_question(pdf_bytes: bytes, number: int) -> dict:
    if not pdf_bytes.startswith(b'%PDF'):
        raise ValueError('문제지 파일은 PDF여야 합니다.')
    if number <= 0:
        raise ValueError('문항 번호는 양수여야 합니다.')
    marker = re.compile(rf'(?<!\d){number}\s*[.．](?!\d)')
    next_marker = re.compile(r'(?<!\d)(\d{1,3})\s*[.．](?!\d)')
    with fitz.open(stream=pdf_bytes, filetype='pdf') as document:
        for page_idx, page in enumerate(document):
            width = page.rect.width
            blocks = page.get_text('blocks')
            candidates = []
            for block in blocks:
                text = str(block[4]).strip()
                # A question starts at the beginning of a text block, not at a random number in the passage.
                if re.match(rf'^\s*{number}\s*[.．](?!\d)', text):
                    candidates.append(block)
            if not candidates:
                # PDF extraction can put multiple lines in one block, so use search_for conservatively.
                candidates = [tuple(r) + ('', 0, 0) for r in page.search_for(f'{number}.')]
            if not candidates:
                continue
            start = min(candidates, key=lambda b: (b[1], b[0]))
            x = float(start[0]); y = float(start[1]); middle = width / 2
            # Most exam pages are split in two columns; only crop the relevant column.
            left, right = (middle, width) if x >= middle else (0, middle)
            # Shared passages can precede multiple numbered questions ([41~42]).
            shared_range = None
            for block in blocks:
                if not (left <= block[0] < right) or block[1] >= y:
                    continue
                group = re.search(r'\[(\d{1,3})\s*[～~\-]\s*(\d{1,3})\]', str(block[4]))
                if group and y - float(block[1]) > 170 and int(group.group(1)) <= number <= int(group.group(2)):
                    shared_range = (int(group.group(1)), int(group.group(2)))
                    y = min(y, float(block[1]))
            bottom = page.rect.height
            # Find the next numbered question *below* this one in the same column.
            for block in blocks:
                if block[1] <= y + 5 or not (left <= block[0] < right):
                    continue
                text = str(block[4]).strip()
                m = re.match(r'^\s*(\d{1,3})\s*[.．](?!\d)', text)
                if m and int(m.group(1)) != number and not (shared_range and shared_range[0] <= int(m.group(1)) <= shared_range[1]):
                    bottom = min(bottom, float(block[1]) - 7)
            if bottom <= y + 50:
                bottom = page.rect.height
            crop = fitz.Rect(left, max(0, y - 14), right, min(page.rect.height, bottom))
            # Very long or shared-passage questions may extend outside the crop: return the crop AND the page.
            pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), clip=crop, alpha=False)
            cropped_text = page.get_text('text', clip=crop)
            return {
                'page': page_idx + 1,
                'text': cropped_text[:12000],
                'png_bytes': pix.tobytes('png'),
                'crop': (round(crop.x0), round(crop.y0), round(crop.x1), round(crop.y1)),
            }
    raise ValueError(f'{number}번 문항을 문제지에서 찾지 못했습니다. 원본 PDF를 확인해 주세요.')
