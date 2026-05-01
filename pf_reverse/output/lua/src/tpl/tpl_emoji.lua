-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','role','name','emoji','unlock',}
    local bodys = {
{1,1001,"confuse","Emoji100101[emoji100101_confuse]",0},
{2,1001,"cry","Emoji100101[emoji100101_cry]",0},
{3,1001,"eat","Emoji100101[emoji100101_eat]",0},
{4,1001,"happy","Emoji100101[emoji100101_happy]",0},
{5,1001,"heart","Emoji100101[emoji100101_heart]",6},
{6,1001,"shy","Emoji100101[emoji100101_shy]",6},
{7,1002,"glow","Emoji100201[emoji100201_glow]",0},
{8,1002,"praise","Emoji100201[emoji100201_praise]",0},
{9,1002,"sad","Emoji100201[emoji100201_sad]",0},
{10,1002,"think","Emoji100201[emoji100201_think]",0},
{11,1002,"poker","Emoji100201[emoji100201_poker]",6},
{12,1002,"show","Emoji100201[emoji100201_show]",6},
{13,1003,"bow","Emoji100301[emoji100301_bow]",0},
{14,1003,"drink","Emoji100301[emoji100301_drink]",0},
{15,1003,"praise","Emoji100301[emoji100301_praise]",0},
{16,1003,"smirk","Emoji100301[emoji100301_smirk]",0},
{17,1003,"fan","Emoji100301[emoji100301_fan]",6},
{18,1003,"heart","Emoji100301[emoji100301_heart]",6},
{19,1004,"angry","Emoji100401[emoji100401_angry]",0},
{20,1004,"smirk","Emoji100401[emoji100401_smirk]",0},
{21,1004,"bow","Emoji100401[emoji100401_bow]",0},
{22,1004,"guilty","Emoji100401[emoji100401_guilty]",0},
{23,1004,"applaud","Emoji100401[emoji100401_applaud]",6},
{24,1004,"toast","Emoji100401[emoji100401_toast]",6},
{25,1005,"alert","Emoji100501[emoji100501_alert]",0},
{26,1005,"bite","Emoji100501[emoji100501_bite]",0},
{27,1005,"daze","Emoji100501[emoji100501_daze]",0},
{28,1005,"run","Emoji100501[emoji100501_run]",0},
{29,1005,"eyes","Emoji100501[emoji100501_eyes]",6},
{30,1005,"sleepy","Emoji100501[emoji100501_sleepy]",6},
{31,1006,"cry","Emoji100601[emoji100601_cry]",0},
{32,1006,"doze","Emoji100601[emoji100601_doze]",0},
{33,1006,"mighty","Emoji100601[emoji100601_mighty]",0},
{34,1006,"weak","Emoji100601[emoji100601_weak]",0},
{35,1006,"popsicle","Emoji100601[emoji100601_popsicle]",6},
{36,1006,"wind","Emoji100601[emoji100601_wind]",6},
{37,1007,"hand","Emoji100701[emoji100701_hand]",0},
{38,1007,"plot","Emoji100701[emoji100701_plot]",0},
{39,1007,"smirk","Emoji100701[emoji100701_smirk]",0},
{40,1007,"tired","Emoji100701[emoji100701_tired]",0},
{41,1007,"game","Emoji100701[emoji100701_game]",6},
{42,1007,"silence","Emoji100701[emoji100701_silence]",6},
{43,1008,"confused","Emoji100801[emoji100801_confused]",0},
{44,1008,"cute","Emoji100801[emoji100801_cute]",0},
{45,1008,"selfie","Emoji100801[emoji100801_selfie]",0},
{46,1008,"shopping","Emoji100801[emoji100801_shopping]",0},
{47,1008,"show","Emoji100801[emoji100801_show]",6},
{48,1008,"idol","Emoji100801[emoji100801_idol]",6},
{49,1009,"confused","Emoji100901[emoji100901_confused]",0},
{50,1009,"go","Emoji100901[emoji100901_go]",0},
{51,1009,"hot","Emoji100901[emoji100901_hot]",0},
{52,1009,"loud","Emoji100901[emoji100901_loud]",0},
{53,1009,"bingo","Emoji100901[emoji100901_bingo]",6},
{54,1009,"enlight","Emoji100901[emoji100901_enlight]",6},
{55,1010,"majesty","Emoji101001[emoji101001_majesty]",0},
{56,1010,"praise","Emoji101001[emoji101001_praise]",0},
{57,1010,"shock","Emoji101001[emoji101001_shock]",0},
{58,1010,"squat","Emoji101001[emoji101001_squat]",0},
{59,1010,"exhausted","Emoji101001[emoji101002_exhausted]",6},
{60,1010,"jail","Emoji101001[emoji101002_jail]",6},
{61,1012,"crystalball","Emoji101201[emoji101201_crystalball]",0},
{62,1012,"hair","Emoji101201[emoji101201_hair]",0},
{63,1012,"heart","Emoji101201[emoji101201_heart]",0},
{64,1012,"wait","Emoji101201[emoji101201_wait]",0},
{65,1012,"confused","Emoji101201[emoji101201_confused]",6},
{66,1012,"kitty","Emoji101201[emoji101201_kitty]",6},
{67,1013,"cute","Emoji101301[emoji101301_cute]",0},
{68,1013,"punch","Emoji101301[emoji101301_punch]",0},
{69,1013,"watermelon","Emoji101301[emoji101301_watermelon]",0},
{70,1013,"work","Emoji101301[emoji101301_work]",0},
{71,1013,"bomb","Emoji101301[emoji101301_bomb]",6},
{72,1013,"dumb","Emoji101301[emoji101301_dumb]",6},
{73,1014,"chill","Emoji101401[emoji101401_chill]",0},
{74,1014,"confuse","Emoji101401[emoji101401_confuse]",0},
{75,1014,"cute","Emoji101401[emoji101401_cute]",0},
{76,1014,"rain","Emoji101401[emoji101401_rain]",0},
{77,1014,"yawn","Emoji101401[emoji101401_yawn]",6},
{78,1014,"mock","Emoji101401[emoji101401_mock]",6}
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

tpl_emoji = P
tpl_emoji_list = PL
function tpl_emoji_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P