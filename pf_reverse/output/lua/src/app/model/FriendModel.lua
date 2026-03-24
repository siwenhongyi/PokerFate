local P = class("ItemModel", BaseModel)

function P:ctor(logic)
	self.saveData = {
		-- checkApplyTime = 0,
		cloud = {},
	}
	P.super.ctor(self)
end

function P:afterLogin()
	self._friendList = nil
	self._applyFriendList = nil
	self._blockedFriendList = nil
	self._gameFriendList = nil
end

function P:initFriendList()
	if not self._friendList then
		self:requestFriendList()
	end
	if not self._applyFriendList then
		self:requestApplyFriendList()
	end
	if not self._blockedFriendList then
		self:requestBlockedList()
	end
end

function P:evt_NoticeBRC(params)
	if not params.to_uids then
		return
	end
	local isMine = false
	for k,v in pairs(params.to_uids) do
		if v == PlayerModel:getUid() then
			isMine = true
			break
		end
	end
	if not isMine then
		return
	end

	local code = tonumber(params.type)
	if code == tpl_PushConsts.APPLY_FRIEND.code then
		self:requestApplyFriendList()
	elseif code == tpl_PushConsts.NEW_FRIEND.code then
		self:requestFriendList()
		self:requestApplyFriendList()
	end
end

function P:getOnlineFriends(cb)
	self:requestFriendList(function(list)
		local friends = {}
		if list then
			for _, v in ipairs(list) do
				if v.is_online then
					table.insert(friends, v)
				end
			end
		end
		cb(friends)
	end)
end

-- 好友列表
function P:requestFriendList(cb)
	Net:post("friend/list", nil, function(data)
		if data.code ~= 0 then
			return
		end
		self._friendList = {}
		local onlineList = {}
		local offlineList = {}
		for k,v in pairs(data.list) do
			if v.is_online then
				table.insert(onlineList, v)
			else
				table.insert(offlineList, v)
			end
		end
		table.sort(onlineList, function(a, b)
			local sumA = 10000
			local sumB = 10000
			if a.is_online then
				sumA = sumA + 1000
			end
			if b.is_online then
				sumB = sumB + 1000
			end
			if a.level > b.level then
				sumA = sumA + 10
			end
			if b.level > a.level then
				sumB = sumB + 10
			end
			if a.uid < b.uid then
				sumA = sumA + 1
			end
			if b.uid < a.uid then
				sumB = sumB + 1
			end
			return sumA > sumB
		end)
		table.sort(offlineList, function(a, b) return a.last_login_time > b.last_login_time end)

		for i,v in ipairs(onlineList) do
			table.insert(self._friendList, v)
		end
		for i,v in ipairs(offlineList) do
			table.insert(self._friendList, v)
		end

		if cb then
			cb(data.list)
		end
		bee.emit("evt_friendList", FRIEND_LIST_TYPE.FRIEND)
	end)
end

function P:getFriendList()
	return self._friendList or {}
end

function P:getFriendCount()
	return #self:getFriendList()
end

function P:getFriendInfo(uid)
	if self._friendList then
		for _, v in pairs(self._friendList) do
			if v.uid == uid then
				return v
			end
		end
	end
	return nil
end

function P:getBlockedInfo(uid)
	for k,v in pairs(self:getBlockedList()) do
		if v.uid == uid then
			return v
		end
	end
	return nil
end

-- 好友申请列表
function P:requestApplyFriendList(cb)
	RedManager:removeTag(RedTag.ApplyFriends)
	Net:post("friend/applyList", nil, function(data)
		if data.code ~= 0 then
			return
		end

		self._applyFriendList = data.list

		-- 提示红点
		if not self.cloud["checkApplyTime" .. PlayerModel:getUid()] then
			self.cloud["checkApplyTime" .. PlayerModel:getUid()] = 0
		end
		for k,v in pairs(self._applyFriendList) do
			if v.time > self.cloud["checkApplyTime" .. PlayerModel:getUid()] then
				RedManager:addTag(RedTag.ApplyFriends, v.time)
			end
		end

		if cb then
			cb()
		end
		bee.emit("evt_friendList", FRIEND_LIST_TYPE.ApplyFriends)
	end)
end

function P:getApplyFriendList()
	return self._applyFriendList or {}
end

-- 黑名单列表
function P:requestBlockedList()
	Net:post("friend/blockedList", nil, function(data)
		if data.code ~= 0 then
			return
		end

		self._blockedFriendList = data.list
		if cb then
			cb()
		end

		bee.emit("evt_friendList", FRIEND_LIST_TYPE.BLOCKED)
	end)
end

function P:getBlockedList()
	return self._blockedFriendList or {}
end

function P:getBlockedInfo(uid)
	if self._blockedFriendList then
		for _, v in pairs(self._blockedFriendList) do
			if v.uid == uid then
				return v
			end
		end
	end
	return nil
end

-- 最近游戏列表
function P:requestRecentGameList(cb)
	Net:post("friend/gameList", nil, function(data)
		if data.code ~= 0 then
			return
		end

		self._gameFriendList = data.list
		if cb then
			cb()
		end
	end)
end

function P:getRecentGameList()
	return self._gameFriendList or {}
end

function P:searchFriend(searchText, cb)
	local uid = tonumber(searchText)
	local args = {}
	if uid then
		args.nickname = searchText
		args.friend_uid = uid
	else
		args.nickname = searchText
	end
	Net:post("/friend/searchList", args, function(data)
		if data.code ~= 0 then
			return
		end

		if cb then
			cb(data.list)
		end
	end)
end

function P:addFriend(uid, cb)
	if self:getFriendCount() >= VipModel:getFriendLimit() then
		UiManager:showToast(_T("LAB_FRIENDS_35"))
		return
	end

	local blockedInfo = self:getBlockedInfo(uid)
	-- 判断是否在黑名单中
	if blockedInfo then
		local showText
		if blockedInfo.mark and blockedInfo.mark ~= "" then
			showText = _F("LAB_FRIENDS_45", blockedInfo.nickname, blockedInfo.mark)
		else
			showText = _F("LAB_FRIENDS_40", blockedInfo.nickname)
		end
		UiManager:showTip({
	        text = showText,
	        onSure = function()
	            self:unblockAndAddFriend(uid, cb)
	        end
	    })
	else
		Net:post("/friend/apply", {friend_uid = uid}, function(data)
			if data.code ~= 0 then
				self:showErrorToast(data.code)
				return
			end

			if data.friend_uid then
				self:removeApplyTag(data.friend_uid)
			end

			self:requestApplyFriendList()
			self:requestFriendList()

			if cb then
				cb(data.friend_uid)
			else
				UiManager:showToast(_T("LAB_FRIENDS_31"))
			end
		end)
	end
end

-- 备注好友
function P:remarkFriend(uid, mark, cb)
	Net:post("/friend/mark", {friend_uid = uid, mark = mark}, function(data)
		if data.code ~= 0 then
			return
		end
		self:requestFriendList()
		self:requestBlockedList()

		if cb then
			cb()
		end
	end)
end

function P:deleteFriend(uid)
	Net:post("/friend/del", {friend_uid = uid, del_apply = false}, function(data)
		if data.code ~= 0 then
			return
		end
		self:requestFriendList()
	end)
end

function P:deleteApply(uid)
	Net:post("/friend/del", {friend_uid = uid, del_apply = true}, function(data)
		if data.code ~= 0 then
			return
		end
		self:requestApplyFriendList()
	end)
end

function P:blockFriend(uid)
	Net:post("/friend/blocked", {friend_uid = uid, blocked = true}, function(data)
		if data.code ~= 0 then
			return
		end
		self:requestFriendList()
		self:requestBlockedList()
		self:requestApplyFriendList()
	end)
end

function P:unblockFriend(uid, cb)
	Net:post("/friend/blocked", {friend_uid = uid, blocked = false}, function (data)
		if data.code ~= 0 then
			return
		end
		self:requestFriendList()
		self:requestBlockedList()
		if cb then
			cb(data)
		end
	end)
end

function P:unblockAndAddFriend(uid, cb)
	self:unblockFriend(uid, function(data)
		if data.friend_uid ~= uid then
			self:addFriend(uid, cb)
		end
	end)
end

-- 查询好友（从好友列表中查询）
function P:searchLocalFriendList(searchList, searchText)
	local list = {}
	if not searchList then
		return list
	end
	searchText = string.lower(searchText)
	for k,v in pairs(searchList) do
		if string.find(string.lower(v.uid), searchText) then
			table.insert(list, v)
		elseif string.find(string.lower(v.nickname), searchText) then
			table.insert(list, v)
		elseif string.find(string.lower(v.mark), searchText) then
			table.insert(list, v)
		end
	end

	return list
end

function P:getOfflineTimeText(last_time)
	local delTime = bee.getServerTime() - last_time

	if delTime < 60 then
		return _T("LAB_FRIENDS_6")
	elseif delTime < 3600 then
		return _F("LAB_FRIENDS_7", math.floor(delTime / 60))
	elseif delTime < 86400 then
		return _F("LAB_FRIENDS_8", math.floor(delTime / 3600))
	elseif delTime < 604800 then
		return _F("LAB_FRIENDS_9", math.floor(delTime / 86400))
	else
		return _F("LAB_FRIENDS_9", 7)
	end
end

function P:showErrorToast(code)
	if code == tpl_HttpCode.HTTP_FRIENDS_LIMIT.code then
		UiManager:showToast(_T("LAB_FRIENDS_36"))
	elseif code == tpl_HttpCode.HTTP_FRIENDS_SELF_LIMIT.code then
		UiManager:showToast(_T("LAB_FRIENDS_35"))
	end
end

function P:refreshApplyRedPoint()
	for k,v in pairs(self:getApplyFriendList()) do
		RedManager:removeTag(RedTag.ApplyFriends, v.time)
	end
	self.cloud["checkApplyTime" .. PlayerModel:getUid()] = bee.getServerTime()
	self:onSave()
end

function P:removeApplyTag(friend_uid)
	for k,v in pairs(self:getApplyFriendList()) do
		if v.uid == friend_uid then
			RedManager:removeTag(RedTag.ApplyFriends, v.time)
			break
		end
	end
end

