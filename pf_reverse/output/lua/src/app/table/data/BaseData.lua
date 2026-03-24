local P = class("BaseData")

function P:ctor(params, scene)
	self.scene = scene
	self.my_position = 0
	self.user_num = 0
	self.play_num = 0
	self:initRoomInfo(params)
end

function P:initRoomInfo(params)
	self.user_num = params.user_num
	self.play_num = params.user_num
	self:assignRoomInfo(params)
	if not self.table_status then
		self.table_status = params.table_status
	end
	self:updateRoomInfo()
	self.friend_room_info = params.friend_room_info
end

function P:assignRoomInfo(params)
	self.room_info = params.room_info
	if params.game_type and params.game_type > 0 then
		self.room_info.game_type = params.game_type
	end
	self.room_status = params.room_status
	self.playing_status = params.playing_status
	self.table_status = params.table_status
end

function P:updateRoomInfo()
	self:refreshRoomTimeStamp()
	self:initEmptySeat()
	self:setMyPosition(0)
	self:initVisitors(self.room_status.observer)
	if self.table_status then
		self:setDealerStatus(self.table_status.dealer_status)
	end

	self:updateSeatInfoList(self.table_status.seat)
end

function P:getGameId()
	return self.table_status.gameid
end

function P:getRoomMode()
	return self.room_info.room_mode
end

function P:getRoomType()
	return self.room_info.room_type
end

function P:getRoomSubType()
	return self.room_info.room_sub_type
end

function P:getGameType()
	return self.room_info.game_type
end

function P:isPoker()
	return GF.isPokerRoom(self:getRoomType())
end

function P:isOmaha()
	return GF.isOmahaRoom(self:getRoomType())
end

function P:isAllinOrFold()
	return self:getGameType() == GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN
end

function P:isFriendsRoom()
	return GF.isFriendsRoom(self:getGameType())
end

function P:isSNG()
	return GF.isSNG(self:getGameType())
end

function P:isRegular()
	return self:getRoomSubType() == GAME_SUB_TYPE.RGL
end

function P:isMTT()
	return self:getRoomSubType() == GAME_SUB_TYPE.NORMAL_MTT
end

function P:isTournament()
	return self:isSNG() or self:isMTT()
end

function P:isJP()
	return self:getRoomSubType() == GAME_SUB_TYPE.JPOT
end

function P:getGameName()
	if self:isSNG() then
		return _T("LAB_TOURNAMENT_SNG") .. "-" .. (GameModel.data:getGameType() == GAME_GAME_TYPE.SNG_HOLDEM_GAME and _T("LAB_POKER_GAME") or _T("LAB_OMAHA"))
	elseif self:isMTT() then
		return _T("LAB_TOURNAMENT_MTT") .. "-" .. (GameModel.data:getGameType() == GAME_GAME_TYPE.MTT_HOLDEM_GAME and _T("LAB_POKER_GAME") or _T("LAB_OMAHA"))
	elseif self:isAllinOrFold() then
		return _T("LAB_ALLIN_01")
	elseif self:isOmaha() then
		return _T("LAB_OMAHA")
	end
	return _T("LAB_POKER_GAME")
end

function P:getChipIcon()
	if self:isSNG() then
		return tpl_props[GPropId.SNGChip].icon
	end
end

function P:getChipEft()
	if self:isSNG() then
		return "Prefab/PKTable/Eff_poker_ingame_chouma_sng"
	end
	return "Prefab/PKTable/Eff_poker_ingame_chouma"
end

function P:getMttConfigId()
	if self:isMTT() and self.mttroom_info then
		return self.mttroom_info.config_id
	end
	return 0
end

function P:getRoomId()
	return self.room_info.roomid
end

function P:getRoomName()
	return self.room_info.room_name
end

function P:getTid()
	return self.table_status.tid
end

function P:getLobbyType()
	return self.room_info.lobby_type
end

function P:getLobbyCoin()
	return self.room_info.lobby_coin
end

function P:getActionTime()
	return self.room_info.action_time
end

function P:getLobbyLevel()
	return self.room_info.lobby_room_lvl
end

function P:getHandId()
	return self.table_status.hand_id
end

function P:getCurHandId()
	return self.room_status.hand_id or 0
end

function P:setHandId(id)
	self.table_status.hand_id = id
end

function P:isPlaying()
	return self.table_status.is_playing
end

function P:isOnGoing()
	return self:isPlaying()
end

function P:setPlaying(state)
	self.table_status.is_playing = state
end

function P:setTableGameOver(flag)
	self._isTableGameOver = flag
end

function P:isTableGameOver()
	return self._isTableGameOver
end

-- 房间是否已经解散掉
function P:isRoomOver()
	return self.room_over == true
end

function P:setRoomOver(gameSummary)
	self.room_over = true
	self.game_summary = gameSummary
end

function P:getGameSummary()
	return self.game_summary
end

function P:getRoomOwner()
	return self.room_info.ownerid
end

function P:isRoomOwner()
	return self:getRoomOwner() == PlayerModel:getMyUid()
end

function P:getSeatNum()
	return self.room_info.seat_num
end

function P:getSelfShowIndex()
	local seat_num = self:getSeatNum()
	if 2 == seat_num or 3 == seat_num or 4 == seat_num then
		return 2
	end
	return math.ceil(seat_num / 2)
end

function P:getClubId()
	return self.room_info.clubid
end

function P:getLeagueId()
	return self.room_info.leagueid
end

function P:isGpsLimit()
	return self.room_info.gps_limit
end

function P:isIpLimit()
	return self.room_info.ip_limit
end

function P:isAnonymous()
	return self:getLobbyType() == LOBBY_ROOM_TYPE.ANTI_CHEATING
end

function P:isTableStarted()
	return self.room_status.is_started or false
end

function P:setTableStarted()
	if not self.room_status.is_started then
		self:refreshRoomTimeStamp()
		self.room_status.is_started = true
	end
end

function P:getAllPlayers()
	return self.player_info
end

function P:getPlayer(index)
	return self.player_info[index]
end

function P:getMyPlayerInfo()
	return self.player_info[self.my_position]
end

function P:getPlayerByUid(uid)
	for i, info in ipairs(self:getAllPlayers()) do
		if info.uid == uid and info.on_seat then
			return info, i
		end
	end
end

function P:getPlayerByUidOld(uid)
	if self.player_old_info then
		return self.player_old_info[uid]
	end
	return nil
end

function P:getPlayerDataByKey(index, key)
	local player = self:getPlayer(index) or {}
	return player[key]
end

function P:setPlayerDataByKey(index, key, value)
	local player = self:getPlayer(index) or {}
	player[key] = value
end

function P:getAllVisitors()
	return self.visitor_info
end

function P:getVisitor(uid)
	for _, info in ipairs(self.visitor_info) do
		if info.uid == uid then
			return info
		end
	end
end

function P:getMyPosition()
	return self.my_position
end

function P:setMyPosition(index)
	self.my_position = index
end

function P:isMeSittingOut()
	local player = self:getMyPlayerInfo()
	return player and player.seat_reserve
end

function P:setMeSittingOut(seat_reserve)
	local player = self:getMyPlayerInfo()
	if player then
		player.seat_reserve = seat_reserve
	end
end

function P:updateSelfInfo(seatid, chips, buff_id, buff_time)
	local index = seatid + 1
	local player = self:getPlayer(index)
	if not player then return end
	player:resetSelfInfo()
	player.on_seat = true
	player.chips = chips
	player.enter_buff_id = buff_id
	player.enter_buff_time = buff_time
	self:setMyPosition(index)
	-- if not anonymous then
	-- 	G.friendsMgr:updateFirendInfo(player.uid, player.name, player.avatar, player.gender, player.vip_level, player.frame)
	-- end
	return player
end

function P:updateOtherInfo(info)
	local index = info.seatid + 1
	local player = self:getPlayer(index)
	if not player then return end
	if index == self:getMyPosition() then
		return player
	end
	self:updateUserInfo(player, info.player)
	player:resetInfo(info, self)
	player.on_seat = true
	player.chips = info.hand_chips
	player.seat_reserve = info.seat_reserve or false
	player.reby_left_time = info.reby_left_time
	player.reby_left_time_st = os.time()
	return player
end

function P:standUpCleanSeat(index)
	local player = self:getPlayer(index)
	player.on_seat = false
	player.item_buff = {}
	if player.uid == PlayerModel:getUid() then
		self:setMyPosition(0)
	end
end

function P:updateSeatInfoList(infoList)
	for _, info in ipairs(infoList) do
		local index = (info.seatid or 0) + 1
		local player = self:getPlayer(index)
		self:updateSeatInfo(player, info)
	end
end

function P:updateSeatInfo(player, info)
	self:updateUserInfo(player, info.player)
	if player.uid == PlayerModel:getUid() then
		self:setMyPosition(info.seatid + 1)
	end
	player:clearCard()
	player:resetInfo(info, self)
end

function P:updateUserInfo(player, brief)
	player:resetBriefInfo(brief)
end

function P:getEmptySeat()
	for _, v in pairs(self.player_info) do
		if not v.on_seat then
			return v.index
		end
	end
	return -1
end

function P:initEmptySeat()
	self.player_info = {}
	self.player_old_info = {}
	for i = 1, self:getSeatNum() do
		local player = require("app.table.data.PlayerData"):create(i)
		self.player_info[i] = player
	end
end

function P:isMeOnSeat()
	return self.my_position > 0
end

function P:isMePlaying()
	if self:isPlaying() then
		local me = self:getMyPlayerInfo()
		return me and me.playing
	end
end

function P:getRoomDuration()
	return self.room_info.game_time ~= 0 and self.room_info.game_time or -1
end

function P:refreshRoomTimeStamp()
	self.left_time_stamp = bee:getServerTime()
end

function P:getRoomTimeLeft()
	if self:isTableStarted() then
		return self.room_status.time_left - bee:getServerTime() + self.left_time_stamp
	else
		return self.room_status.time_left
	end
end

function P:setRoomTimeLeft(time)
	self:refreshRoomTimeStamp()
	self.room_status.time_left = time
end

function P:getOnSeatDict(include_self)
	local uid = PlayerModel:getUid()
	local onSeatDict = {[uid] = include_self}
	for _, info in ipairs(self:getAllPlayers()) do
		if info.on_seat and info.uid then
			onSeatDict[info.uid] = true
		end
	end
	return onSeatDict
end

function P:getSeatedSeatList()
	local list = {}
	for i, info in ipairs(self:getAllPlayers()) do
		if info.on_seat then
			list[#list + 1] = i
		end
	end
	return list
end

function P:getOnSeatCount()
	return #self:getSeatedSeatList()
end

function P:initVisitors(visitors)
	self.visitor_info = {}
	if visitors then
		for i, info in ipairs(visitors) do
			local visitor = {uid = info.uid, name = info.name, avatar = info.avatar}
			self.visitor_info[i] = visitor
		end
	end
end

function P:onVisitorIn(info)
	if info then
		for _, visitor in ipairs(self.visitor_info) do
			if visitor.uid == info.uid then
				return
			end
		end
		local visitor = {uid = info.uid, name = info.name, avatar = info.avatar or info.icon}
		self.visitor_info[#self.visitor_info + 1] = visitor
	end
end

function P:onVisitorOut(uid)
	for i, visitor in ipairs(self.visitor_info) do
		if visitor.uid == uid then
			table.remove(self.visitor_info, i)
			break
		end
	end
end

function P:updatePlayerNum(num, play_num)
	self.user_num = num
	if play_num then
		self.play_num = play_num
	end
end

function P:getPlayerNum()
	return self.user_num
end

function P:getVisitorNum()
	local num = self.user_num
	for _, v in ipairs(self.player_info) do
		if v.on_seat then
			num = num - 1
		end
	end

	if num < 0 then
		return 0
	end
	return num
end

function P:getOnSeatNum()
	local num = 0
	for _, v in ipairs(self.player_info) do
		if v.on_seat then
			num = num + 1
		end
	end
	return num
end

function P:addPlayerChips(index, chips)
	self.player_info[index].chips = self.player_info[index].chips + chips
end

-- 返回 HomePage 要打开的界面
function P:getOpenPage()
end

function P:sendLocalLog(format, ...)
	-- if format then
	-- 	local room_type = self:getRoomType()
	-- 	local game_mode = self:getGameMode()
	-- 	local room_mode = self:getRoomMode()
	-- 	local kind
	-- 	local lvl = self:getLobbyLevel()
	-- 	local args
	-- 	if room_type == GAME_ROOM_TYPE.TP then
	-- 		if self:isSNG() then
	-- 			kind = "sng_tpclassic"
	-- 		elseif self:isMTT() then
	-- 			kind = "mtt_table"
	-- 			lvl = self.mttroom_info.config_id
	-- 			args = 2
	-- 		elseif game_mode == D.TEEN_GAME_MODE.CLASSIC then
	-- 			kind = "tp_classic"
	-- 		elseif game_mode == D.TEEN_GAME_MODE.POT_BLIND then
	-- 			kind = "tp_potblind"
	-- 		elseif game_mode == D.TEEN_GAME_MODE.JOKER then
	-- 			kind = "tp_joker"
	-- 		elseif game_mode == D.TEEN_GAME_MODE.AK47 then
	-- 			kind = "tp_ak47"
	-- 		elseif game_mode == D.TEEN_GAME_MODE.MUFLIS then
	-- 			kind = "tp_muflis"
	-- 		elseif game_mode == D.TEEN_GAME_MODE.HUKAM then
	-- 			kind = "tp_hukam"
	-- 		end
	-- 	elseif room_type == GAME_ROOM_TYPE.POKER then
	-- 		if self:isMTT() then
	-- 			kind = "mtt_table"
	-- 			lvl = self.mttroom_info.config_id
	-- 			args = 1
	-- 		else
	-- 			kind = "poker_reg"
	-- 		end
	-- 	elseif room_type == GAME_ROOM_TYPE.POKER_MTT then
	-- 		kind = "mtt_table"
	-- 		lvl = self.mttroom_info.config_id
	-- 		args = 1
	-- 	elseif room_type == GAME_ROOM_TYPE.JACKPOT then
	-- 		kind = "poker_jackpot"
	-- 	elseif room_type == GAME_ROOM_TYPE.POKER_SNG then
	-- 		kind = "sng_poker"
	-- 	elseif room_type == GAME_ROOM_TYPE.POKET_PRIVATE_ROOM then
	-- 		kind = "poker_private"
	-- 	elseif room_type == GAME_ROOM_TYPE.CASINOWAR then
	-- 		if room_mode == D.GAME_ROOM_MODE.PVP then
	-- 		else
	-- 			kind = "luckywar_reg"
	-- 		end
	-- 	elseif room_type == GAME_ROOM_TYPE.ADBH then
	-- 		if room_mode == D.GAME_ROOM_MODE.PVP then
	-- 		else
	-- 			kind = "ab_reg"
	-- 		end
	-- 	elseif room_type == GAME_ROOM_TYPE.RUMMY then
	-- 		kind = "rummy"
	-- 	elseif room_type == GAME_ROOM_TYPE.RUMMY_1V1 then
	-- 		kind = "rummy_1v1"
	-- 	elseif room_type == GAME_ROOM_TYPE.CHATAI then
	-- 		kind = "chatai"
	-- 	elseif room_type == GAME_ROOM_TYPE.DRAGON_TIGER then
	-- 		kind = "dragon_tiger_reg"
	-- 		if self:getGameType() == D.DT_GAME_TYPE.CLASSIC then
	-- 			kind = "dragon_tiger_classic"
	-- 		end
	-- 	elseif room_type == GAME_ROOM_TYPE.CARDS_32 then
	-- 		kind = "32_reg"
	-- 		if self:getGameType() == D.C32_GAME_TYPE.LOW_POINT then
	-- 			kind = "32_lowpoint"
	-- 		end
	-- 	elseif room_type == GAME_ROOM_TYPE.WINGO then
	-- 		kind = "wingo_lottery_reg"
	-- 	elseif room_type == GAME_ROOM_TYPE.JHANDI_MUNDA then
	-- 		kind = "JhandiMunda_reg"
	-- 	elseif room_type == GAME_ROOM_TYPE.CHESS_WHEEL then
	-- 		kind = "chess_wheel_reg"
	-- 	elseif room_type == GAME_ROOM_TYPE.COWBOY then
	-- 		kind = "Cowboy_Beauty_classic"
	-- 	end
	-- 	if kind then
	-- 		if args then
	-- 			G.logTool:addLocalLog(string.format(format, kind), lvl, args, ...)
	-- 		else
	-- 			G.logTool:addLocalLog(string.format(format, kind), lvl, ...)
	-- 		end
	-- 	end
	-- end
end

--牌桌内玩家的n倍经验卡信息
function P:updatePlayerNewItemBuffInfo(uid, buff_list)
	-- local player = self:getPlayerByUid(uid)
	-- if player then
	-- 	player.item_buff = {}
	-- 	local bu
	-- 	for _, buff in ipairs(buff_list) do
	-- 		if buff.buff_type == D.BAG_ITEM_LOGICTYPE.ADD_EXP_N then
	-- 			bu = {}
	-- 			bu.buff_type = buff.buff_type
	-- 			bu.expire_time = buff.expire_time
	-- 			bu.cur_time = os.time()
				
	-- 			player.item_buff[#player.item_buff+1] = bu
	-- 		end
	-- 	end
	-- end
end

function P:setDealerStatus(status)
	self.dealer_status = status
	self.dealer_st = os.time()
end

function P:getDealerStatus()
	return self.dealer_status
end

function P:getDealerRemainTime()
	local dt = self.dealer_status.remained_time - os.time() + self.dealer_st
	if dt < 0 then
		dt = 0
	end
	return dt
end

function P:getBuyin()
	if self:isMTT() then
		return self:getMttRoomBuyin()
	elseif self:isSNG() then
		return self:getSngRoomBuyin()
	else
		if self.getBigBlind then
			return self:getBigBlind()
		elseif self.getBoot then
			return self:getBoot()
		elseif self.getMinBet then
			return self:getMinBet()
		elseif self.getScoreValue then
			return self:getScoreValue()
		end
	end
	return 0
end

function P:showGoldProtectItem()
	local roomType = self:getRoomType()
	local roomMode = self:getRoomMode()
	local isShow = false
	-- if roomType == GAME_ROOM_TYPE.ADBH then
	-- 	isShow = true
	-- elseif roomType == GAME_ROOM_TYPE.CASINOWAR then
	-- 	isShow = true
	-- elseif roomType == GAME_ROOM_TYPE.BLACKJACK then
	-- 	isShow = true
	-- elseif roomType == GAME_ROOM_TYPE.DRAGON_TIGER then
	-- 	isShow = true
	-- elseif roomType == GAME_ROOM_TYPE.CARDS_32 then
	-- 	isShow = true
	-- elseif roomType == GAME_ROOM_TYPE.WINGO then
	-- 	isShow = true
	-- elseif roomType == GAME_ROOM_TYPE.JHANDI_MUNDA then
	-- 	isShow = true
	-- elseif roomType == GAME_ROOM_TYPE.CHESS_WHEEL then
	-- 	isShow = true
	-- elseif roomType == GAME_ROOM_TYPE.COWBOY then
	-- 	isShow = true
	-- elseif roomType == GAME_ROOM_TYPE.JACKPOT then 
	-- 	isShow = true
	-- elseif roomType == GAME_ROOM_TYPE.RUMMY_1V1 then 
	-- 	isShow = true
	-- end
	return isShow
end

function P:updateRoomGoldProtectInfo(info)
	-- G.bagMgr:setGoldProtectItemInfo(info)
	-- G.eventCenter:dispatchEvent({name = D.EVENT_NAME.MSG_ITEM_REFRESH_GOLD_PROTECT})
end

function P:hideGoldProtectUI()
	-- G.ccsMgr:hideCCSUI("PackGoldProtectIntro")
	-- G.ccsMgr:hideCCSUI("PackGoldProtectLayer")
end

function P:setDelayLeaveRoom(flag)
	self.playing_status.delay_leave_flag = flag
end

function P:getDelayLeaveRoom()
	return self.playing_status.delay_leave_flag
end

function P:getDelayRebyChips()
	return self.playing_status.delay_reby_chips or 0
end

function P:setDelayRebyChips(chips)
	self.playing_status.delay_reby_chips = chips
end

function P:getShowCardInfo()
	return self.playing_status.show_card_info
end

function P:setShowCardInfo(pos, flag)
	if not pos then
		self.playing_status.show_card_info = nil
		return
	end
	if not self.playing_status.show_card_info then
		self.playing_status.show_card_info = {0,0,0,0}
	end
	self.playing_status.show_card_info[pos] = flag
end

