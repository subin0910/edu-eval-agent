"""Batch skill analysis. Outputs hypotheses rather than unsupported learner diagnoses."""
from __future__ import annotations
import base64
from pydantic import BaseModel,Field
from core.question_parser import locate_question
from .question_generator import model
from .prompts import ANALYZER_PROMPT

class ItemAnalysis(BaseModel):
    question_number:int
    question_type:str
    learning_objective:str
    solving_strategy:str
    possible_difficulty:str
    limitation:str=''

class AnalysisBatch(BaseModel):
    items:list[ItemAnalysis]=Field(default_factory=list)


def analyze_items(numbers:list[int],pdf:bytes)->AnalysisBatch:
    from langchain_core.messages import HumanMessage,SystemMessage
    content=[{'type':'text','text':f'다음 원본 문항 번호 각각 분석: {numbers}. 번호를 바꾸지 말 것. 원문 근거와 가능성 가설을 구분할 것.'}]
    for n in numbers:
        source=locate_question(pdf,n)
        content.extend([
            {'type':'text','text':f'{n}번 원문: {source["text"][:7500]}'},
            {'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(source['png_bytes']).decode('ascii')}}
        ])
    return model().with_structured_output(AnalysisBatch,method='function_calling').invoke([
        SystemMessage(content=ANALYZER_PROMPT),HumanMessage(content=content)
    ])
