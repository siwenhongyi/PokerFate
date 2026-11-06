local P = class("ShopSayakaExclusive", UiBase)

function P:onAwake()
	local Panel = self:find("AnimRoot/Center/Panel")

	self.propItems = {}
	for i = 1, 4 do
		self.propItems[i] = self:find("Items/PropItem" .. i, Panel)
	end

	self.LeftTimeText = self:find("LeftTime/LeftTimeText", Panel)
	self.PurchaseButton = self:find("PurchaseButton", Panel)
	self.PurchaseGreyButton = self:find("PurchaseGreyButton", Panel)
	self.OriPri = self:find("PriCont/OriPri", self.PurchaseButton)
	self.CurPri = self:find("PriCont/CurPri", self.PurchaseButton)
	self.Discount = self:find("Discount", self.PurchaseButton)
	self.DiscountText = self:find("DiscountText", self.Discount)
	self.ShopSkinButton = self:find("ShopSkinButton", Panel)
	self.SkinNameText = self:find("SkinNameText", self.ShopSkinButton)
	-- self.NameText = self:find("NameText", self.ShopSkinButton)

	bee.addClick(self.ShopSkinButton, function()
		bee.logEvent("shop-exclusive-pack-link", self._shop_id)
		local cfg = tpl_shop_gifts_skin[self._shop_id]
		ItemModel:jumpView(cfg.link, cfg.role_skin)
	end)
	bee.addClick(self.PurchaseButton, function()
		bee.logEvent("shop-exclusive-pack-buy", self._shop_id)
		UiManager:showUI("ShopPurchaseGiftsSkin", {cfg = tpl_shop_gifts_skin[self._shop_id]})
	end)
	bee.addClick(self.PurchaseGreyButton, function()
		UiManager:showToast(_T("LAB_SKIN_GIFTS_5"))
	end)
end

function P:onStart()
	self._shop_type = SHOP_TYPE.skin_gifts
	self._shop_id = 1001

	self:refreshUI()
end

function P:evt_SkinUnlockRSP()
	self:refreshUI()
end

function P:evt_updateShopLimit()
	self:refreshUI()
end

function P:refreshUI()
	local cfg = tpl_shop_gifts_skin[self._shop_id]
	local rewards = {}
	if cfg.props_ex then
		for i, v in ipairs(ShopModel:getRewardsList(cfg.props_ex)) do
			table.insert(rewards, v)
		end
	end
	if cfg.props then
		for i, v in ipairs(ShopModel:getRewardsList(cfg.props)) do
			table.insert(rewards, v)
		end
	end
	for i = 1, 4 do
		local p = PropItem:create(self.propItems[i], rewards[i])
		p:bindTips(nil, function()
			bee.logEvent("shop-exclusive-pack-item", rewards[i].item_id)
		end)
	end

	-- 已拥有该服饰
	if CharacterModel:isOwnedSkin(cfg.role_skin) then
		self.OriPri:SetActive(false)
		self.Discount:SetActive(false)

		bee.setIconInAtlas(self:find("Icon", self.CurPri), tpl_props[cfg.pri2[1]].icon)
		bee.setText(self:find("PriText", self.CurPri), cfg.pri2[2] .. _T("LAB_SHOP_COMMON_4"))
	else
		self.OriPri:SetActive(true)

		bee.setIconInAtlas(self:find("Icon", self.Ori), tpl_props[cfg.original_pri[1]].icon)
		bee.setText(self:find("PriText", self.OriPri), cfg.original_pri[2])

		bee.setIconInAtlas(self:find("Icon", self.CurPri), tpl_props[cfg.pri[1]].icon)
		bee.setText(self:find("PriText", self.CurPri), cfg.pri[2])

		if cfg.discount and cfg.discount > 0 then
			self.Discount:SetActive(true)
			bee.setText(self.DiscountText, cfg.discount .. "%")
		else
			self.Discount:SetActive(false)
		end
	end

	local skinCfg = tpl_character_skin[cfg.role_skin]
	bee.setText(self.SkinNameText, _T(skinCfg.name))
	-- local roleCfg = tpl_character[skinCfg.role]
	-- bee.setText(self.NameText, _T(roleCfg.name))

	if self._timeTag then
		scheduler:removeTag(self._timeTag)
		self._timeTag = nil
	end

	if cfg.time_end then
		local leftTime = cfg.time_end - bee.getServerTime()
		if leftTime > 0 then
			bee.setText(self.LeftTimeText, ShopModel:getShopTimeText(leftTime))
			self._timeTag = self:schedule(1, function()
				leftTime = leftTime - 1
				bee.setText(self.LeftTimeText, ShopModel:getShopTimeText(leftTime))
			end)
		else
			bee.setText(self.LeftTimeText, _T("LAB_BACKPACK_DES_21"))
		end
	end

	if ShopModel:getProductIsSoldOut(cfg) then
		self.PurchaseGreyButton:SetActive(true)
		self.PurchaseButton:SetActive(false)
	else
		self.PurchaseGreyButton:SetActive(false)
		self.PurchaseButton:SetActive(true)
	end
end

return P