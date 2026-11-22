local P = class("SpiritCatStyleMain", UiFullView)

local TabType = {
	Reward = 1,
	Task = 2,
}

local TaskType = {
	Period = 1,
	Weekly = 2,
}

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)
	local RightTop = self:find("RightTop", AnimRoot)
	local LeftTop = self:find("LeftTop", AnimRoot)

	self.CharacterImage = self:find("Bg/CharacterImageRaw", Center)
	self.PreviewButton = self:find("Outfit/Nameplate/PreviewButton", Center)
	self.RoleNameText = self:find("Outfit/Nameplate/RoleNameText", Center)
	self.SkinNameText = self:find("Outfit/Nameplate/SkinNameText", Center)

	self.Reward = self:find("Main/Reward", Center)
	self.RewardListObj = self:find("RewardList", self.Reward)
	self.RewardItem = self:find("RewardItem", self.RewardListObj)
	self.CycleRewardItem = self:find("CycleRewardItem", self.RewardListObj)
	self.SpecialRewardItem = self:find("SpecialRewardItem", self.Reward)
	self.RewardItem:SetActive(false)
	self.CycleRewardItem:SetActive(false)
	self.SpecialRewardItem:SetActive(false)
	self.Premium = self:find("RewardTitle/Premium", self.Reward)
	self.LockedIcon = self:find("RewardTitle/Premium/LockedIcon", self.Reward)
	self.UnlockedIcon = self:find("RewardTitle/Premium/UnlockedIcon", self.Reward)

	self.Task = self:find("Main/Task", Center)
	self.TabWeekly = self:find("LeftTab/TabWeekly", self.Task)
	self.TabPeriod = self:find("LeftTab/TabPeriod", self.Task)
	self.TaskListObj = self:find("TaskList", self.Task)
	self.TaskItem = self:find("TaskItem", self.TaskListObj)
	self.TaskItem:SetActive(false)

	local TopCont = self:find("TopCont", Center)
	local Middle = self:find("Middle", TopCont)
	local Tab = self:find("Tab", TopCont)
	self.TabTask = self:find("TabTask", Tab)
	self.TabReward = self:find("TabReward", Tab)
	self.Title = self:find("Title", TopCont)
	self.Number = self:find("Level/Number", Middle)
	self.Num1 = self:find("Num1", self.Number)
	self.Num2 = self:find("Num2", self.Number)
	self.Num3 = self:find("Num3", self.Number)
	local Experience = self:find("Experience", Middle)
	self.ExpSlider = self:find("ExpSlider", Experience)
	self.ExpText = self:find("ExpText", Experience)
	self.ExpNameText = self:find("ExpNameText", Experience)
	self.BuyExpButton = self:find("BuyExpButton", Middle)
	self.Max = self:find("Max", Middle)

	local BtnCont = self:find("BtnCont", Center)
	local ClaimReward = self:find("ClaimReward", BtnCont)
	self.ClaimAllButton = self:find("ClaimAllButton", ClaimReward)
	self.GrayClaimAllButton = self:find("GrayClaimAllButton", ClaimReward)
	local UnlockPass = self:find("UnlockPass", BtnCont)
	self.LockedButton = self:find("LockedButton", UnlockPass)
	self.UpgradeButton = self:find("UpgradeButton", UnlockPass)
	self.Unlocked = self:find("Unlocked", UnlockPass)

	self.TimeText = self:find("Time/TimeText", RightTop)
	self.InfoButton = self:find("InfoButton", LeftTop)
	self.BackButton = self:find("BackButton", LeftTop)

	self.ClickMask = self:find("ClickMask", AnimRoot)
	self.ClickMask:SetActive(false)

	bee.addClick(self.BackButton, function()
		bee.logEvent("battle-pass-back", BattlePassModel:getCurPassId())
		self:hideUI()
	end)

	bee.addClick(self.PreviewButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("battle-pass-main-link", BattlePassModel:getCurPassId())
		UiManager:showUI("CharacterMainGarments", {data = CharacterModel:getRoleData(self._skinCfg.role), selectId = self._skinCfg.id})
	end)

	bee.addClick(self.TabReward, function ()
		Game:playSound("ui_tab_switch_1")
		bee.logEvent("battle-pass-tag-reward", BattlePassModel:getCurPassId())
		if self._curTabType == TabType.Reward then
			return
		end
		self._curTabType = TabType.Reward
		self:refreshTab()
		self:setRewardCont()
	end)
	bee.addClick(self.TabTask, function ()
		Game:playSound("ui_tab_switch_1")
		bee.logEvent("battle-pass-tag-task", BattlePassModel:getCurPassId())
		if self._curTabType == TabType.Task then
			return
		end
		self._curTabType = TabType.Task
		self._isShowTaskInit = true
		BattlePassModel:reqBattlePassDetail()
		self:refreshTab()
	end)

	bee.addClick(self.TabWeekly, function()
		Game:playSound("ui_tab_switch_1")
		if self._curTaskType == TaskType.Weekly then
			return
		end
		self._curTaskType = TaskType.Weekly
		self:refreshTaskTab()
		self._isShowTaskInit = true
		self:setTaskList()
	end)
	bee.addClick(self.TabPeriod, function()
		Game:playSound("ui_tab_switch_1")
		if self._curTaskType == TaskType.Period then
			return
		end
		self._curTaskType = TaskType.Period
		self:refreshTaskTab()
		self._isShowTaskInit = true
		self:setTaskList()
	end)

	bee.addClick(self.LockedButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("battle-pass-button-unlock", BattlePassModel:getCurPassId())
		UiManager:showUI("SpiritCatStyleBuy")
	end)
	bee.addClick(self.UpgradeButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("battle-pass-button-upgrade", BattlePassModel:getCurPassId())
		UiManager:showUI("SpiritCatStyleBuy")
	end)

	bee.addClick(self.ClaimAllButton, function()
		self:onClickClaimAll()
	end)
	bee.addClick(self.GrayClaimAllButton, function()
		UiManager:showToast(_T("LAB_TASKS_NOREWARDS"))
	end)

	bee.addClick(self.BuyExpButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("battle-pass-button-buy-level", BattlePassModel:getCurPassId())
		UiManager:showUI("SpiritCatStyleBuyLevel")
	end)

    bee.addClick(self.InfoButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("battle-pass-rules", BattlePassModel:getCurPassId())
        UiManager:showUI("SpiritCatStyleRule", {text = _T("TAB_BATTLE_PASS_5")})
    end)

    bee.addClick(self.LockedIcon, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("battle-pass-button-upgrade", BattlePassModel:getCurPassId())
		UiManager:showUI("SpiritCatStyleBuy")
	end)

	RedManager:bind(self:find("RedPoint", self.TabReward), RedTag.BattlePassReward)
	RedManager:bind(self:find("RedPoint", self.TabTask), RedTag.BattlePassTask)
	RedManager:bind(self:find("RedPoint", self.TabWeekly), RedTag.BattlePassWeekly)
	RedManager:bind(self:find("RedPoint", self.TabPeriod), RedTag.BattlePassPeriod)
end

function P:onStart()
	self._curTabType = TabType.Reward
	self._curTaskType = TaskType.Weekly
	self:refreshTab()
	self:setOutfitCont()
	self:setUnlockPassCont()
	self:setLevelCont()
	if self._curTabType == TabType.Reward then
		self:setRewardCont()
	else
		self:setTaskCont(true)
	end

	if BattlePassModel:isShowActiveView() then
		UiManager:showUI("SpiritCatStyleActivate")
	end

	local curLanguage = LanguageManager:getLanguage()
	for i = 1, self.Title.transform.childCount do
		local t = self.Title.transform:GetChild(i - 1)
		t.gameObject:SetActive(t.name == curLanguage)
	end
end

function P:evt_item_refresh()
	self:setLevelCont()
	if self._curTabType == TabType.Reward then
		self:setRewardCont()
	end
	self:setRewardButton()
	BattlePassModel:refreshBattlePassRedTag()
end

function P:evt_updateBattlePass()
	if self._curTabType == TabType.Reward then
		self:setRewardCont()
	else
		self:setTaskCont(self._isShowTaskInit)
		self._isShowTaskInit = false
	end
end

function P:evt_updateShopLimit()
	self:setUnlockPassCont()
	if self._curTabType == TabType.Reward then
		self:setRewardCont()
	end
end

function P:setOutfitCont()
	local cfg = tpl_battle_pass_info[BattlePassModel:getCurPassId()]
	if not cfg then
		return
	end
	local skinCfg = tpl_character_skin[cfg.skin]
	self._skinCfg = skinCfg
	if not skinCfg then
		return
	end
	if not self._characterCls then
		self._characterCls = ObjectPool:getCls(self.CharacterImage)
		self._characterCls:setShowReal(true)
		self._characterCls:createRoleCanvas()
	end
	self._characterCls:setShowReal(true)
	self._characterCls:setRole(CharacterModel:getRoleData(skinCfg.role), true)
	self._characterCls:setSkin(skinCfg, true)
	self._characterCls:setRoleOffset(bee.v3zero, bee.v3(0.59, 0.59, 1))

	bee.setText(self.SkinNameText, _T(skinCfg.name))
	bee.setText(self.RoleNameText, _T(tpl_character[skinCfg.role].name))

	-- 结束时间
	local dt = cfg.time_end - bee.getServerTime()
	bee.setText(self.TimeText, TimeHelp:getTimeLeftStr(dt))
	self:schedule(1, function()
		dt = cfg.time_end - bee.getServerTime()
		if dt > 0 then
			bee.setText(self.TimeText, TimeHelp:getTimeLeftStr(dt))
		else
			bee.setText(self.TimeText, _T("LAB_BACKPACK_DES_21"))
		end
	end)
end

function P:refreshTab()
	self:find("On", self.TabReward):SetActive(self._curTabType == TabType.Reward)
	self:find("Off", self.TabReward):SetActive(self._curTabType ~= TabType.Reward)
	self:find("On", self.TabTask):SetActive(self._curTabType == TabType.Task)
	self:find("Off", self.TabTask):SetActive(self._curTabType ~= TabType.Task)
end

function P:setLevelCont()
	self._curExp = BattlePassModel:getBattlePassExp()
	self._curLevelId = BattlePassModel:getCurPassLevelId()
	self._levelCfg = BattlePassModel:getBattlePassLevelCfg()
	self._levelDic = BattlePassModel:getBattlePassLevelDic()
	local maxLevel = BattlePassModel:getBattlePassMaxLevel()

	self._curLevel = tpl_battle_pass_level[self._curLevelId] and tpl_battle_pass_level[self._curLevelId].level or 0
	if self._curLevel == 0 then
		self._isMax = false
	else
		self._isMax = tpl_battle_pass_level[self._curLevelId].level >= maxLevel
	end

	bee.setText(self.ExpNameText, _T(tpl_props[GPropId.BattlePassExp].name))
	
	self.Max:SetActive(self._isMax)
	self.BuyExpButton:SetActive(not self._isMax)
	self:_setLevelText(self._curLevel)
	
	if not self._isMax then
		local nextLevel = self._curLevel + 1
		local exp = self._levelCfg[self._curLevel] and (self._curExp - self._levelCfg[self._curLevel].exp) or self._curExp
		local nextExp = self._levelCfg[self._curLevel] and (self._levelCfg[nextLevel].exp - self._levelCfg[self._curLevel].exp) or self._levelCfg[nextLevel].exp
		bee.setText(self.ExpText, exp .. "/" .. nextExp)
		bee.setSliderValue(self.ExpSlider, exp / nextExp)
	else
		local overflowExp = BattlePassModel:getPassOverflowExp()
		local needValue = self._levelCfg[#self._levelCfg].exp
		local curOverflowExp = overflowExp % needValue
		bee.setText(self.ExpText, curOverflowExp .. "/" .. needValue)
		bee.setSliderValue(self.ExpSlider, curOverflowExp / needValue)
	end
end

-- 等级显示
function P:_setLevelText(curLevel)
	local h = math.floor(curLevel / 100)
	local t = math.floor((curLevel - h * 100) / 10)
	local u = curLevel - h * 100 - t * 10
	if h > 0 then
		self.Num1:SetActive(true)
		bee.setIcon(self.Num1, "spiritcat_number_" .. h, "Spiritcat")
	else
		self.Num1:SetActive(false)
	end
	if h > 0 or t > 0 then
		self.Num2:SetActive(true)
		bee.setIcon(self.Num2, "spiritcat_number_" .. t, "Spiritcat")
	else
		self.Num2:SetActive(false)
	end
	bee.setIcon(self.Num3, "spiritcat_number_" .. u, "Spiritcat")
end

function P:setUnlockPassCont()
	local isBought1 = BattlePassModel:isBoughtPass(1)
	local isBought2 = BattlePassModel:isBoughtPass(2)
	local isBought3 = BattlePassModel:isBoughtPass(3)

	if isBought1 and not isBought2 and not isBought3 then
		self.LockedButton:SetActive(false)
		self.UpgradeButton:SetActive(true)
		self.Unlocked:SetActive(false)
	elseif isBought2 or isBought3 then
		self.LockedButton:SetActive(false)
		self.UpgradeButton:SetActive(false)
		self.Unlocked:SetActive(true)
	else
		self.LockedButton:SetActive(true)
		self.UpgradeButton:SetActive(false)
		self.Unlocked:SetActive(false)
	end

	if self._isUnlockPass ~= nil then
		if self._isUnlockPass ~= BattlePassModel:isUnlockPass() then
			self._isShowUnlockEffect = true
		end
	end

	self._isUnlockPass = BattlePassModel:isUnlockPass()
	self.LockedIcon:SetActive(not self._isUnlockPass)
	self.UnlockedIcon:SetActive(self._isUnlockPass)
end

function P:showUnlockEffect()
	self.ClickMask:SetActive(true)
	if self._curTabType ~= TabType.Reward then
		self._curTabType = TabType.Reward
		self:refreshTab()
		self:setRewardCont()
	end

	self:find("Eff_poker_SpiritCatStyle_js", self.Premium):SetActive(true)
	self:once(4, function()
		self:find("Eff_poker_SpiritCatStyle_js", self.Premium):SetActive(false)
	end)

	for i, v in ipairs(self.rewardList:getShows()) do
		local item = self.rewardList:getNode(v)
		self:once((i - 1) * 0.15, function()
			local Rewards = self:find("Ani_root/Pay/Rewards", self.rewardList:getNode(v))
			AnimationMgr:playUIEffect("Prefab/SpiritCatStyle/Eff_poker_SpiritCatStyle_sg_loop", self:find("Reward1/PropItem", Rewards).transform, bee.v3(0, 10, 0))
			AnimationMgr:playUIEffect("Prefab/SpiritCatStyle/Eff_poker_SpiritCatStyle_sg_loop", self:find("Reward2/PropItem", Rewards).transform, bee.v3(0, 10, 0))
		end)
	end

	self:once(1.2, function()
		self.ClickMask:SetActive(false)
	end)
end

function P:setRewardCont()
	self.Reward:SetActive(true)
	self.Task:SetActive(false)
	self:setRewardButton()

	if not self.rewardList then
		self.rewardList = UiListEx:create(self.RewardListObj)
		self.rewardList:setCreateFunc(function(data)
			if data.__kind == 1 then
				return CU.GameObject.Instantiate(self.RewardItem)
			else
				return CU.GameObject.Instantiate(self.CycleRewardItem)
			end
		end)
		self.rewardList:setRefreshFunc(function(data, item, isInit, index)
			if data.__kind == 1 then
				self:setNormalRewardItem(item, data, isInit, index)
			else
				self:setCycleRewardItem(item, data, isInit, index)
			end
		end)
		self.rewardList:setWidth(185)
		self.rewardList:setTopBottom(40, 40)

		self.rewardList:addValueChanged(function()
			local shows = self.rewardList:getShows()
			local lastData = self.rewardList:getData(shows[#shows - 1])
			for i,v in ipairs(self._specialLevelList) do
				if v.id >lastData.id then
					self.SpecialRewardItem:SetActive(true)
					self:setNormalRewardItem(self.SpecialRewardItem, v)
					return
				end
			end
			self.SpecialRewardItem:SetActive(false)
		end)
	end
	self._specialLevelList = {}
	for i, v in ipairs(self._levelCfg) do
		if v.is_special then
			table.insert(self._specialLevelList, v)
		end
		if v.level == -1 then
			v.__kind = 2
		else
			v.__kind = 1
		end
	end
	self.rewardList:setDatas(self._levelCfg)
	if not self._isInit then
		local showIndex = self._isMax and #self._levelCfg or self._curLevel
		for k, v in ipairs(self._levelCfg) do
			if v.level > 0 and v.level <= self._curLevel then
				if not BattlePassModel:getFreeRewardIsClaim(v.id) then
					showIndex = v.level
					break
				elseif self._isUnlockPass and not BattlePassModel:getPayRewardIsClaim(v.id) then
					showIndex = v.level
					break
				end
			else
				break
			end
		end
		showIndex = math.max(1, showIndex - 1)
		if showIndex > 1 then
			self.rewardList:moveToYItem(showIndex)
		end
		self._isInit = true
	end
end

function P:setNormalRewardItem(item, data)
	local Ani_root = self:find("Ani_root", item)
	local Free = self:find("Free", Ani_root)
	local Pay = self:find("Pay", Ani_root)

	local isReach = data.id <= self._curLevelId
	bee.setText(self:find("Normal/IndexText", Free), "<I>" ..data.id .. "</I>")
	bee.setText(self:find("Available/IndexText", Free), "<I>" ..data.id .. "</I>")
	self:find("Rewards/Reward1/Locked", Free):SetActive(false)
	self:find("Rewards/Reward1/Locked", Pay):SetActive(not self._isUnlockPass)
	self:find("Rewards/Reward2/Locked", Pay):SetActive(not self._isUnlockPass)

	-- 免费奖励显示
	local freeIsClaim = BattlePassModel:getFreeRewardIsClaim(data.id)
	local freeRewards = ShopModel:getRewardsList(data.rewards_1)
	local FreeRewardItem = self:find("Rewards/Reward1", Free)
	PropItem:create(self:find("PropItem", FreeRewardItem), freeRewards[1])
	self:find("Claimed", FreeRewardItem):SetActive(freeIsClaim)
	
	if isReach and not freeIsClaim then
		self:find("ClaimEffect", FreeRewardItem):SetActive(true)
		self:find("RedPoint", FreeRewardItem):SetActive(true)
		self:find("Normal", Free):SetActive(false)
		self:find("Available", Free):SetActive(true)
	else
		self:find("ClaimEffect", FreeRewardItem):SetActive(false)
		self:find("RedPoint", FreeRewardItem):SetActive(false)
		self:find("Normal", Free):SetActive(true)
		self:find("Available", Free):SetActive(false)
	end

	local receiveReward = function()
		BattlePassModel:reqBattlePassClaimReward(3, {data.id})
	end

	bee.removeAllClick(FreeRewardItem)
	bee.addClick(FreeRewardItem, function()
		if isReach and not freeIsClaim then
			receiveReward()
		else
			UiManager:showUI("CommonItemTip", {data = freeRewards[1], target = FreeRewardItem})
		end
	end)

	-- 付费奖励显示
	local payRewards = ShopModel:getRewardsList(data.rewards_2)
	local payIsClaim = BattlePassModel:getPayRewardIsClaim(data.id)
	if self._isUnlockPass and isReach and not payIsClaim then
		self:find("Normal", Pay):SetActive(false)
		self:find("Available", Pay):SetActive(true)
	else
		self:find("Normal", Pay):SetActive(true)
		self:find("Available", Pay):SetActive(false)
	end
	for i = 1, 2 do
		local payRewardItem = self:find("Rewards/Reward" .. i, Pay)
		if payRewards[i] then
			payRewardItem:SetActive(true)
			PropItem:create(self:find("PropItem", payRewardItem), payRewards[i])

			self:find("Claimed", payRewardItem):SetActive(payIsClaim)
			self:find("ClaimEffect", payRewardItem):SetActive(self._isUnlockPass and isReach and not payIsClaim)
			self:find("RedPoint", payRewardItem):SetActive(self._isUnlockPass and isReach and not payIsClaim)

			bee.removeAllClick(payRewardItem)
			bee.addClick(payRewardItem, function()
				if isReach and self._isUnlockPass and not payIsClaim then
					receiveReward()
				else
					UiManager:showUI("CommonItemTip", {data = payRewards[i], target = payRewardItem})
				end
			end)
		else
			payRewardItem:SetActive(false)
		end
	end

	bee.removeAllClick(item)
	bee.addClick(item, function()
		if not isReach then
			return
		end
		if not freeIsClaim then
			receiveReward()
			return
		end
		if self._isUnlockPass and not payIsClaim then
			receiveReward()
			return
		end
	end)
end

function P:setCycleRewardItem(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local Free = self:find("Free", Ani_root)
	local Pay = self:find("Pay", Ani_root)
	local FreeRewardCount = self:find("RewardCount", Free)
	local PayRewardCount = self:find("RewardCount", Pay)

	self:find("Rewards/Reward1/Locked", Free):SetActive(not self._isMax)
	self:find("Rewards/Reward1/Locked", Pay):SetActive(not self._isMax or not self._isUnlockPass)
	self:find("Rewards/Reward2/Locked", Pay):SetActive(not self._isMax or not self._isUnlockPass)

	-- 循环次数
	local cycleCount = BattlePassModel:getPassCycleCount()

	local receiveReward = function()
		-- 领取循环奖励
		BattlePassModel:reqBattlePassClaimReward(3, {data.id})
	end

	-- 免费奖励显示
	local freeRewards = ShopModel:getRewardsList(data.rewards_1)
	local FreeRewardItem = self:find("Rewards/Reward1", Free)
	PropItem:create(self:find("PropItem", FreeRewardItem), freeRewards[1])
	local freeClaimCount = cycleCount - BattlePassModel:getClaimloopTimesFree()
	FreeRewardCount:SetActive(freeClaimCount > 0)
	self:find("RedPoint", FreeRewardItem):SetActive(freeClaimCount > 0)
	self:find("ClaimEffect", FreeRewardItem):SetActive(freeClaimCount > 0)
	self:find("Normal", Free):SetActive(freeClaimCount <= 0)
	self:find("Available", Free):SetActive(freeClaimCount > 0)
	if freeClaimCount > 0 then
		bee.setText(self:find("CountText", FreeRewardCount), "x" .. freeClaimCount)
	end

	bee.removeAllClick(FreeRewardItem)
	bee.addClick(FreeRewardItem, function()
		if freeClaimCount > 0 then
			receiveReward()
		else
			UiManager:showUI("CommonItemTip", {data = freeRewards[1], target = FreeRewardItem})
		end
	end)

	-- 付费奖励显示
	local payRewards = ShopModel:getRewardsList(data.rewards_2)
	local payClaimCount = self._isUnlockPass and cycleCount - BattlePassModel:getClaimloopTimesPay() or 0
	PayRewardCount:SetActive(payClaimCount > 0)
	self:find("Normal", Pay):SetActive(payClaimCount <= 0)
	self:find("Available", Pay):SetActive(payClaimCount > 0)
	if payClaimCount > 0 then
		bee.setText(self:find("CountText", PayRewardCount), "x" .. payClaimCount)
	end

	for i = 1, 2 do
		local payRewardItem = self:find("Rewards/Reward" .. i, Pay)
		if payRewards[i] then
			payRewardItem:SetActive(true)
			PropItem:create(self:find("PropItem", payRewardItem), payRewards[i])

			self:find("RedPoint", payRewardItem):SetActive(self._isUnlockPass and payClaimCount > 0)
			self:find("ClaimEffect", payRewardItem):SetActive(self._isUnlockPass and payClaimCount > 0)

			bee.removeAllClick(payRewardItem)
			bee.addClick(payRewardItem, function()
				if self._isUnlockPass and payClaimCount > 0 then
					receiveReward()
				else
					UiManager:showUI("CommonItemTip", {data = payRewards[i], target = payRewardItem})
				end
			end)
		else
			payRewardItem:SetActive(false)
		end
	end

	bee.removeAllClick(item)
	bee.addClick(item, function()
		if not self._isMax then
			return
		end
		if freeClaimCount > 0 then
			receiveReward()
			return
		end
		if self._isUnlockPass and payClaimCount > 0 then
			receiveReward()
			return
		end
	end)
end

function P:setTaskCont()
	self.Reward:SetActive(false)
	self.Task:SetActive(true)
	self:setRewardButton()

	self:refreshTaskTab()
	self:setTaskList()
end

function P:refreshTaskTab()
	self:find("On", self.TabWeekly):SetActive(self._curTaskType == TaskType.Weekly)
	self:find("Off", self.TabWeekly):SetActive(self._curTaskType ~= TaskType.Weekly)
	self:find("On", self.TabPeriod):SetActive(self._curTaskType == TaskType.Period)
	self:find("Off", self.TabPeriod):SetActive(self._curTaskType ~= TaskType.Period)
end

function P:setTaskList()
	if not self.taskList then
		self.taskList = UiListEx:create(self.TaskListObj)
		self.taskList:setCreateFunc(function(data)
			return CU.GameObject.Instantiate(self.TaskItem)
		end)
		self.taskList:setRefreshFunc(function(data, item, isInit, index)
			self:setTaskItem(item, data, isInit, index)
		end)
		self.taskList:setWidth(165)
	end

	if self._curTaskType == TaskType.Weekly then
		self.taskList:setDatas(BattlePassModel:getPassWeeklyTaskList())
	elseif self._curTaskType == TaskType.Period then
		self.taskList:setDatas(BattlePassModel:getPassPeriodTaskList())
	end
	self._isShowTaskInit = false
end

function P:setTaskItem(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local TaskText = self:find("Information/TaskText", Ani_root)
	local Slider = self:find("Information/Progress/Slider", Ani_root)
	local ProgressText1 = self:find("Information/Progress/ProgressText1", Ani_root)
	local ProgressText2 = self:find("Information/Progress/ProgressText2", Ani_root)
	local Reward1 = self:find("Reward1", Ani_root)
	local GoButton = self:find("GoButton", Ani_root)
	local InProgress = self:find("InProgress", Ani_root)
	local ClaimButton = self:find("ClaimButton", Ani_root)
	local Completed = self:find("Completed", Ani_root)

    if self._isShowTaskInit and isInit and index > 0 then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_AchievementMain_item", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_AchievementMain_item_idle", Ani_root)
    end

	local cfg
	if self._curTaskType == TaskType.Weekly then
		cfg = tpl_battle_pass_tasks_week[data.task_id]
	else
		cfg = tpl_battle_pass_tasks_period[data.task_id]
	end
	if not cfg then
		return
	end

	-- 任务描述
	local showText = TaskModel:getTaskDesc(cfg, data)
	bee.setText(TaskText, showText)

	local needValue = #data.value == 1 and data.value[1] or data.value[2]
	if cfg.task_type == 313 or cfg.task_type == 111 then
		needValue = data.value[3]
	end
	if data.current_value >= needValue then
		ProgressText1:SetActive(false)
		ProgressText2:SetActive(true)
		bee.setText(ProgressText2, "(" .. _N(math.min(needValue, data.current_value)) .."/" .. _N(needValue) .. ")")
	else
		ProgressText1:SetActive(true)
		ProgressText2:SetActive(false)
		bee.setText(ProgressText1, "(" .. _N(math.min(needValue, data.current_value)) .."/" .. _N(needValue) .. ")")
	end
	bee.setSliderValue(Slider, data.current_value / needValue)

	-- 任务奖励
	local rewards = ShopModel:getRewardsList(cfg.rewards)
	PropItem:create(Reward1, rewards[1]):bindTips()

	-- 任务状态
	if data.status == TaskStatus.InProgress then
		GoButton:SetActive(cfg.jump ~= nil)
		InProgress:SetActive(cfg.jump == nil)
	else
		GoButton:SetActive(false)
		InProgress:SetActive(false)
	end
	ClaimButton:SetActive(data.status == TaskStatus.Completed)
	Completed:SetActive(data.status == TaskStatus.Received)

	bee.removeAllClick(GoButton)
	bee.addClick(GoButton, function()
		Game:playSound("ui_button_confirm")
		-- 前往跳转
		if cfg.jump then
			if cfg.jump == 4001 then
				self:hideUI()
			else
				ItemModel:jumpView(cfg.jump)
			end
		end
	end)

	bee.removeAllClick(ClaimButton)
	bee.addClick(ClaimButton, function()
		BattlePassModel:reqBattlePassClaimReward(self._curTaskType, {data.id})
	end)
end

function P:setRewardButton()
	local isCanClaim = false
	if self._curTabType == TabType.Reward then
		-- 是否有可领取奖励
		for k, v in ipairs(self._levelCfg) do
			if v.level ~= -1 and v.level <= self._curLevel then
				if not BattlePassModel:getFreeRewardIsClaim(v.id) then
					isCanClaim = true
					break
				elseif self._isUnlockPass and not BattlePassModel:getPayRewardIsClaim(v.id) then
					isCanClaim = true
					break
				end
			else
				break
			end
		end
		-- 循环奖励
		local cycleCount = BattlePassModel:getPassCycleCount()
		if cycleCount - BattlePassModel:getClaimloopTimesFree() > 0 then
			isCanClaim = true
		elseif self._isUnlockPass and cycleCount - BattlePassModel:getClaimloopTimesPay() > 0 then
			isCanClaim = true
		end
	else
		-- 是否有可领取任务
		for k, v in pairs(BattlePassModel:getPassWeeklyTaskList()) do
			if v.status == TaskStatus.Completed then
				isCanClaim = true
				break
			end
		end
		for k, v in pairs(BattlePassModel:getPassPeriodTaskList()) do
			if v.status == TaskStatus.Completed then
				isCanClaim = true
				break
			end
		end
	end

	self.ClaimAllButton:SetActive(isCanClaim)
	self.GrayClaimAllButton:SetActive(not isCanClaim)
end

function P:onClickClaimAll()
	if self._curTabType == TabType.Reward then
		bee.logEvent("battle-pass-claim-all", BattlePassModel:getCurPassId(), 1)
		self:onClickClaimReward()
	else
		bee.logEvent("battle-pass-claim-all", BattlePassModel:getCurPassId(), 2)
		self:onClickClaimTask()
	end
end

function P:onClickClaimReward()
	local ids = {}
	-- 等级奖励
	for k, v in ipairs(self._levelCfg) do
		if v.level > 0 and v.level <= self._curLevel then
			if not BattlePassModel:getFreeRewardIsClaim(v.id) then
				table.insert(ids, v.id)
			elseif self._isUnlockPass and not BattlePassModel:getPayRewardIsClaim(v.id) then
				table.insert(ids, v.id)
			end
		else
			break
		end
	end
	-- 循环奖励
	if self._isMax then
		local cycleCount = BattlePassModel:getPassCycleCount()
		if cycleCount > 0 then
			table.insert(ids, self._levelCfg[#self._levelCfg].id)
		end
	end
	if not next(ids) then
		return
	end
	BattlePassModel:reqBattlePassClaimReward(3, ids)
end

function P:onClickClaimTask()
	BattlePassModel:reqBattlePassClaimReward(0)
end

function P:evt_PinballActionRSP()
	self:once(0.5, function()
		BattlePassModel:reqBattlePassDetail()
	end)
end

function P:evt_ColorGameActionRSP()
	self:once(0.5, function()
		BattlePassModel:reqBattlePassDetail()
	end)
end

function P:evt_unlockBattlePass()
	if self._isShowUnlockEffect then
		self:showUnlockEffect()
		self._isShowUnlockEffect = false
	end
end

return P