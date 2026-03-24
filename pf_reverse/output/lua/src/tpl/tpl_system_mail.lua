-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','title','sender','send_time','main_text','attachments','important','special','unrestricted','theme',}
    local bodys = {
{1001,"LAB_MAIL_TITLE_2","LAB_MAIL_SENDER_1",nil,"LAB_MAIL_MAIN_TEXT_2",nil,nil,nil,nil,nil},
{1002,"LAB_MONTHLY_CARD_MAIL_TITLE_1","LAB_MAIL_SENDER_1",nil,"LAB_MONTHLY_CARD_MAIL_DEC_1",nil,nil,nil,nil,nil},
{2001,"LAB_MAIL_TITLE_1","LAB_MAIL_SENDER_1",nil,"LAB_MAIL_MAIN_TEXT_1",nil,nil,nil,nil,nil},
{3001,"LAB_MAIL_TITLE_2","LAB_MAIL_SENDER_1",nil,"LAB_MAIL_MAIN_TEXT_2",nil,nil,nil,1,nil},
{4001,"LAB_MAIL_TITLE_3","LAB_MAIL_SENDER_1",nil,"LAB_MAIL_MAIN_TEXT_3",nil,nil,nil,nil,1},
{4002,"LAB_MAIL_TITLE_4","LAB_MAIL_SENDER_1",nil,"LAB_MAIL_MAIN_TEXT_4",{10100001,2000,30200001,1},nil,nil,nil,1},
{5001,"LAB_LEADERBOARD_MAIL_TITLE_1","LAB_MAIL_SENDER_1",nil,"LAB_LEADERBOARD_MAIL_DEC_101",nil,nil,nil,nil,nil},
{5002,"LAB_LEADERBOARD_MAIL_TITLE_1","LAB_MAIL_SENDER_1",nil,"LAB_LEADERBOARD_MAIL_DEC_102",nil,nil,nil,nil,nil},
{5011,"LAB_LEADERBOARD_MAIL_TITLE_2","LAB_MAIL_SENDER_1",nil,"LAB_LEADERBOARD_MAIL_DEC_201",nil,nil,nil,nil,nil},
{5012,"LAB_LEADERBOARD_MAIL_TITLE_2","LAB_MAIL_SENDER_1",nil,"LAB_LEADERBOARD_MAIL_DEC_202",nil,nil,nil,nil,nil},
{51001,"LAB_LEADERBOARD_MAIL_TITLE_3","LAB_MAIL_SENDER_1",nil,"LAB_LEADERBOARD_MAIL_DEC_1",nil,nil,nil,nil,nil},
{51002,"LAB_LEADERBOARD_MAIL_TITLE_3","LAB_MAIL_SENDER_1",nil,"LAB_LEADERBOARD_MAIL_DEC_2",nil,nil,nil,nil,nil},
{61001,"LAB_MAIL_030","LAB_MAIL_SENDER_1",nil,"LAB_MAIL_031",nil,nil,nil,nil,nil}
}
    for _, v in pairs(bodys) do
        local m = {}
        for i, k in pairs(keys) do
            m[k] = v[i]
        end
        P[v[1]] = m
        PL[#PL+1] = m
    end
end
_initData()

tpl_system_mail = P
tpl_system_mail_list = PL
function tpl_system_mail_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

