local P = class("CenterRewardCenter", Object)

function P:onAwake()
	self.DesignationReward = self:find("DesignationReward")
	self.RewardItem = self:find("RewardItem", self.DesignationReward)
	self.ScheduleSlider = self:find("ScheduleSlider", self.DesignationReward)
	self.ProgressText = self:find("ProgressText", self.ScheduleSlider)
	self.Max = self:find("MAX", self.ScheduleSlider)
	self.ClaimButton = self:find("State/ClaimButton", self.DesignationReward)
	self.InProgress = self:find("State/InProgress", self.DesignationReward)
	self.Received = self:find("State/Received", self.DesignationReward)
	
	self.TaskListObj = self:find("TaskList")
	self.Item01 = self:find("Item01", self.TaskListObj)
	self.Item01:SetActive(false)
	self.DesignationReward:SetActive(false)

	self.ClaimAllButton = self:find("ClaimAllButton")
	self.ClaimGrayButton = self:find("ClaimGrayButton")

	bee.addClick(self.ClaimButton, function()
		self:onClickClaimReward()
	end)
	bee.addClick(self.ClaimAllButton, function()
		self:onClickClaimAll()
	end)
end

function P:onStart()
	self:initTaskList()
	if not GuideManager:checkGuidePlayed(23002) then
		self:setTaskList()
	else
		DispatchModel:reqDispatchTaskList()
	end
end

function P:evt_updateDispatchTask()
	self:setTaskList()
end

function P:initTaskList()
	self.taskList = UiListEx:create(self.TaskListObj)
	self.taskList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.Item01)
	end)
	self.taskList:setRefreshFunc(function(data, item, isInit, index)
		self:setTaskItem(item, data, isInit, index)
	end)
	self.taskList:setWidth(206)
end

function P:setTaskList()
	self.DesignationReward:SetActive(true)
	local list = DispatchModel:getTaskList()
	table.sort(list, function(a, b)
		local sumA = 100000
		local sumB = 100000

		if a.status == 2 then
			sumA = sumA + 10000
		end
		if b.status == 2 then
			sumB = sumB + 10000
		end
		if a.status == 1 then
			sumA = sumA + 1000
		end
		if b.status == 1 then
			sumB = sumB + 1000
		end
		if a.status == 3 then
			sumA = sumA + 100
		end
		if b.status == 3 then
			sumB = sumB + 100
		end

		if a.finished_at > b.finished_at then
			sumA = sumA + 10
		end
		if b.finished_at > a.finished_at then
			sumB = sumB + 10
		end
		if a.task_id < b.task_id then
			sumA = sumA + 1
		end
		if b.task_id < a.task_id then
			sumB = sumB + 1
		end

		return sumA > sumB
	end)
	self.taskList:setDatas(list)

	-- 赛季奖励
	PropItem:create(self.RewardItem, {id = tpl_constdata.Dispatch_Season_Reward[1], num = tpl_constdata.Dispatch_Season_Reward[1]}):bindTips()

	local isRewardSeason = DispatchModel:seasonRewardIsReward()	-- 赛季奖励是否已领取
	local totalCount = 0
	local completedCount = 0
	local waitReceivedCount = 0
	for k, v in pairs(list) do
		totalCount = totalCount + 1
		if v.status ~= TaskStatus.InProgress then
			completedCount = completedCount + 1
			if v.status == TaskStatus.Completed then
				waitReceivedCount = waitReceivedCount + 1
			end
		end
	end
	self._isCompleteSeason = completedCount >= totalCount -- 赛季是否已完成
	if self._isCompleteSeason and not isRewardSeason then
		waitReceivedCount = waitReceivedCount + 1
	end

	self.ProgressText:SetActive(not self._isCompleteSeason)
	self.Max:SetActive(self._isCompleteSeason)
	bee.setText(self.ProgressText, completedCount .. "/" .. totalCount)
	bee.setSliderValue(self.ScheduleSlider, completedCount / totalCount)

	self.InProgress:SetActive(not self._isCompleteSeason)
	self.Received:SetActive(isRewardSeason)
	self.ClaimButton:SetActive(self._isCompleteSeason and not isRewardSeason)

	-- 按钮显示
	if waitReceivedCount > 0 then
		self.ClaimAllButton:SetActive(true)
		self.ClaimGrayButton:SetActive(false)
	else
		self.ClaimAllButton:SetActive(false)
		self.ClaimGrayButton:SetActive(true)
		if isRewardSeason then
			bee.setText(self:find("Text", self.ClaimGrayButton), _T("LAB_BUTTON_TEXT_6"))
		else
			bee.setText(self:find("Text", self.ClaimGrayButton), _T("LAB_DISPATCH_97"))
		end
	end
end

function P:setTaskItem(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local Icon = self:find("Icon", Ani_root)
	local AffairIcon = self:find("AffairIcon", Icon)
	local CharacterIcon = self:find("CharacterIcon", Icon)
	local CampIcon = self:find("CampIcon", Icon)
	local Information = self:find("Information", Ani_root)
	local TaskDesc = self:find("TaskDesc", Information)
	local TaskName = self:find("TaskName", Information)
	local TaskReward = self:find("TaskReward", Ani_root)
	local State = self:find("State", Ani_root)
	local Schedule = self:find("Schedule", State)
	local ScheduleText = self:find("ScheduleText", Schedule)
	local Completed = self:find("Completed", State)
	local CompletedText = self:find("CompletedText", Completed)
	local Claim = self:find("Claim", State)
	local ReceiveButton = self:find("ReceiveButton", Claim)

    if isInit and index > 0 then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            AnimationMgr:playAnim(Ani_root, "UI_1_DispatchStar_item")
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        AnimationMgr:playAnim(Ani_root, "UI_1_DispatchStar_item_idle")
    end

	local taskCfg = tpl_rewards_info[data.task_id]
	if not taskCfg then
		return
	end

	AffairIcon:SetActive(taskCfg.task_type == 401)
	CharacterIcon:SetActive(taskCfg.task_type == 402)
	CampIcon:SetActive(taskCfg.task_type == 403)
	if taskCfg.task_type == 401 then
		bee.setIcon(AffairIcon, "dispatch_seasonpass_detail_affair_icon_0" .. taskCfg.value[1], "Dispatch")
		bee.setText(TaskName, _F(taskCfg.name, DispatchModel:getLevelName(taskCfg.value[1])))
	elseif taskCfg.task_type == 402 then
		bee.setIcon(CharacterIcon, "dispatch_seasonpass_detail_character_icon_0" .. taskCfg.value[1], "Dispatch")
		bee.setText(TaskName, _T(taskCfg.name))
	elseif taskCfg.task_type == 403 then
		bee.setIcon(CampIcon, "dispatch_seasonpass_detail_firm_bg_0" .. taskCfg.value[1], "Dispatch")
		local campCfg = tpl_camp_detail[taskCfg.value[1]]
		bee.setText(TaskName, _T(taskCfg.name))
	end
	bee.setText(TaskDesc, TaskModel:getTaskDesc(taskCfg))

	local rewards = ShopModel:getRewardsList(data.rewards)
	for i = 1, 3 do
		self:setRewardItem(self:find("RewardItem" .. i, TaskReward), rewards[i], data)
	end

	Schedule:SetActive(data.status == TaskStatus.InProgress)
	Claim:SetActive(data.status == TaskStatus.Completed)
	Completed:SetActive(data.status == TaskStatus.Received)

	if data.status == TaskStatus.InProgress then
		bee.setText(ScheduleText, "<color=#FFDBA3>" .. data.current_value .. "</color>/" .. taskCfg.value[2])
	else
		bee.setText(CompletedText, TimeHelp:getDateTimeStr(data.finished_at, "/", ":"))
	end

	bee.removeAllClick(ReceiveButton)
	bee.addClick(ReceiveButton, function()
		DispatchModel:reqRecDispatchTaskRw({data.id})
	end)
end

function P:setRewardItem(item, rewardData, data)
	if not rewardData then
		item:SetActive(false)
		return
	end
	item:SetActive(true)

	local PropItemObj = self:find("PropItem", item)
	local Received = self:find("Received", item)
	local RedPoint = self:find("common_reddot_01", item)
	PropItem:create(PropItemObj, rewardData)
	Received:SetActive(data.status == TaskStatus.Received)
	-- RedPoint:SetActive(data.status == TaskStatus.Completed)

	bee.removeAllClick(PropItemObj)
	bee.addClick(PropItemObj, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonItemTip", {data = rewardData, target = PropItemObj})
	end)
end

function P:_getRewardList()
	local list = {}
	for k,v in pairs(DispatchModel:getTaskList()) do
		if v.status == TaskStatus.Completed then
			table.insert(list, v.id)
		end
	end
	return list
end

function P:onClickClaimAll()
	local ids = self:_getRewardList()
	if self._isCompleteSeason then
		DispatchModel:reqRecSeasonReward(ids)
	else
		DispatchModel:reqRecDispatchTaskRw(ids)
	end
end

function P:onClickClaimReward()
	DispatchModel:reqRecSeasonReward()
end

return P