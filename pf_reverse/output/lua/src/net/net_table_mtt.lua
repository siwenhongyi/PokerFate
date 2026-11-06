net = net or {}

function net:MttBreakTimeBRC(msg)
	if not GameModel.data then return end
	local dt = GameModel.data:getBlindUpTime()
	GameModel.data.room_info.break_left_time = msg.break_left_time
	GameModel.data.break_left_time_st = os.time()
	GameModel.data.room_info.upblind_time = dt
end

function net:MttSyncDealBRC(msg)
	if not GameModel.data then return end

	GameModel.data.table_status.wait_sync = msg.type
end

function net:MttBubbleRoundBRC(msg)
	if not GameModel.data then return end

	GameModel.data.room_info.mtt_round = 1

	if not GameModel.data:isInOpenObserve() then
		GameModel.data.room_info.src_room_mtt_round = 1
	end
end

function net:MttWinRoundBRC(msg)
	if not GameModel.data then return end
	GameModel.data.room_info.mtt_round = 2

	if not GameModel.data:isInOpenObserve() then
		GameModel.data.room_info.src_room_mtt_round = 2
	end
end

function net:MttFinalRoundBRC(msg)
	if not GameModel.data then return end
	GameModel.data.room_info.mtt_round = 3

	if not GameModel.data:isInOpenObserve() then
		GameModel.data.room_info.src_room_mtt_round = 3
	end
end

function net:SrcRoomMttRoundChangeBRC(msg)
	if not GameModel.data then return end
	GameModel.data.room_info.src_room_mtt_round = msg.src_room_mtt_round
end

function net:NoticeAddonBRC(msg)
	if not GameModel.data then return end
	if msg.type == 1 then
		GameModel.data:setAddOnBuyinRemainTime(msg.addon_left_sec)
		GameModel.data:refreshBlindLevel()

		if GameModel.data:isPlaying() then
			UiManager:showUI("TournamentMTTAddOnTip")
		else
            TournamentModel:showAddon()
		end
	else
		GameModel.data:setAddOnBuyinRemainTime()
		UiManager:hideUI("TournamentMTTAddOn")
		UiManager:hideUI("TournamentMTTAddOnBuyin")
		UiManager:hideUI("TournamentMTTAddOnTip")
		UiManager:hideUI("TournamentMTTRebuy")

		UiManager:showToast(_T("LAB_TOURNAMENT_MTT_INFO98"))
	end
end

function net:AddonBRC(msg)
	if not GameModel.data then return end

	local player = GameModel.data:getPlayer(msg.seatid + 1)
	if player then
		player.chips = player.chips + msg.chips
		if player.uid == PlayerModel:getUid() then
			GameModel.data.room_status.left_addon_times = GameModel.data.room_status.left_addon_times - 1
		end
	end
end