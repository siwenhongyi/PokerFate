local P = class("ShopExchangeSingle", UiDialog)

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", self.AnimRoot)

	self.CloseButton = self:find("CloseButton", Center)
	self.ItemCont = self:find("ItemCont", Center)
	self.Own = self:find("Own", Center)
	self.UnOwn = self:find("UnOwn", Center)
	self.OwnCount = self:find("OwnCount", Center)
	self.PropItemObj = self:find("ItemCont/PropItem", Center)
	self.RoleItemObj = self:find("ItemCont/RoleItem", Center)
	self.TitleText = self:find("TitleText", Center)
	self.DescText = self:find("DescCont/Viewport/Content/DescText", Center)

	self.PurchaseButton = self:find("PurchaseButton", Center)
	self.PurchaseGrayButton = self:find("PurchaseGrayButton", Center)

	self.PriCont = self:find("PriCont", Center)
	self.PriIcon = self:find("PriIcon/PriIcon", self.PriCont)
	self.RedPriText = self:find("RedPriText", self.PriCont)
	self.Line = self:find("Line", self.PriCont)
	self.PriText = self:find("PriText", self.PriCont)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.PurchaseButton, function()
		bee.logEvent("shop-goods-tap", self._params.data.cfg.shop_type, self._params.data.cfg.id)
		self:onClickExchange()
	end)
	bee.addClick(self.PurchaseGrayButton, function()
		self:onClickExchange()
	end)
end

function P:onShow()
	self:refreshCont()
end

function P:refreshCont()
	local data = self._params.data
	local cfg = self._params.data.cfg
	local exchange
	if cfg.shop_type == SHOP_TYPE.shop_theme or cfg.shop_type == SHOP_TYPE.shop_scene 
		or cfg.shop_type == SHOP_TYPE.shop_table or cfg.shop_type == SHOP_TYPE.shop_music 
		or cfg.shop_type == SHOP_TYPE.shop_effect then
		-- 装饰商城和兑换商城奖励配置字段不一样
		exchange = ShopModel:getRewardsList(cfg.props)[1]
	else
		exchange = ShopModel:getRewardsListWithType(cfg.props)[1]
	end
	local exchangeCfg = ShopModel:getRewardCfg(exchange)

	if exchange.major_type == GMajorType.PROP then
		self.PropItemObj:SetActive(true)
		self.RoleItemObj:SetActive(false)
		PropItem:create(self.PropItemObj, exchange)
	else
		self.PropItemObj:SetActive(false)
		self.RoleItemObj:SetActive(true)
		RoleItem:create(self.RoleItemObj, exchange)
	end
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

	local ownNum = ItemModel:getItemNumById(exchangeCfg.id)
	if exchange.major_type == GMajorType.PROP and ItemModel:getGPropType(exchangeCfg.type) ~= GPropType.Display then
		self.OwnCount:SetActive(true)
		self.Own:SetActive(false)
		self.UnOwn:SetActive(false)
		bee.setText(self.OwnCount, _T("LAB_SHOP_COMMON_5") .. ":" .. ownNum)
	else
		self.OwnCount:SetActive(false)
		self.Own:SetActive(ownNum > 0)
		self.UnOwn:SetActive(ownNum <= 0)
	end

	local consumeId = cfg.exchange_cost and cfg.exchange_cost[1] or cfg.pri[1]
	local consumeCount = cfg.exchange_cost and cfg.exchange_cost[2] or cfg.pri[2]
	local ownCount = ItemModel:getItemNumById(consumeId)

	if ownCount >= consumeCount then
		self.PurchaseButton:SetActive(true)
		self.PurchaseGrayButton:SetActive(false)

		self.RedPriText:SetActive(false)
		self.Line:SetActive(false)
	else
		self.PurchaseButton:SetActive(false)
		self.PurchaseGrayButton:SetActive(true)

		self.RedPriText:SetActive(true)
		self.Line:SetActive(true)
		bee.setText(self.RedPriText, ownCount)
	end

	bee.setIconInAtlas(self.PriIcon, tpl_props[consumeId].icon)
	bee.setText(self.PriText, consumeCount)
end

function P:onClickExchange()
	local cfg = self._params.data.cfg
	local consumeId = cfg.exchange_cost and cfg.exchange_cost[1] or cfg.pri[1]
	local consumeCount = cfg.exchange_cost and cfg.exchange_cost[2] or cfg.pri[2]
	local ownCount = ItemModel:getItemNumById(consumeId)
	
	if consumeCount > ownCount then
		UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[consumeId].name)))
		UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(consumeId, true)})
		return
	end
	Game:playSound("ui_button_confirm")
	ShopModel:buyWithProp(cfg.shop_type, cfg.id, 1)
	self:hideUI()
end

function P:evt_ItemChangeRSP()
	self:refreshCont()
end

