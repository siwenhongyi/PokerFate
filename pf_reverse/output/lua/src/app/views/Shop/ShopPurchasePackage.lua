local P = class("ShopPurchasePackage", UiDialog)

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", self.AnimRoot)

	self.CloseButton = self:find("CloseButton", Center)

	local Package = self:find("Content/Package", Center)
	self.PackageBg = self:find("PackageBg", Package)
	self.PackageIcon = self:find("PackageIcon", Package)
	self.PackageNameText = self:find("PackageNameText", Package)
	self.LimitText = self:find("LimitText", Package)

	self.PackageList = self:find("Content/PackageList", Center)
	self.ItemProp = self:find("ItemProp", self.PackageList)
	self.ItemProp:SetActive(false)

	self.PurchaseButton = self:find("PurchaseButton", Center)
	self.PriText = self:find("PriText", self.PurchaseButton)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.PurchaseButton, function()
		self:onClickPurchase()
	end)
end

function P:onStart()
	local data = self._params.data
	local cfg = self._params.data.cfg

	-- 礼包信息
	if cfg.goods_bg == 1 then
		bee.setIcon(self.PackageBg, "shop_package_bg_01_s", "Shop")
	else
		bee.setIcon(self.PackageBg, "shop_package_bg_02_s", "Shop")
	end
	bee.setIconInAtlas(self.PackageIcon, cfg.icon)
	bee.setText(self.PackageNameText, _T(cfg.name))

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

	-- 道具列表
	local list = {}
	for i = 1, #cfg.props, 2 do
		table.insert(list, {item_id = cfg.props[i], num = cfg.props[i + 1]})
	end
	self.packageList = UiListEx:create(self.PackageList)
	self.packageList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.ItemProp)
	end)
	self.packageList:setRefreshFunc(function(data, item)
		self:setItemProp(item, data)
	end)
	self.packageList:setWidth(100)
	self.packageList:setDatas(list)

	-- 购买价格显示
	local pidCfg = ShopModel:getPidData(cfg.buy_id)
	bee.setText(self.PriText, ShopModel:getPriText(pidCfg))
end

function P:setItemProp(item, data)
	local PropItem = self:find("PropItem", item)
	local ItemNameText = self:find("ItemNameText", item)
	local ItemCountText = self:find("ItemCountText", item)

	bee.emitTo(PropItem, "init", {item_id = data.item_id, num = 0})
	local propCfg = tpl_props[data.item_id]
	bee.setText(ItemNameText, _T(propCfg.name))
	bee.setText(ItemCountText, _N(data.num))

	bee.removeAllClick(PropItem)
	bee.addClick(PropItem, function()
		UiManager:showUI("CommonItemTip", {data = data, target = PropItem})
	end)
end

function P:onClickPurchase()
	if self._params.data.cfg.time_end and (self._params.data.cfg.time_end - bee.getServerTime()) < 0 then
		UiManager:showToast(_T("LAB_SHOP_COMMON_10"))
		bee.emit("evt_updateShopLimit")
		return
	end

	bee.logEvent("shop-goods-tap", self._params.data.cfg.shop_type, self._params.data.cfg.id)

	if self._params.buyCb then
		self._params.buyCb()
	end

	Game:playSound("ui_button_confirm")
	ShopModel:pay(self._params.data.cfg)
	self:hideUI()
end

