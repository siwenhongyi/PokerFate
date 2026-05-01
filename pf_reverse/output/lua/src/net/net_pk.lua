net = net or {}


-- BTN位信息
function net:DealerInfoRSP(msg)
	if not GameModel.data then return end
	GameModel.data.table_status.gameid = msg.gameid
	GameModel.data:setPlaying(true)
	GameModel.data:setActionIndex(-1)
	GameModel.data:setPotInfo({})
	GameModel.data:setBoardInfo({})
	GameModel.data:setDealerIndex(msg.dealer)
	GameModel.data:setSBIndex(msg.small_blind)
	GameModel.data:setBBIndex(msg.big_blind)
	GameModel.data:resetPlayerInfo(msg.start_info)
	GameModel.data:setDelayRebyChips(0)
	GameModel.data:setShowCardInfo()
	GameModel.data:setTableGameOver(false)
end

-- 发手牌
function net:HandCardRSP(msg)
	if not GameModel.data then return end
	GameModel.data:updateSelfCard(msg)
	GameModel.data:begenDealCard()
	local player = GameModel.data:getMyPlayerInfo()
	if player then
		player.has_card = true
	end
end

-- 轮到某玩家行动
function net:ActionNotifyBRC(msg)
	if not GameModel.data then return end
	if GameModel.data.setActionIndex then
		GameModel.data:setActionIndex(msg.seatid)
	end
	GameModel.data:setCallNeedChip(msg.call_need_chips)
	GameModel.data:setMinChipIn(msg.min_chipin)
	GameModel.data:setMaxChipIn(msg.max_chipin)
	GameModel.data:endDealCard()
	GameModel.data:setAntiActionDt(nil)
	GameModel.data:setLeftActionTime(GameModel.data:getActionTime())
	GameModel.data:setThinkTime(msg.think_time)
end

function net:ActionRSP(msg)
end

-- 某玩家做出行动
function net:ActionBRC(msg)
	if not GameModel.data then return end

	GameModel.data:refreshLastPotNum()
	
	local player = GameModel.data:getPlayer(msg.seatid + 1)
	player.action_type = msg.action_type
	player.bet_change = msg.chips
	player.bet_chip = player.bet_chip + msg.chips
	player.chips = msg.hand_chips
	
	if GF.isFoldAction(msg.action_type) then
		player.is_fold = true
	end

	if msg.chips and GameModel.data.updateMaxBetValue then
		GameModel.data:updateMaxBetValue(msg.chips)
	end
	if GameModel.data:getActionIndex() == msg.seatid + 1 then
		GameModel.data:setActionIndex(-1)
	end
end

-- 下注圈开始
function net:RoundStartBRC(msg)
	if not GameModel.data then return end
	if GameModel.data.resetRoundInfo then
		GameModel.data:resetRoundInfo()
	end
	GameModel.data:setRoundStage(msg.stage)
	
	if msg.board then
		GameModel.data:addBoardInfo(msg.board)
	end
end

-- 下注圈结束
function net:RoundOverBRC(msg)
	if not GameModel.data then return end
	GameModel.data:setPotInfo(msg.pool)
end

-- 手牌结算
function net:WinnerRSP(msg)
	if not GameModel.data then return end
	GameModel.data:setWinnerRSP(msg)
	GameModel.data:setPotInfo({})
	GameModel.data:setRoundStage(POKER_ROUND.FINISH)
	GameModel.data:setActionIndex(-1)
	GameModel.data:setPlaying(false)
end

-- 系统亮牌
function net:ShowHandRSP(msg)
	if GameModel.data then 
		for _, v in ipairs(msg.info) do
			local seatid = v.seatid + 1
			local player = GameModel.data:getPlayer(seatid)
			if player then
				player.has_card = true
				player.is_fold = false

				player.hand_cards = {}
				for i = 1, GameModel.data:getHandCardNum() do
					player.hand_cards[i] = v["card" .. i]
				end
			end
		end
		-- GameModel.data:setRoundStage(POKER_ROUND.FINISH)
	end
end

function net:ShowMyCardRSP(msg)
	if GameModel.data and msg.code == 0 and msg.gameid == GameModel.data:getGameId() then
		GameModel.data:setShowCardInfo(msg.pos, msg.flag)
		if 1 == msg.flag then
			UiManager:showToast(_T("LAB_GAME_018"))
		end
	end
end

function net:ShowMyCardBRC(msg)
	if GameModel.data then 
		for _, v in ipairs(msg.info) do
			local seatid = v.seatid + 1
			local player = GameModel.data:getPlayer(seatid)
			if player then
				player.has_card = true
				player.is_fold = false

				player.hand_cards = v.hand_cards
			end
		end
	end
end

-- 筹码从桌子返回到手里
function net:ChipsBackBRC(msg)
	if GameModel.data then 
		local player = GameModel.data:getPlayer(msg.seatid + 1)
		if player then
			player.chips = player.chips + msg.chips
		end
	end
end

-- 少于2人牌局中断
function net:TableGameOverRSP(msg)
	if not GameModel.data then return end
	GameModel.data:setPlaying(false)
	GameModel.data:setDealerIndex(-1)
	GameModel.data:setActionIndex(-1)
	GameModel.data:setPotInfo({})
	GameModel.data:setBoardInfo({})
	GameModel.data:resetPlayerInfo({})
	GameModel.data:setTableGameOver(true)
end

-- 发现缺牌时重新请求
function net:GetCardsRSP(msg)
	if not GameModel.data then return end
	GameModel.data:setBoardInfo(msg.board_cards)
	GameModel.data:updateSelfCard(msg)
end

function net:AnteBRC(msg)
	if not GameModel.data then return end
	GameModel.data:setIsInAnte(true)
end

function net:LobJackPotRSP(msg)
end

function net:LobJackPotPrizeBRC(msg)
end

function net:LobJackPotConfigRSP(msg)
end

function net:LobJackPotRankRSP(msg)
end

function net:LobJackPotAllRankRSP(msg)
end

function net:LobJackPotRummyRankRSP(msg)
end

function net:LobJackPotRummyInfRSP(msg)
end

function net:LobJackPotRummyDrawRSP(msg)
end

function net:LobJackPotRummyRoomListRSP(msg)
end

function net:PokerGuessHandRSP(msg)
	if 0 == msg.code then
		if not GameModel.data then return end
		GameModel.data:setGuesses(msg.guess_infos)
	elseif -5 == msg.code then
		UiManager:showToast(_T("LAB_CHIP_INSUFFICIENT"))
	else
		print("recMsg_GuessHandRSP", msg.code)
		UiManager:showToast(_T("LAB_GUESS_TIP_2"))
	end
end

function net:PokerGuessHandResultRSP(msg)
	if not GameModel.data then return end
	GameModel.data:setGuessResult(msg)
end

function net:PokerGuessHandRewardBRC(msg)
end

-- {新牌局历史
function net:GetHandsListRSP(msg)
	if 0 ~= msg.code then
		bee.emit("evt_GetHandsListRSP", msg)
	end
end

function net:PayHandRSP(msg)
	if not GameModel.data then return end
	if msg.code == 0 then
	elseif msg.code == -4 then
		M.lackDiamondAlert(true)
	else
	end
end
--}

function net:SetWaitBlindTypeRSP(msg)
	if not GameModel.data then return end

	if msg.code == 0 then
		local player = GameModel.data:getMyPlayerInfo()
		if player then
			player.wait_blind_type = msg.wait_blind_type
		end
	end
end

function net:NoticeRebyRSP(msg)
	if not GameModel.data then return end

	if GameModel.data:isSNG() or GameModel.data:isMTT() then
		return
	end

	if msg.type == 1 then
		local player = GameModel.data:getPlayer(msg.seatid + 1)
		if player then
			player.reby_left_time = msg.reby_left_time or 60
			player.reby_left_time_st = os.time()
		end
	end
end

function net:RebyBRC(msg)
	if not GameModel.data then return end
	local player = GameModel.data:getPlayer(msg.seatid + 1)
	if player then
		player.chips = player.chips + msg.chips
		player.reby_left_time, player.reby_left_time_st = 0, nil
	end
end

function net:SetRebyRSP(msg)
	if not GameModel.data then return end
	if msg.code == 0 then
		if GameModel.data:isPlaying() then
			UiManager:showToast(_T("LAB_GAME_029"))
		else
			UiManager:showToast(_F("LAB_GAME_030", _N(msg.reby_chips)))
		end
	end
end

function net:PreActionRSP(msg)
	if not GameModel.data then return end

	if msg.code == 0 then
		GameModel.data:setPreActionDatas(msg.type, msg.chips)
	end
end

function net:PreActionResetRSP(msg)
	if not GameModel.data then return end

	GameModel.data:setPreActionDatas(0, 0)
end

function net:BlindStatusBRC(msg)
	if not GameModel.data then return end
	GameModel.data:setBlindStatus(msg)
end