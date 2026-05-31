local P = class("TournamentIngamePopupTipRest", UiBase)

function P:onAwake()
    self.LeftBottom = self:find("AnimRoot/LeftBottom")

    self.RestTip = self:find("Rest", self.LeftBottom)

    bee.addClick(self:find("CloseButton", self.LeftBottom), function()
        self:hideUI()
    end)
end

function P:onShow()
    local data = GameModel.data
    
    bee.setText(self:find("TextTip", self.RestTip), _F("LAB_TOURNAMENT_MTT_INFO17", (data.room_info.break_duration or 0) / 60))
    
    -- self:once(2, function()
    --     self:hideUI()
    -- end)

    UiManager:hideUI("TournamentIngamePopupTipBubble")
    UiManager:hideUI("TournamentIngamePopupTipSuccess")
end

function P:evt_DealerInfoRSP()
    self:hideUIForce()
end

function P:evt_MttFinalRoundBRC()
    self:hideUIForce()
end

return P