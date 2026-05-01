
local P = class("PKData", require("app.table.data.BaseData"))

function P:ctor(params, scene)
	self.max_bet_value = 0
	P.super.ctor(self, params, scene)
	self.hand_history = {}
	-- self.save_gameids = {}
end

function P:assignRoomInfo(params)
	P.super.assignRoomInfo(self, params)
	self.actionSt = os.time()

	self:setGuesses(self.playing_status.poker_guess_infos)
	self:setPreActionDatas(self.playing_status.pre_action_type, self.playing_status.pre_action_chips)
end

function P:updateRoomInfo()
	P.super.updateRoomInfo(self)
	
	self:setBoardInfo(self.table_status.board)
	self:setPotInfo(self.table_status.pool)
	self:initSelfHandCard()
	self:calMaxBetValue()

	if self.table_status.action_idx >= 0 then
		local info = self:getPlayer(self.table_status.action_idx + 1)
		if not info or (info.action_type ~= POKER_ACTION.WAIT 
			and info.action_type ~= POKER_ACTION.SB
			and info.action_type ~= POKER_ACTION.BB
			and info.action_type ~= POKER_ACTION.FORCE_BB
		)
		then
			self.table_status.action_idx = -1
		end
	end
end

function P:getRebuyRemainTime(seatid)
	local dt = 0
	local player = self:getPlayer(seatid)
	if player and player.reby_left_time and player.reby_left_time > 0 and player.reby_left_time_st then
		dt = player.reby_left_time - os.time() + player.reby_left_time_st
		if dt < 0 then
			dt = 0
		end
	end
	return dt
end

function P:clearPlayerCards()
	for _, info in ipairs(self:getAllPlayers()) do
		info:clearCard()
	end
end

function P:isPlayerPlaying(seatid)
	local player = self:getPlayer(seatid)
	return player and (player.has_card or (player.hand_cards and #player.hand_cards > 0))
end

function P:isMePlaying()
	local me = self:getMyPlayerInfo()
	return me and (me.has_card or (me.hand_cards and #me.hand_cards > 0))
end

function P:isMeFold()
	local me = self:getMyPlayerInfo()
	return me and me.is_fold
end

function P:isMeAllin()
	local me = self:getMyPlayerInfo()
	return me and me.chips == 0
end

function P:isAllAllin()
	if not self:isPlaying() then
		return false
	end
	local num, hasCardNum = 0, 0
	for _, v in pairs(self.player_info) do
		if v.on_seat and not v.is_fold and v.has_card then
			if v.has_card and not v.hand_cards or #v.hand_cards <= 0 or v.hand_cards[1] == 0 then
				return false
			end
			hasCardNum = hasCardNum + 1
			if v.chips > 0 then
				num = num + 1
			end
		end
	end
	return num <= 1 and hasCardNum >= 2
end

function P:standUpCleanSeat(index)
	P.super.standUpCleanSeat(self, index)
	local old = self:getPlayer(index)
	self.player_old_info[old.uid] = old
	local player = require("app.table.data.PlayerData"):create(index)
	self.player_info[index] = player

	if old.bet_chip > 0 then
		-- player:resetBriefInfo()
		player.is_fold = old.is_fold
		-- player.on_seat = false
		player.chips = 0
		player.bet_chip = old.bet_chip
		-- player.action_type = POKER_ACTION.NONE
		-- player.last_action_type = POKER_ACTION.NONE
		-- player.reby_left_time = 0
		-- player.reby_left_time_st = 0
	end
end

function P:updateSelfInfo(seatid, chips, buff_id, buff_time)
	local player = P.super.updateSelfInfo(self, seatid, chips, buff_id, buff_time)
	-- player:clearCard()
end

function P:updateOtherInfo(info)	
	local player = P.super.updateOtherInfo(self, info)
	if not player then return end
	player.chips = info.hand_chips
	-- player:clearCard()
end

function P:getBoardInfo()
	return self.board_info
end

function P:setBoardInfo(board)
	self.board_info = {}
	if board then
		for _, v in ipairs(board) do
			self.board_info[#self.board_info + 1] = v
		end
	end
end

function P:addBoardInfo(board)
	for _, v in ipairs(board) do
		self.board_info[#self.board_info + 1] = v
	end
end

function P:getPotInfo()
	return self.pot_info
end

function P:setPotInfo(pot_info)
	self.pot_info = 0
	if pot_info then
		for _, v in ipairs(pot_info) do
			self.pot_info = self.pot_info + v
		end
	end
end

function P:getTotalPot()
	local ret = self.pot_info or 0
	for _, v in pairs(self.player_info) do
		if v.on_seat then
			ret = ret + v.bet_chip
		end
	end
	if self:isOmaha() then
		 ret = ret + self:getCallNeedChip() * 2
	else
		ret = ret + self:getCallNeedChip() * 2
	end
	return ret
end

function P:refreshLastPotNum()
	self._lastPotNum = self:getTotalPot()
end

function P:getLastPotNum()
	return self._lastPotNum or 0
end

function P:initSelfHandCard()
	local player = self:getMyPlayerInfo()
	if not player then
		return
	end
	self:updateSelfCard(self.playing_status)
end

function P:updateSelfCard(msg)
	self:updateHandCard(self.my_position, msg)
end

function P:updateHandCard(player_index, msg)
	local player = self:getPlayer(player_index)
	if nil == player then
		return
	end
	player.hand_cards = player.hand_cards or {}
	for i = 1, self:getHandCardNum() do
		local card_value = msg["card" .. i]
		if card_value and card_value > 0 then
			player.hand_cards[i] = card_value
		end
	end
end

function P:calMaxBetValue()
	if not self:isMeOnSeat() then
		return
	end
	local seat_num = self:getSeatNum()
	local bet_chip = 0
	for i = 1, seat_num do
		local player = self:getPlayer(i)
		if player.bet_chip and player.bet_chip > bet_chip then
			bet_chip = player.bet_chip
		end
	end
	self.max_bet_value = 0
	self:updateMaxBetValue(bet_chip)
end

function P:getMaxBetValue()
	return self.max_bet_value
end

function P:updateMaxBetValue(value)
	if value > self.max_bet_value then
		self.max_bet_value = value
	end
end

function P:resetRoundInfo()
	self.max_bet_value = 0
	for _, v in ipairs(self:getAllPlayers()) do
		v.bet_chip = 0
		v.bet_change = 0
		if v.on_seat and v.action_type ~= POKER_ACTION.SITED then
			v.action_type = POKER_ACTION.WAIT
		end
	end
end

-- 跟注需要的金币，有可能比手上的金币多
function P:getCallNeedChip()
	return self.playing_status.call_need_chips or 0
end

function P:setCallNeedChip(value)
	self.playing_status.call_need_chips = value
end

-- 获取自动跟注的金币
function P:getAutoCallChip()
	local myPosition = self:getMyPosition()
	local maxChip, myChip = 0, 0
	for _, v in pairs(self.player_info) do
		if v.bet_chip > maxChip then
			maxChip = v.bet_chip
		end
		if v.seatid == myPosition then
			myChip = v.bet_chip
		end
	end
	if maxChip > myChip then
		return maxChip - myChip
	end
	return 0
end

-- 加注需要的最小金币量，有可能比手上的金币多，遇到无效加注的情况，玩家不能raise，min_chipin为0
function P:getMinChipIn()
	return self.playing_status.min_chipin or 0
end

function P:setMinChipIn(value)
	self.playing_status.min_chipin = value
end

function P:getMyMaxChipIn()
	local chips = self:getMyPlayerInfo().chips
	if self:isOmaha() then
		local pot = self:getTotalPot()
		if chips >= pot then
			return pot
		end
	end
	return chips
end

-- 可以下的最大金币量
function P:getMaxChipIn()
	return self.playing_status.max_chipin or 0
end

function P:setMaxChipIn(value)
	self.playing_status.max_chipin = value
end

function P:getMinChipValue()
	return Config.SERVER_CLIENT_RATIO
end

-- 获取 2x 加注基础值
function P:getRaiseBase()
	local minchip = self:getMinChipIn()
	if minchip > 0 then
		local callchip = self:getCallNeedChip()
		if minchip > 0 then
			return callchip + self:getMyPlayerInfo().bet_chip
		else
			return math.floor(minchip / 2) + self:getMyPlayerInfo().bet_chip
		end
	end
	return 0
end

function P:getSmallBlind()
	return self.room_info.sb
end

function P:setSmallBlind(sb)
	self.room_info.sb = sb
	self.room_info.bb = sb * 2
end

function P:getBetChipsStr(chips)
	if SettingModel:isShowBB() then
		if chips > 0 then
			if chips * 10 < self:getBigBlind() then
				return "<0.1BB"
			end
			return "" .. tostring(math.floor(chips / self:getBigBlind() * 10) / 10) .. "BB"
		end
		return "0BB"
	end
	return _N(chips)
end

function P:getBigBlind()
	return self:getSmallBlind() * 2
end

function P:getAnte()
	return self.room_info.ante or 0
end

function P:setAnte(ante)
	self.room_info.ante = ante
end

function P:getMinBuyIn()
	return self.room_info.min_byin or 0
end

function P:getMaxBuyIn()
	return self.room_info.max_byin or 0
end

function P:getDealerIndex()
	if self:isPlaying() then
		return self.table_status.d_idx + 1
	else
		return -1
	end
end

function P:setDealerIndex(index)
	self.table_status.d_idx = index
end

function P:getSBIndex()
	return self.table_status.sb_idx + 1
end

function P:setSBIndex(index)
	self.table_status.sb_idx = index
end

function P:getBBIndex()
	return self.table_status.bb_idx + 1
end

function P:setBBIndex(index)
	self.table_status.bb_idx = index
end

function P:isInAnte()
	return self._isInAnte
end

function P:setIsInAnte(flag)
	self._isInAnte = flag
end

function P:setAntiActionDt(dt)
	self._antiActionDt = dt
end

function P:getAntiActionDt()
	return self._antiActionDt
end

function P:getHandCardNum()
	if self:isOmaha() then
		return 4
	end
	return 2
end

function P:resetPlayerInfo(player_info)
	for _, info in ipairs(self.player_info) do
		info:clearCard()
	end
	for _, info in ipairs(player_info) do
		local player = self:getPlayer(info.seatid + 1)
		player.on_seat = true
		player.action_type = POKER_ACTION.WAIT
		player.last_action_type = POKER_ACTION.NONE
		player.chips = info.chips
		player.bet_chip = 0
		player.begin_chips = info.begin_chips or player.chips
		player.win_rate = 0
    	player.last_win_rate = 0
	end
end

function P:getActionIndex()
	return self.table_status.action_idx + 1
end

function P:setActionIndex(index)
	self.table_status.action_idx = index
end

function P:getLeftActionTime()
	if self.actionSt then
		local dt = os.time() - self.actionSt
		local left_time = self.playing_status.action_time - dt
		if left_time < 0 then
			left_time = 0
		end
		return left_time
	end
	return self.playing_status.action_time
end

function P:setLeftActionTime(action_time)
	self.playing_status.action_time = action_time
	self.actionSt = os.time()
end

-- 获取比赛思考时间，减掉了容错时间
function P:getThinkTime()
	return self.playing_status.think_time - tpl_constdata.Sng_Timebank_Extra
end

function P:setThinkTime(think_time)
	self.playing_status.think_time = think_time
end

function P:setRoundStage(stage)
	self.round_stage = stage
end

function P:getRoundStage()
	return self.round_stage
end

function P:getOpenPage()
	return "PokerJpHomePage"
end

function P:getUpblindTime()
	return self.room_info.upblind_time
end

function P:begenDealCard()
	self._isDealing = true
end

function P:endDealCard()
	if self._isDealing then
		self._isDealing = nil
		if #self.guess_infos > 0 then
			self.guess_infos = {}
		end
		-- G.eventCenter:dispatchEvent({name = D.EVENT_NAME.MSG_POKER_GUESS_RESET})
		self:setGuessResult(nil)
	end
end

function P:setGuesses(guess_infos)
	self.guess_infos = {}
	if guess_infos then
		for _, v in ipairs(guess_infos) do
			self.guess_infos[#self.guess_infos + 1] = v
		end
	end
	self:setGuessResult(nil)
end

function P:getGuessInfos()
	return self.guess_infos
end

function P:getGuessInfo(handType)
	for _, v in pairs(self.guess_infos) do
		if v.guess_type == handType then
			return v
		end
	end
	return nil
end

function P:setGuessResult(msg)
	self.guess_result = msg
end

function P:getGuessResult()
	return self.guess_result
end

function P:isCanGuess()
	if self:isMTT() or self:isFriendsRoom() then
		return false
	end
	if self:isMeOnSeat() and self:getOnSeatNum() > 1 then
		if self:isSNG() and self._toStartTime then
			return os.time() - self._toStartTime >= 6 and not self._isDealing
		end
		return not self._isDealing
	end
	return false
end

function P:getHandInfo(id)
	return self.hand_history[id]
end

function P:setHandInfo(id, info)
	self.hand_history[id] = info
end

-- function P:getSaveGameids()
-- 	return self.save_gameids
-- end
-- function P:setSaveGameids(id)
-- 	table.insert(self.save_gameids, id)
-- end
-- function P:removeSaveGameids(id)
-- 	table.removebyvalue(self.save_gameids, id)
-- end

--当前牌桌内最大的下注值
function P:getMaxDesktopBet()
	local seat_num = self:getSeatNum()
	local bet_chip = 0
	for i = 1, seat_num do
		local player = self:getPlayer(i)
		if player.bet_chip and player.bet_chip > bet_chip then
			bet_chip = player.bet_chip
		end
	end
	return bet_chip
end

function P:setPreActionDatas(ntype, chips)
	self.pre_action_datas = {}
	self.pre_action_datas.pre_action_type = ntype or 0 -- 0 没有预行动    1 fold    2 check    3 call    4 call any
	self.pre_action_datas.pre_action_chips = chips or 0
end

function P:getPreActionDatas()
	return self.pre_action_datas or {}
end

function P:getWaitNextHand()
	return self.wait_next_hand
end

function P:setWaitNextHand(state)
	self.wait_next_hand = state
end

function P:setRecord(record)
	self._recordData = record
end

function P:getRecord()
	return self._recordData
end

function P:isRecord()
	return self._recordData ~= nil
end

function P:isCanSaveRecord()
	if self:isRecord() then
		return false
	end
	local info = self:getMyPlayerInfo()
	if info and info.has_card then
		return self._saveGameId ~= self:getGameId()
	end
	return false
end

function P:saveRecord(tip)
	if self:getGameId() and "" ~= self:getGameId() then
		self._saveGameId = self:getGameId()
		Net:post("/collCard/update", {
			add_id = self:getGameId(),
			roomid = tostring(self:getRoomId()),
			tid = tostring(self:getTid()),
		}, function(d)
			if 0 == d.code then
				PlayerModel:setCurRecord(#d.gameids)
				if tip then
        			UiManager:showToast(tip)
				end
			end
		end)
	end
end

function P:setWinnerRSP(msg)
	self.winner_rsp = msg
end

function P:getWinnerRSP()
	return self.winner_rsp
end

-- 获取赢牌类型 -1 失败 0普通赢牌 1 big win 2 megawin
function P:getWinType(seatid)
	if self.winner_rsp then
		if not seatid then
			seatid = self:getMyPosition()
		end
		for _, v in ipairs(self.winner_rsp.profit) do
			if v.seatid + 1 == seatid then
				if v.chips >= tpl_constdata.IngameMegaWinBB * self:getBigBlind() then
					return 2
				elseif v.chips >= tpl_constdata.IngameBigWinBB * self:getBigBlind() then
					return 1
				elseif v.chips >= 0 then
					return 0
				else
					return -1
				end
				break
			end
		end
	end
	return -1
end

function P:isCanShowWinRate()
	if self:getRoundStage() and self:isOmaha() and (self:getRoundStage() < POKER_ROUND.TURN or self:getRoundStage() > POKER_ROUND.OVER) then
		return false
	end
	return true
end

function P:calculateWinOdds(boardCount, seed)
	if not self:isCanShowWinRate() then
		return
	end
	local hands, boards = {}, {}
	for i, info in ipairs(self:getAllPlayers()) do
		if info.on_seat and info.has_card and not info.is_fold and info.hand_cards then
			table.insert(hands, table.concat({info.seatid, info.hand_cards[1], info.hand_cards[2], info.hand_cards[3], info.hand_cards[4]}, ","))
		end
	end
	for k, v in ipairs(self.board_info) do
		if not boardCount or k <= boardCount then
			table.insert(boards, v)
		end
	end
	CS.WinOdds.CalculateWinOdds(table.concat(hands, ";"), table.concat(boards, ","), "", 999999, self:isOmaha() and 1000 or 3000, function(result)
		print("==== 计算胜率结果", result)
		local d = json.decode(result)
		for _, v in ipairs(d) do
			local player = self:getPlayer(v[1])
			if player then
				player.last_win_rate = player.win_rate
				player.win_rate = v[2]
			end
		end
	end)
end

function P:isHaveSurelyWinner()
	for _, v in ipairs(self:getAllPlayers()) do
		if v.on_seat and not v.is_fold and v.has_card then
			if v.last_win_rate >= 100 then
				return true
			end
		end
	end
	return false
end

function P:isCanScrop(chips)
	if self:isTournament() then
		return chips >= self.room_info.bust_threshold
	end
	return chips >= tpl_constdata.ScrapRecoverBlindRate * self:getBigBlind()
end

return P