local P = class("TournamentIngamePopupRest", UiBase)

function P:onAwake()
    self.Bottom = self:find("AnimRoot/Bottom")
    self.Rest = self:find("Rest", self.Bottom)
end

function P:onShow()
    UiManager:hideUIForce("TournamentIngamePopupTipRest")
    local data = GameModel.data

    local dt = (data.room_info.break_left_time or 0) - (os.time() - (data.break_left_time_st or 0))
    bee.setText(self:find("TextTime", self.Rest), _F("LAB_TOURNAMENT_MTT_INFO18", TimeHelp:getTimeStrHMS(dt)))

    self:schedule(1, function()
        dt = (data.room_info.break_left_time or 0) - (os.time() - (data.break_left_time_st or 0))
        if dt <= 0 then
            dt = 0
            self:hideUI()
        end
        bee.setText(self:find("TextTime", self.Rest), _F("LAB_TOURNAMENT_MTT_INFO18", TimeHelp:getTimeStrHMS(dt)))
    end)
end

function P:evt_DealerInfoRSP()
    self:hideUIForce()
end

function P:evt_MttFinalRoundBRC()
    self:hideUIForce()
end

return P