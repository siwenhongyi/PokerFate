local P = class("ShopExchangeBatch", UiDialog)

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", self.AnimRoot)
	self.Center = Center

	self.CloseButton = self:find("CloseButton", Center)
	self.ItemCont = self:find("ItemCont", Center)
	self.Own = self:find("Own", Center)
	self.UnOwn = self:find("UnOwn", Center)
	self.PropItemObj = self:find("ItemCont/PropItem", Center)
	self.TitleText = self:find("TitleText", Center)
	self.DescText = self:find("DescCont/Viewport/Content/DescText", Center)

	local Batch = self:find("Batch", Center) or Center	-- 子类可能是把 ui 放在 Batch 下
	self.LimitText = self:find("LimitText", Batch)
	self.InputFieldCount = self:find("InputFieldCount", Batch)
	self.AddButton = self:find("AddButton", Batch)
	self.AddTenButton = self:find("AddTenButton", Batch)
	self.MaxButton = self:find("MaxButton", Batch)
	self.MinusButton = self:find("MinusButton", Batch)
	self.MinTenButton = self:find("MinTenButton", Batch)
	self.MinButton = self:find("MinButton", Batch)

	self.ExchangeButton = self:find("ExchangeButton", Batch)
	self.PriIcon = self:find("Pri/Currency/PriIcon", self.ExchangeButton)
	self.PriText = self:find("Pri/PriText", self.ExchangeButton)

	self.ExchangeGrayButton = self:find("ExchangeGrayButton", Batch)
	self.GrayPriIcon = self:find("Pri/Currency/GrayPriIcon", self.ExchangeGrayButton)
	self.CurCount = self:find("Pri/CurCount", self.ExchangeGrayButton)
	self.GrayPriText = self:find("Pri/GrayPriText", self.ExchangeGrayButton)

	self.InputFieldCount:GetComponent("InputField").contentType = CU.UI.InputField.ContentType.IntegerNumber

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.ExchangeButton, function()
		bee.logEvent("shop-goods-tap", self._params.data.cfg.shop_type, self._params.data.cfg.id)
		self:onClickExchange()
	end)
	bee.addClick(self.ExchangeGrayButton, function()
		self:onClickExchange()
	end)
end

function P:onShow()
	self:refreshCont()
end

function P:refreshCont()
	local data = self._params.data
	local cfg = self._params.data.cfg
	local exchange = ShopModel:getRewardsListWithType(cfg.props)[1]
	local exchangeCfg = ShopModel:getRewardCfg(exchange)

	PropItem:create(self.PropItemObj, {item_id = exchangeCfg.id, num = 0})
	if exchange.num > 1 then
		bee.setText(self.TitleText, _T(exchangeCfg.name) .. " x" .. exchange.num)
	else
		bee.setText(self.TitleText, _T(exchangeCfg.name))
	end
	if exchangeCfg.des then
		if tpl_props[exchangeCfg.id] then
			bee.setText(self.DescText, ItemModel:getItemDesText(exchangeCfg.id))
		else
			bee.setText(self.DescText, _T(exchangeCfg.des))
		end
	else
		bee.setText(self.DescText, "")
	end

	local OwnCount = ItemModel:getItemNumById(exchangeCfg.id)
	bee.setText(self.Own, _T("LAB_SHOP_COMMON_5") .. ":" .. OwnCount)

	if cfg.limit_type == SHOP_LIMIT_TYPE.DAILY then
		self.LimitText:SetActive(true)
		bee.setText(self.LimitText, _T("LAB_SHOP_COMMON_11") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.WEEKLY then
		self.LimitText:SetActive(true)
		bee.setText(self.LimitText, _T("LAB_SHOP_COMMON_12") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.MONTHLY then
		self.LimitText:SetActive(true)
		bee.setText(self.LimitText, _T("LAB_SHOP_COMMON_13") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	elseif cfg.limit_type == SHOP_LIMIT_TYPE.PERMANENT then
		self.LimitText:SetActive(true)
		bee.setText(self.LimitText, _T("LAB_SHOP_COMMON_14") .. ":" .. data.buyCount .. "/" .. cfg.limit_count)
	else
		self.LimitText:SetActive(false)
	end

	-- 初始化价格显示
	local consumeId = cfg.exchange_cost[1]
	local consumeCount = cfg.exchange_cost[2]
	local ownCount = ItemModel:getItemNumById(consumeId)

	self._selectedCount = 1
	self._maxCount = math.max(1, math.floor(ownCount / consumeCount))
	if cfg.limit_count then
		self._maxCount = math.min(cfg.limit_count - data.buyCount, self._maxCount)
	end

	if ownCount >= consumeCount then
		self.ExchangeButton:SetActive(true)
		self.ExchangeGrayButton:SetActive(false)

		bee.setIconInAtlas(self.PriIcon, tpl_props[consumeId].icon)
		self:refreshButtonShow(consumeCount)
	else
		self.ExchangeButton:SetActive(false)
		self.ExchangeGrayButton:SetActive(true)

		bee.setIconInAtlas(self.GrayPriIcon, tpl_props[consumeId].icon)
		bee.setText(self.CurCount, ownCount)
		bee.setText(self.GrayPriText, consumeCount)
		self:refreshButtonShow(consumeCount)
	end

	bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
	bee.removeAllClick(self.MinButton)
	bee.addClick(self.MinButton, function()
		if self._selectedCount <= 1 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = 1
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.removeAllClick(self.MaxButton)
	bee.addClick(self.MaxButton, function()
		if self._selectedCount >= self._maxCount then
			UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = self._maxCount
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.removeAllClick(self.MinusButton)
	bee.addClick(self.MinusButton, function()
		if self._selectedCount <= 1 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.max(1, self._selectedCount - 1)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.removeAllClick(self.AddTenButton)
	bee.addClick(self.AddTenButton, function()
		if self._selectedCount >= self._maxCount then
			UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.min(self._maxCount, self._selectedCount + 10)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.removeAllClick(self.MinTenButton)
	bee.addClick(self.MinTenButton, function()
		if self._selectedCount <= 1 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.max(1, self._selectedCount - 10)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.addLongClick(self.MinusButton, function()
		if self._selectedCount <= 1 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.max(1, self._selectedCount - 1)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)
	bee.removeAllClick(self.AddButton)
	bee.addClick(self.AddButton, function()
		if self._selectedCount >= self._maxCount then
			UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.min(self._maxCount, self._selectedCount + 1)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)

	end)
	bee.addLongClick(self.AddButton, function()
		if self._selectedCount >= self._maxCount then
			UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedCount = math.min(self._maxCount, self._selectedCount + 1)
		bee.setText(self.InputFieldCount, self._selectedCount, "InputField")
		self:refreshButtonShow(consumeCount)
	end)

	self.InputFieldCount:GetComponent("InputField").onEndEdit:RemoveAllListeners()
	self.InputFieldCount:GetComponent("InputField").onEndEdit:AddListener(function()
		local inputCount = tonumber(bee.getText(self.InputFieldCount, "InputField"))
		if not inputCount then
			inputCount = 1
		end
		if inputCount < 1 then
			inputCount = 1
		end
		if inputCount > self._maxCount then
			inputCount = self._maxCount
		end
		bee.setText(self.InputFieldCount, inputCount, "InputField")
		self._selectedCount = inputCount
		self:refreshButtonShow(consumeCount)
	end, "InputField")
end

function P:refreshButtonShow(consumeCount)
	if self._selectedCount <= 1 then
		self:setButtonShow(self.MinButton, false)
		self:setButtonShow(self.MinusButton, false)
		self:setButtonShow(self.MinTenButton, false)
	else
		self:setButtonShow(self.MinButton, true)
		self:setButtonShow(self.MinusButton, true)
		self:setButtonShow(self.MinTenButton, true)
	end
	if self._selectedCount >= self._maxCount then
		self:setButtonShow(self.MaxButton, false)
		self:setButtonShow(self.AddButton, false)
		self:setButtonShow(self.AddTenButton, false)
	else
		self:setButtonShow(self.MaxButton, true)
		self:setButtonShow(self.AddButton, true)
		self:setButtonShow(self.AddTenButton, true)
	end

	bee.setText(self.PriText, consumeCount * self._selectedCount)
	self:refreshText()
end

function P:setButtonShow(button, isOn)
	if not button then return end
	local Off = self:find("Off", button)
	local On = self:find("On", button)
	Off:SetActive(not isOn)
	On:SetActive(isOn)
end

function P:onClickExchange()
	local cfg = self._params.data.cfg
	local consumeCount = cfg.exchange_cost[2]
	local own = ItemModel:getItemNumById(cfg.exchange_cost[1])
	if consumeCount * self._selectedCount > own then
		UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[cfg.exchange_cost[1]].name)))
		UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(cfg.exchange_cost[1], true)})
		return
	end
	Game:playSound("ui_button_confirm")
	ShopModel:buyWithProp(cfg.shop_type, cfg.id, self._selectedCount)
	self:hideUI()
end

function P:refreshText()
	
end

function P:evt_ItemChangeRSP()
	self:refreshCont()
end

return P