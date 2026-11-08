import pandas as pd
from core.answer_parser import KeyItem
from core.grading import grade_students
from core.statistics import calculate_statistics

def test_new_students_and_questions():
    key = {1:KeyItem(1,2,2),2:KeyItem(2,5,3)}
    data = pd.DataFrame({'student_id':['A','B','C'], 'Q01':[2,1,2], 'Q02':[5,5,None]})
    result = grade_students(data,key)
    stats = calculate_statistics(result,key)
    assert result['score'].tolist() == [5,3,2]
    assert stats['student_count'] == 3
    assert stats['median'] == 3
    assert stats['hardest_questions'][0]['number'] == 1
