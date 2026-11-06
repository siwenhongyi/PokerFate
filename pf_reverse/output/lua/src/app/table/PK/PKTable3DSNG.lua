local P = class("PKTable3DSNG", require("app.table.PK.PKTable"))

function P:refreshUI()
	P.super.refreshUI(self)
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