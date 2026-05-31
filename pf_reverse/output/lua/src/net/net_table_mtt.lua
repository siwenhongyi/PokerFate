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
end

function net:MttWinRoundBRC(msg)
	if not GameModel.data then return end
	GameModel.data.room_info.mtt_round = 2
end

function net:MttFinalRoundBRC(msg)
	if not GameModel.data then return end
	GameModel.data.room_info.mtt_round = 3
end