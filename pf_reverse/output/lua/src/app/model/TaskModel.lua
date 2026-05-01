local P = class("TaskModel", BaseModel)

function P:ctor()
	self.saveData = {}
	P.super.ctor(self)

	self._reportTasks = {}	-- 已经上报的任务信息
end

function P:requestTaskList(immediately)
	local args = {}
	args.immediately = immediately
	Net:post("task/list", args, function(data)
		if data.code ~= 0 then
			return
		end

		self._daily_task_list = data.daily_list 	-- 每日任务列表
		self._weekly_task_list = data.weekly_list 	-- 每周任务列表
		self._challenge_task_list = data.challenge_list -- 挑战任务列表
		self._point_data = data.point_data 			-- 活跃点数据
		-- 每日活跃点配置
		self._daily_point_conf_list = data.daily_point_conf_list
		table.sort(self._daily_point_conf_list, function(a, b) return a.reward_point < b.reward_point end)
		-- 每周活跃点配置
		self._weekly_point_conf_list = data.weekly_point_conf_list
		table.sort(self._weekly_point_conf_list, function(a, b) return a.reward_point < b.reward_point end)
		-- 挑战任务活跃点配置
		self._challenge_point_conf_list = data.challenge_point_conf_list
		table.sort(self._challenge_point_conf_list, function(a, b) return a.reward_point < b.reward_point end)

		self:refreshRedPoint()

		bee.emit("evt_taskUpdate")
	end)
end

function P:reportTask(task_type, id)
	if task_type == TaskType.RoleInteraction then
		-- 查找是否有 TaskType.RoleInteraction 的任务
		if not self:isHaveTaskType(task_type) then
			return
		end
	end

	local args = {}
	args.task_type = task_type
	args.id = id or 0
	Net:post("task/report", args, function(data)
		if data.code ~= 0 then
			return
		end
	end)
end

function P:isHaveTaskType(task_type)
	local flag = false
	for _, v in ipairs(self._daily_task_list or {}) do
		if v.status == TaskStatus.InProgress then
			local cfg = tpl_dailytasks[v.task_id]
			if cfg and cfg.task_type == task_type then
				flag = true
				break
			end
		end
	end
	if not flag then
		for _, v in ipairs(self._weekly_task_list or {}) do
			if v.status == TaskStatus.InProgress then
				local cfg = tpl_weeklytasks[v.task_id]
				if cfg and cfg.task_type == task_type then
					flag = true
					break
				end
			end
		end
	end
	return flag
end

-- 获取任务活跃数据
function P:getTaskPointData(task_cate)
	if task_cate == TaskCate.Daily then
		return self._daily_point_conf_list or {}
	elseif task_cate == TaskCate.Weekly then
		return self._weekly_point_conf_list or {}
	elseif task_cate == TaskCate.Challenge then
		return self._challenge_point_conf_list or {}
	end
	return {}
end

-- 每日任务奖励点是否已领取
function P:_getDailyActiveIsRewarded(id)
	if not self._point_data.daily_reward_id_list then
		return false
	end
	for k,v in pairs(self._point_data.daily_reward_id_list) do
		if v == id then
			return true
		end
	end
	return false
end

-- 每周任务奖励点是否已领取
function P:_getWeeklyActiveIsRewarded(id)
	if not self._point_data.weekly_reward_id_list then
		return false
	end
	for k,v in pairs(self._point_data.weekly_reward_id_list) do
		if v == id then
			return true
		end
	end
	return false
end

-- 挑战任务奖励点是否已领取
function P:_getChallengeActiveIsRewarded(id)
	if not self._point_data.challenge_reward_id_list then
		return false
	end
	for k,v in pairs(self._point_data.challenge_reward_id_list) do
		if v == id then
			return true
		end
	end
	return false
end

-- 任务活跃点奖励是否已领取
function P:getTaskActiveIsRewarded(task_cate, id)
	if task_cate == TaskCate.Daily then
		return self:_getDailyActiveIsRewarded(id)
	elseif task_cate == TaskCate.Weekly then
		return self:_getWeeklyActiveIsRewarded(id)
	elseif task_cate == TaskCate.Challenge then
		return self:_getChallengeActiveIsRewarded(id)
	end
end

-- 获取每日活跃点
function P:getDailyPointVal()
	if not self._point_data then
		return 0
	end
	return self._point_data.daily_point
end

-- 获取每周活跃点
function P:getWeeklyPointVal()
	if not self._point_data then
		return 0
	end
	return self._point_data.weekly_point
end

-- 获取任务活跃点
function P:getTaskPointVal(task_cate)
	if not self._point_data then
		return 0
	end
	if task_cate == TaskCate.Daily then
		return self._point_data.daily_point
	elseif task_cate == TaskCate.Weekly then
		return self._point_data.weekly_point
	elseif task_cate == TaskCate.Challenge then
		return self._point_data.challenge_point
	end
	return 0
end

function P:getTaskActiveIsAllRewarded(task_cate)
	local pointData = self:getTaskPointData(task_cate)
	local maxId = #pointData
	return self:getTaskActiveIsRewarded(task_cate, pointData[maxId].id)
end

local _sortTaskList = function(list)
	if not list then
		return {}
	end

	local list1 = {}	-- 已完成未领取
	local list2 = {}	-- 未完成
	local list3 = {}	-- 已领取

	for k,v in pairs(list) do
		if v.status == TaskStatus.Completed then
			table.insert(list1, v)
		elseif v.status == TaskStatus.InProgress then
			table.insert(list2, v)
		elseif v.status == TaskStatus.Received then
			table.insert(list3, v)
		end
	end

	table.sort(list1, function(a, b) return a.sort < b.sort end)
	table.sort(list2, function(a, b) return a.sort < b.sort end)
	table.sort(list3, function(a, b) return a.sort < b.sort end)

	for i,v in ipairs(list2) do
		table.insert(list1, v)
	end
	for i,v in ipairs(list3) do
		table.insert(list1, v)
	end
	return list1
end

-- 获取每日任务列表
function P:getDailyTaskList()
	return _sortTaskList(self._daily_task_list)
end

-- 获取每周任务列表
function P:getWeeklyTaskList()
	return _sortTaskList(self._weekly_task_list)
end

-- 获取挑战任务列表
function P:getChallengeTaskList()
	if not self._challenge_task_list then
		return {}
	end
	return _sortTaskList(self._challenge_task_list)
end

-- 是否有挑战任务
function P:isHaveChallengeTask()
	if not self._challenge_task_list or not next(self._challenge_task_list) then
		return false
	end
	return true
end

-- 获取任务描述
function P:getTaskDesc(cfg, data)
	local value = cfg.value
	if data then
		value = data.value
	end
	local valCount = #value
	if cfg.task_type == 311 then
		return _T(cfg.dec)
	elseif cfg.task_type == 313 then
		return _F(cfg.dec, value[3])
	elseif valCount == 1 then
		return _F(cfg.dec, _N(value[1]))
	elseif valCount == 2 then
		if value[1] == 0 then
			-- 任意玩法
			return _F(cfg.dec, _N(value[2]))
		elseif tpl_task_type_info[value[1]] then
			return _F(cfg.dec, _N(value[2]), _T(tpl_task_type_info[value[1]].name))
		else
			return _F(cfg.dec, _N(value[2]))
		end
	else
		return _T(cfg.dec)
	end
end

function P:getTaskCanReceiveList(task_cate)
	local taskList
	if task_cate == TaskCate.Daily then
		taskList = self:getDailyTaskList()
	elseif task_cate == TaskCate.Weekly then
		taskList = self:getWeeklyTaskList()
	elseif task_cate == TaskCate.Challenge then
		taskList = self:getChallengeTaskList()
	end

	local list = {}
	if not taskList then
		return list
	end
	local isMonthlyCard = ShopModel:isMonthlyCard()
	for k, v in pairs(taskList) do
		if v.status == TaskStatus.Completed then
			if not v.monthly_card_task or isMonthlyCard then
				table.insert(list, v.id)
			end
		end
	end
	return list
end

-- 判断是否有可领取的任务奖励
function P:isCanRecTaskReward(task_cate)
	-- 任务奖励
	local ids = self:getTaskCanReceiveList(task_cate)

	-- 活跃点奖励
	local rewardPoints = self:getCanRewardTaskPointList(task_cate)

	if not next(ids) and not next(rewardPoints) then
		return false
	else
		return true
	end
end

-- 领取任务奖励
function P:receiveTaskReward(id, task_cate)
	if task_cate == 0 then
		return
	end
	local args = {}
	args.task_cate = task_cate
	if id then
		args.id_arr = {id}
		args.all = false
	else
		args.id_arr = self:getTaskCanReceiveList(task_cate)
		args.all = true
	end

	-- 活跃点奖励（一键领取时可同时领取活跃点奖励）
	local rewardPoints
	if args.all then
		rewardPoints = self:getCanRewardTaskPointList(task_cate)
	end

	-- 判断是否有可领取的
	if not args.id_arr or not next(args.id_arr) then
		if not rewardPoints or not next(rewardPoints) then
			UiManager:showToast(_T("LAB_TASKS_NOREWARDS"))
			return
		end
	end
	
	Net:post("task/recReward", args, function(data)
		if data.code ~= 0 then
			return
		end

		-- 红点消除
		if task_cate == TaskCate.Weekly then
			if rewardPoints then
				for k,v in pairs(rewardPoints) do
					RedManager:removeTag(RedTag.WeeklyPoint, v)
				end
			end
			if args.id_arr then
				for k,v in pairs(args.id_arr) do
					RedManager:removeTag(RedTag.WeeklyReward, v)
				end
			end
		elseif task_cate == TaskCate.Challenge then
			if rewardPoints then
				for k,v in pairs(rewardPoints) do
					RedManager:removeTag(RedTag.ChallengePoint, v)
				end
			end
			if args.id_arr then
				for k,v in pairs(args.id_arr) do
					RedManager:removeTag(RedTag.ChallengeReward, v)
				end
			end
		else
			if rewardPoints then
				for k,v in pairs(rewardPoints) do
					RedManager:removeTag(RedTag.DailyPoint, v)
				end
			end
			if args.id_arr then
				for k,v in pairs(args.id_arr) do
					RedManager:removeTag(RedTag.DailyReward, v)
				end
			end
		end

		-- 获得展示界面
		local rewards = {}
		if data.reward_chips and data.reward_chips > 0 then
			table.insert(rewards, {major_type = GMajorType.PROP, item_id = GPropId.Gold, num = data.reward_chips})
		end
		if data.reward_point and data.reward_point > 0 then
			if task_cate == TaskCate.Weekly then
				table.insert(rewards, {major_type = GMajorType.PROP, item_id = GPropId.WeeklyPoint, num = data.reward_point})
			elseif task_cate == TaskCate.Challenge then
				table.insert(rewards, {major_type = GMajorType.PROP, item_id = GPropId.ChallengePoint, num = data.reward_point})
			else
				table.insert(rewards, {major_type = GMajorType.PROP, item_id = GPropId.ActivePoint, num = data.reward_point})
			end
		end
		if data.item_list then
			for k, v in pairs(data.item_list) do
				table.insert(rewards, v)
			end
		end
		if next(rewards) then
			ShopModel:showRewardView(rewards)
		end

		self:requestTaskList()
	end)
end

-- 领取活跃点奖励
function P:receivePointReward(id, task_cate)
	Net:post("task/recPointReward", {id = id, task_cate = task_cate}, function(data)
		if data.code ~= 0 then
			return
		end

		if task_cate == TaskCate.Weekly then
			RedManager:removeTag(RedTag.WeeklyPoint, id)
		elseif task_cate == TaskCate.Challenge then
			RedManager:removeTag(RedTag.ChallengePoint, id)
		else
			RedManager:removeTag(RedTag.DailyPoint, id)
		end

		-- 获得展示界面
		ShopModel:showRewardView(data.item_list)

		self:requestTaskList()
	end)
end

function P:evt_NoticeBRC(params)
	if params.type == tpl_PushConsts.TASK_REFRESH.code then
        TaskModel:requestTaskList()
	end
end

function P:getCanRewardTaskPointList(task_cate)
	local pointVal = self:getTaskPointVal(task_cate)
	local pointData = self:getTaskPointData(task_cate)
	local list = {}
	for i,v in ipairs(pointData) do
		if pointVal >= v.reward_point then
			if not self:getTaskActiveIsRewarded(task_cate, v.id) then
				-- RedManager:addTag(RedTag.WeeklyPoint, v.id)
				table.insert(list, v.id)
			end
		end
	end
	return list
end

function P:refreshRedPoint()
	RedManager:removeTag(RedTag.Task)

	-- 每日活跃奖励
	for k,v in pairs(self:getCanRewardTaskPointList(TaskCate.Daily)) do
		RedManager:addTag(RedTag.DailyPoint, v)
	end
	-- 每周活跃奖励
	for k,v in pairs(self:getCanRewardTaskPointList(TaskCate.Weekly)) do
		RedManager:addTag(RedTag.WeeklyPoint, v)
	end
	-- 挑战任务活跃奖励
	for k,v in pairs(self:getCanRewardTaskPointList(TaskCate.Challenge)) do
		RedManager:addTag(RedTag.ChallengePoint, v)
	end

	-- 每日可领取任务
	for k, v in pairs(self:getTaskCanReceiveList(TaskCate.Daily)) do
		RedManager:addTag(RedTag.DailyReward, v)
	end
	-- 每周可领取任务
	for k, v in pairs(self:getTaskCanReceiveList(TaskCate.Weekly)) do
		RedManager:addTag(RedTag.WeeklyReward, v)
	end
	-- 挑战可领取任务
	for k, v in pairs(self:getTaskCanReceiveList(TaskCate.Challenge)) do
		RedManager:addTag(RedTag.ChallengeReward, v)
	end
end

-- 日常活跃点奖励已全部领取完成
function P:getDailyRewardIsAllReceived()
	for k,v in pairs(self:getDailyTaskList()) do
		if v.status ~= TaskStatus.Received then
			return false
		end
	end
	local dailyPointData = self:getDailyPointData()
	if dailyPointData then
		for k,v in pairs(dailyPointData) do
			if not self:getDailyActiveIsRewarded(v.id) then
				return false
			end
		end
	end
	return true
end

-- 周常活跃点奖励已全部领取完成
function P:getWeeklyRewardIsAllReceived()
	for k,v in pairs(self:getWeeklyTaskList()) do
		if v.status ~= TaskStatus.Received then
			return false
		end
	end
	for k,v in pairs(self:getWeeklyPointData()) do
		if not self:getWeeklyActiveIsRewarded(v.id) then
			return false
		end
	end
	return true
end

function P:evt_serverTimeCrossDay()
	bee.once(math.random(1, 60), function()
		self:requestTaskList()
		self._reportTasks = {}
    end)
end

return P