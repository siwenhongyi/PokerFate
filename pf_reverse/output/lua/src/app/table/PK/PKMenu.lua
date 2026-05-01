local P = class("PKMenu", UiBase)

function P:onAwake()
    self.Menu = self:find("Menu")
    -- self.ButtonItem = self:find("ButtonItem")
    -- self.ButtonItem:SetActive(false)

    self.ByinButton = self:find("ByinButton", self.Menu)
    self.SwitchButton = self:find("SwitchButton", self.Menu)
    self.NextExitButton = self:find("NextExitButton", self.Menu)
    self.CancelExitButton = self:find("CancelExitButton", self.Menu)

    bee.addClick(self:find("ImageBg"), function()
        self:hideUI()
    end)

    bee.addClick(self:find("HistoryButton", self.Menu), function() self:onBtHistory() end)
    bee.addClick(self.ByinButton, function() self:onBtByin() end)
    bee.addClick(self:find("SettingButton", self.Menu), function() self:onBtSetting() end)
    bee.addClick(self:find("RulesButton", self.Menu), function() self:onBtRules() end)
    bee.addClick(self.NextExitButton, function() self:onBtNextExit() end)
    bee.addClick(self.CancelExitButton, function() self:onBtCancelExit() end)
    bee.addClick(self:find("ExitButton", self.Menu), function() self:onBtExit() end)
    bee.addClick(self.SwitchButton, function() self:onBtSwitch() end)
end

function P:onShow()
    self:refreshUI()

    self:once(-1, function()
        if not bee.isInGame() then
            self:hideUIForce()
        end
    end)
end

function P:refreshUI()
    if GameModel.data then
        self.NextExitButton:SetActive(not GameModel.data:getDelayLeaveRoom())
        self.CancelExitButton:SetActive(GameModel.data:getDelayLeaveRoom())

        if GameModel.data:isAllinOrFold() or GameModel.data:isSNG() then
            self.ByinButton:SetActive(false)
        else
            self.ByinButton:SetActive(true)
        end

        if GameModel.data:isSNG() then
            self.SwitchButton:SetActive(false)
            self.NextExitButton:SetActive(false)
            self.CancelExitButton:SetActive(false)
        else
            if GameModel.data:isFriendsRoom() then
                self.SwitchButton:SetActive(false)
            end
        end
    end
end

function P:onBtHistory()
    local ui = UiManager:getUI("IngameHistory")
    if ui and not bee.isNull(ui.node) then
        ui.transform.localPosition = bee.v3zero
    else
        UiManager:showUI("IngameHistory")
    end
    self:hideUI()

    bee.logEvent("ingame-menu-history", GameModel.data:getGameType(), GameModel.data:getRoomId())
end

function P:onBtByin()
    self:hideUI()
    if GameModel.data:isFriendsRoom() then
        local player = GameModel.data:getMyPlayerInfo()
        if not player then
            return
        end
        if player.chips >= GameModel.data:getMaxBuyIn() then
            UiManager:showToast(_T("LAB_GAME_028"))
            return
        end
        UiManager:showUI("FriendsRoomByin", {isSetReby = true})
    else
        local data = GF.getTableDataBySB(GameModel.data:getGameType(), GameModel.data:getSmallBlind())
        if data then
            local player = GameModel.data:getMyPlayerInfo()
            if not player then
                return
            end
            if player.chips >= data.max_byin then
                UiManager:showToast(_T("LAB_GAME_028"))
                return
            end
            UiManager:showUI("LobbyByinDialog", {data = data, isSetReby = true})
        end
    end
end

function P:onBtSetting()
    -- if GameModel.data:isAllinOrFold() then
    --     local ui = UiManager:getUI("AllinSettings")
    --     if ui and not bee.isNull(ui.node) then
    --         ui.transform.localPosition = bee.v3zero
    --     else
    --         UiManager:showUI("AllinSettings")
    --     end
    -- else
    -- end
    local ui = UiManager:getUI("Setting")
    if ui and not bee.isNull(ui.node) then
        ui.transform.localPosition = bee.v3zero
    else
        UiManager:showUI("Setting")
    end
    self:hideUI()

    bee.logEvent("ingame-menu-setting", GameModel.data:getGameType(), GameModel.data:getRoomId())
end

function P:onBtRules()
    local name = "IngameRules"
    if GameModel.data:isSNG() then
        name = "TournamentSNGRules"
    end
    local ui = UiManager:getUI(name)
    if ui and not bee.isNull(ui.node) then
        ui.transform.localPosition = bee.v3zero
    else
        UiManager:showUI(name, {data = GameModel.data.room_info})
    end
    self:hideUI()

    bee.logEvent("ingame-menu-rules", GameModel.data:getGameType(), GameModel.data:getRoomId())
end

function P:onBtSwitch()
    if not bee.checkCd("PKMenu_onBtSwitch", 3) then
        UiManager:showToast(_T("ERR_MSG_FREQUENT"))
    else
        GameModel:switchTable(true)
    end
    self:hideUI()
    bee.logEvent("ingame-menu-switch", GameModel.data:getGameType(), GameModel.data:getRoomId())
end

function P:onBtNextExit()
    Net:sendReq("pb.DelayLeaveRoomREQ", {flag = true})
    self:hideUI()
    bee.logEvent("ingame-menu-exit-next-hand", GameModel.data:getGameType(), GameModel.data:getRoomId())
end

function P:onBtCancelExit()
    Net:sendReq("pb.DelayLeaveRoomREQ", {flag = false})
    self:hideUI()
end

function P:onBtExit()
    if GameModel.data:isPlaying() and GameModel.data:isMePlaying() and not GameModel.data:isMeFold() then
        UiManager:showTip({
            text = GameModel.data:isSNG() and _T("LAB_TOURNAMENT_SNG_INFO31") or _T("LAB_SURE_EXIT"),
            onSure = function()
                Net:sendReq("pb.LeaveRoomREQ", {})
            end
        })
        bee.logEvent("ingame-menu-exit-ongoing", GameModel.data:getGameType(), GameModel.data:getRoomId())
    else
        Net:sendReq("pb.LeaveRoomREQ", {})
        bee.logEvent("ingame-menu-exit-before", GameModel.data:getGameType(), GameModel.data:getRoomId())
    end
    self:hideUI()
end

function P:addItem(txt, cb)
    local item = CU.GameObject.Instantiate(self.ButtonItem, self.BgMenu.transform, false)
    item:SetActive(true)
    bee.setText(self:find("Text", item), txt)
    bee.addClick(item, cb)
end

function P:evt_gameBlur(flag, name)
    if flag then
        self:hideUIForce()
    end
end

return P