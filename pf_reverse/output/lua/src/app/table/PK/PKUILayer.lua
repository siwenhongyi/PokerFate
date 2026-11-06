local P = class("PKUILayer", UiBlurBase)

function P:onAwake()
    self.LeftTop = self:find("LeftTop")
    self.RightTop = self:find("RightTop")
    self.MenuButton = self:find("MenuButton", self.LeftTop)
    self.NetworkButton = self:find("NetworkButton", self.LeftTop)
    self.AssistantButton = self:find("AssistantButton", self.LeftTop)
    self.TextBlind = self:find("BlindsInfo/TextBlind", self.LeftTop)
    self.BlindsInfoAllin = self:find("BlindsInfoAllin", self.LeftTop)

    self.IntensityButton = self:find("IntensityButton")
    self.ChatButton = self:find("ChatButton")
    self.ColorButton = self:find("ColorButton", self.RightTop)

    bee.addClick(self.MenuButton, function()
        if not bee.isInGame() then
            return
        end
        Game:playSound("ui_button_confirm")
        UiManager:showUI("PKMenu")
        bee.logEvent("ingame-menu", GameModel.data:getGameType(), GameModel.data:getRoomId())
    end)

    bee.addClick(self.NetworkButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("Loginline")
        bee.logEvent("table-route-access", GameModel.data:getGameType(), GameModel.data:getRoomId())
    end)

    bee.addClick(self.AssistantButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("IngameAssistant")
        bee.logEvent("ingame-helper", GameModel.data:getGameType(), GameModel.data:getRoomId())
    end)
                                                                                           
    bee.addClick(self.IntensityButton, function ()
        Game:playSound("ui_button_confirm")
        --UiManager:showUI("IngameIntensity")
        local intensityUI = ResManager:GetGameObject("views/table/IngameIntensity")
        if intensityUI then
            intensityUI.transform:SetParent(self.transform, false)
        end
    end)

    bee.addClick(self.ChatButton, function()
        Game:playSound("ui_button_confirm")
        local ui = UiManager:getUI("TableChatLayer")
        if ui and not bee.isNull(ui.node) then
            ui.transform.localPosition = bee.v3zero
        else
            UiManager:showUI("TableChatLayer", {hideCb = function()
                if not bee.isNull(self.ChatButton) then
                    self.ChatButton:SetActive(true)
                end
            end})
            self.ChatButton:SetActive(false)
            bee.emit("evt_clickIngameChatEvent")
        end
        bee.logEvent("ingame-chat", GameModel.data:getGameType(), GameModel.data:getRoomId())
    end)

    bee.addClick(self.ColorButton, function()
        Game:playSound("ui_button_confirm")
        local ui = UiManager:getUI("SideGameView")
        if ui and not bee.isNull(ui.node) then
            ui.transform.localPosition = bee.v3zero
        else
            UiManager:showUI("SideGameView")
        end
        bee.logEvent("ingame-colorgame", GameModel.data:getGameType(), GameModel.data:getRoomId())
    end)
end

function P:onShow()
    self:evt_refreshBlind()
    self:refreshGameName()

    if GuideManager:isInGuide() then
        self.ChatButton:SetActive(false)
        self.ColorButton:SetActive(false)
        self.MenuButton:SetActive(false)
        if self.NetworkButton then self.NetworkButton:SetActive(false) end
        if self.AssistantButton then self.AssistantButton:SetActive(false) end
        if self.IntensityButton then self.IntensityButton:SetActive(false) end
    else
        self:refreshColorButton()
        self:evt_switch_intensity()
    end

    QuickByModel:addButtonItem(self.uiName, self:find("Buttons/QuickByButton", self.RightTop))
    QuickByModel:addLimitButtonItem(self.uiName, self:find("Buttons/LimitPackageButton", self.RightTop))

    if GameModel.data and GameModel.data:isInObserve() then
        self.ChatButton:SetActive(false)
    end
    if self.Observe then
        self.Observe:SetActive(GameModel.data:isOpenObserve())
    end
end

function P:refreshGameName()
    if self.BlindsInfoAllin then
        bee.setText(self:find("TextName", self.BlindsInfoAllin), GF.getGameTypeName(GameModel.data:getGameType()))
    end
end

function P:refreshColorButton()
    if not GuideManager:isInGuide() and self.ColorButton then
        self.ColorButton:SetActive(SettingModel:isColorGameUnlock())
    end
end

function P:evt_HandCardRSP()
    if GuideManager:isInGuide() then
        return
    end
end

function P:evt_WinnerRSP(msg)
    if GuideManager:isInGuide() then
        return
    end
end

function P:evt_SelfUserInfoRSP(msg)
    self:refreshColorButton()
end

function P:evt_refreshBlind()
    if GameModel.data:isTrainingGame() then
	    bee.setText(self.TextBlind, _F("LAB_BLINDS", _T("LAB_GAME_053")))
        return
    end
	local sb = GameModel.data:getSmallBlind()
	local bb = GameModel.data:getBigBlind()
    if GameModel.data:isAllinOrFold() then
        local ante = GameModel.data:getAnte()
        bee.setText(self.TextBlind, _F("LAB_BLINDS", _N(sb) .. "/" .. _N(bb) .. " (" .. _N(ante) .. ")"))
    else
	   bee.setText(self.TextBlind, _F("LAB_BLINDS", _N(sb) .. "/" .. _N(bb)))
    end
end

function P:evt_guide_show_menu()
    self.MenuButton:SetActive(true)
end

function P:evt_gameBlur(flag, name)
    self:onUiBlur(flag, name)
end

function P:evt_lan_mod()
    self:evt_refreshBlind()
    self:refreshGameName()
end

function P:evt_switch_intensity()
    local flag = SettingModel:isShowIntensity(GameModel.data:getGameType())
    self.IntensityButton:SetActive(flag)
    
    if GameModel.data:isInObserve() then
        return
    end

    if GF.isSNG(GameModel.gameType) then
        return
    end

    if flag and LocalStore:isTagValid("ingame_intensity_tip" .. PlayerModel:getUid()) then
        self:once(0.05, function ()
            UiManager:showUI("CommonTextTipRL", {text = _T("LAB_GAME_079"), target = self:find("Point", self.IntensityButton)})
        end)
    end
end

function P:evt_shortcutOpenMenu()
    local btn = self.MenuButton:GetComponent("Button")
    btn.onClick:Invoke()
end

-- function P:evt_reshowChatLayer()
--     local btn = self.ChatButton:GetComponent("Button")
--     btn.onClick:Invoke()
-- end

-- function P:evt_swtichEmojiTipView(data)
--     self.ChatButton:SetActive(not data.sw)
-- end

return P