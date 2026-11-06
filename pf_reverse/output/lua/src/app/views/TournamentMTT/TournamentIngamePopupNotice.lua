local P = class("TournamentIngamePopupNotice", UiBase)

function P:onAwake()
    self.Bottom = self:find("AnimRoot/Bottom")
    self.Notice = self:find("Notice", self.Bottom)
end

function P:onShow()
    local data = GameModel.data
    if 1 == data.table_status.wait_sync then
        bee.setText(self:find("TextTitle", self.Notice), _F("LAB_TOURNAMENT_MTT_INFO23"))
        bee.setText(self:find("TextTip", self.Notice), _F("LAB_TOURNAMENT_MTT_INFO24"))
    elseif 2 == data.table_status.wait_sync then
        bee.setText(self:find("TextTitle", self.Notice), _F("LAB_TOURNAMENT_MTT_INFO54"))
        bee.setText(self:find("TextTip", self.Notice), _F("LAB_TOURNAMENT_MTT_INFO55"))
    else
        self:once(-1, function()
            self:hideUI()
        end)
    end
end

function P:evt_DealerInfoRSP()
    self:hideUIForce()
end

function P:evt_MttFinalRoundBRC()
    self:hideUIForce()
end

return P