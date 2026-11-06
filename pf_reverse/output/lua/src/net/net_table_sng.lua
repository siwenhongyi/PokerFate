net = net or {}

function net:SngWaitingOtherEnterBRC(msg)
    TournamentModel:setMatchingSngInfo(msg.roomid, msg.num, msg.name, msg.tour_id)

    TournamentModel:refreshMatchingTip()

    if msg.num == 0 then
        UiManager:showToast(_T("LAB_TOURNAMENT_SNG_INFO19"))
    end
end

function net:SngMatchPlayerNumRSP(msg)
    TournamentModel:setMatchingSngInfo(msg.roomid, msg.num, msg.name, msg.tour_id)
    
    TournamentModel:refreshMatchingTip()
end

function net:SngRoomStartBRC(msg)
    TournamentModel:setMatchingSngInfo(0, 0, {}, 0)
end