
__G__TRACKBACK__ = function(msg)
    if bee.logEvent and (bee.isInTest or bee.isRelease) and G_UPDATE_VERSION then
        local info = G_UPDATE_VERSION .. " " .. (PlayerModel and PlayerModel:getUid() or "") .. msg
        bee.logEvent("client_error", info)
    end
    return msg
end

require "tpl.init"
UiManager:setUiConfig(tpl_ui_config)
PayHelper:initSku()

require "app.Constants"
require "app.config"
require "app.VersionConfig"

require "app.global.GFunctions"
require "app.mgr.GameManager"
require "app.mgr.GameABTestManager"
require "app.mgr.UICameraBlurMgr"

require "app.mgr.AnimationMgr"
require "app.mvc.BaseModel"

require "app.Types.EventDef"
require "app.Types.RedTag"
require "app.Utils.utils"
require "app.Utils.FontUtil"
require "app.mgr.UrlManager"

ModelManager=require "app.mgr.ModelManager"
require "app.Utils.UIDUtil"
require "app.mgr.Game"
require "app.mgr.GuideManager"
require "app.Utils.NodeCache"
PKHelper = require("app.table.PK.PKHelper")

require "app.views.UIExtend.UiBlurBase"
require "app.views.UIExtend.UiFullView"
require "app.views.UIExtend.UiDialog"
require "app.views.UIExtend.PropItem"

-- CS.SdkHelper.Instance:logEvent("witch_open", json.encode({num = 1}))
LocalStore:clear()
RedManager:init()  --红点初始化要最早
UrlManager:init()

LanguageManager:init()
GameManager:init()

if not G_RUN_IN_JOB then
    ModelManager:init()
    GameABTestManager:init()
    
    require("app.mgr.MobileNotificationsManager")
    MobileNotificationsManager:init()
end


if not LocalStore:getBoolForKey("app_init") then
    LocalStore:setBoolForKey("app_init")
    -- bee.logEvent("zhu_ce")
end

bee.on("show_game_debug_button", function()
    if not bee.checkCd("show_game_debug_button", 1) then
        return
    end
	local ui = UiManager:getUI("GameDebugUI")
    if ui then
        ui:hideUI()
    else
        package.loaded["app.views.GameDebugUI"] = nil
        ResManager:ReleaseHandleByName("src/app/views/GameDebugUI.lua")
        require("app.views.GameDebugUI")
        UiManager:showUI("GameDebugUI")
    end
end)

bee.enterSceneEx = function(name, params, loadNow)
    -- if not Config.IS_HIGH_MEMORY or name == "GameScene" then
    if name == "GameScene" or name == "MainScene" then
        if not loadNow then
            if not params then
                params={}
            end
            params.relaScene=name
            bee.enterScene("LoadingScene", params, true)
        else
            bee.enterScene(name, params)
        end
    else
        bee.enterScene(name, params)
    end
end

bee.adaptTop = function(node)
    if 0 ~= Config.UI_OFFSET_LEFT then
        local pos = node.transform.localPosition
        node.transform.localPosition = bee.v3(pos.x + Config.UI_OFFSET_LEFT, pos.y, 0)
    end
end

bee.adaptBottom = function(node)
    if 0 ~= Config.UI_OFFSET_RIGHT then
        local pos = node.transform.localPosition
        node.transform.localPosition = bee.v3(pos.x + Config.UI_OFFSET_RIGHT, pos.y, 0)
    end
end

-- 适配顶部自动区域
bee.adaptTopOffset = function(node)
    if 0 ~= Config.UI_OFFSET_LEFT then
        node.transform.offsetMax = bee.v2(Config.UI_OFFSET_LEFT, 0)
    end
end

-- 适配底部自动区域
bee.adaptBottomOffset = function(node)
    if 0 ~= Config.UI_OFFSET_RIGHT then
        node.transform.offsetMax = bee.v2(Config.UI_OFFSET_RIGHT, 0)
    end
end

-- 分辨率
bee.getResolution = function()
    return LocalStore:getIntegerForKey("cfg_Resolution", 1)
end

bee.setResolution = function(val)
    LocalStore:setIntegerForKey("cfg_Resolution", val)
    return val
end

-- 全屏
bee.isFullScreen = function()
    return LocalStore:getBoolForKey("cfg_FullScreen", false)
end

bee.setFullScreen = function(flag)
    LocalStore:setBoolForKey("cfg_FullScreen", flag)
    return flag
end

bee.refreshScreen = function()
    if bee.isPc and not bee.isEditor then
        local info = CU.Screen.mainWindowDisplayInfo
        if bee.isFullScreen() then
            local info = CU.Screen.mainWindowDisplayInfo
            CU.Screen.SetResolution(info.width, info.height, CU.FullScreenMode.ExclusiveFullScreen)
            refreshScreenSize()
            if UiManager and CS.GameMain.Instance then
                UiManager:resetScreenMatch()
            end
        else
            local d = Config.Resolutions[bee.getResolution()]
            if d then
                CU.Screen.SetResolution(d[1], d[2], bee.isFullScreen())
                refreshScreenSize()
                if UiManager and CS.GameMain.Instance then
                    UiManager:resetScreenMatch()
                end
            end
        end
    end
end

-- 帧率
bee.getFrameRate = function()
    return LocalStore:getIntegerForKey("cfg_FrameRate", 60)
end

bee.setFrameRate = function(val)
    LocalStore:setIntegerForKey("cfg_FrameRate", val)
    return val
end

bee.refreshFrameRate = function()
    CU.Application.targetFrameRate = bee.getFrameRate()
end

if bee.isPc and not bee.isEditor and bee.isFullScreen() then
    bee.refreshScreen()
end
bee.refreshFrameRate()

bee.setGraphicQuality = function(index)
    LocalStore:setIntegerForKey("cfg_GraphicQuality", index)

    if 1 == index then
        CS.Utils.SetQualityLevel(0)
    elseif 2 == index then
        CS.Utils.SetQualityLevel(2)
    else
        CS.Utils.SetQualityLevel(5)
    end

    local scale = 1
    if 1 == index then
        scale = 0.5
    elseif 2 == index then
        scale = 1
    end
    UiManager:resizeBuffers(scale, scale)
end

bee.getGraphicQuality = function(def)
    if not def then
        def = bee.isPc and 3 or 2
    end
    return LocalStore:getIntegerForKey("cfg_GraphicQuality", def)
end

bee.setSorstingOrder=function(obj,value,cmpName)
	if obj then
		obj:GetComponent(cmpName or "Canvas").sortingOrder=value
	end
end

function string.formatnumberthousands(num)
    local formatted = tostring(checknumber(num))
    local k
    local ftStr = '%1,%2'
    if LanguageManager:getLanguage() == "de" then
        ftStr = '%1.%2'
    end
    while true do
        formatted, k = string.gsub(formatted, "^(-?%d+)(%d%d%d)", ftStr)
        if k == 0 then break end
    end
    return formatted
end

function string.getBigNumStr(num)
	if not num then
		return num
	end
    local presign = num < 0 and "-" or ""
    if num < 0 then
        num = -num
    end
    local strLen=string.len(num)
    local bigNumStr=tostring(num)
    local sign = ""
    if num > 10000 and strLen<7 then
        sign = "K"
        if num % 1000 == 0 then
            bigNumStr= string.format("%d",num/1000)
        else
            bigNumStr= string.format("%0.1f",num/1000)
        end
    elseif  strLen>=7 and strLen<=10 then
        sign = "M"
        if num % 1000000 == 0 then
            bigNumStr= string.format("%d",num/1000000)
        elseif num <= 100000000 then
            bigNumStr = tostring(math.floor(num/100000) / 10)
            -- bigNumStr = string.format("%0.1f", num/1000000)
        else
            bigNumStr= string.format("%d",num/1000000)
        end
    elseif  strLen> 10  then
        sign = "B"
        if num % 1000000000 == 0 then
            bigNumStr= string.format("%d",num/1000000000)
        else
            bigNumStr = tostring(math.floor(num/100000000) / 10)
            -- bigNumStr= string.format("%0.1f", num/1000000000)
        end
    end

    -- local pointIndex = string.find( bigNumStr, "." ,1, true)
    -- if not pointIndex then
    --     return string.formatnumberthousands(bigNumStr) .. sign
    -- else
    --     local front = string.sub(bigNumStr, 1, pointIndex -1)
    --     local tail = string.sub(bigNumStr, pointIndex + 1, string.len(bigNumStr))
    --     if LanguageManager:getLanguage() == "de" then
    --         return string.format("%s,%s", string.formatnumberthousands(front), tail) .. sign
    --     end
    --     return string.format("%s.%s", string.formatnumberthousands(front), tail) .. sign
    -- end
    return presign .. bigNumStr .. sign
end

-- 不显示B
function string.getBigNumStr1(num)
    if not num then
        return num
    end
    local presign = num < 0 and "-" or ""
    if num < 0 then
        num = -num
    end
    local strLen=string.len(num)
    local bigNumStr=tostring(num)
    local sign = ""
    if num > 10000 and strLen<7 then
        sign = "K"
        if num % 1000 == 0 then
            bigNumStr= string.format("%d",num/1000)
        else
            bigNumStr= string.format("%0.1f",num/1000)
        end
    elseif strLen >=7 then
        sign = "M"
        if num % 1000000 == 0 then
            bigNumStr= string.format("%d",num/1000000)
        elseif num <= 100000000 then
            bigNumStr = tostring(math.floor(num/100000) / 10)
            -- bigNumStr = string.format("%0.1f", num/1000000)
        else
            bigNumStr= string.format("%d",num/1000000)
        end
    end

    -- local pointIndex = string.find( bigNumStr, "." ,1, true)
    -- if not pointIndex then
    --     return string.formatnumberthousands(bigNumStr) .. sign
    -- else
    --     local front = string.sub(bigNumStr, 1, pointIndex -1)
    --     local tail = string.sub(bigNumStr, pointIndex + 1, string.len(bigNumStr))
    --     if LanguageManager:getLanguage() == "de" then
    --         return string.format("%s,%s", string.formatnumberthousands(front), tail) .. sign
    --     end
    --     return string.format("%s.%s", string.formatnumberthousands(front), tail) .. sign
    -- end
    return presign .. bigNumStr .. sign
end

-- 显示两位小数
function string.getBigNumStr2(num)
    if not num then
        return num
    end
    local presign = num < 0 and "-" or ""
    if num < 0 then
        num = -num
    end
    local strLen=string.len(num)
    local bigNumStr=tostring(num)
    local sign = ""
    if num > 10000 and strLen<7 then
        sign = "K"
        if num % 1000 == 0 then
            bigNumStr= string.format("%d",num/1000)
        else
            -- bigNumStr= string.format("%0.2f",num/1000)
            bigNumStr = tostring(math.floor(num / 10) / 100)
        end
    elseif strLen >=7 then
        sign = "M"
        if num % 1000000 == 0 then
            bigNumStr= string.format("%d",num/1000000)
        elseif num <= 100000000 then
            bigNumStr = tostring(math.floor(num/10000) / 100)
            -- bigNumStr = string.format("%0.1f", num/1000000)
        else
            bigNumStr= string.format("%d",num/1000000)
        end
    end

    -- local pointIndex = string.find( bigNumStr, "." ,1, true)
    -- if not pointIndex then
    --     return string.formatnumberthousands(bigNumStr) .. sign
    -- else
    --     local front = string.sub(bigNumStr, 1, pointIndex -1)
    --     local tail = string.sub(bigNumStr, pointIndex + 1, string.len(bigNumStr))
    --     if LanguageManager:getLanguage() == "de" then
    --         return string.format("%s,%s", string.formatnumberthousands(front), tail) .. sign
    --     end
    --     return string.format("%s.%s", string.formatnumberthousands(front), tail) .. sign
    -- end
    return presign .. bigNumStr .. sign
end

if bee.isAndroid then
    -- CU.SystemInfo.graphicsMemorySize
    local mem = CU.SystemInfo.systemMemorySize / 1024
    Config.IS_LOW_MEMORY = mem <= 4.5
    Config.IS_HIGH_MEMORY = mem > 7.2
    print("============== ggg systemMemorySize", CU.SystemInfo.systemMemorySize, mem)
    if 0 == bee.getGraphicQuality(0) and Config.IS_LOW_MEMORY then
        bee.setGraphicQuality(1)
    end
else
    Config.IS_HIGH_MEMORY = true
    if 0 == bee.getGraphicQuality(0) then
        bee.setGraphicQuality(3)
    end
end

bee.setGraphicQuality(bee.getGraphicQuality())

if not LocalStore:getBoolForKey("log_user_phone_ram") then
    LocalStore:setBoolForKey("log_user_phone_ram", true)
    bee.logEvent("user_phone_ram", math.floor(CU.SystemInfo.systemMemorySize / 1000))
end

bee.log("game-open")

if not bee.isRelease then
    -- profiler = require("perf.profiler")
    -- memory = require("perf.memory")
end

Game:start()

tpl_errorCode = {}
for _, v in ipairs(tpl_RetCode_list) do
    tpl_errorCode[v.code] = v
    tpl_mult_language[v.id] = v
end
for _, v in ipairs(tpl_HttpCode_list) do
    tpl_errorCode[v.code] = v
    tpl_mult_language[v.id] = v
end

VibrateManager:init()
