import json

import pytest

from dishmook.output_parser import parse_candidate
from dishmook.runtime_models import ResearchCandidate

OBSERVED = r'{"text":"Calculate the kinetic energy using the formula \( \frac{1}{2}mv^2 \). Here, \( m = 3 \) kg and \( v = 4 \) m/s.","answer":24,"citations":[],"disagreements":[]}'


def test_observed_energy_latex_repaired_without_changing_answer():
    parsed, metadata = parse_candidate(OBSERVED, ResearchCandidate)
    assert parsed.answer == 24
    assert r'\frac{1}{2}' in parsed.text
    assert '\f' not in parsed.text
    assert parsed.citations == parsed.disagreements == []
    assert metadata == {'mode':'latex_text_escape','raw_schema_valid':False}
    with pytest.raises(json.JSONDecodeError):
        json.loads(OBSERVED)  # raw evidence remains invalid, not relabelled strict


def test_valid_json_keeps_original_string_semantics():
    value={'text':'formula \\(x\\), newline\nquoted "word"','answer':24,'citations':[],'disagreements':[]}
    parsed, metadata = parse_candidate(json.dumps(value), ResearchCandidate)
    assert parsed.text == value['text']
    assert metadata['mode'] == 'strict'


@pytest.mark.parametrize('raw', [
    OBSERVED.replace('"answer":24', r'"answer":"\(24\)"'),
    OBSERVED.replace('"answer":24', '"answer":24,"answer":99'),
    OBSERVED.replace('"disagreements":[]','"disagreements":[{"issue":"none"}]'),
    OBSERVED.replace('"citations":[]',r'"citations":["bad\q"]'),
    OBSERVED[:-1]+',}',
    '```json\n'+OBSERVED+'\n```',
    OBSERVED+' extra',
    r'{"text":"unsupported \q","answer":24}',
])
def test_fallback_never_repairs_other_fields_or_structure(raw):
    with pytest.raises(ValueError):
        parse_candidate(raw, ResearchCandidate)


def test_runtime_keeps_raw_response_and_exports_repair(tmp_path):
    from dishmook.domain import Problem, Agent
    from dishmook.runtime_models import ExecutionSpec, ModelResponse
    from dishmook.runtime import prepare,resume
    spec=ExecutionSpec(agent=Agent(agent_id='test',role='test',instructions='test'),problem=Problem(problem_id='energy',title='Energy',statement='Find energy'),output_mode='research')
    def runner(*args):
        return ModelResponse(text=OBSERVED,input_tokens=1,output_tokens=10,token_unit='utf8_bytes')
    run_id=prepare(tmp_path,spec)
    state=resume(tmp_path,run_id,runner=runner)
    assert state['status']=='completed'
    assert state['response']['text']==OBSERVED
    assert state['output_parse']['raw_schema_valid'] is False
    assert state['candidate']['answer']==24
    assert json.loads((tmp_path/run_id/'manifest.json').read_text())['output_parse']['mode']=='latex_text_escape'
