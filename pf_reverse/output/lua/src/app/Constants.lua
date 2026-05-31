--全局引用的常量定义文件

--[[ 连接服务器类型
    dev: 测试服，代码 1
    dmod: 时间测试服，代码 2
    pre: 预发布服，代码 3
    release: 正式服，代码 4
]]
G_PACKAGE_TYPE = 4

G_GAME_NAME = "PokerFate"

--[[
    1 官网网页
    2 官方PC
    3 官方APK
    4 Steam
    5 Google
    6 AppStore
    7 Qoo
    8 Stove
    9 官方PC(简中)
    10 官方APK(简中)
]]
G_CHNL_ID = CS.ThirdManager.Instance:getThirdId()
if 0 == G_CHNL_ID then
    G_CHNL_ID = bee.isAndroid and 5 or (bee.isIos and 6 or 2)
end

-- 是否测试服
bee.isTest = G_PACKAGE_TYPE == 1 or G_PACKAGE_TYPE == 2
bee.isDev = G_PACKAGE_TYPE == 1

bee.isDmod = G_PACKAGE_TYPE == 2
-- 是否预发布服
bee.isPre = G_PACKAGE_TYPE == 3
-- 是否正式服
bee.isRelease = G_PACKAGE_TYPE == 4

bee.isInTest = bee.isRelease or bee.isPre

-- 是否直接付费
bee.isPayTest = bee.isTest

-- 服务器地址
if bee.isDev then
    G_SERVER_URL = nil
    -- G_SERVER_URL = "ws://10.100.5.56:9012"   -- 凯
    -- G_SERVER_URL = "ws://10.100.5.62:9012"   -- 海
    -- G_SERVER_URL = "ws://10.100.5.53:4001"   -- luo
elseif bee.isDmod then
    G_SERVER_URL = nil
elseif bee.isPre then
    G_SERVER_URL = nil
elseif bee.isRelease then
    G_SERVER_URL = nil
end

-- http 服务地址
if bee.isDev then
    G_HTTP_URL = "https://dev-login.poker-fate.com/"
    -- G_HTTP_URL = "http://10.100.1.237:8888/"
elseif bee.isDmod then
    G_HTTP_URL = "http://10.100.0.197/"
elseif bee.isPre then
    G_HTTP_URL = "https://pre-login.poker-fate.com/"
elseif bee.isRelease then
    if G_CHNL_ID == 9 or G_CHNL_ID == 10 then
        G_HTTP_URL = "http://8.163.49.33:8888/"
        G_HTTP_URL_2 = "http://121.196.174.32:8888/"
        G_HTTP_URL_3 = "https://ga-foreign.poker-fate.com/"
        G_HTTP_URL_4 = "https://awsb-entry.poker-fate.com/"
        -- _HTTP_URL_5 = "http://106.15.91.81/"
    else
        G_HTTP_URL = "https://ga-foreign.poker-fate.com/"
        G_HTTP_URL_2 = "https://awsb-entry.poker-fate.com/"
        -- G_HTTP_URL_3 = "https://zga-entry.allinmoe.com/"
        -- G_HTTP_URL_4 = "https://zga-entry.poker-fate.net/"
        -- G_HTTP_URL_5 = "http://106.15.91.81/"
    end
end

-- 分享地址
if bee.isDev then
    G_SHARE_URL = "http://10.100.1.199:6602/"
elseif bee.isDmod then
    G_SHARE_URL = "http://10.100.1.199:6602/"
elseif bee.isPre then
    G_SHARE_URL = "https://share.pokerfate.com/"
elseif bee.isRelease then
    G_SHARE_URL = "https://share.pokerfate.com/"
end


if bee.isDev then
    G_REMOTE_RES_HOST = "https://dev-cdn.poker-fate.com/client/remote_res/dev/"
elseif bee.isDmod then
    G_REMOTE_RES_HOST = "https://dev-cdn.poker-fate.com/client/remote_res/dmod/"
elseif bee.isPre then
	G_REMOTE_RES_HOST = "https://dev-cdn.poker-fate.com/client/remote_res/pre/"
elseif bee.isRelease then
    if G_CHNL_ID == 9 or G_CHNL_ID == 10 then
        G_REMOTE_RES_HOST = "https://bh-cn.oss-cn-shanghai.aliyuncs.com/res/"
	    G_REMOTE_RES_HOST_2 = "https://aws.poker-fate.com/res/"
        G_REMOTE_RES_HOST_3 = "https://cdn.poker-fate.com/client/remote_res/release/"
    else
	    G_REMOTE_RES_HOST = "https://aws.poker-fate.com/res/"
	    G_REMOTE_RES_HOST_2 = "https://cdn.poker-fate.com/client/remote_res/release/"
        G_REMOTE_RES_HOST_3 = "https://bh-cn.oss-cn-shanghai.aliyuncs.com/res/"
    end
end

if bee.isDev then
    G_RES_BASE_HOST = "https://dev-cdn.poker-fate.com"
elseif bee.isDmod then
    G_RES_BASE_HOST = "https://dev-cdn.poker-fate.com"
elseif bee.isPre then
	G_RES_BASE_HOST = "https://dev-cdn.poker-fate.com"
elseif bee.isRelease then
    if G_CHNL_ID == 9 or G_CHNL_ID == 10 then
        G_RES_BASE_HOST = "https://bh-cn.oss-cn-shanghai.aliyuncs.com"
        G_RES_BASE_HOST_2 = "https://djc1p2apfo64w.cloudfront.net"
        G_RES_BASE_HOST_3 = "https://cdn.poker-fate.com"
    else
        G_RES_BASE_HOST = "https://djc1p2apfo64w.cloudfront.net"
        G_RES_BASE_HOST_2 = "https://cdn.poker-fate.com"
        G_RES_BASE_HOST_3 = "https://bh-cn.oss-cn-shanghai.aliyuncs.com"
    end
end

G_WEBSITE_URL = "https://www.pokerfate.com/"
if bee.isAndroid then
    if G_CHNL_ID == 5 then
        G_QGLK = "https://play.google.com/store/apps/details?id=com.pokerfate.play"
    elseif G_CHNL_ID == 10 then
        G_WEBSITE_URL = "https://www.blufffate.com/"
        G_QGLK = G_WEBSITE_URL
        if bee.isPre then
            G_SHARE_URL = "https://share.blufffate.com/"
        elseif bee.isRelease then
            G_SHARE_URL = "https://share.blufffate.com/"
        end
    else
        G_QGLK = G_WEBSITE_URL
    end
elseif bee.isIos then
    G_QGLK = "https://apps.apple.com/app/poker-fate/id6754012032"
else
    if G_CHNL_ID == 9 then
        G_WEBSITE_URL = "https://www.blufffate.com/"
        G_QGLK = G_WEBSITE_URL
        if bee.isPre then
            G_SHARE_URL = "https://share.blufffate.com/"
        elseif bee.isRelease then
            G_SHARE_URL = "https://share.blufffate.com/"
        end
    elseif G_CHNL_ID == 4 then
        G_QGLK = "https://store.steampowered.com/app/1234567/Poker_Fate/"
    elseif G_CHNL_ID == 8 then
        G_QGLK = "https://store.onstove.com/games/102875/"
    else
        G_QGLK = G_WEBSITE_URL
    end
end

G_U_PP = G_WEBSITE_URL .. "privacyPolicy"
G_U_TS = G_WEBSITE_URL .. "termsofService"

SALT = "Z3r0w0nd3rd3!3z4jz89z9DLbg&8Gjt("

CS.SdkHelper.setPackageType(G_PACKAGE_TYPE)

if G_CHNL_ID == 5 then
    CS.StoveMobileHelper.InitProviders("")
elseif G_CHNL_ID == 6 then
    CS.StoveMobileHelper.InitProviders("")
end