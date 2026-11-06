-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','mask','type','name','name2','interval','sends','flys','receives','receive_loop','fly_type_img','fly_time','item','sort','send_offset','receive_offset',}
    local bodys = {
{1,"比心",1,"EmojiHeart[emoji_heart_01]",nil,80,{1,16},{17,23},{24,40},nil,nil,nil,{11400001,1},1,{100,70},{35,20}},
{2,"干杯",1,"EmojiCheers[emoji_cheers_01]",nil,80,{1,15},{16,22},{23,45},nil,nil,nil,{11400001,1},2,{100,70},{35,100}},
{3,"送花",1,"EmojiFlower[emoji_flower_01]",nil,80,{1,12},{13,19},{20,33},nil,nil,nil,{11400001,1},3,{40,40},{25,80}},
{4,"泼水",1,"EmojiWater[emoji_water_01]",nil,80,{1,5},nil,{7,37},nil,"emoji_water_06",300,{11400001,1},4,{40,40},{70,95}},
{5,"抓鸡",1,"EmojiChick[emoji_chick_01]",nil,80,{1,8},nil,{10,39},nil,"emoji_chick_09",300,{11400001,1},5,{80,50},{80,80}},
{6,"捕食",1,"EmojiShark[emoji_shark_01]",nil,80,{1,26},{27,32},{33,45},nil,nil,nil,{11400001,1},6,{47,50},{20,115}},
{7,"长草",1,"EmojiGrass[emoji_grass_01]",nil,80,{1,4},nil,{6,39},nil,"emoji_grass_05",300,{11400001,1},7,{30,30},{50,85}},
{8,"猫猫拳",2,"EmojiCatPunchA[emoji_cat_punch_a_01]","EmojiCatPunchB[emoji_cat_punch_b_01]",80,{1,29},nil,{1,26},nil,nil,600,{11400001,1},8,{120,60},{120,80}},
{9,"咸鱼寿司",1,"EmojiFish[emoji_fish_01]",nil,80,{1,8},{9,15},{16,30},nil,nil,nil,{11400001,1},9,{40,40},{30,90}},
{10,"哑弹",1,"EmojiBomb[emoji_bomb_01]",nil,80,{1,5},{6,10},{11,22},nil,nil,nil,{11400001,1},10,{40,40},{40,90}},
{11,"闹钟",1,"EmojiClock[emoji_clock_01]",nil,80,{1,5},{6,9},{10,27},nil,nil,nil,{11400001,1},11,{40,40},{10,80}},
{12,"应援",1,"EmojiCall[emoji_call_01]",nil,80,{1,5},{6,10},{11,12},{1,12,2},nil,nil,{11400001,1},12,{40,40},{35,90}},
{13,"汽水",1,"EmojiCola[emoji_cola_01]",nil,80,{1,5},{6,12},{13,47},nil,nil,nil,{11400001,1},13,{150,120},{140,120}}
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

tpl_table_emoji = P
tpl_table_emoji_list = PL
function tpl_table_emoji_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P