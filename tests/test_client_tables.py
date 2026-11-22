"""pf_reverse.tables: the client's tpl_*.lua as Python values."""
import os

import pytest

from pf_reverse import tables as tb

ROWS = '''-- create by export_excel.py
local P = {}
local function _initData()
    local keys = {'id','name','time_start','task','note',}
    local bodys = {
{30001,"LAB_X",1794448800,{1001},nil},
{30002,"LAB_Y",-5,{{10,15},{0}},[[two
lines]]},
{30003,KEY_GLOBAL,0x10,{a = 1, [2] = "b"},'it''s'}
}
    for _, v in pairs(bodys) do end
end
_initData()
return P'''

CONST = '''local P, M = nil, {}
tpl_constdata = {
	Dispatch_Start = 1787796000,
	Steps = {20,21},
	Name = "x"
}
P = tpl_constdata'''


@pytest.mark.parametrize("text, value", [
    ("{1, 2.5, -3, nil, true}", [1, 2.5, -3, None, True]),
    ('{"a\\"b", [[x]], [==[y]]==]}', ['a"b', "x", "y]"]),     # a long string ends at its own bracket
    ("{k = 1, [5] = 2, 3}", {"k": 1, 5: 2, 1: 3}),
    ("{{}, {{1}}}", [[], [[1]]]),
])
def test_parse_value(text, value):
    assert tb.parse_value(text) == value


def test_rows_constants_and_text(tmp_path):
    (tmp_path / "tpl_act.lua").write_text(ROWS.replace("'it''s'", "'its'"), encoding="utf-8")
    (tmp_path / "tpl_constdata.lua").write_text(CONST, encoding="utf-8")
    (tmp_path / "tpl_mult_language.lua").write_text(
        "local keys = {'id','zh','en',}\nlocal bodys = {\n{\"LAB_X\",\"活动\",\"Event\"}\n}", encoding="utf-8")
    t = tb.Tables(tmp_path)
    assert t.rows("act") == [
        {"id": 30001, "name": "LAB_X", "time_start": 1794448800, "task": [1001], "note": None},
        {"id": 30002, "name": "LAB_Y", "time_start": -5, "task": [[10, 15], [0]], "note": "two\nlines"},
        {"id": 30003, "name": "KEY_GLOBAL", "time_start": 16, "task": {"a": 1, 2: "b"}, "note": "its"}]
    assert t.row("act", 30002)["note"] == "two\nlines" and t.row("act", 1) is None
    assert t.const("Dispatch_Start") == 1787796000 and t.const("Steps") == [20, 21] and t.const("none", 7) == 7
    assert t.text("LAB_X") == "活动" and t.text("LAB_NONE") == "LAB_NONE"
    assert t.names() == ["act", "constdata", "mult_language"] and t.rows("missing") == []


def test_a_changed_file_is_read_again(tmp_path):
    path = tmp_path / "tpl_act.lua"
    path.write_text("local keys = {'id',}\nlocal bodys = {\n{1}\n}", encoding="utf-8")
    t = tb.Tables(tmp_path)
    assert t.rows("act") == [{"id": 1}]
    path.write_text("local keys = {'id',}\nlocal bodys = {\n{1},\n{2}\n}", encoding="utf-8")
    os.utime(path, ns=(1, 2))
    assert t.rows("act") == [{"id": 1}, {"id": 2}]


def test_every_client_table_reads():
    if not tb.TPL.exists():
        pytest.skip("client tables not checked out")
    for name in tb.TABLES.names():
        tb.TABLES.constants() if name == "constdata" else tb.TABLES.rows(name)
    assert tb.TABLES.row("monopoly_activity", 30001)["time_end"] == 1795633200
