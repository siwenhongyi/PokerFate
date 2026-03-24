local P = class("ActivitySignIn", UiBase)

local SliderValueList = {[0] = 0, [1] = 0.022, [2] = 0.221, [3] = 0.4125, [4] = 0.612, [5] = 0.803, [6] = 1, [7] = 1}

function P:onAwake()
	local Center = self:find("AnimRoot/Center")
	local Panel = self:find("AnimRoot/Center/Panel")

	local RewardCont = self:find("RewardCont", Panel)

	local GrandTotal = self:find("GrandTotal", RewardCont)
	self.TotalItem1 = self:find("GridBg1/TotalItem1", GrandTotal)
	self.Received1 = self:find("GridBg1/Received1", GrandTotal)
	self.TotalItem2 = self:find("GridBg2/TotalItem2", GrandTotal)
	self.Received2 = self:find("GridBg2/Received2", GrandTotal)
	self.TotalItem3 = self:find("GridBg3/TotalItem3", GrandTotal)
	self.Received3 = self:find("GridBg3/Received3", GrandTotal)
	self.TotalText1 = self:find("TotalText1", GrandTotal)
	self.TotalText2 = self:find("TotalText2", GrandTotal)
	self.TotalText3 = self:find("TotalText3", GrandTotal)
	self.SignInSlider = self:find("SignInSlider", GrandTotal)

	self.Item1 = self:find("Item1", RewardCont)
	self.Item1:SetActive(false)

	local Monthly = self:find("Monthly", RewardCont)
	self.MonthlyList = self:find("MonthlyList/Viewport/Content", Monthly)
	self.ActiveButton = self:find("ActiveButton", Monthly)
	self.ReceivedMask = self:find("ReceivedMask", Monthly)

	local SignIn = self:find("SignIn", RewardCont)
	self.SignInItemList = self:find("SignInItemList", SignIn)
	self.ItemSignIn = self:find("ItemSignIn", SignIn)
	self.ItemSignIn:SetActive(false)

	local Dialogue = self:find("Dialogue", RewardCont)
	self.DialogueText = self:find("DialogueText", Dialogue)

	bee.addClick(self.ActiveButton, function()
		Game:playSound("ui_button_confirm")
		ItemModel:jumpView(101002)
		bee.logEvent("7daycheckin-sharkpass")
	end)
end

function P:onStart()
	self:refreshCont()
end

function P:refreshCont()
	self._curDay = SignInModel:getCurSignInDay()
	-- 自动签到
	self:signIn()

	self:setGrandTotal()
	self:setMonthlyCardShow()
	self:setSignInList()
end

function P:evt_initSevenSignData()
	self:refreshCont()
end

function P:showPanel(panel)
	for _, v in ipairs(self._Panels) do
		v:SetActive(v == panel)
	end
end

function P:setGrandTotal()
	local itemList = SignInModel:getTotalItemList()
	if not next(itemList) then
		return
	end
	PropItem:create(self.TotalItem1, itemList[1].item_list[1]):bindTips()
	PropItem:create(self.TotalItem2, itemList[2].item_list[1]):bindTips()
	PropItem:create(self.TotalItem3, itemList[3].item_list[1]):bindTips()
	bee.setText(self.TotalText1, _F("LAB_DAILY_SIGN_IN_11", tpl_total_rewards[1].total_days))
	bee.setText(self.TotalText2, _F("LAB_DAILY_SIGN_IN_11", tpl_total_rewards[2].total_days))
	bee.setText(self.TotalText3, _F("LAB_DAILY_SIGN_IN_11", tpl_total_rewards[3].total_days))

	local signInCount = SignInModel:getSignInTimes()
	bee.setSliderValue(self.SignInSlider, SliderValueList[signInCount])
	self.Received1:SetActive(signInCount >= tpl_total_rewards[1].total_days)
	self.Received2:SetActive(signInCount >= tpl_total_rewards[2].total_days)
	self.Received3:SetActive(signInCount >= tpl_total_rewards[3].total_days)
end

function P:setMonthlyCardShow()
	if self.MonthlyList.transform.childCount <= 0 then
		local rewards = ShopModel:getMonthlyCardSignInRewards()
		for i, v in ipairs(rewards) do
			local item1 = CU.GameObject.Instantiate(self.Item1)
			item1.transform:SetParent(self.MonthlyList.transform)
			item1.transform.localPosition = bee.v3(0, 0, 0)
			item1.transform.localScale = bee.v3(1, 1, 1)
			item1:SetActive(true)
			PropItem:create(self:find("PropItem", item1), v):bindTips()
		end
	end

	if ShopModel:isMonthlyCard() then
		self.ActiveButton:SetActive(false)
		if SignInModel:getIsSigned(self._curDay) then
			self.ReceivedMask:SetActive(true)
		end
	else
		self.ActiveButton:SetActive(true)
		self.ReceivedMask:SetActive(false)
	end
end

function P:initSignInList()
	self.signInList = UiListEx:create(self.SignInItemList)
	self.signInList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.ItemSignIn)
	end)
	self.signInList:setRefreshFunc(function(data, item)
		self:setSignInItem(item, data)
	end)
	self.signInList:setWidth(180)
end

function P:setSignInList()
	if not self.signInList then
		self:initSignInList()
	end
	self.signInList:setDatas(SignInModel:getSignInRewardsData())
	self.signInList:moveToYItem(self._curDay)
end

function P:setSignInItem(item, data)
	local CurFrame = self:find("CurFrame", item)
	local DayText = self:find("DayText", item)
	local LockIcon = self:find("LockIcon", item)
	local ItemList = self:find("ItemList/Viewport/Content", item)
	local TagStatus = self:find("TagStatus", item)
	local PassTag = self:find("PassTag", TagStatus)
	local RestroactiveTag = self:find("RestroactiveTag", TagStatus)
	local SignInTag = self:find("SignInTag", TagStatus)

	CurFrame:SetActive(self._curDay == data.day)
	bee.setText(DayText, string.format("%02d", data.day))
	LockIcon:SetActive(data.day > self._curDay)
	local rewardCount = #data.rewards
	local childCount = ItemList.transform.childCount
	for i = 1, rewardCount do
		if i > childCount then
			local p = CU.GameObject.Instantiate(self.Item1)
			p.transform:SetParent(ItemList.transform)
			p.transform.localPosition = bee.v3(0, 0, 0)
			p.transform.localScale = bee.v3(1, 1, 1)
			p:SetActive(true)
			
			PropItem:create(self:find("PropItem", p), data.rewards[i]):bindTips()
		else
			PropItem:create(self:find("PropItem", ItemList.transform:GetChild(i - 1)), data.rewards[i]):bindTips()
		end
	end
	if childCount > rewardCount then
		for i = rewardCount + 1, childCount do
			ItemList.transform:GetChild(i - 1):SetActive(false)
		end
	end

	if data.day == self._curDay then
		if data.isSigned then
			TagStatus:SetActive(true)
			SignInTag:SetActive(true)
			RestroactiveTag:SetActive(false)
			PassTag:SetActive(false)
		else
			TagStatus:SetActive(false)
		end
	elseif data.day < self._curDay then
		TagStatus:SetActive(true)
		if data.isSigned then
			SignInTag:SetActive(true)
			RestroactiveTag:SetActive(false)
			PassTag:SetActive(false)
		elseif SignInModel:getLeftRetroactiveTimes() > 0 then
			SignInTag:SetActive(false)
			RestroactiveTag:SetActive(true)
			PassTag:SetActive(false)
		else
			SignInTag:SetActive(false)
			RestroactiveTag:SetActive(false)
			PassTag:SetActive(true)
		end
	else
		TagStatus:SetActive(false)
	end

	bee.removeAllClick(item)
	bee.addClick(item, function()
		if data.isSigned then
			return
		end
		if data.day >= self._curDay then
			return
		end
		if SignInModel:getLeftRetroactiveTimes() <= 0 then
			return
		end
		Game:playSound("ui_button_confirm")
		if ShopModel:isMonthlyCard() then
			UiManager:showUI("ActivitySignInRetroactive", {day = data.day})
		else
			UiManager:showTip({
		        text = _F("LAB_DAILY_SIGN_IN_10", _T("LAB_SHOP_NAME_SUB_2")),
		        sureStr = _T("LAB_BUTTON_TEXT_1"),
		        onSure = function()
		        	ItemModel:jumpView(101002)
		        end
		    })
		end
	end)
end

function P:signIn()
	if SignInModel:getIsSigned(self._curDay) then
		return
	end
	SignInModel:sendSignIn(0)
end

function P:evt_ActivitySignIn()
	self:setGrandTotal()
	self:setSignInList()
	self:setMonthlyCardShow()
end

function P:evt_updateMonthlyCard()
	self:setMonthlyCardShow()
end

