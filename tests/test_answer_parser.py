import fitz
from core.answer_parser import parse_answer_pdf

def test_simple_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50,100),'1 2 2   3 4 3')
    page.insert_text((50,120),'2 3 2   4 1 2')
    key = parse_answer_pdf(doc.tobytes())
    assert len(key)==4
    assert key[3].answer == 4
    assert key[3].points == 3
