import pandas as pd
from core.answer_parser import KeyItem
from core.grading import grade_students
from core.statistics import calculate_statistics

def test_tied_lowest():
    key={1:KeyItem(1,1,2)}
    o=pd.DataFrame({'student_id':['new1','new2','new3'], 'Q01':[3,2,1]})
    s=calculate_statistics(grade_students(o,key),key)
    assert s['lowest_students']==['new1','new2']
