local P = class("IngameExactBet", Object)

function P:onAwake()
    self.inputText = ""
    self.cursorPos = 0 --光标位置
    self.cursorBlinkTimer = 0
    self.lightTime = 0.5
    self.isCursorVisible = true
    self.isFocused = false
    self.BBDif = 0 

    self.LineRect = self:find("Enter/Content/ingame_exact_enter_line"):GetComponent("RectTransform")
    self.LineImage = self.LineRect:GetComponent("Image")
    self.ValueRect = self:find("Enter/Content/Value"):GetComponent("RectTransform")
    self.ValueText = self.ValueRect:GetComponent("Text")
    self.ValueClick = self.ValueRect:GetComponent("EventTriggerListener")
    self.BBGo = self:find("Enter/BB")
    self.ChipIcon = self:find("Enter/icon_10100001")

    self.betList = {}
    self.bb = 0

    self._watiStart = false

    self.ButtonRoot = self:find("ExactButton")
    -- self.NumberButtons = {}
    for i = 0, 9 do
        local indexStr = tostring(i)
        local item = self:find("ingame_exact_button_" .. indexStr, self.ButtonRoot)
        bee.addClick(item, function()
            self:inputValue(indexStr)
        end)
    end
    self.BackButton = self:find("ingame_exact_button_back", self.ButtonRoot)
    bee.addClick(self.BackButton, function()
        self:inputDelete()
    end)
    self.ClearAllButton = self:find("ingame_exact_button_clear", self.ButtonRoot)
    bee.addClick(self.ClearAllButton, function()
        self:clearAllValue()
    end)
    self.PointButton = self:find("ingame_exact_button_point", self.ButtonRoot)
    bee.addClick(self.PointButton, function()
        self:inputPoint()
    end)
end

function P:onStart()
    self.ValueClick.onClick:AddListener(function (go, eventData)
        self:clickEvent(eventData)
    end)

    -- 数字键映射
    self.numKeyMappings = {}
    for i = 0, 9 do
        local alphaKey = CU.KeyCode["Alpha" .. i]
        local keypadKey = CU.KeyCode["Keypad" .. i]
        table.insert(self.numKeyMappings, { key = alphaKey, ch = tostring(i) })
        table.insert(self.numKeyMappings, { key = keypadKey, ch = tostring(i) })
    end

    local chipIcon = GameModel.data:getChipIcon()
    if chipIcon then
        bee.setIcon(self.ChipIcon, chipIcon)
    end

    self:updateCursorPosition()
    self:focus()
end

function P:onEnable()
    self:initShowType()
end

function P:initShowType()
    local showBB = SettingModel:isShowBB()
    self.BBGo:SetActive(showBB)
    self.BBDif = showBB and 55 or 100
    self.ValueRect.anchoredPosition = bee.v2(showBB and -48 or -2, 0)
    self.ClearAllButton:SetActive(not showBB)
end

function P:setBetList(valList, bb)
    self.betList = valList or {}
    self.bb = bb
end

function P:onUpdate(dt)
    self.cursorBlinkTimer = self.cursorBlinkTimer + dt
    if self.cursorBlinkTimer >= self.lightTime then
        self.cursorBlinkTimer = 0
        self.isCursorVisible = not self.isCursorVisible
        self.LineImage.enabled = self.isCursorVisible
    end

    self:inputEvent()
end

--更新光标位置
function P:updateCursorPosition()
    local textGen = self.ValueText.cachedTextGenerator
    if textGen == nil or textGen.characterCount == 0 then
        self.LineRect.anchoredPosition = bee.v2(0 + self.BBDif, self.LineRect.anchoredPosition.y)
        return
    end

    local xPos = 0
    if self.cursorPos < textGen.characters.Count then
        if self.cursorPos >= 0 then
            local charInfo = textGen.characters[self.cursorPos]
            xPos = charInfo.cursorPos.x
        else
            self.cursorPos = 0
        end
    else
        local lastChar = textGen.characters[textGen.characters.Count - 1]
        xPos = lastChar.cursorPos.x + lastChar.charWidth
    end

    local scale = self.ValueText.canvas.scaleFactor
    self.LineRect.anchoredPosition = bee.v2(xPos / scale + self.BBDif, self.LineRect.anchoredPosition.y)
end

--聚焦
function P:focus()
    self.isFocused = true
    self.LineImage.enabled = true
    self.isCursorVisible = true
    self.cursorBlinkTimer = 0
end

--点击事件
function P:clickEvent(eventData)
    -- 获取点击在Text上的本地坐标
    local success, localPoint = CU.RectTransformUtility.ScreenPointToLocalPointInRectangle(
        self.ValueRect,
        eventData.position,
        eventData.pressEventCamera
    )

    if not success then
        self.cursorPos = 0
        self:updateCursorPosition()
        return
    end

    local textGen = self.ValueText.cachedTextGenerator
    if textGen == nil or textGen.characterCount == 0 then
        self.cursorPos = 0
        self:updateCursorPosition()
        return
    end

    local newCursorPos = 0
    local minDistance = math.huge
    local characters = textGen.characters

    for i = 0, #self.inputText do
        local charPos

        if i < characters.Count then
            local charInfo = characters[i]
            charPos = charInfo.cursorPos
        else
            if characters.Count > 0 then
                local lastChar = characters[characters.Count - 1]
                charPos = bee.v2(lastChar.cursorPos.x + lastChar.charWidth, lastChar.cursorPos.y)
            else
                charPos = bee.v3zero
            end
        end

        local scale = self.ValueText.canvas.scaleFactor
        local distance = math.abs(localPoint.x * scale - charPos.x)

        if distance < minDistance then
            minDistance = distance
            newCursorPos = i
        end
    end

    self.cursorPos = math.max(0, math.min(#self.inputText, newCursorPos))
    self:updateCursorPosition()
    self:resetCursorBlink()
end


function P:resetCursorBlink()
    self.cursorBlinkTimer = 0
    self.isCursorVisible = true
    self.LineImage.enabled = true
end

function P:updateDisplay(onlyShow)
    local inputText = self.inputText
    local dotIndex = string.find(inputText, "%.")
    if dotIndex and #inputText - dotIndex > 2 then
        local inputNumber = tonumber(inputText)
        inputNumber = math.floor(inputNumber * 100) / 100
        self.ValueText.text = tostring(inputNumber)
    else
        self.ValueText.text = self.inputText
    end

    CU.Canvas.ForceUpdateCanvases()
    self:updateCursorPosition()
    self:resetCursorBlink()
    if onlyShow then
        return
    end
    local valueStr = self.inputText == "" and "0" or self.inputText
    local value = tonumber(valueStr)
    bee.emit("evt_exact_bet_input", {value = value})
end

--移动光标
function P:moveCursor(delta)
    self.cursorPos = math.max(0, math.min(self.cursorPos + delta, #self.inputText))
    self:updateCursorPosition()
    self:resetCursorBlink()
end


function P:inputEvent()
    if self.numKeyMappings then
        for _, kv in ipairs(self.numKeyMappings) do
            if CU.Input.GetKeyDown(kv.key) then
                self:inputValue(kv.ch)
            end
        end
    end

    if CU.Input.GetKeyDown(CU.KeyCode.Period) or CU.Input.GetKeyDown(CU.KeyCode.KeypadPeriod) then
        self:inputPoint()
    end

    if CU.Input.GetKeyDown(CU.KeyCode.Delete) or CU.Input.GetKeyDown(CU.KeyCode.Backspace) then
        self:inputDelete()
    end

    if CU.Input.GetKeyDown(CU.KeyCode.LeftArrow) then
        self:moveCursor(-1)
    end
    if CU.Input.GetKeyDown(CU.KeyCode.RightArrow) then
        self:moveCursor(1)
    end
end

function P:inputValue(value)
    if value == "0" and self.cursorPos == 0 then
        return
    end

    local cacheStr = self.inputText:sub(1, self.cursorPos) .. value .. self.inputText:sub(self.cursorPos + 1)
    local valueStr = self:checkPointValue(cacheStr)
    if valueStr == nil then
        return
    end
    self.inputText = valueStr
    local limit = self:checkLimit()
    if limit then
        if #valueStr == #self.inputText then
            self.cursorPos = self.cursorPos + 1
        end
        if self.cursorPos > #self.inputText then
            self.cursorPos = #self.inputText
        end
    else
        self.cursorPos = self.cursorPos + 1
    end

    -- local value = tonumber(self.inputText)
    -- local maxBet = self:getMaxBB()

    -- if value > maxBet then
    --     value = maxBet
    --     self.inputText = tostring(value)
    --     if #valueStr == #self.inputText then
    --         self.cursorPos = self.cursorPos + 1
    --     end
    -- else
    --     self.cursorPos = self.cursorPos + 1
    -- end
    self:updateDisplay()
end

function P:getMaxBB()
    return SettingModel:isShowBB() and self.betList[#self.betList] / self.bb or self.betList[#self.betList]
end
function P:checkLimit()
    local value = tonumber(self.inputText) or 0
    local maxBet = self:getMaxBB()
    if value > maxBet then
        value = maxBet
        self.inputText = tostring(value)
        return true
    end
    return false
end

function P:inputDelete()
    if self.cursorPos > 0 and self.cursorPos < #self.inputText then
        local cacheStr = string.sub(self.inputText, 1, self.cursorPos - 1) .. string.sub(self.inputText, self.cursorPos + 1)
        
        local pointPos = string.find(cacheStr, "%.")
        if pointPos == 1 then
            return
        end
        local zeroPos = string.find(cacheStr, "0")
        if zeroPos == 1 then
            local cacheValue = tonumber(cacheStr)
            cacheStr = cacheValue > 0 and tostring(cacheValue) or ""
            self.cursorPos = 0
        end

        self.inputText = cacheStr
        local limit = self:checkLimit()
        if not limit then
            self.cursorPos = self.cursorPos - 1
            self.cursorPos = math.max(0, self.cursorPos)
        else
            --self.cursorPos = self.cursorPos - 1
            if #self.inputText < self.cursorPos then
                self.cursorPos = #self.inputText
            end
        end
        self:updateDisplay()
    elseif self.cursorPos == #self.inputText then
        self.inputText = string.sub(self.inputText, 1, self.cursorPos - 1)
        self.cursorPos = self.cursorPos - 1
        self:updateDisplay()
    end
end

function P:clearAllValue()
    self.inputText = ""
    self.cursorPos = 0
    self:updateDisplay()
end

function P:inputPoint()
    local showBB = SettingModel:isShowBB()
    if not showBB then
        return
    end

    if self.inputText == "" then
        return
    end
    if string.find(self.inputText, "%.") then
        return
    end

    local cacheStr = self.inputText:sub(1, self.cursorPos) .. "." .. self.inputText:sub(self.cursorPos + 1)
    local valueStr = self:checkPointValue(cacheStr)
    if valueStr == nil then
        return
    end
    self.inputText = valueStr
    self.cursorPos = self.cursorPos + 1
    self:updateDisplay()
end

function P:setValue(value)
    self.inputText = value
    self.cursorPos = #self.inputText
    self:updateDisplay(true)
end

function P:evt_exact_bet_refresh(data)
    local showBB = SettingModel:isShowBB()
    if showBB then
        local valStr = data.chipStr
        if #valStr >= 2 and string.sub(valStr, -2) == "BB" then
            valStr = string.sub(valStr, 1, -3)
        end
        self:setValue(valStr)
    else
        self:setValue(tostring(data.value))
    end
end

function P:checkPointValue(valueStr)
    local pointPos = string.find(valueStr, "%.")
    if pointPos == nil or (pointPos and pointPos >= #valueStr - 2 and pointPos ~= 1)then
        return valueStr
    end
    return nil
end

function P:onDestroy()
    P.super.onDestroy(self)
    bee.off("evt_exact_bet_refresh", self["evt_exact_bet_refresh"], self)
end

return P