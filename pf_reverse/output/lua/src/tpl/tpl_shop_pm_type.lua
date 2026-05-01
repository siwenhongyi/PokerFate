-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','pm_type','icon','payment_id',}
    local bodys = {
{101,"Alipay",nil,nil},
{102,"American Express",nil,nil},
{103,"Mastercard",nil,nil},
{104,"PayPal",nil,nil},
{105,"Visa",nil,nil},
{106,"Unionpay",nil,nil},
{201,"Alipay HK","Shoppayment[shoppayment_icon_201]",3624},
{202,"Bitcash","Shoppayment[shoppayment_icon_202]",3043},
{203,"Cash APP","Shoppayment[shoppayment_icon_203]",3679},
{204,"Dragonpay","Shoppayment[shoppayment_icon_204]",3314},
{205,"FPX","Shoppayment[shoppayment_icon_205]",3833},
{206,"Gcash","Shoppayment[shoppayment_icon_206]",3625},
{207,"Grabpay","Shoppayment[shoppayment_icon_207]",3549},
{208,"Other methods","Shoppayment[shoppayment_icon_208]",nil},
{209,"PayPay","Shoppayment[shoppayment_icon_209]",3669},
{210,"PromptPay","Shoppayment[shoppayment_icon_210]",3656},
{211,"TouchNGo","Shoppayment[shoppayment_icon_211]",3630},
{212,"TrueMoney Wallet","Shoppayment[shoppayment_icon_212]",3628},
{213,"Wechat Pay","Shoppayment[shoppayment_icon_213]",3215},
{214,"Wechat Pay HK","Shoppayment[shoppayment_icon_214]",3690},
{215,"Alipay","Shoppayment[shoppayment_icon_215]",3623},
{216,"American Express","Shoppayment[shoppayment_icon_102]",1380},
{217,"Mastercard","Shoppayment[shoppayment_icon_103]",1380},
{218,"Visa","Shoppayment[shoppayment_icon_105]",1380},
{219,"Unionpay","Shoppayment[shoppayment_icon_106]",1380},
{301,"Alipay HK","Shoppayment[shoppayment_icon_201]",nil},
{302,"Visa","Shoppayment[shoppayment_icon_105]",nil},
{303,"Mastercard","Shoppayment[shoppayment_icon_103]",nil},
{304,"JCB","Shoppayment[shoppayment_icon_logo_jcb]",nil},
{305,"Discover","Shoppayment[shoppayment_icon_logo_discover]",nil},
{306,"Unionpay","Shoppayment[shoppayment_icon_106]",nil}
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

tpl_shop_pm_type = P
tpl_shop_pm_type_list = PL
function tpl_shop_pm_type_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P