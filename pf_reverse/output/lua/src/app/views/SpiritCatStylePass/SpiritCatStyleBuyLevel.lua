local P = class("SpiritCatStyleBuyLevel", UiDialog)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)
	local Panel = self:find("Panel", Center)

	local Right = self:find("Right", Panel)
	self.RewardText = self:find("RewardText", Right)
	self.ObtainListObj = self:find("Reward/ObtainList", Right)
	self.RewardItem = self:find("Reward/RewardItem", Right)
	self.GrayButton = self:find("GrayButton", Right)
	self.BuyButton = self:find("BuyButton", Right)
	local Quantity = self:find("Quantity", Right)
	self.BuyCountText = self:find("BuyCountText", Quantity)
	self.AddButton = self:find("AddButton", Quantity)
	self.MaxButton = self:find("MaxButton", Quantity)
	self.MinusButton = self:find("MinusButton", Quantity)
	self.MinButton = self:find("MinButton", Quantity)

	local Left = self:find("Left", Panel)
	self.Number = self:find("Number", Left)
	self.Num1 = self:find("Num1", self.Number)
	self.Num2 = self:find("Num2", self.Number)
	self.Num3 = self:find("Num3", self.Number)
	self.CloseButton = self:find("CloseButton", Panel)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)

	bee.addClick(self.MinButton, function()
		if self._addLevel <= 1 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._addLevel = 1
		self:refreshButtonShow()
	end)
	bee.addClick(self.MaxButton, function()
		if self._addLevel >= self._maxCount then
			UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._addLevel = self._maxCount
		self:refreshButtonShow()
	end)
	bee.addClick(self.MinusButton, function()
		if self._addLevel <= 1 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._addLevel = math.max(self._addLevel - 1, 1)
		self:refreshButtonShow()
	end)
	bee.addClick(self.AddButton, function()
		if self._addLevel >= self._maxCount then
			UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._addLevel = math.min(self._addLevel + 1, self._maxCount)
		self:refreshButtonShow()
	end)

	bee.addClick(self.GrayButton, function()
		UiManager:showToast(_T("LAB_COMMON_TIPS_1"))
		local cfg = tpl_battle_pass_info[BattlePassModel:getCurPassId()]
		local cost = ShopModel:getRewardsList(cfg.cost)[1]
		UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(cost.id, true)})
	end)
	bee.addClick(self.BuyButton, function()
		self:onClickBuyLevel()
	end)
end

function P:onStart()
	self._levelCfg = BattlePassModel:getBattlePassLevelCfg()
	self._levelDic = BattlePassModel:getBattlePassLevelDic()
	self._maxLevel = BattlePassModel:getBattlePassMaxLevel()
	self._curLevelId = BattlePassModel:getCurPassLevelId()
	self._curLevel = tpl_battle_pass_level[self._curLevelId] and tpl_battle_pass_level[self._curLevelId].level or 0
	self._isUnlockPass = BattlePassModel:isUnlockPass()
	self._addLevel = 1

	self:setCostShow()
	self:setLevelText(self._curLevel + self._addLevel)
	self:setLevelReward()
	self:refreshButtonShow()
end

function P:evt_item_refresh()
	self:setCostShow()
	self:refreshButtonShow()
end

function P:setCostShow()
	local cfg = tpl_battle_pass_info[BattlePassModel:getCurPassId()]
	self._cost = ShopModel:getRewardsList(cfg.cost)[1]
	local ownCount = ItemModel:getItemNumById(self._cost.id)
	if ownCount < self._cost.num then
		self.GrayButton:SetActive(true)
		self.BuyButton:SetActive(false)
		bee.setIcon(self:find("Icon", self.GrayButton), tpl_props[self._cost.id].icon)
		bee.setText(self:find("CurText", self.GrayButton), ownCount)
		bee.setText(self:find("PriText", self.GrayButton), self._cost.num)
	else
		self.GrayButton:SetActive(false)
		self.BuyButton:SetActive(true)
		bee.setIcon(self:find("Icon", self.BuyButton), tpl_props[self._cost.id].icon)
	end
	self._maxCount = math.min(self._maxLevel - self._curLevel, math.floor(ownCount / self._cost.num))
end

function P:setLevelReward()
	if not self.obtainList then
		self.obtainList = UiListEx:create(self.ObtainListObj)
		self.obtainList:setCreateFunc(function()
			return CU.GameObject.Instantiate(self.RewardItem)
		end)
		self.obtainList:setRefreshFunc(function(data, item)
			self:setRewardItem(item, data)
		end)
		self.obtainList:setRowCount(5)
		self.obtainList:setRowPostions({-258, -129, 0, 129, 258})
		self.obtainList:setWidth(130)
		self.obtainList:setTopBottom(10, 0)
	end

	local list = {}
	for i = self._curLevel + 1, self._curLevel + self._addLevel do
		local freeReward = ShopModel:getRewardsList(self._levelCfg[i].rewards_1)
		for k, v in pairs(freeReward) do
			if not list[v.id] then
				list[v.id] = v
				list[v.id].typeSort = ItemModel:_getTypeSort(tpl_props[v.id].type)
			else
				list[v.id].num = list[v.id].num + v.num
			end
		end
		if self._isUnlockPass then
			local payReward = ShopModel:getRewardsList(self._levelCfg[i].rewards_2)
			for k, v in pairs(payReward) do
				if not list[v.id] then
					list[v.id] = v
					list[v.id].typeSort = ItemModel:_getTypeSort(tpl_props[v.id].type)
				else
					list[v.id].num = list[v.id].num + v.num
				end
			end
		end
	end

	local showList = {}
	for k, v in pairs(list) do
		table.insert(showList, v)
	end
	table.sort(showList, function(a, b) return a.typeSort < b.typeSort end)
	self.obtainList:setDatas(showList)
end

function P:setRewardItem(item, data)
	PropItem:create(self:find("PropItem", item), data):bindTips()
end

function P:setLevelText(curLevel)
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

	bee.setText(self.RewardText, _F("TAB_BATTLE_PASS_21", curLevel))
end

function P:refreshButtonShow()
	if self._addLevel <= 1 then
		self:setButtonShow(self.MinButton, false)
		self:setButtonShow(self.MinusButton, false)
	else
		self:setButtonShow(self.MinButton, true)
		self:setButtonShow(self.MinusButton, true)
	end
	if self._addLevel >= self._maxCount then
		self:setButtonShow(self.MaxButton, false)
		self:setButtonShow(self.AddButton, false)
	else
		self:setButtonShow(self.MaxButton, true)
		self:setButtonShow(self.AddButton, true)
	end

	bee.setText(self:find("PriText", self.BuyButton), self._cost.num * self._addLevel)
	bee.setText(self.BuyCountText, self._addLevel)
	self:setLevelText(self._curLevel + self._addLevel)
	self:setLevelReward()
end

function P:setButtonShow(button, isOn)
	if not button then return end
	local Off = self:find("Off", button)
	local On = self:find("On", button)
	Off:SetActive(not isOn)
	On:SetActive(isOn)
end

function P:onClickBuyLevel()
	local cfg = tpl_battle_pass_info[BattlePassModel:getCurPassId()]
	local cost = ShopModel:getRewardsList(cfg.cost)[1]
	local propCfg = tpl_props[cost.id]
	local params = {}
	params.richText = _F("TAB_BATTLE_PASS_22", string.format("<icon name=%s scale=2/>", propCfg.icon) .. "<color=#CE1C84>x" .. cost.num * self._addLevel .. "</color>", self._addLevel)
	params.onSure = function()
		BattlePassModel:reqBattlePassPurchaseLevel(self._addLevel)
		self:hideUI()
	end
	UiManager:showUI("SpiritCatStyleTip", params)
end

return P