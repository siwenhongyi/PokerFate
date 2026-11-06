local P = class("TournamentMTTAddOnTip", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    local Tips2 = self:find("LeftBottom/Tips2", self.AnimRoot)
    self.TextTip = self:find("TextTip", Tips2)
    self.TextTime = self:find("TextTime", Tips2)
    self.CloseButton = self:find("CloseButton", Tips2)

    bee.addClick(self.CloseButton, function()
        self:hideUI()
    end)
end

function P:onShow()
    self:refreshDeadline()
    bee.setText(self.TextTip, _F("LAB_TOURNAMENT_MTT_INFO131", GameModel.data and (GameModel.data.room_info.addon_selection_time / 60) or 0))

    -- 每秒刷新倒计时
    self:schedule(1, function()
        self:refreshDeadline()
    end)
end

function P:refreshDeadline()
    if not GameModel.data then
        bee.setText(self.TextTime, "")
        return
    end

    local dt = GameModel.data:getAddOnBuyinRemainTime()
    if dt <= 0 then
        dt = 0
    end

    bee.setText(self.TextTime, _F("LAB_TOURNAMENT_MTT_INFO94", TimeHelp:getTimeStrHMS(dt)))
    
    if dt <= 0 then
        self:hideUIForce()
    end
end


return P