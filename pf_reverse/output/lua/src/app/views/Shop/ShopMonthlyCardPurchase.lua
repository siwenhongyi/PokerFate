local P = class("ShopMonthlyCardPurchase", UiDialog)

function P:onAwake()
	local Panel = self:find("AnimRoot/Center")

	self.MonthlyCardItem = self:find("MonthlyCardItem", Panel)
	self.TitleText = self:find("TitleText", Panel)
	self.TimeTag = self:find("TimeTag", Panel)
	self.TimeText = self:find("TimeTag/TimeText", Panel)
	self.Item1 = self:find("Item1", Panel)
	self.Item2 = self:find("Item2", Panel)
	self.Item3 = self:find("Item3", Panel)
	self.PurchaseButton = self:find("PurchaseButton", Panel)
	self.PriceText = self:find("PurchaseButton/PriceText", Panel)
	self.CloseButton = self:find("CloseButton", Panel)

	bee.addClick(self.PurchaseButton, function()
		bee.logEvent("shop-newpresident-outfit-icon")
		self:onClickPurchase()
	end)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
end

function P:onStart()
	self.TimeTag:SetActive(false)
	if ShopModel:isMonthlyCard() then
		self.TimeTag:SetActive(true)
		local leftTime = ShopModel:getMonthlyCardLeftTime()
		bee.setText(self.TimeText, ShopModel:getShopTimeText(leftTime))
		self:schedule(1, function()
			leftTime = leftTime - 1
			if leftTime > 0 then
				bee.setText(self.TimeText, ShopModel:getShopTimeText(leftTime))
			else
				bee.setText(self.TimeText, _T("LAB_BACKPACK_DES_21"))
			end
		end)
	else
		self.TimeTag:SetActive(false)
	end

	self._selectedId = 1

	self:setItem(self.Item1, tpl_monthly_card[1])
	self:setItem(self.Item2, tpl_monthly_card[2])
	self:setItem(self.Item3, tpl_monthly_card[3])

	PropItem:create(self.MonthlyCardItem, {item_id = GPropId.MonthlyCard, num = 0})

	local cfg = tpl_monthly_card[self._selectedId]
	bee.setText(self.TitleText, _F("LAB_MONTHLY_CARD_26", cfg.days))
	local pidCfg = ShopModel:getPidData(cfg.buy_id)
	bee.setText(self.PriceText, ShopModel:getPriText(pidCfg))
end

function P:setItem(item, data)
	local DayText = self:find("DayText", item)
	local ItemIcon1 = self:find("ItemIcon1", item)
	local CountText1 = self:find("CountText1", item)
	local ItemIcon2 = self:find("ItemIcon2", item)
	local CountText2 = self:find("CountText2", item)
	local CheckToggle = self:find("CheckToggle", item)

	local activeRewards = ShopModel:getRewardsList(data.activate_rewards)
	bee.setText(DayText, _F("LAB_MONTHLY_CARD_15", data.days))
	bee.setIconInAtlas(ItemIcon1, tpl_props[activeRewards[1].id].icon)
	bee.setText(CountText1, _N(activeRewards[1].num))
	bee.setIconInAtlas(ItemIcon2, tpl_props[activeRewards[2].id].icon)
	bee.setText(CountText2, _N(activeRewards[2].num))

	bee.removeValueChanged(CheckToggle)
	bee.addValueChanged(CheckToggle, function(isOn)
		if isOn then
			Game:playSound("ui_button_disabled")
			self._selectedId = data.id

			bee.setText(self.TitleText, _F("LAB_MONTHLY_CARD_26", data.days))
			local pidCfg = ShopModel:getPidData(data.buy_id)
			bee.setText(self.PriceText, ShopModel:getPriText(pidCfg))
		end
	end)

	if self._selectedId == data.id then
		bee.setCheck(CheckToggle, true)
	else
		bee.setUncheck(CheckToggle)
	end
end

function P:onClickPurchase()
	bee.logEvent("shop-goods-tap", SHOP_TYPE.monthly_card, self._selectedId)
	
	local leftTime = ShopModel:getMonthlyCardLeftTime()
	if leftTime > 0 and (leftTime / 86400) > tpl_constdata.Monthly_Card_Limit then
		UiManager:showToast(_T("LAB_MONTHLY_CARD_11"))
		return
	end
	Game:playSound("ui_button_confirm")
	local data = tpl_monthly_card[self._selectedId]
	ShopModel:pay(data)
end

function P:evt_pay_sucess()
	self:hideUI()
end

return P