local M = {}
GF = M

function M.getCardCode(num, suit)
	if not suit then
		return num.number + num.color * 256
	end
	return num + suit * 256
end

function M.getCardSuit(code)
	return math.floor(code / 256)
end

function M.getCardNumber(code)
	return math.floor(code % 256)
end

function M.getCardValue(code1, code2)
	if code1 and code2 then
		local n1, n2 = GF.getCardNumber(code1), GF.getCardNumber(code2)
		local c1, c2 = GF.getCardSuit(code1), GF.getCardSuit(code2)
		if not M.__cardValueTbr then
			M.__cardValueTbr = {}
			for _, v in ipairs(tpl_poker_card_value_list) do
				M.__cardValueTbr[v.card1 * 1000 + v.card2 * 10 + v.suit] = v.value
			end
		end
		if n1 < n2 then n1, n2 = n2, n1 end
		return M.__cardValueTbr[n1 * 1000 + n2 * 10 + (c1 == c2 and 1 or 0)]
	end
	return 0
end

function M.getCardNumberSuit(code)
	local number = M.getCardNumber(code)
	local color = M.getCardSuit(code)
	return Config.CARD_NUM_2_STRING[number], Config.CARD_COLOR_2_STRING[color]
end

function M.getCardInfoDict(code)
	local n = M.getCardNumber(code)
	local s = M.getCardSuit(code)
	return {n = n, s = s}
end

function M.getCardImageByCode(code, itemId)
	if code == Config.JOKER_CARD then
		return Config.IMAGE.CARD_JOKER
	elseif 0 == code or not code then
		-- return "Card[card_back]"
		return PlayerModel:getCurCardBackImage()
	end
	local number, color = M.getCardNumberSuit(code)
	return M.getCardImage(number, color, itemId)
end

function M.getCardImage(number, color, itemId)
	if not itemId then
		itemId = PlayerModel:getCardFace()
	end
	local cfg = tpl_card[tpl_props[itemId].mapId]
	return string.format("Card[" .. cfg.image .."_%s_%s]", color, number)
end

function M.getHukamCardImage(number)
	return string.format(Config.IMAGE.CARD_BLANK, number)
end

function M.isPokerRoom(roomType)
	return roomType and (roomType == GAME_ROOM_TYPE.HOLDEM)
end

function M.isPokerGame(gameType)
	return gameType == GAME_GAME_TYPE.LOBBY_HOLDEM_GAME or gameType == GAME_GAME_TYPE.TRAINING_HOLDEM_GAME
end

function M.isOmahaRoom(roomType)
	return roomType == GAME_ROOM_TYPE.OMAHA
end

function M.isOmahaGame(gameType)
	return gameType == GAME_GAME_TYPE.LOBBY_OMAHA_GAME or gameType == GAME_GAME_TYPE.TRAINING_OMAHA_GAME
end

function M.isAllinPoker(gameType)
	return gameType == GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN
end

function M.isFriendsRoom(gameType)
	return gameType == GAME_GAME_TYPE.FRIEND_HOLDEM_GAME
end

function M.isSNG(gameType)
	return gameType == GAME_GAME_TYPE.SNG_HOLDEM_GAME or gameType == GAME_GAME_TYPE.SNG_OMAHA_GAME or gameType == GAME_GAME_TYPE.SNG_TRAIN_GAME
end

function M.isMTT(gameType)
	return gameType == GAME_GAME_TYPE.MTT_HOLDEM_GAME or gameType == GAME_GAME_TYPE.MTT_OMAHA_GAME
end

function M.isTrainingGame(gameType)
	return gameType == GAME_GAME_TYPE.TRAINING_HOLDEM_GAME or gameType == GAME_GAME_TYPE.TRAINING_OMAHA_GAME or gameType == GAME_GAME_TYPE.SNG_TRAIN_GAME
end

function M.getGameTypeName(gameType, showRealName)
	if M.isOmahaGame(gameType) then
		return _T("LAB_OMAHA")
	elseif M.isAllinPoker(gameType) then
		return _T("LAB_ALLIN_01")
	elseif showRealName and M.isSNG(gameType) then
		return _T("LAB_SNG")
	elseif showRealName and M.isMTT(gameType) then
		return _T("LAB_MTT")
	elseif showRealName and M.isFriendsRoom(gameType) then
		return _T("LAB_FRIROOM_001")
	end
	return _T("LAB_POKER_GAME")
end

function M.isFoldAction(action_type)
	return action_type == POKER_ACTION.FOLD or action_type == POKER_ACTION.SYS_FOLD or action_type == POKER_ACTION.LEAVE_FOLD
end

-- 是否任意下注类型
function M.isBetAction(action_type)
	return action_type == POKER_ACTION.CALL or action_type == POKER_ACTION.RAISE or action_type == POKER_ACTION.BET or action_type == POKER_ACTION.SB or action_type == POKER_ACTION.BB or action_type == POKER_ACTION.FORCE_BB or action_type == POKER_ACTION.ANTE or action_type == POKER_ACTION.ALLIN
end

function M.getTableDatas(gameType)
	if gameType == GAME_GAME_TYPE.LOBBY_OMAHA_GAME then
		if not M.__tpl_table_omaha then
			M.__tpl_table_omaha = {}
			for _, v in ipairs(tpl_table_omaha_free_list) do
				table.insert(M.__tpl_table_omaha, v)
			end
			for _, v in ipairs(tpl_table_omaha_list) do
				table.insert(M.__tpl_table_omaha, v)
			end
		end
		return M.__tpl_table_omaha
	elseif gameType == GAME_GAME_TYPE.FRIEND_HOLDEM_GAME then
		return tpl_table_poker_friend
	elseif gameType == GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN then
		return tpl_table_poker_allin
	end
	if not M.__tpl_table_poker then
		M.__tpl_table_poker = {}
		for _, v in ipairs(tpl_table_poker_free_list) do
			table.insert(M.__tpl_table_poker, v)
		end
		for _, v in ipairs(tpl_table_poker_list) do
			table.insert(M.__tpl_table_poker, v)
		end
	end
	return M.__tpl_table_poker
end

function M.getTableDataBySB(gameType, sb)
	local datas = M.getTableDatas(gameType)
	for _, v in pairs(datas) do
		if v.sb == sb then
			return v
		end
	end
	return nil
end

function M.sendSitDownRequest(seatid, chips)
	local location = M.getCurrentLocation()
	if type(location) ~= "table" then
		return
	end
	local params = {seatid = seatid, chips = chips, pc = bee.isPc,
	gps_lon = location.longitude, gps_lat = location.latitude, ip = PlayerModel:getIP()}
	Net:sendReq("pb.SitDownREQ", params)
end

function M.getBetNameStr(betVal)
	if betVal[2] then
		return _F("LAB_GAME_016", "" .. betVal[1] .. "/" .. betVal[2])
	end
	if 1 == betVal[1] then
		return _F("LAB_GAME_016", "")
	end
	return _F("LAB_GAME_016", betVal[1])
end

function M.getRaiseNameStr(raiseVal)
	if type(raiseVal) == "table" then
		return M.getBetNameStr(raiseVal)
	end
	return "" .. raiseVal .. "x"
end

function M.gotoShop()
end

function M.isValidEmail(str)
	local pattern = "^[%w%.%_%+%-]+@[%w%.%-]+%.[%a][%a]+$"
	return string.match(str, pattern)
	-- if str == nil then return nil end
	-- if (type(str) ~= 'string') then
	-- 	return false, "Expected string"
	-- end
	-- local lastAt = str:find("[^%@]+$")
	-- if lastAt == nil then
	-- 	return false, "no @ symbol"
	-- end
	-- local localPart = str:sub(1, (lastAt - 2)) -- Returns the substring before '@' symbol
	-- local domainPart = str:sub(lastAt, #str) -- Returns the substring after '@' symbol
	-- -- we werent able to split the email properly
	-- if localPart == nil then
	-- 	return false, "Local name is invalid"
	-- end

	-- if domainPart == nil then
	-- 	return false, "Domain is invalid"
	-- end
	-- -- local part is maxed at 64 characters
	-- if #localPart > 64 then
	-- 	return false, "Local name must be less than 64 characters"
	-- end
	-- -- domains are maxed at 253 characters
	-- if #domainPart > 253 then
	-- 	return false, "Domain must be less than 253 characters"
	-- end
	-- -- somthing is wrong
	-- if lastAt >= 65 then
	-- 	return false, "Invalid @ symbol usage"
	-- end
	-- -- quotes are only allowed at the beginning of a the local name
	-- local quotes = localPart:find("[\"]")
	-- if type(quotes) == 'number' and quotes > 1 then
	-- 	return false, "Invalid usage of quotes"
	-- end
	-- -- no @ symbols allowed outside quotes
	-- if localPart:find("%@+") and quotes == nil then
	-- 	return false, "Invalid @ symbol usage in local part"
	-- end
	-- -- only 1 period in succession allowed
	-- -- if domainPart:find("%.%.") then
	-- -- 	return false, "Too many periods in domain"
	-- -- end
	-- local _,count = string.gsub(domainPart, "%.", "")
	-- if (count < 1 ) or (count > 3) then
    --      return false
    -- end

	-- -- just a general match
	-- if not str:match('[%w]*[%p]*%@+[%w]*[%.]?[%w]*') then
	-- 	return false, "Email pattern test failed"
	-- end
	-- -- all our tests passed, so we are ok
	-- return true
end

function M.getSecretEmail(email)
    local sp = string.split(email, "@")
    local h = string.sub(sp[1], 1, 3)
    return h .. "****@" .. (sp[2] or "")
end

function M.isValidPassword(str, TextTips)
	if #str < 6 or #str > 12 then
		if TextTips then
			bee.setText(TextTips, _T("HTTP_INVALID_EMAIL_PASSWORD_FORMAT"))
		end
		return false
	end
	return true
end

function M.isValidName(name, TextTip)
	local n = string.utf8len2(name)
	if n < 2 or n > 16 then
		if TextTip then
			bee.setText(TextTip, _T("HTTP_NICKNAME_INVALID_LENGTH"))
		else
			UiManager:showError(_T("HTTP_NICKNAME_INVALID_LENGTH"))
		end
		return false
	elseif string.match(name, "^%d+$") ~= nil then
		if TextTip then
			bee.setText(TextTip, _T("HTTP_NICKNAME_NOT_ALL_NUMERIC"))
		else
			UiManager:showError(_T("HTTP_NICKNAME_NOT_ALL_NUMERIC"))
		end
		return false
	-- elseif string.find(name, "@") ~= nil then
	-- 	if TextTip then
	-- 		bee.setText(TextTip, _T("LAB_INFO_018"))
	-- 	else
	-- 		UiManager:showError(_T("LAB_INFO_018"))
	-- 	end
	-- 	return false
	elseif name == PlayerModel:getName() then
		if TextTip then
			bee.setText(TextTip, _T("LAB_INFO_039"))
		else
			UiManager:showError(_T("LAB_INFO_039"))
		end
		return false
	end
	return true
end

function M:getValidString(s)
	-- return string.gsub(s, "\\", "\\\\")
	return s
end

function M.parseLinks(s)
    local textList = {}
    local i, startIndex = 1, 1
    while i do
        local i1, j1 = string.find(s, "<a ", i)
        if i1 then
            local i2, j2 = string.find(s, "</a>", j1)
            if i2 then
                local a = string.sub(s, i1, j2)
                if string.find(a, "<img>") then
					M.parseImgs(string.sub(s, startIndex, i1 - 1), textList)
                    -- table.insert(textList, string.sub(s, startIndex, i1 - 1))
                    table.insert(textList, a)
                    startIndex = j2 + 1
                end
                i = j2
            else
                break
            end
        else
            break
        end
    end
    if startIndex == 1 then
        M.parseImgs(s, textList)
    else
        M.parseImgs(string.sub(s, startIndex), textList)
    end
    return textList
end

function M.parseImgs(s, textList)
	local startIndex = 1
	local i, j = string.find(s, "<img>")
	while i do
		local i1, j1 = string.find(s, "</img>", i)
		if i1 then
			table.insert(textList, string.sub(s, startIndex, i - 1))
            table.insert(textList, string.sub(s, i, j1))
			startIndex = j1 + 1
		else
			break
		end
		i = j1
	end
	if startIndex == 1 then
		table.insert(textList, s)
	else
		table.insert(textList, string.sub(s, startIndex))
	end
	return textList
end

function M.onClickLink(href)
	if string.find(href, "http") then
		bee.openUrl(href)
	elseif string.find(href, "@") then
		CS.SdkHelper.copyText(href)
        UiManager:showToast(_T("LAB_COPY_SUC"))
	else
		local id = tonumber(href)
		if id then
			ItemModel:jumpView(id)
		end
	end
end

function M.showServerMaintain(data, loginCb, stopCb)
	local ct = bee.getServerTime()
	
	if ct >= data.start_time then
		UiManager:showUI("UpdateShutdown", {
			title = _T("LAB_UPDATE_TITILE_3"),
			text = _T("LAB_UPDATE_INFO_4"),
			data = data,
			button = 1,
			noClose = true,
			onSure = function()
				if stopCb then
					stopCb()
				end
			end
		})
	elseif not data.show_time or ct >= data.show_time then
		local text = "LAB_UPDATE_INFO_1"
		if data.start_time - ct <= 300 then
			text = "LAB_UPDATE_INFO_3"
		end
		local ui = UiManager:showUI("UpdateShutdown", {
			title = _T("LAB_UPDATE_TITILE_2"),
			text = _F(text, TimeHelp:getTimeLeftStr(data.start_time - ct)),
			data = data,
			button = 1,
			noClose = true,
			onSure = function()
				if loginCb then
					loginCb()
				end
			end,
		})
		ui:schedule(1, function()
			ct = bee.getServerTime()
			if ct >= data.start_time then
				UiManager:hideUI("UpdateShutdown")
				UiManager:showUI("UpdateShutdown", {
					title = _T("LAB_UPDATE_TITILE_3"),
					text = _T("LAB_UPDATE_INFO_4"),
					data = data,
					button = 1,
					noClose = true,
					onSure = function()
						if stopCb then
							stopCb()
						end
					end
				})
			else
				local text = "LAB_UPDATE_INFO_1"
				if data.start_time - ct <= 300 then
					text = "LAB_UPDATE_INFO_3"
				end
				bee.setText(ui.TextTip, _F(text, TimeHelp:getTimeLeftStr(data.start_time - ct)))
			end
		end)
	else
		if loginCb then
			loginCb()
		end
	end
end

function M.startCheckUpdate(isWhite, cb)
	local st = os.time()
	require("appload.AppLoadRes")
	AppLoadRes:checkUpdate(false, isWhite, cb, function(err)
		if "check_error" == err then
			if os.time() - st <= 1 then
				bee.once(2, function()
					M.startCheckUpdate(isWhite, cb)
				end)
			else
				UiManager:showTip({
					text = _T("LAB_UPDATE_TIPS_4"),
					button = 2,
					sureStr = _T("LAB_BUTTON_TEXT_3"),
					cancelStr = _T("LAB_SETTINGS_030"),
					noClose = true,
					onSure = function()
						M.startCheckUpdate(isWhite, cb)
					end,
					onCancel = function()
						Game:quit()
					end
				})
			end
		else
			local text = _T("LAB_UPDATE_TIPS_3")
			if err == "net_error" then
				text =  _T("LAB_UPDATE_TIPS_4")
			elseif err == "filelist_error" then
				text =  _T("LAB_UPDATE_TIPS_4")
			end
			UiManager:showTip({
				text = text,
				button = 2,
				sureStr = _T("LAB_UPDATE_BTN_4"),
				cancelStr = _T("LAB_UPDATE_BTN_1"),
				noClose = true,
				onSure = function()
					if err == "filelist_error" then
						M.startCheckUpdate(isWhite, cb)
					else
						AppLoadRes:startDownload()
					end
				end,
				onCancel = function()
					if AppLoadRes.forceUpdate then
						Game:quit()
					else
						AppLoadRes:onUpdateFinish(false)
					end
				end
			})
		end
    end)
end

function M.dealDeepLinkParams()
	local DeepLinkParams = CS.SdkHelper.GetDeepLinkParams()
	-- print("===== ggggggg dealDeepLinkParams", DeepLinkParams, debug.traceback())
	if DeepLinkParams and DeepLinkParams~= "" and PlayerModel:isLogin() and Net:isConnected() then
		local params = json.decode(DeepLinkParams)
		if params then
			if params["kind"] == "friendsgame" then
				local nickname = params["nickname"]
				local room_num = tonumber(params["room_num"] or "0")
				if nickname and room_num and room_num > 0 then
					if GameModel.data then
						if GameModel.data:getRoomId() ~= room_num then
							Net:sendReq("pb.LeaveRoomREQ", {
								client_str = json.encode({
									key = "invite",
									roomid = room_num,
								})
							})
						end
					else
						Net:sendReq("pb.JoinFriendRoomREQ", {
							roomid = tonumber(room_num),
						})
					end
				end
			elseif params["kind"] == "payment" then
			end
		end
		CS.SdkHelper.ClearDeepLinkParams()
	end
end

---------------- ui 工具函数 ---------------------
function M.setTitleImage(ImageTitle, title, nativeSize, hide)
	if not ImageTitle then return end
	local d = tpl_props[title]
	if d then
		ImageTitle:SetActive(true)
		bee.setIcon(ImageTitle, d.icon, nativeSize)
	else
		if hide then
			ImageTitle:SetActive(false)
		else
			ImageTitle:SetActive(true)
			bee.setIcon(ImageTitle, _I("avatartitle_non_01_tw"), nativeSize)
		end
	end
end

function M.setFrameImage(ImageFrame, frame, nativeSize)
	if not ImageFrame then return end
	local d = tpl_props[frame]
	if d then
		ImageFrame:SetActive(true)
		bee.setIcon(ImageFrame, d.icon, nativeSize)
	else
		ImageFrame:SetActive(false)
	end
end

return M