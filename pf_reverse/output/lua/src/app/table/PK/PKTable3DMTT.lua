local P = class("PKTable3DMTT", require("app.table.PK.PKTable"))

function P:refreshUI()
	P.super.refreshUI(self)

    if self.data.room_info.break_left_time and self.data.room_info.break_left_time > 0 then
        if not self.data:isPlaying() then
            UiManager:showUI("TournamentIngamePopupRest", {is_rest = true})
        else
            UiManager:hideUI("TournamentIngamePopupRest")
        end
        UiManager:hideUI("TournamentIngamePopupNotice")
    elseif self.data.table_status.wait_sync and self.data.table_status.wait_sync > 0 then
    	UiManager:showUI("TournamentIngamePopupNotice", {is_notice = true})
        UiManager:hideUI("TournamentIngamePopupRest")
    else
        UiManager:hideUI("TournamentIngamePopupRest")
        UiManager:hideUI("TournamentIngamePopupNotice")
    end
end

function P:refreshWaitingPlayerTip()
    self.BgWaitBBTip:SetActive(false)
    self.BgPayBBTip:SetActive(false)

    if not self.data:isMttStart() then
        self:showTips("LAB_TOURNAMENT_MTT_INFO14")
        return
    end

	if self.data:isInObserve() then
		self:showTips()
		return
	end
    
    local tip = nil
    if self.data:isMeOnSeat() then
        if self.data:getOnSeatNum() == 1 then
            tip = "LAB_WAIT_FOR_PLAYER"
        end
    end
    self:showTips(tip)
end

function P:evt_MttBreakSoonBRC(msg)
    UiManager:showUI("TournamentIngamePopupTipRest", {is_rest_tip = true})
end

function P:evt_MttBreakTimeBRC(msg)
    UiManager:showUI("TournamentIngamePopupRest", {is_rest = true})
end

function P:evt_MttSyncDealBRC(msg)
    UiManager:showUI("TournamentIngamePopupNotice", {is_notice = true})
end

function P:evt_MttBubbleRoundBRC(msg)
    UiManager:showUI("TournamentIngamePopupTipBubble", {is_bubble_tip = true, data = msg})
end

function P:evt_MttWinRoundBRC(msg)
    UiManager:showUI("TournamentIngamePopupTipSuccess", {is_success_tip = true, data = msg})
end

function P:evt_MttFinalRoundBRC(msg)
    UiManager:showUI("TournamentIngameCount", {data = msg})
end

function P:evt_UserMttOverRSP(msg)
    if not msg.is_enter_win_round and msg.rank ~= 0 then
        UiManager:showUI("TournamentMTTShowdownLose", {data = msg})
    elseif msg.rank <= 3 then
        UiManager:showUI("TournamentMTTShowdown02", {data = msg})
    else
        UiManager:showUI("TournamentMTTShowdown", {data = msg})
    end
    UiManager:hideUI("TournamentIngamePopupRest")
    UiManager:hideUI("TournamentIngamePopupNotice")

    UiManager:hideUI("TournamentIngamePopupTipRest")
    UiManager:hideUI("TournamentIngamePopupTipBubble")
    UiManager:hideUI("TournamentIngamePopupTipSuccess")
end

function P:evt_ChangeTableRSP(msg)
    P.super.evt_ChangeTableRSP(self, msg)

    if not self.data:isInObserve() and not self.data.room_info.is_in_final_table then
        UiManager:showToast(_T("LAB_TOURNAMENT_MTT_INFO62"))
    end
end

return P