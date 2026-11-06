local P = class("SoccerGuessingModel", BaseModel)

function P:ctor()
	self.saveData = {
		cloud = {}
	}
	P.super.ctor(self)
end

function P:afterLogin()
	if not self.cloud["checkSoccer" .. PlayerModel:getUid()] then
		self.cloud["checkSoccer" .. PlayerModel:getUid()] = {}
	end
	self._checkSoccer = {}
	for k,v in pairs(self.cloud["checkSoccer" .. PlayerModel:getUid()]) do
		self._checkSoccer[v] = 1
	end

	self:reqBetStatus()
end

-- 请求竞猜活动状态
function P:reqBetStatus()
	Net:post("activity/betStatus", {}, function(data)
		if data.code ~= 0 then
			return
		end

		self._betStatus = data.open
		self._betLive = data.live
		self._betIds = data.bet_ids

		bee.emit("evt_BetStatusUpdate")
		self:refreshReddot()
	end)
end

function P:getBetStatus()
	return self._betStatus
end

function P:getBetLive()
	return self._betLive == 1
end

-- 请求足球竞猜列表
function P:reqBetList(cb)
	Net:post("activity/betList", {}, function(data)
		if data.code ~= 0 then
			return
		end

		self._betList = data.list
		self._betIds = {}
		for k, v in pairs(self._betList) do
			if v.sequence == 0 then
				v.sequence = 9999999999
			end
			table.insert(self._betIds, v.bet_id)
		end
		self._betMap = {}
		for k,v in pairs(self._betList) do
			self._betMap[v.bet_id] = v
		end

		bee.emit("evt_BetListUpdate")
		self:refreshReddot()
		if cb then
			cb()
		end
	end)
end

-- 请求足球竞猜历史记录
function P:reqBetHistory()
	Net:post("activity/betHistory", {}, function(data)
		if data.code ~= 0 then
			return
		end

		self._betHistoryList = data.list

		bee.emit("evt_BetHistoryListUpdate")
	end)
end

-- 足球活动下注
function P:reqBet(id, bets)
	local params = {}
	params.bet_id = id
	params.areas = {}
	for k, v in pairs(bets) do
		local l = {}
		l.bet_area = k
		l.amount = v
		table.insert(params.areas, l)
	end
	Net:post("activity/bet", params, function(data)
		self:reqBetList()
		if data.code ~= 0 then
			return
		end
		UiManager:showToast(_T("LAB_FOOTBALL_TIPS_1"))
	end)
end

-- 获取足球活动列表
function P:getSoccerList()
	local list = {}
	for i, v in ipairs(self._betList) do
		if v.status == 0 then
			table.insert(list, v)
		end
	end

	table.sort(list, function(a, b)
		local sumA = 100
		local sumB = 100

		if a.sequence < b.sequence then
			sumA = sumA + 10
		end
		if b.sequence < a.sequence then
			sumB = sumB + 10
		end

		if a.game_start_time < b.game_start_time then
			sumA = sumA + 1
		end
		if b.game_start_time < a.game_start_time then
			sumB = sumB + 1
		end

		return sumA > sumB
	end)
	return list
end

function P:getSoccerInfo(id)
	if not self._betMap then
		return
	end
	return self._betMap[id]
end

-- 获取足球竞猜历史记录
function P:getSoccerHistoryList()
	return self._betHistoryList
end

-- 是否有可下注比赛
function P:getIsCanBet()
	for k,v in pairs(self._betList) do
		if v.status == 0 then
			return true, v.bet_id
		end
	end
	return false
end

-- 获取当前比赛是否可下注
function P:getSoccerIsCanBet(id)
	if not self._betMap or not self._betMap[id] then
		return false
	end
	return self._betMap[id].lock ~= 1
end

function P:isShowNew(id)
	return self._checkSoccer[id] ~= 1
end

function P:setCheckSoccer(id)
	if self._checkSoccer[id] then
		return
	end

	self._checkSoccer[id] = 1
	table.insert(self.cloud["checkSoccer" .. PlayerModel:getUid()], id)
	self:onSave()

	self:refreshReddot()
end

function P:refreshReddot()
	local isIn = false
	local saveData = LocalStore:getTableData("SoccerData" .. PlayerModel:getUid()) or {}
	for _, v in pairs(self._betIds) do
		if table.keyof(saveData, v) == nil then
			RedManager:addTag(RedTag.Soccer)
			return
		end
		-- if not self._checkSoccer[v] then
		-- 	RedManager:addTag(RedTag.Soccer)
		-- 	return
		-- end
	end
	RedManager:removeTag(RedTag.Soccer)
end

function P:clearReddot()
	local saveData = {}
	for _, v in pairs(self._betIds) do
		table.insert(saveData, v)
	end
	LocalStore:saveTableData("SoccerData" .. PlayerModel:getUid(), saveData)
	RedManager:removeTag(RedTag.Soccer)
end

return P