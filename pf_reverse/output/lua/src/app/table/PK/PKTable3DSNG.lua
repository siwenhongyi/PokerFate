local P = class("PKTable3DSNG", require("app.table.PK.PKTable"))

function P:refreshUI()
	P.super.refreshUI(self)

    self:refreshMatch()
end

function P:refreshMatch()
    local seatNum = self.data:getSeatNum()
    if not self.data:isSngStart() and self.data:getOnSeatCount() < seatNum 
        or (self.data.room_info.room_stage == "Wait") 
        or (self.data.room_info.room_stage == "PreStart") then
        UiManager:showUI("TournamentSNGMatchmaking")
    else
        UiManager:hideUIForce("TournamentSNGMatchmaking")
    end
end

function P:evt_SngRoomStartBRC(msg)
end

function P:evt_SngSpinBRC(msg)
    UiManager:hideUIForce("TournamentSNGMatchmaking")
    UiManager:showUI("TournamentPrizePoolDraw", {data = msg})
end

function P:evt_UserSngOverRSP(msg)
    if msg.rank == 1 then
        UiManager:showUI("TournamentSNGShowdownWin", {data = msg})
    else
        UiManager:showUI("TournamentSNGShowdownLose", {data = msg})
    end
end

return P