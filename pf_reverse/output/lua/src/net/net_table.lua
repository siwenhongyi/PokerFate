net = net or {}

function net:GetRoomDataRSP(msg)
	GameModel.stopGameMsg = nil
	if msg.code == 0 and msg.roomid > 0 then
		if GameModel.data then
			GameModel.data:initRoomInfo(msg)
		end
	elseif bee.isInGame() then
		bee.enterScene("MainScene")
	end
end

function net:QuickStartRSP(msg)
	if msg.code ~= 0 then
		if bee.isInGame() then
			bee.enterScene("MainScene")
		end
	end
end

--进入房间牌桌信息返回
function net:EnterRoomRSP(msg)
	local code = msg.code or 0
	local roomid = msg.roomid
	local old_room_id = msg.old_room_id
	local lab
	local _delay = false
	local gameType = 0
	local game_type = msg.game_type or 0
	local gameSubType = 0
	print("EnterRoomRSP", code, roomid, old_room_id, game_type)
	local friends_enter_toast = SettingModel:hasTag("friends_enter_toast")
	
	if code == 0 then
		GameModel.stopGameMsg = nil
        local data
		if msg.game_type == GAME_GAME_TYPE.SNG_HOLDEM_GAME or msg.game_type == GAME_GAME_TYPE.SNG_OMAHA_GAME then
			data = require("app.table.data.PKDataSNG"):create(msg)
		else
			data = require("app.table.data.PKData"):create(msg)
		end
		GameModel:setData(data, nil)
		
		bee.enterScene("GameScene", {onEnter = function()
			if data:isSNG() then
				UiManager:showUI("PKTable3DSNG", {data = data})
			else
				UiManager:showUI("PKTable3D", {data = data})
			end
			if data:isFriendsRoom() and friends_enter_toast then
				UiManager:showToast(_F("LAB_FRIROOM_042", data.friend_room_info.owner_name))
			end
			if GameModel:isAutoSwitchTable() then
				UiManager:showToast(_T("LAB_GAME_044"))
			end
		end})
		Net:sendReq("pb.SetTableFlagREQ", {is_auto_byin = SettingModel:isAutoByin() and 2 or 1})
		return
	else
		if code == tpl_RetCode.ALREADY_IN_ROOM.code then
			if old_room_id ~= roomid then
				Net:sendReq("pb.EnterRoomREQ", {roomid = old_room_id})
			end
		elseif bee.isInStart() or bee.isInGame() then
			bee.enterScene("MainScene")
		elseif msg.client_str and "" ~= msg.client_str then
			local info = json.decode(msg.client_str)
			if info and info.key == "invite" then
				bee.enterScene("MainScene")
				return
			end
		end
	end
	if code == -2 then
		if old_room_id ~= roomid then
            Net:sendReq("pb.EnterRoomREQ", {roomid = old_room_id})
		end
		return
	elseif code == -1 then
		lab = "LAB_ROOM_NOT_EXSIT"
	elseif code == -12 or code == -13 then
	elseif code == -14 then
		lab = "LAB_UPDATING_TIP"
	elseif code == -15 then	-- -15人满即开mtt不可围观
	elseif code == -16 then 	-- -16 表示服务器错误
		lab = "SERVER ERROR"
	elseif code == -19 then 	-- -19 too many players（dgtg中使用）
		lab = "LAB_GT_MAX_PLAYERS"
		-- local tableInfo = display.curScene.tableInfo
		-- if tableInfo then
		-- 	local openPage, openParams = tableInfo:getOpenPage()
		-- 	display.enterScene("HomePageScene", {openPage = openPage, openParams = openParams})
		-- end
	elseif code == -22 then
		lab = "LAB_VERSION_NEED_UPDATE" -- - 22 客户端版本过低无法进入房间，需升级版本
	elseif code == -23 then
		lab = "LAB_VERSION_UNABLE_ROOMS"
		_delay = true
	end
	if lab then
		if not _delay then
			UiManager:showToast(lab)
		else
			bee.once(0.5, function ()
				UiManager:showToast(lab)
			end)
		end
	end
end

-- 离开房间
function net:LeaveRoomRSP(msg)
	local code = msg.code
	local last_info = GameModel.bond_settle_info
	local last_over_info = GameModel.over_bond_settle_info
	GameModel.bond_settle_info = nil
	GameModel.over_bond_settle_info = nil
	GameModel.summary = nil
	if code == 0 or code == 2 or code == 3 then
		GameModel.bond_settle_info = msg.bond_settle_info
		if GameModel.bond_settle_info then
			GameModel.bond_settle_info.game_type = msg.game_type
			if last_info and last_info.role_id == GameModel.bond_settle_info.role_id then
				GameModel.bond_settle_info.bond_inc = GameModel.bond_settle_info.bond_inc + last_info.bond_inc
				GameModel.bond_settle_info.old_bond_level = last_info.old_bond_level
				GameModel.bond_settle_info.win_hands = GameModel.bond_settle_info.win_hands + last_info.win_hands
			end
		end
		GameModel.over_bond_settle_info = msg.over_bond_settle_info
		if GameModel.over_bond_settle_info then
			GameModel.over_bond_settle_info.game_type = msg.game_type
			if last_over_info then
				GameModel.over_bond_settle_info.add_over_bond_inc = GameModel.over_bond_settle_info.add_over_bond_inc + last_over_info.add_over_bond_inc
				GameModel.over_bond_settle_info.start_over_bond_inc = last_over_info.start_over_bond_inc
			end
		end

		local info
		if msg.client_str and "" ~= msg.client_str then
			info = json.decode(msg.client_str)
			if info and info.key == "invite" then
				Net:sendReq("pb.EnterRoomREQ", {
					roomid = info.roomid,
					uid = PlayerModel:getUid(),
					byin_chips = 0,
					client_str = msg.client_str,
				})
				return
			elseif info and info.key == "switch_table" then
				UiManager:showUI("LoadingLayer", {cb = function()
					Net:sendReq("pb.QuickStartREQ", info)
				end})
				return
			end
		end

		if not GameModel:isStopLeaveRoom() then
			bee.enterScene("MainScene", {info = info})
		end
		if code == 2 then --no limit table 2局未操作被踢出
			bee.once(1.5, function ()
				UiManager:showTip({
					text = _T("LAB_NO_LIMIT_TIMEOUT_TIP")
				})
			end)
		elseif code == 3 then --no limit table 3过码行为被踢出
			bee.once(1.5, function ()
				UiManager:showTip({
					text = _T("LAB_CHIP_DUMPING_TOAST")
				})
			end)
		elseif msg.game_type ~= GAME_GAME_TYPE.FRIEND_HOLDEM_GAME then
			GameModel.summary = msg.summary
			-- if msg.summary then
				-- if ShopModel:isShowShopPush() then
				-- 	bee.showUiTask("ShopPushView", {isAuto = true}, nil, LOBBY_POP_PRIORITY.ShopPush)
				-- end
				-- if msg.summary.profit >= tpl_constdata.Score_Profit * GameModel.data:getBigBlind() then
				-- 	SdkHelper:startAppReview()
				-- end
			-- end
		end
	end
end

--其他玩家进入房间
function net:OtherEnterRoomBRC(msg)
	if GameModel.data then
		GameModel.data:onVisitorIn(user)
		GameModel.data:updatePlayerNum(msg.num, msg.player)
	end
	-- G.friendsMgr:updateOtherPlayerInfo(msg.user)
end

--其他玩家离开房间
function net:OtherLeaveRoomBRC(msg)
	if GameModel.data then
		if msg.roomid and msg.roomid ~= 0 and msg.roomid ~= GameModel.data:getRoomId() then
			return  --不是当前房间的leave消息不处理
		end
		GameModel.data:onVisitorOut(msg.uid)
		GameModel.data:updatePlayerNum(msg.num, msg.player)
	end
end

-- 解散房间
function net:DismissTableRSP(msg)
	local code = msg.code
	if code == 0 then
	elseif code == -1 then
		UiManager:showToast("LAB_DISMISS_TABLE_FAIL_1")
	else
		UiManager:showToast("LAB_DISMISS_TABLE_FAIL_2")
	end
end

-- 解散房间广播
function net:DismissTableBRC(msg)
	bee.once(function ()
		UiManager:showToast("LAB_DISMISS_TABLE_SUCCESS")
	end, 1)
    bee.once(1, function()
        UiManager:showToast(_T("LAB_DISMISS_TABLE_SUCCESS"))
    end)
end

-- 牌桌结束
function net:ClubRoomOverBRC(msg)
end

-- 坐下返回
function net:SitDownRSP(msg)
	if not GameModel.data then return end
	local code = msg.code or 0
	-- print("SitDownRSP =======", code)
	local tip
	if code == 0 then
		GameModel.data:onVisitorOut(PlayerModel:getUid())
		GameModel.data:updateSelfInfo(msg.seatid, msg.chips, msg.enter_buff_id, msg.enter_buff_time)
		
		bee.once(0.5, function()
			local r = CharacterModel:getUsingRole()
			if r and GameModel.data and (not GameModel.data:isSNG() and not GameModel.data:isMTT()) then
				local skin = r:getSkinData()
				if skin and skin.kind == SKIN_KIND.AWAKEN then
					Game:playRoleInVoice(CharacterModel:getUsingRoleId(), ROLE_VOICE.take_a_seat_awakened)
				else
					Game:playRoleInVoice(CharacterModel:getUsingRoleId(), ROLE_VOICE.take_a_seat)
				end
			end
		end)
	elseif code == 1 then
		tip = "LAB_WAIT_AUTH"
	elseif code == -1 then
		tip = "LAB_QBGMR"
		local room_mode = GameModel.data:getRoomMode()
		if room_mode == GAME_ROOM_MODE.LOBBY or room_mode == GAME_ROOM_MODE.PVP then
			-- GF.lackGoldAlert(true)
		end
	elseif code == -2 then
		tip = "LAB_CZWYBZY"
	elseif code == -8 then
		tip = "LAB_GPS_TOO_CLOSE"
	elseif code == -9 then
		tip = "LAB_SAME_IP"
	elseif code == -10 then
		tip = "LAB_ILLEGAL_GPS"
	elseif code == -11 then  --sng门票不存在
		
	elseif code == -12 then
	elseif code == -14 then
		tip = "LAB_UPDATING_TIP"
	elseif code == -15 then
	end
	if tip then
		UiManager:showToast(tip)
	end
end

-- 坐下广播
function net:SitDownBRC(msg)
	if not GameModel.data then return end
	local uid = msg.status.player.uid
	GameModel.data:onVisitorOut(uid)
	msg.status.seatid = msg.status.seatid or 0
	GameModel.data:updateOtherInfo(msg.status)
end

-- 站起返回
function net:StandUpRSP(msg)
	if not GameModel.data then return end
	local code = msg.code or 0
	-- print("StandUpRSP", code)
	local lab
	if code == 0 then
		-- lab = "LAB_ZQCG"
	elseif code == 1 then
		if GameModel.data:isSNG() or GameModel.data:isMTT() then
			return
		end
		lab = "LAB_NYMCM"
		local room_mode = GameModel.data:getRoomMode()
		if room_mode == GAME_ROOM_MODE.LOBBY or room_mode == GAME_ROOM_MODE.PVP then
			local room_type = GameModel.data:getRoomType()
			local seatid = GameModel.data:getMyPosition()
			if GF.isPokerRoom(room_type) then
				UiManager:showUI("PokerBuyin", {data = GameModel.data, seatid = seatid})
			end
		end
	elseif code == 3 then
		lab = "LAB_CSBTQ"
	elseif code == 11 then
	elseif code == -2 then
		lab = "LAB_STAND_FAIL_TIP2"
	end
	if lab then
		UiManager:showToast(lab)
	end
	if code >= 0 then
		GameModel.data:hideGoldProtectUI()
		GameModel.data:setMyPosition(0)
		if GameModel.data:isPoker() then
			GameModel.data:setGuesses(nil)
		end
		SettingModel:clearScrapPlayers()
	end
end

-- 站起广播
function net:StandUpBRC(msg)
	if not GameModel.data then return end
	local index = msg.seatid + 1
	local player = GameModel.data:getPlayer(index)
	if player then
		SettingModel:setScrapPlayer(GameModel.data, player.uid, nil)
	end
	GameModel.data:standUpCleanSeat(index)
	if player then
		GameModel.data:onVisitorIn(player)
	end
end

function net:DelayStandUpRSP(msg)
	if not GameModel.data then return end
	local code = msg.code
	if code == 0 then
		UiManager:showToast("LAB_MENU_STANDUP_NEXT")
	end
end

function net:TableNoticeMsg(msg)
	local code = msg.code
	if code == -1 then
		-- 不能离座
		UiManager:showToast("LAB_FORBID_SIT_OUT")
	end
end

function net:AddClubRoomTimeRSP(msg)
	local code = msg.code
	if code == 0 then
		UiManager:showToast("LAB_DELAY_TABLE_SUCC")
	elseif code == -1 then
		UiManager:showToast("LAB_DELAY_TABLE_FAIL")
	elseif -4 == code then
		UiManager:showToast("LAB_EXTEND_FAIL_TIME")
	elseif -5 == code then
	else
		UiManager:showToast("LAB_FAIL_EXTENDED")
	end
end

--房间开始返回
function net:ClubRoomCountdownRSP(msg)
	local code = msg.code
	if code == 0 then
	elseif code == -4 then
	elseif code == -1 then
		UiManager:showToast("LAB_RSBZLR")
	end
end

--房间开始的广播
function net:ClubRoomCountdownBRC(msg)
	if not GameModel.data then return end
	GameModel.data:setTableStarted()
end

-- 房间玩家踢出
function net:KickRoomUserRSP(msg)
	print("----------------- recMsg_KickRoomUserRSP ", msg.code, msg.flag)
	if msg.code == 0 then
		if msg.flag == 0 then -- 立即踢出
		elseif msg.flag == 1 then -- 手牌结束后踢出
			UiManager:showToast("LAB_KICK_NOTICE_MA")
		end
	elseif msg.code == -3 then
		UiManager:showToast("LAB_KICK_ON_MANAGER")
	end
end

-- 推送被踢出玩家
function net:KickedRoomRSP(msg)
	bee.once(1, function ()
		UiManager:showToast("LAB_KICK_NOTICE_PL")
	end)
end

function net:VoiceBRC(msg)
	-- if not GameModel.data then return end
	-- local params = {}
	-- params.seatid = msg.seatid
	-- params.file = msg.file
	-- params.uid = msg.uid
	-- params.timestamp = msg.timestamp
	-- params.time = msg.time
	-- params.chatType = CHAT_TYPE.VOICE
	-- G.tChatMgr:addNewMsg(params)
end

function net:TextBRC(msg)
	-- if not GameModel.data then return end
	-- local params = {}
	-- params.seatid = msg.seatid
	-- params.content = msg.content
	-- params.uid = msg.uid
	-- params.timestamp = msg.timestamp
	-- params.chatType = CHAT_TYPE.TEXT
	-- G.tChatMgr:addNewMsg(params)
end

function net:VoiceRSP(msg)
	if msg.code == -1 then
		UiManager:showToast("LAB_SEND_MSG_TOO_OFTEN")
	end
end

function net:TextRSP(msg)
	if msg.code == -1 then
		UiManager:showToast("LAB_SEND_MSG_TOO_OFTEN")
	end
end

-- 自己表情
function net:FaceBRC(msg)
end

-- 实时战绩
function net:ProfitListRSP(msg)
	if not GameModel.data then return end
	GameModel.data:initProfitInfo(msg.profit)
end

-- sitting out
function net:ReserveSeatRSP(msg)
	if not GameModel.data then return end
	if msg.code == 0 then
		GameModel.data:setMeSittingOut(msg.reserve)
	end
end

-- sitting out 广播
function net:SeatStatusBRC(msg)
	if not GameModel.data then return end
	local seatid = msg.seatid + 1
	local seat_reserve = msg.seat_reserve
	GameModel.data:setPlayerDataByKey(seatid, "seat_reserve", seat_reserve)
end

-- 操作延时广播
function net:AddActionTimeBRC(msg)
	if not GameModel.data then return end
	local code = msg.code
	if code == 0 then
		if GameModel.data:getMyPosition() == msg.seatid + 1 then
			GameModel.data:setDelayCost(msg.next_cost)
		end
	elseif code == -1 then
		GF.lackDiamondAlert()
	end
end

-- 校准房间时间
function net:ClubRoomTimeUpBRC(msg)
	if not GameModel.data then return end
	GameModel.data:setRoomTimeLeft(msg.left)
end

-- 单用户手牌胜负
function net:TableInfoRSP(msg)
end

function net:DelayLeaveRoomRSP(msg)
    if msg.code == 0 and GameModel.data then
        GameModel.data:setDelayLeaveRoom(msg.flag)

		UiManager:showToast(_T(msg.flag and "LAB_GAME_034" or "LAB_GAME_035"))
    end
end

function net:SngSpinBRC(msg)
	if not GameModel.data then return end
	GameModel.data.room_info.total_reward = msg.total_reward
end

function net:TourRoomRankRefreshBRC(msg)
	if not GameModel.data then return end
	GameModel.data.rank_list = msg.rank_list
