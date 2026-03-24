local P = class("SevenDayTaskModel", BaseModel)

function P:ctor()
	self.saveData = {
		cloud = {
			-- files .. uid = {seven_day_tasks_stage = {}}
		}
	}
	P.super.ctor(self)

	-- if not self.cloud["files" .. PlayerModel:getUid()] then
	-- 	self.cloud["files" .. PlayerModel:getUid()] = {}
	-- end
	-- self._localData = self.cloud["files" .. PlayerModel:getUid()]
end

function P:initSevenTask()
	-- if not self._localData.seven_day_tasks_stage then
	-- 	-- 初始化七日任务配置(存本地)
		Net:post("task/sevenTaskConf", nil, function(data)
			if data.code ~= 0 then
				return
			end

			-- if not self.cloud["files" .. PlayerModel:getUid()] then
			-- 	self.cloud["files" .. PlayerModel:getUid()] = {}
			-- end
			-- self.cloud["files" .. PlayerModel:getUid()].seven_day_tasks_stage = data.seven_day_tasks_stage
			-- self._localData = self.cloud["files" .. PlayerModel:getUid()]
			-- self:onSave()

			self._seven_day_tasks_stage_list = data.seven_day_tasks_stage
			self._seven_day_tasks_stage_dic = {}
			for k,v in pairs(data.seven_day_tasks_stage) do
				self._seven_day_tasks_stage_dic[v.id] = v
			end
		end)
	-- else
	-- 	self._seven_day_tasks_stage_dic = {}
	-- 	for k,v in pairs(self._localData.seven_day_tasks_stage) do
	-- 		self._seven_day_tasks_stage_dic[v.id] = v
	-- 	end
	-- end

	self:requestSevenDayTaskList()
	self._curQuestionGroup = nil
	self:initAnswerList()
end

function P:initAnswerList()
	if not self._curQuestionGroup then
		Net:post("activity/answerList", nil, function(data)
			if data.code ~= 0 then
				return
			end

			self._curQuestionGroup = data.group
			self._curQuestionId = data.id
		end)
	end
end

function P:requestSevenDayTaskList()
	self._task_data = {}
	self._task_list = {}
	Net:post("task/sevenTaskList", {immediately = true}, function(data)
		if data.code ~= 0 then
			return
		end

		self._task_data = data.data
		
		for k,v in pairs(data.list) do
			self._task_list[v.task_id] = v
		end

		if data.list and next(data.list) then
			self:refreshRedPoint()
		end

		if ShopModel:isMonthlyCard() and self:getCurUnlockChapterStatus() == SevenDayTaskStatus.Rewarded then
			SevenDayTaskModel:requestOpenNextChapter()
		end

		bee.emit("evt_refreshSevenDayTask")
	end)
end

-- 获取任务状态
function P:getTaskInfo(id)
	return self._task_list[id]
end

-- 获取章节配置
function P:getChapterInfo(index)
	if not self._seven_day_tasks_stage_list then
		self:initSevenTask()
		return
	end
	for k, v in pairs(self._seven_day_tasks_stage_list) do
		if v.id == index then
			return v
		end
	end
end

local _sortSevenDayTaskList = function(list)
	if not list then
		return {}
	end

	local list1 = {}	-- 已完成未领取
	local list2 = {}	-- 未完成
	local list3 = {}	-- 已领取

	for k,v in pairs(list) do
		local data = SevenDayTaskModel:getTaskInfo(v.task_id)
		if data.status == TaskStatus.Completed then
			table.insert(list1, v)
		elseif data.status == TaskStatus.InProgress then
			table.insert(list2, v)
		elseif data.status == TaskStatus.Received then
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

-- 根据章节获取任务列表
function P:getTaskListByChapter(index, isSort)
	if not self._seven_day_tasks_stage_dic then
		return {}
	end
	if not self._seven_day_tasks_stage_dic[index] then
		return {}
	end
	local list = {}
	for k, v in pairs(self._seven_day_tasks_stage_dic[index].chapter_task) do
		table.insert(list, tpl_seven_day_tasks[v])
	end
	if isSort then
		return _sortSevenDayTaskList(list)
	else
		return list
	end
end

-- 获取当前章节已完成任务个数
function P:getChapterCompleteTaskCount(index)
	local count = 0
	for k,v in pairs(self:getTaskListByChapter(index)) do
		local data = SevenDayTaskModel:getTaskInfo(v.task_id)
		if data.status == TaskStatus.Received then
			count = count + 1
		end
	end
	return count
end

-- 获取当前解锁的章节
function P:getCurUnlockChapter()
	if not self._task_data then
		return
	end
	return self._task_data.cur_day
end

-- 获取当前解锁章节的状态
function P:getCurUnlockChapterStatus()
	if not self._task_data then
		return
	end
	return self._task_data.status
end

-- 获取章节状态
function P:getChapterStatus(index)
	local curUnlock = self:getCurUnlockChapter()
	if index > curUnlock then
		if self:getCurUnlockChapterStatus() == SevenDayTaskStatus.Running then
			return SevenDayChapterStatus.Locked
		else
			return SevenDayChapterStatus.UnReach
		end
	elseif index == curUnlock then
		if self:getCurUnlockChapterStatus() == SevenDayTaskStatus.Running then
			return SevenDayChapterStatus.Running
		else
			return SevenDayChapterStatus.Completed
		end
	else
		return SevenDayChapterStatus.Completed
	end
end

-- 获取题目组
function P:getQuestionGroup(groupId)
	local list = {}
	for k,v in pairs(tpl_question_bank) do
		if v.group == groupId then
			table.insert(list, v)
		end
	end
	table.sort(list, function(a, b) return a.order < b.order end)
	return list
end

-- 获取当前答题进度id
function P:getQuestionProgressId(groupId)
	if not self._curQuestionGroup then
		return 0
	end
	if groupId > self._curQuestionGroup then
		return 0
	elseif groupId < self._curQuestionGroup then
		return 4
	elseif groupId == self._curQuestionGroup then
		return self._curQuestionId
	end
end

function P:sendAnswer(group, id, cb)
	if group < self._curQuestionGroup then
		return
	elseif group == self._curQuestionGroup and id <= self._curQuestionId then
		return
	elseif group > self._curQuestionGroup and id ~= 1 then
		return
	end

	local args = {}
	args.group = group
	args.id = id
	Net:post("activity/answer", args, function(data)
		if data.code ~= 0 then
			return
		end

		self._curQuestionGroup = group
		self._curQuestionId = id

		if not self._isWaitingRefresh then
			self._isWaitingRefresh = true
			scheduler:once(0.5, function()
				self:requestSevenDayTaskList()
				self._isWaitingRefresh = false
			end)
		end

		if cb then
			cb()
		end
	end)
end

function P:evt_NoticeBRC(params)
	if params.type == tpl_PushConsts.SEVEN_TASK_REFRESH.code then
        self:requestSevenDayTaskList()
	end
end

-- 领取任务奖励
function P:receiveSevenDayTaskReward(id)
	local args = {}
	args.id_arr = {id}
	args.task_cate = TaskCate.SevenDay
	Net:post("task/recReward", args, function(data)
		if data.code ~= 0 then
			return
		end

		-- 获得展示界面
		local rewards = {}
		if data.reward_chips and data.reward_chips > 0 then
			table.insert(rewards, {major_type = GMajorType.PROP, item_id = GPropId.Gold, num = data.reward_chips})
		end
		if data.reward_point and data.reward_point > 0 then
			table.insert(rewards, {major_type = GMajorType.PROP, item_id = GPropId.ActivePoint, num = data.reward_point})
		end
		if data.item_list then
			for k, v in pairs(data.item_list) do
				local isIn = false
				for k1, v1 in pairs(rewards) do
					if v1.item_id == v.item_id then
						v1.num = v.num + v1.num
						isIn = true
						break
					end
				end
				if not isIn then
					table.insert(rewards, v)
				end
			end
		end
		if next(rewards) then
			ShopModel:showRewardView(rewards, function()
				self:requestSevenDayTaskList()
			end)
		end	
	end)
end

-- 领取章节奖励
function P:receiveSevenDayChapterReward(groupId)
	Net:post("task/recChapterReward", nil, function(data)
		if data.code ~= 0 then
			return
		end

		UiManager:showUI("SevenDayTaskplot", {id = groupId, closeCb = function()
			if data.item_list then
				ShopModel:showRewardView(data.item_list, function()
					self:requestSevenDayTaskList()
				end)
			end
		end})
	end)
end

-- 开启下一章节任务
function P:requestOpenNextChapter()
	if self:getCurUnlockChapterStatus() == SevenDayTaskStatus.Running then
		return
	end
	Net:post("task/openNextChapter", nil, function()
		self:requestSevenDayTaskList()
	end)
end

-- 上传签名
function P:sendCertificationSign(body, cb)
	Net:post("task/uploadAuthCert", {body = body, suffix = "png"}, function(data)
		if data.code ~= 0 then
			return
		end

		-- 重新获取个人信息
		Net:sendReq("pb.SelfUserInfoREQ", {})
		scheduler:once(0.5, function()
			self:requestSevenDayTaskList()
		end)

		if cb then
			cb(data.url)
		end
	end)
end

-- 获取跨天剩余时间
function P:getCrossDayLeftTime()
	local curTime = bee.getServerTime()
	local utc_date = os.date("!*t", curTime)
	local crossTime
	if utc_date.hour < TimeHelp.crossHour then
		crossTime = os.time({year = utc_date.year, month = utc_date.month, day = utc_date.day, hour = TimeHelp.crossHour, min = 0, sec = 0})
	else
		crossTime = os.time({year = utc_date.year, month = utc_date.month, day = utc_date.day + 1, hour = TimeHelp.crossHour, min = 0, sec = 0})
	end
	return crossTime - curTime
end

-- 跨天
function P:evt_serverTimeCrossDay()
	bee.once(math.random(1, 60), function()
		self:requestSevenDayTaskList()
    end)
end

-- 刷新红点
function P:refreshRedPoint()
	-- 未签名认证红点
	if self:getCurUnlockChapterStatus() == SevenDayTaskStatus.Completed then
		RedManager:removeTag(RedTag.TaskChapterTag, 7)
		RedManager:addTag(RedTag.Sign)
		return
	elseif self:getCurUnlockChapterStatus() == SevenDayTaskStatus.Upload then
		RedManager:removeTag(RedTag.Sign)
		return
	end

	for i = 1, 7 do
		if i == self:getCurUnlockChapter() then
			local taskList = SevenDayTaskModel:getTaskListByChapter(i)
			local completedCount = 0
			for k,v in pairs(taskList) do
				local info = self:getTaskInfo(v.task_id)
				if info.status == TaskStatus.Completed then
					-- 未领取奖励红点
					RedManager:addTag(RedTag.TaskChapterTag, i)
					return
				elseif info.status == TaskStatus.Received then
					completedCount = completedCount + 1
				end
				if completedCount == #taskList and self:getChapterStatus(i) ~= SevenDayChapterStatus.Completed then
					-- 章节未认证红点
					RedManager:addTag(RedTag.TaskChapterTag, i)
					return
				else
					RedManager:removeTag(RedTag.TaskChapterTag, i)
				end
			end
		else
			RedManager:removeTag(RedTag.TaskChapterTag, i)
		end
	end
end

