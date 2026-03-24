local P = class("SignInModel", BaseModel)

function P:ctor(logic)
	self._retroactiveCount = 0
	self._nextSignTs = 0

	self.saveData = {}
	P.super.ctor(self)
end

-- 获取签到数据
function P:initSignData()
	Net:post("activity/sevenSignData", nil, function(data)
		if data.code ~= 0 then
			return
		end

		self._signInDays = data.days or {}			-- 签到天数数组
		self._nextSignTs = data.next_sign_ts 	-- 下次签到时间戳 小于当前时间戳代表今日还没签到
		self._retroactiveCount = data.miss_sign_cnt -- 已使用的补签次数
		self._signItemList = data.sign_item_list 	-- 签到奖励列表
		self._totalItemList = data.total_item_list 	-- 累签奖励列表
		self._curSignInDay = math.ceil((data.cur_ts - data.cycle_ts) / 86400)	-- 签到天数

		bee.emit("evt_initSevenSignData")
	end)
end

function P:getSignInDays()
	return self._signInDays or {}
end

function P:getSignItemList()
	if self._signItemList then
		return self._signItemList
	else
		self:initSignData()
		return {}
	end
end

-- 获取累签奖励列表
function P:getTotalItemList()
	if self._totalItemList then
		return self._totalItemList
	else
		self:initSignData()
		return {}
	end
end

-- 获取累签天数
function P:getSignInTimes()
	return #self:getSignInDays()
end

function P:getIsSigned(day)
	for k,v in pairs(self:getSignInDays()) do
		if v == day then
			return true
		end
	end
	return false
end

function P:getSignInRewardsData()
	local list = {}
	if self._signItemList then
		for i, v in ipairs(self._signItemList) do
			local temp = {}
			temp.day = i
			temp.rewards = v.item_list
			temp.isSigned = self:getIsSigned(i)
			table.insert(list, temp)
		end
	end
	return list
end

-- 最高可补签次数
function P:getTotalCanRetroactiveTimes()
	return tpl_constdata.Monthly_Card_Sign_In
end

-- 本人可补签次数
function P:getCanRetroactiveTimes()
	if ShopModel:isMonthlyCard() then
		return tpl_constdata.Monthly_Card_Sign_In
	end
	return 0
end

function P:getLeftRetroactiveTimes()
	return self:getTotalCanRetroactiveTimes() - self._retroactiveCount
end

function P:sendSignIn(day)
	Net:post("activity/sevenSign", {day = day or 0}, function(data)
		if data.code ~= 0 then
			return
		end

		self._signInDays = data.days or {}		-- 签到天数数组
		self._nextSignTs = data.next_sign_ts 	-- 下次签到时间戳 小于当前时间戳代表今日还没签到
		self._retroactiveCount = data.miss_sign_cnt -- 已使用的补签次数

		if data.item_list and next(data.item_list) then
			if data.total_item_list then
				for k,v in pairs(data.total_item_list) do
					table.insert(data.item_list, v)
				end
			end
        	bee.showUiTask("BackpackClaimResult", {items = data.item_list, title = "activity_reward_title_tw"}, POP_TAG.Reward, LOBBY_POP_PRIORITY.Reward)
        end
        if data.ext_item_list then
        	bee.showUiTask("ShopMonthlyCardReward", {items = data.ext_item_list}, POP_TAG.Reward, LOBBY_POP_PRIORITY.RewardMonthlyCard)
        end
        bee.runTask(POP_TAG.Reward)

		bee.emit("evt_ActivitySignIn")
	end)
end

function P:checkSignIn()
	if not self._curSignInDay then
		return
	end
	if not self:getIsSigned(self:getCurSignInDay()) then
        bee.showUiTask("ActivityMain", {activityId = ActivityId.SevenSignIn}, nil, LOBBY_POP_PRIORITY.SignIn)
    end
end

function P:getCurSignInDay()
	return self._curSignInDay or 1
end

function P:evt_serverTimeCrossDay()
	bee.once(math.random(1, 60), function()
		self:initSignData()
    end)
end

