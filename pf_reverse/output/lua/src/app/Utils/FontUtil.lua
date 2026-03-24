bee = bee or {}
-- 字体适配工具

bee._fontCache = {}

local function isSerifFont(name)
    if name then
        local i1, i2 = string.find(name, "^SourceHanSerif")
        if i1 then
            return true
        end
    end
    return false
end

-- 货币类数字显示字体
function G_FONT_COIN(name)
    return ResManager:GetFont("Fonts/bebasneueregular-vm3oz.ttf")
end

-- 英文、数字显示字体
function G_FONT_EN(name)
    if isSerifFont(name) then
        return ResManager:GetFont("FontsSerif/SourceHanSerifCN-Heavy.otf")
    end
    return ResManager:GetFont("Fonts/CreatoBold.ttf")
end

-- 简体中文字体
function G_FONT_SC(name)
    if isSerifFont(name) then
        return ResManager:GetFont("FontsSerif/SourceHanSerifCN-Heavy.otf")
    end
    return ResManager:GetFont("Fonts/SourceHanSansSC-Bold-2.otf")
end

-- 台湾繁体字体
function G_FONT_TW(name)
    if isSerifFont(name) then
        return ResManager:GetFont("FontsSerif/SourceHanSerifTW-Heavy.ttf")
    end
    return ResManager:GetFont("Fonts/SourceHanSansTC-Bold.otf")
end

-- 日文字体
function G_FONT_JP(name)
    if isSerifFont(name) then
        return ResManager:GetFont("FontsSerif/SourceHanSerifJP-Heavy.otf")
    end
    return ResManager:GetFont("Fonts/SourceHanSansJP-Bold.otf")
end

function isAsciiString(s)
    local i = 1
    while i <= #s do
        if string.byte(s, i) > 127 then
            if string.byte(s, i) == 226 and i + 2 <= #s and string.byte(s, i + 1) == 128 and (string.byte(s, i + 2) == 148 or string.byte(s, i + 2) == 147) then
                -- 处理特殊的长短破折号
                i = i + 3
            else
                return false
            end
        end
        i = i + 1
    end
    -- for i = 1, #s do
    --     if string.byte(s, i) > 127 then
    --         return false
    --     end
    -- end
    return true
end

function getTextFont(s, textCmp)
    local name = nil
    if textCmp and not bee.isNull(textCmp.font) then
        name = textCmp.font.name
    end
    if name and not bee._fontCache[textCmp] then
        bee._fontCache[textCmp] = name
    end
    if type(s) == "number" or LanguageManager:getLanguage() == "en" or isAsciiString(s) then
        if bee._fontCache[textCmp] then
            if bee._fontCache[textCmp] == "CreatoExtraBold" then
                return ResManager:GetFont("Fonts/CreatoExtraBold.TTF")
            elseif bee._fontCache[textCmp] == "CreatoBlack" then
                return ResManager:GetFont("Fonts/CreatoBlack.TTF")
            end
        end
        return G_FONT_EN(name)
    else
        if "jp" == LAN:getLanguage() then
            return G_FONT_JP(name)
        elseif "tw" == LAN:getLanguage() then
            return G_FONT_TW(name)
        elseif "ko" == LAN:getLanguage() then
            return G_FONT_SC(name)
        else
            return G_FONT_SC(name)
        end
    end
end

bee.clearFontCache = function()
    bee._fontCache = {}
end

bee.setText = function(obj, s, cmpName)
    if obj then
        local cmp = obj:GetComponent(cmpName or "Text")
        if cmp then
            cmp.text = s
            if s and "" ~= s then
                if cmpName == "InputField" then
                    cmp.textComponent.font = getTextFont(s, cmp.textComponent)
                else
                    cmp.font = getTextFont(s, cmp)
                end
            end
        elseif not cmpName then
            cmp = obj:GetComponent("TextMeshProUGUI")
            if cmp then
                cmp.text = s
            end
        end
    end
end

bee.setTextCut = function(obj, s, width)
    if obj then
        local cmp = obj:GetComponent("Text")
        if cmp then
            if s and "" ~= s then
                cmp.font = getTextFont(s)
            end
            CS.Utils.SetTextWithWidth(cmp, s, width)
        end
    end
end

-- 设置货币数字
bee.setTextGold = function(obj, s, cmpName)
    bee.setText(obj, s, cmpName)
    -- if obj then
    --     local cmp = obj:GetComponent(cmpName or "Text")
    --     if cmp then
    --         cmp.font = G_FONT_COIN()
    --         cmp.text = s
    --     elseif not cmpName then
    --         cmp = obj:GetComponent("TextMeshProUGUI")
    --         if cmp then
    --             cmp.text = s
    --         end
    --     end
    -- end
end

-- 设置文本，不改变字体
bee.setTextOrigin = function(obj, s, cmpName)
    if obj then
        local cmp = obj:GetComponent(cmpName or "Text")
        if cmp then
            cmp.text = s
        elseif not cmpName then
            cmp = obj:GetComponent("TextMeshProUGUI")
            if cmp then
                cmp.text = s
            end
        end
    end
