local P = class("TaskView", UiFullView)

local MaxRewardCount = 5

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")

	local Center = self:find("Center", self.AnimRoot)
	self.CharacterImage = self:find("CharacterImage", Center)
	self.BubbleItem = self:find("BubbleItem", Center)
	self.DailyToggle = self:find("Tab/DailyToggle", Center)
	self.WeeklyToggle = self:find("Tab/WeeklyToggle", Center)
	self.ChallengeToggle = self:find("Tab/ChallengeToggle", Center)
	RedManager:bind(self:find("RedPoint", self.DailyToggle), RedTag.DailyTask)
	RedManager:bind(self:find("RedPoint", self.WeeklyToggle), RedTag.WeeklyTask)
	RedManager:bind(self:find("RedPoint", self.ChallengeToggle), RedTag.ChallengeTask)

	local Reward = self:find("Reward", Center)
	self.CurPointText = self:find("PointList/Point/CurPointText", Reward)
	self.Point = self:find("PointList/Point", Reward)
	self.RewardSlider = self:find("RewardSlider", Reward)
	self.rewardItemList = {}
	for i = 1, MaxRewardCount do
		self.rewardItemList[i] = self:find("PointList/Reward" .. i, Reward)
	end

	self.TaskListObj = self:find("TaskList", Center)
	self.Item1 = self:find("Item1", self.TaskListObj)
	self.Item1:SetActive(false)

	self.TipsText = self:find("task_bg_02/TipsText", Center)
	self.ClaimButton = self:find("ClaimButton", Center)
	self.ClaimGreyButton = self:find("ClaimGreyButton", Center)

	local LeftTop = self:find("LeftTop", self.AnimRoot)
	self.BackButton = self:find("BackButton", LeftTop)
	bee.addClick(self.BackButton, function()
		if self.characterCls then
			self.characterCls:stopVoice()
		end
		self:hideUI()
	end)

	bee.addClick2(self.DailyToggle, function()
		if self._selectType == TaskCate.Daily then
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectType = TaskCate.Daily
		self:setToggleShow()
		self:setActivePointCont()
		self:refreshTaskList(true)
	end)
	bee.addClick2(self.WeeklyToggle, function()
		if self._selectType == TaskCate.Weekly then
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectType = TaskCate.Weekly
		self:setToggleShow()
		self:setActivePointCont()
		self:refreshTaskList(true)
	end)
	bee.addClick2(self.ChallengeToggle, function()
		if self._selectType == TaskCate.Challenge then
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectType = TaskCate.Challenge
		self:setToggleShow()
		self:setActivePointCont()
		self:refreshTaskList(true)
	end)

	bee.addClick(self.ClaimButton, function()
		TaskModel:receiveTaskReward(nil, self._selectType)
		self:checkReceiveVoice()
	end)
	bee.addClick(self.ClaimGreyButton, function()
		UiManager:showToast(_T("LAB_TASKS_NOREWARDS"))
	end)

	bee.addClick(self.Point, function()
		Game:playSound("ui_button_confirm")
		if self._selectType == TaskCate.Daily then
			UiManager:showUI("CommonItemTip", {data = {item_id = GPropId.ActivePoint, num = 0}, target = self.Point})
		elseif self._selectType == TaskCate.Weekly then
			UiManager:showUI("CommonItemTip", {data = {item_id = GPropId.WeeklyPoint, num = 0}, target = self.Point})
		elseif self._selectType == TaskCate.Challenge then
			UiManager:showUI("CommonItemTip", {data = {item_id = GPropId.ChallengePoint, num = 0}, target = self.Point})
		end
	end)
end

function P:onStart()
	if self._params and self._params.jump and self._params.jump.sub_page then
		self._selectType = self._params.jump.sub_page[1]
	else
		self._selectType = TaskCate.Daily
	end
	self:setToggleShow()
	self:setActivePointCont()

	TaskModel:requestTaskList(true)

	self._role = CharacterModel:getUsingRole()
    if self._role then
        self.characterCls = ObjectPool:getCls(self.CharacterImage)
        self.characterCls:setRole(self._role)
        self.characterCls:setBubbleItem(self.BubbleItem)
        self:initClickVoice()
        self._characterInit = true
    end

    bee.setIconInAtlas(self.Point, tpl_props[GPropId.ActivePoint].icon)

	self:taskGuide()
end

function P:evt_taskUpdate()
	if not self._selectType then
		if not TaskModel:getTaskActiveIsAllRewarded(TaskCate.Daily) then
			self._selectType = TaskCate.Daily
		elseif not TaskModel:getTaskActiveIsAllRewarded(TaskCate.Weekly) then
			self._selectType = TaskCate.Weekly
		elseif TaskModel:isHaveChallengeTask() and (not TaskModel:getTaskActiveIsAllRewarded(TaskCate.Challenge)) then
			self._selectType = TaskCate.Challenge
		else
			self._selectType = TaskCate.Daily
		end
		self:setToggleShow()
	end

	self:setActivePointCont()
	self:refreshTaskList(false)

	if self._characterInit then
		self:playCharacterGreeting()
		self._characterInit = false
	end

	self.ChallengeToggle:SetActive(TaskModel:isHaveChallengeTask())
end

-- 播放打招呼语音
function P:playCharacterGreeting()
	if not self.characterCls then
		return
	end

	local skinCfg = self._role:getSkinData()
	local greetingCfg
	if TaskModel:isCanRecTaskReward(TaskCate.Daily) or TaskModel:isCanRecTaskReward(TaskCate.Weekly) then
		greetingCfg = skinCfg.task_receive_voice
	else
		greetingCfg = skinCfg.task_normal_voice
	end
	if greetingCfg then
		local voice = {sound = greetingCfg[1], face = greetingCfg[2], text = greetingCfg[3]}
		self.characterCls:playVoice(voice)
	end
end

-- 初始化点击语音
function P:initClickVoice()
	if not self.characterCls then
		return
	end

	local voiceCfg = self._role:getSkinData().task_click_voice
	local chatList = {}
	if voiceCfg then
		for i = 1, #voiceCfg, 3 do
			table.insert(chatList, {sound = voiceCfg[i], face = voiceCfg[i + 1], text = voiceCfg[i + 2]})
		end
	end
	self.characterCls:initClickVoice(chatList)
end

function P:evt_updateMonthlyCard()
	self:refreshTaskList(false)
end

function P:setToggleShow()
	self:find("task_tab_on", self.DailyToggle):SetActive(self._selectType == TaskCate.Daily)
	self:find("task_tab_off", self.DailyToggle):SetActive(self._selectType ~= TaskCate.Daily)

	self:find("task_tab_on", self.WeeklyToggle):SetActive(self._selectType == TaskCate.Weekly)
	self:find("task_tab_off", self.WeeklyToggle):SetActive(self._selectType ~= TaskCate.Weekly)

	self:find("task_tab_on", self.ChallengeToggle):SetActive(self._selectType == TaskCate.Challenge)
	self:find("task_tab_off", self.ChallengeToggle):SetActive(self._selectType ~= TaskCate.Challenge)
end

local PointListWidth = 852
function P:setActivePointCont()
	local pointData = TaskModel:getTaskPointData(self._selectType)
	local maxPointCount = #pointData

	if self._selectType == TaskCate.Weekly then
		bee.setIconInAtlas(self.Point, tpl_props[GPropId.WeeklyPoint].icon)
	elseif self._selectType == TaskCate.Challenge then
		bee.setIconInAtlas(self.Point, tpl_props[GPropId.ChallengePoint].icon)
	else
		bee.setIconInAtlas(self.Point, tpl_props[GPropId.ActivePoint].icon)
	end

	local val = TaskModel:getTaskPointVal(self._selectType)
	bee.setText(self.CurPointText, val)

	local delVal = 1 / maxPointCount
	local showVal = 0
	for i, v in ipairs(pointData) do
		if val >= v.reward_point then
			showVal = showVal + delVal
		else
			local lastRewardPoint = pointData[i - 1] and pointData[i - 1].reward_point or 0
			local a = val - lastRewardPoint
			local b = v.reward_point - lastRewardPoint
			showVal = showVal + (a / b * delVal)
			break
		end
	end
	bee.setSliderValue(self.RewardSlider, showVal)

	for i = 1, MaxRewardCount do
		local item = self.rewardItemList[i]
		if pointData[i] then
			item:SetActive(true)
			item.transform.localPosition = bee.v3((i / maxPointCount) * PointListWidth - PointListWidth / 2, -8.1, 0)

			local PointCountText = self:find("PointCountText", item)
			local Icon = self:find("Icon", item)
			local Check = self:find("Check", item)
			local OpenEffect = self:find("OpenEffect", item)
			bee.setText(PointCountText, pointData[i].reward_point)

			local isReward = TaskModel:getTaskActiveIsRewarded(self._selectType, pointData[i].id)
			OpenEffect:SetActive(val >= pointData[i].reward_point and not isReward)
			Check:SetActive(isReward)
			Icon:SetActive(not isReward)

			bee.removeAllClick(item)
			bee.addClick(item, function()
				if val >= pointData[i].reward_point and not isReward then
					TaskModel:receivePointReward(pointData[i].id, self._selectType)
					self:checkReceiveVoice()
				else
					Game:playSound("ui_button_confirm")
					UiManager:showUI("CommonPackageTip", {items = pointData[i].item_list, target = item})
				end
			end)
		else
			item:SetActive(false)
		end
	end

	if self._selectType == TaskCate.Weekly or self._selectType == TaskCate.Challenge then
		bee.setText(self.TipsText, _T("LAB_TASKS_UI_18"))
	else
		bee.setText(self.TipsText, _T("LAB_TASKS_UI_06"))
	end
end

function P:initTaskList()
	self.taskList = UiListEx:create(self.TaskListObj)
	self.taskList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.Item1)
	end)
	self.taskList:setRefreshFunc(function(data, item, isInit, index)
		self:setTaskItem(item, data, isInit, index)
	end)
	self.taskList:setWidth(156)
	self.taskList:setTopBottom(0, 40)
end

function P:refreshTaskList(isInit)
	local data
	if self._selectType == TaskCate.Weekly then
		data = TaskModel:getWeeklyTaskList()
	elseif self._selectType == TaskCate.Challenge then
		data = TaskModel:getChallengeTaskList()
	else
		data = TaskModel:getDailyTaskList()
	end

	if not self.taskList then
		self:initTaskList()
		self:once(0.15, function()
			self.taskList:setDatas(data)
		end)
	else
		self.taskList:setDatas(data, isInit)
	end

	local isCanRecTaskReward = TaskModel:isCanRecTaskReward(self._selectType)
	self.ClaimButton:SetActive(isCanRecTaskReward)
	self.ClaimGreyButton:SetActive(not isCanRecTaskReward)
end

function P:setTaskItem(item, data, isInit, index)
    local Ani_root = self:find("Ani_root", item)
	local TaskText = self:find("TaskText", Ani_root)
	local Icon2 = self:find("Icon2", Ani_root)
	local Icon1 = self:find("Icon1", Ani_root)
	local ActivateButton = self:find("ActivateButton", Ani_root)
	local GoButton = self:find("GoButton", Ani_root)
	local ReceiveButton = self:find("ReceiveButton", Ani_root)
	local TagClaimed = self:find("TagClaimed", Ani_root)
	local MonthlyCardTag = self:find("MonthlyCardTag", Ani_root)
	local Mask = self:find("Mask", Ani_root)

    if isInit and index > 0 then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_TaskView_item_into", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_TaskView_item_idle", Ani_root)
    end

	local cfg
	if self._selectType == TaskCate.Daily then
		cfg = tpl_dailytasks[data.task_id]
	elseif self._selectType == TaskCate.Weekly then
		cfg = tpl_weeklytasks[data.task_id]
	elseif self._selectType == TaskCate.Challenge then
		cfg = tpl_challengetasks[data.task_id]
	end
	if not cfg then
		return
	end

	-- 任务描述
	local showText = TaskModel:getTaskDesc(cfg, data)
	local needValue = #data.value == 1 and data.value[1] or data.value[2]
	if cfg.task_type == 313 then
		needValue = data.value[3]
	end
	if data.current_value < needValue then
		showText = showText .. " (" .. "<color=#ec0b7a>" .. _N(data.current_value) .. "</color>/" ..  _N(needValue) .. ")"
	else
		local cur = math.min(data.current_value, needValue)
		showText = showText .. " (" .. _N(cur) .. "/" ..  _N(needValue) .. ")"
	end
	bee.setText(TaskText, showText)

	local rewards = ShopModel:getRewardsList(cfg.rewards)
	local rewardId1, rewardId2, rewardCount1, rewardCount2
	if #rewards > 1 then
		rewardId1 = rewards[1].item_id
		rewardCount1 = rewards[1].num
		rewardId2 = rewards[2].item_id
		rewardCount2 = rewards[2].num
	else
		rewardId1 = rewards[1].item_id
		rewardCount1 = rewards[1].num
		if self._selectType == TaskCate.Weekly then
			rewardId2 = GPropId.WeeklyPoint
		elseif self._selectType == TaskCate.Challenge then
			rewardId2 = GPropId.ChallengePoint
		else
			rewardId2 = GPropId.ActivePoint
		end
		rewardCount2 = cfg.reward_point
	end

	bee.setIconInAtlas(Icon1, tpl_props[rewardId1].icon)
	bee.setText(self:find("CountText", Icon1), _N(rewardCount1))
	bee.setIconInAtlas(Icon2, tpl_props[rewardId2].icon)
	bee.setText(self:find("CountText", Icon2), _N(rewardCount2))

	bee.removeAllClick(Icon2)
	bee.addClick(Icon2, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonItemTip", {data = {item_id = rewardId2, num = 0}, target = Icon2})
	end)
	bee.removeAllClick(Icon1)
	bee.addClick(Icon1, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonItemTip", {data = {item_id = rewardId1, num = 0}, target = Icon1})
	end)

	MonthlyCardTag:SetActive(data.monthly_card_task)

	-- 月卡专属
	if data.monthly_card_task and not ShopModel:isMonthlyCard() then
		ActivateButton:SetActive(true)
		GoButton:SetActive(false)
		ReceiveButton:SetActive(false)
	elseif data.status == TaskStatus.InProgress then
		ActivateButton:SetActive(false)
		GoButton:SetActive(true)
		ReceiveButton:SetActive(false)
	elseif data.status == TaskStatus.Completed then
		ActivateButton:SetActive(false)
		GoButton:SetActive(false)
		ReceiveButton:SetActive(true)
	elseif data.status == TaskStatus.Received then
		ActivateButton:SetActive(false)
		GoButton:SetActive(false)
		ReceiveButton:SetActive(false)
	end

	TagClaimed:SetActive(data.status == TaskStatus.Received)

	bee.removeAllClick(ActivateButton)
	bee.addClick(ActivateButton, function()
		Game:playSound("ui_button_confirm")
		ItemModel:jumpView(101002)
	end)
	bee.removeAllClick(GoButton)
	bee.addClick(GoButton, function()
		Game:playSound("ui_button_confirm")
		-- 前往跳转
		if cfg.jump then
			if cfg.jump == 4001 then
				if self.characterCls then
					self.characterCls:stopVoice()
				end
				self:hideUI()
			else
				ItemModel:jumpView(cfg.jump)
			end
		end
	end)
	bee.removeAllClick(ReceiveButton)
	bee.addClick(ReceiveButton, function()
		TaskModel:receiveTaskReward(data.id, self._selectType)
		self:checkReceiveVoice()
	end)
end

-- 领取奖励语音
function P:checkReceiveVoice()
	self._waitClaimResult = nil
	if not TaskModel:getTaskActiveIsAllRewarded(self._selectType) then
		self._waitClaimResult = clone(self._selectType)
	end
end

function P:evt_ColorGameActionRSP()
	self:once(0.5, function()
		TaskModel:requestTaskList()
	end)
end

function P:evt_PinballActionRSP()
	self:once(0.5, function()
		TaskModel:requestTaskList()
	end)
end

-- 领取奖励后语音
function P:evt_BackpackClaimResultClose()
	if not self._waitClaimResult then
		return
	end
	if not self.characterCls then
		return
	end

	local pointData = TaskModel:getTaskPointData(self._waitClaimResult)
	local maxPoint = pointData[#pointData].reward_point
	local curPoint = TaskModel:getTaskPointVal(self._waitClaimResult)
	local isReach = curPoint >= maxPoint

	local voiceCfg
	if isReach then
		voiceCfg = self._role:getSkinData().award_enough_voice
	else
		voiceCfg = self._role:getSkinData().award_notenough_voice
	end
	if voiceCfg then
		local voice = {sound = voiceCfg[1], face = voiceCfg[2], text = voiceCfg[3]}
		self.characterCls:playVoice(voice)
	end
	self._waitClaimResult = nil
end

--引导
function P:taskGuide()
	GuideManager:startSystemGuide(15001, 0.65)

end

function P:evt_guide_turn_week()
	self.WeeklyToggle:GetComponent("Button").onClick:Invoke()
	local maxCount = table.nums(self.rewardItemList)
	local item = self.rewardItemList[maxCount]
	item:GetComponent("Button").onClick:Invoke()
end

function P:evt_guide_turn_challenge()
	self.ChallengeToggle:GetComponent("Button").onClick:Invoke()
end


return P