local P = class("ShopPurchaseTheme", UiDialog)

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
	self.CurPriText = self:find("CurPriText", self.PurchaseButton)
	self.OriPriText = self:find("OriPriText", self.PurchaseButton)
	self.OriPriIcon = self:find("OriPriIcon", self.PurchaseButton)
	self.CurPriIcon = self:find("CurPriIcon", self.PurchaseButton)
	self.Discount = self:find("Discount", Center)
	self.DiscountText = self:find("DiscountText", self.Discount)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.PurchaseButton, function()
		self:onClickPurchase()
	end)
end

function P:onStart()
	local data = self._params.data

	-- 礼包信息
	bee.setIconInAtlas(self.PackageIcon, data.icon)
	bee.setText(self.PackageNameText, _T(data.name))

	-- 道具列表
	self.packageList = UiListEx:create(self.PackageList)
	self.packageList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.ItemProp)
	end)
	self.packageList:setRefreshFunc(function(data, item)
		self:setItemProp(item, data)
	end)
	self.packageList:setWidth(100)
	self.packageList:setDatas(data.items)

	-- 购买价格显示
	bee.setIcon(self.OriPriIcon, tpl_props[data.consumeId].icon)
	bee.setIcon(self.CurPriIcon, tpl_props[data.consumeId].icon)
	bee.setText(self.OriPriText, data.oriPri)
	bee.setText(self.CurPriText, data.pri)
	bee.setText(self.DiscountText, ((1000 - data.discount) / 10) .. "%")
end

function P:setItemProp(item, data)
	local cfg = data.cfg
	local PropItemObj = self:find("PropItem", item)
	local ItemNameText = self:find("ItemNameText", item)
	local UnOwnTag = self:find("UnOwnTag", item)
	local OwnTag = self:find("OwnTag", item)

	PropItem:create(PropItemObj, cfg):bindTips()
	bee.setText(ItemNameText, _T(cfg.name))
	OwnTag:SetActive(data.isOwn)
	UnOwnTag:SetActive(not data.isOwn)
end

function P:onClickPurchase()
	local data = self._params.data
	bee.logEvent("shop-goods-preview", data.shop_type, data.id)
	if data.time_end and (data.time_end - bee.getServerTime()) < 0 then
		UiManager:showToast(_T("LAB_SHOP_COMMON_10"))
		bee.emit("evt_updateShopLimit")
		return
	end

	Game:playSound("ui_button_confirm")

	local ownCount = ItemModel:getItemNumById(data.consumeId)
	if ownCount < self._params.data.pri then
		-- 前往获得提示
		local propCfg = tpl_props[self._params.data.consumeId]
	    local params = {}
	    params.text = _F("LAB_SHOP_ROLE_SKIN_10", _T(propCfg.name))
	    params.onSure = function()
	    	UiManager:hideUI("ShopThemePreview")
	    	self:hideUI()
	        ItemModel:jumpView(propCfg.accesses[1])
	    end
	    UiManager:showTip(params)
		return
	end

	ShopModel:buyWithProp(data.shop_type, data.id, 1)
	self:hideUI()
end

return P