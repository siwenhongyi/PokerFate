local P = class("PKUILayer", UiBlurBase)

function P:onAwake()
    self.LeftTop = self:find("LeftTop")
    self.RightTop = self:find("RightTop")
    self.MenuButton = self:find("MenuButton", self.LeftTop)
    self.NetworkButton = self:find("NetworkButton", self.LeftTop)
    self.TextBlind = self:find("BlindsInfo/TextBlind", self.LeftTop)
    self.BlindsInfoAllin = self:find("BlindsInfoAllin", self.LeftTop)

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
    else
        self:refreshColorButton()
    end

    QuickByModel:addButtonItem(self.uiName, self:find("QuickByButton", self.RightTop))
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
	bee.setText(self.TextBlind, _F("LAB_BLINDS", _N(sb) .. "/" .. _N(bb)))
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

return P