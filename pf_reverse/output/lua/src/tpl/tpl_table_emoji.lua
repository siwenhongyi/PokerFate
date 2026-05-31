-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','type','send','fly_type_img','fly_time','item','sort','send_offset','receive_offset',}
    local bodys = {
{1,1,nil,"Icon[icon_10100001]",1000,{11400001,1},1,nil,nil},
{2,1,nil,"Icon[icon_10100001]",1000,{11400001,1},2,nil,nil},
{3,1,nil,"Icon[icon_10100001]",1000,{11400001,1},3,nil,nil},
{4,1,nil,"Icon[icon_10100001]",1000,{11400001,1},4,nil,nil},
{5,1,nil,"Icon[icon_10100001]",1000,{11400001,1},5,nil,nil},
{6,2,nil,"Icon[icon_10100001]",nil,{11400001,1},6,nil,nil},
{7,1,nil,"Icon[icon_10100001]",1000,{11400001,1},7,nil,nil},
{8,2,nil,"Icon[icon_10100001]",nil,{11400001,1},8,nil,nil},
{9,1,nil,"Icon[icon_10100001]",1000,{11400001,1},9,nil,nil}
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