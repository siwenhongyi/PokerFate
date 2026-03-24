local P = class("PKUILayer", UiBlurBase)

function P:onAwake()
    self.LeftTop = self:find("LeftTop")
    self.RightTop = self:find("RightTop")
    self.MenuButton = self:find("MenuButton", self.LeftTop)
    self.SaveButton = self:find("SaveButton", self.LeftTop)
    self.TextBlind = self:find("BlindsInfo/TextBlind", self.LeftTop)
    self.BlindsInfoAllin = self:find("BlindsInfoAllin", self.LeftTop)

    self.ChatButton = self:find("ChatButton")
    self.ColorButton = self:find("ColorButton", self.RightTop)
    self.SideGameTips = self:find("SideGameTips", self.RightTop)
    self.SideGameTips:SetActive(SideGameModel:isPinballUnlock() and not SideGameModel:isShowPinball())

    bee.addClick(self.MenuButton, function()
        if not bee.isInGame() then
            return
        end
        Game:playSound("ui_button_confirm")
        UiManager:showUI("PKMenu")
        bee.logEvent("ingame-menu", GameModel.data:getGameType(), GameModel.data:getRoomId())
    end)

    if self.SaveButton then
        bee.addClick(self.SaveButton, function()
            if PlayerModel:getCurRecord() >= PlayerModel:getRecordNum() then
                GameModel:getReplayList(function(data)
                    if 0 == data.code then
                        if data.list and #data.list > 0 then
                            UiManager:showTip({
                                text = _F("LAB_DEL_PLAYBACK_TIP5", GameModel:getReplayTitle(data.data)),
                                sureStr = _T("LAB_SAVE"),
                                cancelStr = _T("LAB_DEL_PLAYBACK_TIP6"),
                                onSure = function()
                                    GameModel:deleteReplay(data.data.gameid)
                                    self:onBtSaveClick()
                                end,
                                onCancel = function()
                                end,
                            })
                        end
                    end
                end)
                return
            end
            self:onBtSaveClick()
        end)
        
        if LocalStore:getBoolForKey("save_recored_tip" .. PlayerModel:getUid(), false) then
            self:find("Tips", self.SaveButton):SetActive(false)
        end
    end

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
            self.SideGameTips:SetActive(false)
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
        if self.SaveButton then
            self.SaveButton:SetActive(false)
        end
    else
        self:refreshColorButton()
        if self.SaveButton then
            self.SaveButton:SetActive(GameModel.data:isMePlaying())
            self:find("Off", self.SaveButton):SetActive(true)
            self:find("On", self.SaveButton):SetActive(false)
        end
    end
end

function P:refreshGameName()
    if self.BlindsInfoAllin then
        bee.setText(self:find("TextName", self.BlindsInfoAllin), GF.getGameTypeName(GameModel.data:getGameType()))
    end
end

function P:onBtSaveClick()
    local flag = self:find("Off", self.SaveButton).activeSelf
    self:find("Off", self.SaveButton):SetActive(not flag)
    self:find("On", self.SaveButton):SetActive(flag)
    -- GameModel.data:saveRecord()
    self:find("Tips", self.SaveButton):SetActive(false)
    LocalStore:setBoolForKey("save_recored_tip" .. PlayerModel:getUid(), true)
    UiManager:showToast(_T(flag and "LAB_SAVE_GAME_TIP3" or "LAB_DEL_PLAYBACK_TIP4"))
    bee.logEvent("ingame-hand-replay", GameModel.data:getGameType(), GameModel.data:getRoomId(), 1)
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
    if self.SaveButton then
        if GameModel.data:isMePlaying() then
            self.SaveButton:SetActive(true)
        end
    end
    if self.SaveButton then
        self:find("Off", self.SaveButton):SetActive(true)
        self:find("On", self.SaveButton):SetActive(false)
    end
end

function P:evt_WinnerRSP(msg)
    if GuideManager:isInGuide() then
        return
    end
    if self:find("On", self.SaveButton).activeSelf then
        GameModel.data:saveRecord()
    end
end

function P:evt_SelfUserInfoRSP(msg)
    self:refreshColorButton()
end

function P:evt_refreshBlind()
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

