local P = class("ShopMonthlyCard", UiBase)

function P:onAwake()
	self.Ani_root = self:find("Ani_root")

	self.LeftTimeText = self:find("LeftTimeText", self.Ani_root)

	local RewardTotal = self:find("RewardTotal", self.Ani_root)
	self.TotalRewardIcon1 = self:find("TotalRewardIcon1", RewardTotal)
	self.TotalRewardIcon2 = self:find("TotalRewardIcon2", RewardTotal)
	self.TotalRewardCount1 = self:find("TotalRewardCount1", RewardTotal)
	self.TotalRewardCount2 = self:find("TotalRewardCount2", RewardTotal)

	local Privilege = self:find("Privilege", self.Ani_root)
	self.ItemTitle = self:find("ItemTitle", Privilege)
	self.ItemFrame = self:find("ItemFrame", Privilege)
	self.SignIn = self:find("SignIn", Privilege)
	self.Task = self:find("Task", Privilege)
	self.OffTitle = self:find("OffTitle", Privilege)
	self.OnTitle = self:find("OnTitle", Privilege)
	self.ActiveEff1 = self:find("ActiveEff1", Privilege)
	self.ActiveEff2 = self:find("ActiveEff2", Privilege)

	self.Reward1 = self:find("Reward1", self.Ani_root)
	self.Reward2 = self:find("Reward2", self.Ani_root)
	self.InfoButton = self:find("InfoButton", self.Ani_root)

	self.PurchaseButton = self:find("PurchaseButton", self.Ani_root)
	self.PriceText = self:find("PriceText", self.PurchaseButton)
	self.BuyEff = self:find("BuyEff", self.PurchaseButton)

	bee.addClick(self.InfoButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("shop-sharkpass-rules")
		UiManager:showUI("ShopMonthlyCardRules")
	end)
	bee.addClick(self.PurchaseButton, function()
		self:onClickPurchase()
	end)

	bee.addClick(self.SignIn, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonTextTipRL", {text = _T("LAB_MONTHLY_CARD_28"), target = self.SignIn})
	end)
	bee.addClick(self.Task, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonTextTipRL", {text = _T("LAB_MONTHLY_CARD_29"), target = self.Task})
	end)
end

function P:refreshUI()
	self:setContShow()
end

function P:onStart()
	self:setContShow()
end

function P:setContShow()
	local showCfg = tpl_monthly_card[1]
	local dailyRewards = ShopModel:getRewardsList(tpl_constdata.Monthly_Card_Daily_Rewards)
	local activeRewards = ShopModel:getRewardsList(showCfg.activate_rewards)

	-- 总计获得
	bee.setIconInAtlas(self.TotalRewardIcon1, tpl_props[dailyRewards[1].id].icon)
	bee.setText(self.TotalRewardCount1, _N(dailyRewards[1].num * showCfg.days + activeRewards[1].num))
	bee.setIconInAtlas(self.TotalRewardIcon2, tpl_props[dailyRewards[2].id].icon)
	bee.setText(self.TotalRewardCount2, _N(dailyRewards[2].num * showCfg.days + activeRewards[2].num))

	-- 立即获得
	self:setRewardItem(self.Reward1, activeRewards)
	-- 签到获得
	self:setRewardItem(self.Reward2, dailyRewards)

	-- 月卡特权
	PropItem:create(self:find("PropItem", self.ItemTitle), {item_id = showCfg.exc_title[1], num = 0}):bindTips()
	bee.setText(self:find("NameText", self.ItemTitle), _T("LAB_MONTHLY_CARD_7"))
	PropItem:create(self:find("PropItem", self.ItemFrame), {item_id = showCfg.exc_frame[1], num = 0}):bindTips()
	bee.setText(self:find("NameText", self.ItemFrame), _T("LAB_MONTHLY_CARD_8"))
	PropItem:create(self:find("PropItem", self.SignIn), {item_id = GPropId.Retroactive, num = 0}):bindTips()
	bee.setText(self:find("NameText", self.SignIn), _T("LAB_MONTHLY_CARD_9"))
	PropItem:create(self:find("PropItem", self.Task), {item_id = GPropId.ExclusiveTask, num = 0}):bindTips()
	bee.setText(self:find("NameText", self.Task), _T("LAB_MONTHLY_CARD_10"))

	if self._timeTag then
		scheduler:removeTag(self._timeTag)
		self._timeTag = nil
	end

	local pidCfg = ShopModel:getPidData(showCfg.buy_id)
	local isActive = ShopModel:isMonthlyCard()
	if isActive then
		-- 月卡已激活
		self.LeftTimeText:SetActive(true)
		local leftTime = ShopModel:getMonthlyCardLeftTime()
		bee.setText(self.LeftTimeText, _F("LAB_TIME_DES", ShopModel:getShopTimeText(leftTime)))
		self._timeTag = self:schedule(1, function()
			leftTime = leftTime - 1
			if leftTime > 0 then
				bee.setText(self.LeftTimeText, _F("LAB_TIME_DES", ShopModel:getShopTimeText(leftTime)))
			else
				bee.setText(self.LeftTimeText, _T("LAB_BACKPACK_DES_21"))
			end
		end)

		bee.setText(self.PriceText, _T("LAB_MONTHLY_CARD_20") .. ShopModel:getPriText(pidCfg))
	else
		self.LeftTimeText:SetActive(false)
		bee.setText(self.PriceText, ShopModel:getPriText(pidCfg))
	end
	self.OnTitle:SetActive(isActive)
	self.OffTitle:SetActive(not isActive)
	self.ActiveEff1:SetActive(isActive)
	self.ActiveEff2:SetActive(isActive)
	self.BuyEff:SetActive(not isActive)
end

function P:setRewardItem(item, rewards)
	bee.setIconInAtlas(self:find("Icon1", item), tpl_props[rewards[1].id].icon)
	bee.setText(self:find("Count1", item), _N(rewards[1].num))
	bee.setIconInAtlas(self:find("Icon2", item), tpl_props[rewards[2].id].icon)
	bee.setText(self:find("Count2", item), _N(rewards[2].num))

	local On = self:find("On", item)
	local Off = self:find("Off", item)
	local isActive = ShopModel:isMonthlyCard()
	On:SetActive(isActive)
	Off:SetActive(not isActive)
end

function P:onClickPurchase()
	local leftTime = ShopModel:getMonthlyCardLeftTime()
	if leftTime > 0 and (leftTime / 86400) > tpl_constdata.Monthly_Card_Limit then
		UiManager:showToast(_T("LAB_MONTHLY_CARD_11"))
		return
	end
	Game:playSound("ui_button_confirm")
	UiManager:showUI("ShopMonthlyCardPurchase")
end

