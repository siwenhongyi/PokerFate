local P = class("SevenDayTask", UiFullView)

local Progress5Value = {0, 0.214, 0.414, 0.588, 0.787, 1}

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)
	self.ClickMask = self:find("ClickMask")
	self.ClickMask:SetActive(false)

	self.TopReward = self:find("TopReward", Center)
	self.CertificateIcon = self:find("CertificateIcon", self.TopReward)
	self.TotalProgress = self:find("TotalProgress", self.TopReward)
	self.totalProgressList = {}
	for i = 1, 6 do
		self.totalProgressList[i] = self:find("TotalProgress" .. i, self.TotalProgress)
	end
	RedManager:bind(self:find("RedPoint", self.TopReward), RedTag.Sign)

	self.TabList = self:find("TabList", Center)
	self.tabItemList = {}
	for i = 1, 7 do
		self.tabItemList[i] = self:find("Tab" .. i, self.TabList)
	end

	self.ChapterInfo = self:find("ChapterInfo", Center)
	self.ChapterNameText = self:find("ChapterNameText", self.ChapterInfo)
	self.ProgressSlider = self:find("ProgressSlider", self.ChapterInfo)
	self.progressSliderList = {}
	self.progressSliderList[6] = self:find("6Slider", self.ProgressSlider)
	self.progressSliderList[5] = self:find("5Slider", self.ProgressSlider)
	self.progressSliderList[4] = self:find("4Slider", self.ProgressSlider)
	self.ProgressText = self:find("ProgressText", self.ProgressSlider)
	self.CompleteCont = self:find("CompleteCont", self.ChapterInfo)
	self.ViewButton = self:find("ViewButton", self.CompleteCont)
	self.RewardList = self:find("RewardList", self.ChapterInfo)
	self.RewardItem = self:find("RewardItem", self.RewardList)
	self.RewardItem:SetActive(false)
	
	self.StartEarlyCont = self:find("StartEarlyCont", self.ChapterInfo)
	self.StartEarlyButton = self:find("StartEarlyButton", self.StartEarlyCont)
	self.UnlockTimeText = self:find("UnlockTimeText", self.StartEarlyCont)
	self.CertificationButton = self:find("CertifivationButton", self.ChapterInfo)
	self.IncompleteButton = self:find("IncompleteButton", self.ChapterInfo)
	self.ChapterTipsText = self:find("ChapterTipsText", self.ChapterInfo)

	self.TaskListObj = self:find("TaskList", Center)
	self.TaskItem = self:find("TaskItem", self.TaskListObj)
	self.TaskItem:SetActive(false)

	self.BackButton = self:find("LeftTop/BackButton", AnimRoot)
	bee.addClick(self.BackButton, function()
		self:hideUI()
	end)

	-- 认证按钮
	bee.addClick(self.CertificationButton, function()
		self:onClickCertificationButton()
	end)
	bee.addClick(self.ViewButton, function()
		UiManager:showUI("SevenDayTaskplot", {id = self._selectChapter})
		bee.logEvent("7daytask-plot", self._selectChapter)
	end)
	bee.addClick(self.StartEarlyButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickStarEarly()
		bee.logEvent("7daytask-advance", self._selectChapter)
	end)
	bee.addClick(self.IncompleteButton, function()
		UiManager:showToast(_T("LAB_SEVEN_DAY_TASKS_TIPS_3"))
	end)
	bee.addClick(self.CertificateIcon, function()
		Game:playSound("ui_button_confirm")
		if SevenDayTaskModel:getCurUnlockChapterStatus() == SevenDayTaskStatus.Completed 
			or SevenDayTaskModel:getCurUnlockChapterStatus() == SevenDayTaskStatus.Upload then
			if PlayerModel:getAuthCertUrl() and PlayerModel:getAuthCertUrl() ~= "" and PlayerModel:getAuthCertUrl() ~= " " then
				local info = {
					name = PlayerModel:getName(),
					uid = self._uid,
					register_time = PlayerModel:getRegisterTime(),
					auth_cert_time = PlayerModel:getAuthTime(),
					auth_cert_url = PlayerModel:getAuthCertUrl(),
				}
				UiManager:showUI("SevenDayTaskCertification", {info = info, isCertification = true})
			else
				UiManager:showUI("SevenDayTaskCertification", {isCertification = true})
			end
		else
			UiManager:showUI("SevenDayTaskTips")
		end
		bee.logEvent("7daytask-rules")
	end)

	self._animTags = {}

	self:initTabList()
end

function P:initTabList()
	for k, v in pairs(self.tabItemList) do
		bee.setText(self:find("Locked/DayText", v), _F("LAB_SEVEN_DAY_TASKS_PAGE", k))
		bee.setText(self:find("Unchecked/DayText", v), _F("LAB_SEVEN_DAY_TASKS_PAGE", k))
		bee.setText(self:find("Selected/DayText", v), _F("LAB_SEVEN_DAY_TASKS_PAGE", k))

		RedManager:bind(self:find("RedPoint", v), RedTag.TaskChapterTag, k)

		bee.addClick(v, function()
			self:onClickTab(k)
		end)
	end
end

function P:onStart()
	self._selectChapter = SevenDayTaskModel:getCurUnlockChapter()

	self._isShowListAnim = true
	SevenDayTaskModel:requestSevenDayTaskList()
	SevenDayTaskModel:initAnswerList()

    bee.logEvent("7daytask-view")
end

function P:evt_updateMonthlyCard()
	if ShopModel:isMonthlyCard() and SevenDayTaskModel:getCurUnlockChapterStatus() == SevenDayTaskStatus.Rewarded then
		SevenDayTaskModel:requestOpenNextChapter()
	end
end

function P:evt_refreshSevenDayTask()
	if self._showCertificationAnim then
		self._showCertificationAnim = false
		self:playCertificationAnim()
	end
	self:setTotalProgress()
	self:refreshTabList()
	self:setChapterInfo()
	self:setTaskList()
end

function P:refreshTabList()
	for k, v in pairs(self.tabItemList) do
		local status = SevenDayTaskModel:getChapterStatus(k)
		if status == SevenDayChapterStatus.Running or status == SevenDayChapterStatus.Completed then
			self:find("Locked", v):SetActive(false)
			self:find("Unchecked", v):SetActive(k ~= self._selectChapter)
			self:find("Selected", v):SetActive(k == self._selectChapter)
		else
			self:find("Locked", v):SetActive(true)
			self:find("Unchecked", v):SetActive(false)
			self:find("Selected", v):SetActive(false)
		end
	end
end

function P:onClickTab(index)
	if self._selectChapter == index then
		Game:playSound("ui_tab_switch_2")
		return
	end

	local status = SevenDayTaskModel:getChapterStatus(index)
	if status == SevenDayChapterStatus.Locked then
		UiManager:showToast(_T("LAB_SEVEN_DAY_TASKS_TIPS_1"))
		bee.logEvent("7daytask-page", index, 0)
		return
	end
	if status == SevenDayChapterStatus.UnReach then
		Game:playSound("ui_tab_switch_2")
		self:onClickStarEarly()
		bee.logEvent("7daytask-page", index, 0)
		return
	end

	Game:playSound("ui_tab_switch_2")
	bee.logEvent("7daytask-page", index, 1)
	self._selectChapter = index
	self._isShowListAnim = true
	self:refreshTabList()
	self:setChapterInfo()
	self:setTaskList()
end

function P:onClickStarEarly()
	local params = {}
    params.text = _T("LAB_SEVEN_DAY_TASKS_DEC_1")
    params.onSure = function()
        ItemModel:jumpView(101002)
		bee.logEvent("7daytask-advance-confirm", self._selectChapter)
    end
    UiManager:showTip(params)
end

function P:setTotalProgress()
	local curChapter = SevenDayTaskModel:getCurUnlockChapter()
	if SevenDayTaskModel:getChapterStatus(curChapter) == SevenDayChapterStatus.Completed then
		self.TotalProgress.transform:GetComponent("Animator"):Play("UI_2_TotalProgress_" .. curChapter)
	else
		self.TotalProgress.transform:GetComponent("Animator"):Play("UI_2_TotalProgress_" .. (curChapter - 1))
	end

	if SevenDayTaskModel:getCurUnlockChapterStatus() == SevenDayTaskStatus.Completed or SevenDayTaskModel:getCurUnlockChapterStatus() == SevenDayTaskStatus.Upload then
		bee.setGrey(self.CertificateIcon, false)
	else
		bee.setGrey(self.CertificateIcon, true)
	end
end

function P:setChapterInfo()
	local cfg = SevenDayTaskModel:getChapterInfo(self._selectChapter)
	if not cfg then
		return
	end

	if self._leftTimeTag then
		scheduler:removeTag(self._leftTimeTag)
		self._leftTimeTag = nil
	end

	bee.setText(self.ChapterNameText, _T(cfg.title_name))

	local status = SevenDayTaskModel:getChapterStatus(self._selectChapter)
	local completedCount = SevenDayTaskModel:getChapterCompleteTaskCount(self._selectChapter)
	local taskCount = #cfg.chapter_task

	-- 章节奖励
	if not self.chapterRewardList then
		self.chapterRewardList = UiListEx:create(self.RewardList)
		self.chapterRewardList:setCreateFunc(function()
			return CU.GameObject.Instantiate(self.RewardItem)
		end)
		self.chapterRewardList:setRefreshFunc(function(data, item)
			self:setRewardItem(item, data)
		end)
		self.chapterRewardList:setWidth(120)
	end
	self.chapterRewardList:setDatas(ShopModel:getRewardsList(cfg.chapter_rewards))

	if SevenDayTaskModel:getCurUnlockChapterStatus() == SevenDayTaskStatus.Upload or 
		SevenDayTaskModel:getCurUnlockChapterStatus() == SevenDayTaskStatus.Completed then
		self.CertificationButton:SetActive(false)
		self.StartEarlyCont:SetActive(false)
		self.IncompleteButton:SetActive(false)
		self.ChapterTipsText:SetActive(true)
		self.ProgressSlider:SetActive(false)
		self.CompleteCont:SetActive(true)
	elseif status == SevenDayChapterStatus.Running then
		if completedCount == taskCount then
			-- 章节已完成但未认证
			self.CertificationButton:SetActive(true)
			self.StartEarlyCont:SetActive(false)
			self.IncompleteButton:SetActive(false)
			self.ChapterTipsText:SetActive(false)

			self.ProgressSlider:SetActive(false)
			self.CompleteCont:SetActive(true)
		else
			-- 章节未完成
			self.CertificationButton:SetActive(false)
			self.StartEarlyCont:SetActive(false)
			self.IncompleteButton:SetActive(true)
			self.ChapterTipsText:SetActive(false)

			-- 任务进度
			self.ProgressSlider:SetActive(true)
			self.CompleteCont:SetActive(false)

			local progress
			for k,v in pairs(self.progressSliderList) do
				v:SetActive(k == taskCount)
				if k == taskCount then
					progress = v
				end
			end
			if taskCount == 5 then
				bee.setFillAmount(self:find("Progress", progress), Progress5Value[completedCount + 1])
			else
				bee.setFillAmount(self:find("Progress", progress), completedCount / taskCount)
			end
			bee.setText(self.ProgressText, _F("LAB_SEVEN_DAY_TASKS_DEC_2", completedCount, taskCount))
		end
	elseif status == SevenDayChapterStatus.Completed then
		if self._selectChapter == SevenDayTaskModel:getCurUnlockChapter() then
			self.CertificationButton:SetActive(false)
			self.StartEarlyCont:SetActive(true)
			self.IncompleteButton:SetActive(false)
			self.ChapterTipsText:SetActive(false)

			local leftTime = SevenDayTaskModel:getCrossDayLeftTime()
			bee.setText(self.UnlockTimeText, _F("LAB_SEVEN_DAY_TASKS_DEC_6", ShopModel:getShopTimeText(leftTime)))
			self._leftTimeTag = self:schedule(1, function()
				leftTime = leftTime - 1
				bee.setText(self.UnlockTimeText, _F("LAB_SEVEN_DAY_TASKS_DEC_6", ShopModel:getShopTimeText(math.max(leftTime, 0))))
			end)
		else
			self.CertificationButton:SetActive(false)
			self.StartEarlyCont:SetActive(false)
			self.IncompleteButton:SetActive(false)
			self.ChapterTipsText:SetActive(true)
		end

		self.ProgressSlider:SetActive(false)
		self.CompleteCont:SetActive(true)
	end

	self.ViewButton:SetActive(status == SevenDayChapterStatus.Completed)
end

function P:setRewardItem(item, data)
	local PropItemObj = self:find("PropItem", item)
	local Received = self:find("Received", item)
	PropItem:create(PropItemObj, data):bindTips()
	Received:SetActive(SevenDayTaskModel:getChapterStatus(self._selectChapter) == SevenDayChapterStatus.Completed)
end

function P:setTaskList()
	if not self.taskList then
		self.taskList = UiListEx:create(self.TaskListObj)
		self.taskList:setCreateFunc(function()
			return CU.GameObject.Instantiate(self.TaskItem)
		end)
		self.taskList:setRefreshFunc(function(data, item)
			self:setTaskItem(item, data)
		end)
		self.taskList:setWidth(165)
	end
	self.taskList:setDatas(SevenDayTaskModel:getTaskListByChapter(self._selectChapter, true))

	for k, v in pairs(self._animTags) do
		scheduler:removeTag(v)
		for k,v in pairs(self.taskList:getShows()) do
			local node = self.taskList:getNode(v)
			node.transform:GetComponent("Animator"):Play("UI_1_SevenDayTask_taskitem_default")
		end
	end
	self._animTags = {}

	if self._isShowListAnim then
		for k,v in pairs(self.taskList:getShows()) do
			local node = self.taskList:getNode(v)
			node:SetActive(false)
			self._animTags[#self._animTags + 1] = self:once(k * 0.12, function()
				node:SetActive(true)
				node.transform:GetComponent("Animator"):Play("UI_1_SevenDayTask_taskitem_into")
			end)
		end
		self._isShowListAnim = false
	end
end

function P:setTaskItem(item, cfg)
	local AnimRoot = self:find("Ani_root", item)
	local NumText1 = self:find("NumText1", AnimRoot)
	local NumText2 = self:find("NumText2", AnimRoot)
	local TaskText = self:find("TaskText", AnimRoot)
	local PropItemObj = self:find("PropItem", AnimRoot)

	local ReceiveButton = self:find("ReceiveButton", AnimRoot)
	local AnswerButton = self:find("AnswerButton", AnimRoot)
	local AnswerText = self:find("AnswerText", AnswerButton)
	local GoButton = self:find("GoButton", AnimRoot)
	local RunningText = self:find("RunningText", AnimRoot)
	local ReceivedMask = self:find("ReceivedMask", AnimRoot)
	local ReviewMask = self:find("ReviewMask", AnimRoot)

	local data = SevenDayTaskModel:getTaskInfo(cfg.task_id)
	if not data then
		return
	end

	local needValue = #data.value == 1 and data.value[1] or data.value[2]
	local curValue = math.min(data.current_value, needValue)
	bee.setText(NumText1, _F("LAB_SEVEN_DAY_TASKS_DEC_34", _N(curValue), _N(needValue)))
	bee.setText(TaskText, TaskModel:getTaskDesc(cfg))
	PropItem:create(PropItemObj, {item_id = cfg.rewards[1], num = cfg.rewards[2]}):bindTips()

	if data.status == TaskStatus.Completed then
		ReceiveButton:SetActive(true)
		AnswerButton:SetActive(false)
		GoButton:SetActive(false)
		RunningText:SetActive(false)
		ReceivedMask:SetActive(false)
		ReviewMask:SetActive(false)
	elseif cfg.task_type == 311 then
		if data.status == TaskStatus.Received then
			ReceiveButton:SetActive(false)
			AnswerButton:SetActive(true)
			GoButton:SetActive(false)
			RunningText:SetActive(false)
			ReceivedMask:SetActive(false)
			ReviewMask:SetActive(true)
			bee.setText(AnswerText, _T("LAB_SEVEN_DAY_TASKS_DEC_9"))
		else
			ReceiveButton:SetActive(false)
			AnswerButton:SetActive(true)
			GoButton:SetActive(false)
			RunningText:SetActive(false)
			ReceivedMask:SetActive(false)
			ReviewMask:SetActive(false)
			bee.setText(AnswerText, _T("LAB_SEVEN_DAY_TASKS_DEC_8"))
		end
	elseif data.status == TaskStatus.Received then
		ReceiveButton:SetActive(false)
		AnswerButton:SetActive(false)
		GoButton:SetActive(false)
		RunningText:SetActive(false)
		ReceivedMask:SetActive(true)
		ReviewMask:SetActive(false)
	else
		if cfg.jump and cfg.jump > 0 then
			ReceiveButton:SetActive(false)
			AnswerButton:SetActive(false)
			GoButton:SetActive(true)
			RunningText:SetActive(false)
			ReceivedMask:SetActive(false)
			ReviewMask:SetActive(false)
		else
			ReceiveButton:SetActive(false)
			AnswerButton:SetActive(false)
			GoButton:SetActive(false)
			RunningText:SetActive(true)
			ReceivedMask:SetActive(false)
			ReviewMask:SetActive(false)
		end
	end

	bee.removeAllClick(AnswerButton)
	bee.addClick(AnswerButton, function()
		Game:playSound("ui_button_confirm")
		if data.status == TaskStatus.Received then
			bee.logEvent("7daytask-answer", cfg.task_id, 1)
		else
			bee.logEvent("7daytask-answer", cfg.task_id, 0)
		end
		UiManager:hideUI("ColorGame")
		UiManager:showUI("SevenDayTaskQuiz", {groupId = cfg.value[1], isReview = data.status == TaskStatus.Received})
	end)

	bee.removeAllClick(GoButton)
	bee.addClick(GoButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("7daytask-task-link", cfg.task_id)
		UiManager:hideUI("ColorGame")
		ItemModel:jumpView(cfg.jump)
	end)

	bee.removeAllClick(ReceiveButton)
	bee.addClick(ReceiveButton, function()
		bee.logEvent("7daytask-task-claim", cfg.task_id)
		UiManager:hideUI("ColorGame")
		SevenDayTaskModel:receiveSevenDayTaskReward(data.id)
	end)
end

function P:onClickCertificationButton()
	if bee.checkCd("SevenDayTask", 2) then
		bee.logEvent("7daytask-finish-button")
		self._showCertificationAnim = true
		SevenDayTaskModel:receiveSevenDayChapterReward(self._selectChapter)
	end
end

function P:playCertificationAnim()
	Game:playSound("ui_7daytask_progress_add_1")
	AnimationMgr:playUIEffect("Prefab/Eff_poker_Ui_sevendaytask_sg", self.TotalProgress.transform, bee.v3(0, 0, 0))
	self:once(0.5 + 0.01 * self._selectChapter, function()
		if self._selectChapter == 7 then
			AnimationMgr:playUIEffect("Prefab/Eff_poker_Ui_sevenday_bf", self.CertificateIcon.transform, bee.v3(0, 0, 0))
		else
			AnimationMgr:playUIEffect("Prefab/Eff_poker_Ui_sevenday_bf", self.TotalProgress.transform, self.totalProgressList[self._selectChapter].transform.localPosition)
		end
	end)

	self._selectChapter = SevenDayTaskModel:getCurUnlockChapter()
	self._isShowListAnim = true
end

function P:preHide()
	if not self.taskList then
		return
	end
	for k,v in pairs(self.taskList:getShows()) do
		local node = self.taskList:getNode(v)
		node:GetComponent("Animator").enabled = false
	end

	P.super.preHide(self)
end

function P:evt_ColorGameActionRSP()
	SevenDayTaskModel:requestSevenDayTaskList()
end

return P