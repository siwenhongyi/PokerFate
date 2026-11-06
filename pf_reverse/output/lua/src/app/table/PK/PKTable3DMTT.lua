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
    elseif self.data.table_status.wait_sync and self.data.table_status.wait_sync > 0 and self.data:isPlaying() then
    	UiManager:showUI("TournamentIngamePopupNotice", {is_notice = true})
        UiManager:hideUI("TournamentIngamePopupRest")
    else
        UiManager:hideUI("TournamentIngamePopupRest")
        UiManager:hideUI("TournamentIngamePopupNotice")
    end

    local dt = self.data:getAddOnBuyinRemainTime()
    if dt > 0 then
        if GameModel.data:isPlaying() then
			UiManager:showUI("TournamentMTTAddOnTip")
		else
            TournamentModel:showAddon()
		end
    else
        UiManager:hideUI("TournamentMTTAddOnTip")
        UiManager:hideUI("TournamentMTTAddOn")
    end
end

function P:refreshWaitingPlayerTip()
    self.BgWaitBBTip:SetActive(false)
    self.BgPayBBTip:SetActive(false)

	if self.data:isInObserve() then
		self:showTips()
		return
	end
    
    if not self.data:isMttStart() then
        local dt = math.floor(self.data.room_info.mtt_start_time - bee.getServerTime())
        if dt > 0 then
            self:showTips(_T("LAB_TOURNAMENT_MTT_INFO125") .. " " .. TimeHelp:getTimeStr(dt))
            if self._tagMttStartDt then
                scheduler:removeTag(self._tagMttStartDt)
                self._tagMttStartDt = nil
            end
            self._tagMttStartDt = bee.once(1, function()
                if not bee.isNull(self.node) then
                    self._tagMttStartDt = nil
                    self:refreshWaitingPlayerTip()
                end
            end)
        else
            self:showTips("LAB_TOURNAMENT_MTT_INFO125")
        end
        return
    end
    if self.data.table_status.is_wait_join then
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
    if msg.type > 0 then
        UiManager:showUI("TournamentIngamePopupNotice", {is_notice = true})
    end
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
    -- 结算界面
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

    -- 整理奖励列表，区分角色/皮肤/其他
    local showRewardList = {}
    local showNewList = {}

    if msg.reward then
        for _, v in ipairs(msg.reward) do
            local d = tpl_props[v.item_id]
            if d then
                local propType = d.type
                if propType == GPropKind.RoleCard then
                    if not CharacterModel:getRole(d.mapId) then
                        local item = {
                            major_type = GMajorType.ROLE,
                            id = d.mapId,
                            new = true,
                        }
                        table.insert(showNewList, item)
                    end
                elseif propType == GPropKind.SkinCard then
                    if not CharacterModel:isOwnedSkin(d.mapId) then
                        local item = {
                            major_type = GMajorType.ROLE_SKIN,
                            id = d.mapId,
                            new = true,
                        }
                        table.insert(showNewList, item)
                    end
                elseif propType == GPropKind.MonthlyCard then
                    local md = tpl_monthly_card[d.mapId]
                    if md then
                        for i = 1, #md.activate_rewards - 1, 2 do
                            table.insert(showRewardList, {item_id = md.activate_rewards[i], item_num = md.activate_rewards[i + 1]})
                        end
                    end
                end
            end
        end
    end

    -- 弹出奖励界面
    if next(showRewardList) then
        UiManager:showUI("BackpackClaimResult", {items = showRewardList, hideCb = function()
            if next(showNewList) then
                UiManager:showUI("GachaResultShow", {showList = showNewList, closeCb = function()
                end})
            end
        end})
    elseif next(showNewList) then
        UiManager:showUI("GachaResultShow", {showList = showNewList, closeCb = function()
        end})
    end
end

function P:evt_ChangeTableRSP(msg)
    P.super.evt_ChangeTableRSP(self, msg)

    if self.data:isInObserve() then
        if not self._inObMainViewStandUp then
            if 1 == msg.observer_change_type then
                UiManager:showToast(_T("LAB_TOURNAMENT_MTT_INFO103"))
            elseif 2 == msg.observer_change_type then
                UiManager:showToast(_T("LAB_TOURNAMENT_MTT_INFO105"))
            end
        end
    elseif msg.is_assign_table then
        UiManager:showToast(_T("LAB_TOURNAMENT_MTT_INFO62"))
    end
    self._inObMainViewStandUp = nil
end

function P:evt_StandUpBRC(msg)
    P.super.evt_StandUpBRC(self, msg)
    if self.data:isInObserve() then
        if msg.reason == "eliminate" and msg.seatid + 1 == self.data:getObserveSeatid() then
            self._inObMainViewStandUp = true
            UiManager:showToast(_T("LAB_TOURNAMENT_MTT_INFO104"))
        end
    end
end

function P:evt_AddonBRC(msg)
	if msg then
        local seatid = msg.seatid + 1
        local player = self.data:getPlayer(seatid)
        if player then
            self.seatController[seatid]:refreshChip(player)
        end
	end
end

return P