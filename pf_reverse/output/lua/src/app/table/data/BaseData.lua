local P = class("BaseData")

function P:ctor(params, scene)
	self.scene = scene
	self.my_position = 0
	self.user_num = 0
	self.play_num = 0
	self:initRoomInfo(params)

	self._ingame_scheme = params.scheme
end

function P:initRoomInfo(params)
	self.user_num = params.user_num
	self.play_num = params.user_num
	self.seatid_being_observed = params.seatid_being_observed or -1
	self:assignRoomInfo(params)
	if not self.table_status then
		self.table_status = params.table_status
	end
	self:updateRoomInfo()
	self.friend_room_info = params.friend_room_info or {}
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
	return GF.isAllinPoker(self:getGameType())
end

function P:isFriendsRoom()
	return GF.isFriendsRoom(self:getGameType())
end

function P:isFriendPoker()
	return GF.isFriendPoker(self:getGameType())
end

function P:isFriendOmaha()
	return GF.isFriendOmaha(self:getGameType())
end

function P:isFriendSNG()
	return GF.isFriendSNG(self:getGameType())
end

function P:isSNG()
	return GF.isSNG(self:getGameType())
end

function P:isRegular()
	return self:getRoomSubType() == GAME_SUB_TYPE.RGL
end

function P:isMTT()
	return GF.isMTT(self:getGameType())
end

function P:isTournament(isAll)
	return self:isSNG() or self:isMTT() or (isAll and self:isFriendSNG())
end

function P:isTrainingGame()
	return GF.isTrainingGame(self:getGameType())
end

function P:isJP()
	return self:getRoomSubType() == GAME_SUB_TYPE.JPOT
end

function P:getGameName()
	if self:isSNG() then
		return _T("LAB_TOURNAMENT_SNG") .. "-" .. ((GameModel.data:getGameType() == GAME_GAME_TYPE.SNG_HOLDEM_GAME or GameModel.data:getGameType() == GAME_GAME_TYPE.SNG_TRAIN_GAME) and _T("LAB_POKER_GAME") or _T("LAB_OMAHA"))
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
	if self:isSNG() or self:isMTT() then
		return tpl_props[GPropId.SNGChip].icon
	end
end

function P:getChipEft()
	if self:isSNG() or self:isMTT() then
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

function P:getSrcRoomId()
	if self:isOpenObserve() then
		if self.room_info.src_roomid and self.room_info.src_roomid > 0 then
			return self.room_info.src_roomid
		end
	end
	return self.room_info.roomid
end

function P:getRoomName()
	local names = self.room_info.room_name or self.room_info.name
    for _, v in ipairs(names) do
        if v.lang == LAN:getLanguage() then
			return v.text
        end
    end
	for _, v in ipairs(names) do
		return v.text
    end
	return ""
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

function P:getPlayerSeatIndex(uid)
	local info, i = self:getPlayerByUid(uid)
	if info then
		return info.seat_index
	end
	return 0
end

function P:getPlayerByShowIndex(index)
	for _, info in ipairs(self:getAllPlayers()) do
		if info.show_index == index and info.on_seat then
			return info
		end
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
	if self:isInObserve() then
		return self:getObserveSeatid()
	end
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
	if index == self:getMyPosition() and index ~= self:getObserveSeatid() then
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

function P:isInObserve()
	return self.seatid_being_observed and self.seatid_being_observed >= 0
end

function P:getObserveSeatid()
	return self.seatid_being_observed + 1
end

function P:isOpenObserve()
	return self.room_info.open_observer or (self.room_info.src_roomid and self.room_info.src_roomid > 0)
end

function P:isInOpenObserve()
	return self:isInObserve() and self:isOpenObserve()
end

function P:getOpenObserveStartTime()
	return self.room_status.delay_ob_start_time or 0
end

function P:getRoomDuration()
	return self.room_info.game_time ~= 0 and self.room_info.game_time or -1
end

function P:refreshRoomTimeStamp()
	self.left_time_stamp = bee.getServerTime()
end

function P:getRoomTimeLeft()
	if self:isTableStarted() then
		return self.room_status.time_left - bee.getServerTime() + self.left_time_stamp
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
		local player, i = self:getPlayerByUid(info.uid)
		if player then
			player:resetBriefInfo(info)
		end
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

function P:getIngameScheme()
	if self._ingame_scheme and self._ingame_scheme.table ~= 0 then
		return self._ingame_scheme
	end
	return DecorationModel:getDefaultInGameCurScheme()
end

return P