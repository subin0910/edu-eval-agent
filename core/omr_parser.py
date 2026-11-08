"""Read student responses with strict schema validation."""
import re
from io import BytesIO
import pandas as pd


def parse_omr_excel(contents: bytes, question_numbers: list[int]) -> pd.DataFrame:
    try:
        df = pd.read_excel(BytesIO(contents), sheet_name=0, dtype=object)
    except Exception as e:
        raise ValueError(f'OMR 엑셀 파일을 읽을 수 없습니다: {e}') from e
    df.columns = [str(c).strip() for c in df.columns]
    if df.empty:
        raise ValueError('OMR 데이터가 비어 있습니다.')
    id_col = next((c for c in df if c.lower() in {'학생명', '학생번호', '학생id', 'student_id', 'student', 'id', 'name'}), None)
    if id_col is None:
        raise ValueError('학생 식별 열을 찾을 수 없습니다. 학생명, 학생번호 또는 student_id 열을 사용해 주세요.')
    question_columns = {}
    for col in df.columns:
        match = re.fullmatch(r'(?:Q|문항|문제)\s*0*(\d+)', col, flags=re.I)
        if match:
            n = int(match.group(1))
            if n in question_columns:
                raise ValueError(f'{n}번 문항 열이 중복되었습니다.')
            question_columns[n] = col
    missing = sorted(set(question_numbers) - question_columns.keys())
    excess = sorted(question_columns.keys() - set(question_numbers))
    if missing or excess:
        raise ValueError(f'OMR 열과 정답지 문항이 일치하지 않습니다. 누락: {missing}, 초과: {excess}')
    df = df[[id_col] + [question_columns[n] for n in question_numbers]].copy()
    # Fully empty trailing rows are allowed; answered rows with no ID are not.
    df = df.dropna(how='all')
    missing_id = df[id_col].isna() | df[id_col].astype(str).str.strip().eq('')
    if missing_id.any():
        raise ValueError(f'학생 식별자가 비어 있는 응답 행이 {int(missing_id.sum())}개 있습니다.')
    df.columns = ['student_id'] + [f'Q{n:02d}' for n in question_numbers]
    df['student_id'] = df['student_id'].astype(str).str.strip()
    df = df[df['student_id'].ne('')]
    if df.empty:
        raise ValueError('유효한 학생이 없습니다.')
    if df['student_id'].duplicated().any():
        raise ValueError('학생 식별자가 중복되었습니다: ' + ', '.join(df.loc[df['student_id'].duplicated(), 'student_id'].tolist()[:5]))
    for n in question_numbers:
        col = f'Q{n:02d}'
        normalized = []
        for idx, val in enumerate(df[col].tolist(), start=2):
            if pd.isna(val) or str(val).strip() in ('', '-', '미응답'):
                normalized.append(None)
                continue
            s = str(val).strip()
            circled = '①②③④⑤'
            if s in circled:
                normalized.append(circled.index(s) + 1)
            elif re.fullmatch(r'[1-5](?:\.0)?', s):
                normalized.append(int(float(s)))
            else:
                raise ValueError(f'OMR {idx}행 {col}의 응답이 잘못되었습니다: {val!r} (1~5 또는 공란 허용)')
        df[col] = normalized
    return df.reset_index(drop=True)
