"""Create an Excel export from current upload, never from fixed fixtures."""
from io import BytesIO
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


def export_excel(graded: pd.DataFrame, stats: dict, key: dict) -> bytes:
    summary = pd.DataFrame([
        ['학생 수', stats['student_count']], ['문항 수', stats['question_count']],
        ['총점', stats['max_score']], ['평균', stats['mean']],
        ['중앙값', stats['median']], ['표준편차(모집단)', stats['std']],
        ['최저점', stats['lowest_score']],
        ['최저점 학생', ', '.join(stats['lowest_students'])],
        ['오답 최다 문항 Top 3', ', '.join(str(q['number']) for q in stats['hardest_questions'])],
    ], columns=['지표','값'])
    item_df = pd.DataFrame(stats['questions']).sort_values('number')
    key_df = pd.DataFrame([{'문항': n, '정답': item.answer, '배점': item.points} for n, item in key.items()])
    result = graded.copy().rename(columns={'student_id':'학생', 'score':'점수', 'correct_count':'정답 개수'})
    # Prevent Excel formula injection via user-provided student IDs.
    result['학생'] = result['학생'].map(lambda v: "'" + str(v) if str(v).startswith(('=', '+', '-', '@')) else str(v))
    for col in result.columns:
        if col.startswith('Q'):
            result[col] = result[col].map({True:'O', False:'X'})
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        summary.to_excel(writer, '전체 성적 요약', index=False)
        result.to_excel(writer, '학생별 채점 결과', index=False)
        item_df.to_excel(writer, '문항별 분석', index=False)
        key_df.to_excel(writer, '추출된 정답표', index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = 'B2'
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.fill = PatternFill('solid', fgColor='17324D')
                cell.font = Font(color='FFFFFF', bold=True)
                cell.alignment = Alignment(horizontal='center')
            for col in sheet.columns:
                values = [len(str(c.value)) for c in list(col)[:250] if c.value is not None]
                sheet.column_dimensions[get_column_letter(col[0].column)].width = min(36, max(12, (max(values) if values else 10) + 2))
    return out.getvalue()
