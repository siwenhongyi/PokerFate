local P = class("ShopNewComerExclusive", UiBase)

function P:onAwake()
	self.Ani_root = self:find("Ani_root")

	self.ItemCont = self:find("ItemCont", self.Ani_root)
	self.itemList = {}
	for i = 1, 3 do
		table.insert(self.itemList, self:find("Item" .. i, self.ItemCont))
	end
	self.PurchaseButton = self:find("PurchaseButton", self.Ani_root)
	self.BoughtText = self:find("BoughtText", self.Ani_root)
	self.PriceText = self:find("PriceText", self.PurchaseButton)
	self.SkinNameText = self:find("shop_newcomer_skin_bg/SkinNameText", self.Ani_root)
	self.RoleNameText = self:find("shop_newcomer_skin_bg/RoleNameText", self.Ani_root)
	self.PreviewButton = self:find("PreviewButton", self.Ani_root)

	bee.addClick(self.itemList[1], function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("shop-newpresident-outfit-icon")
		self:onClickPreview()
	end)
	bee.addClick(self.PreviewButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("shop-newpresident-outfit-preview")
		self:onClickPreview()
	end)
	bee.addClick(self.PurchaseButton, function()
		bee.logEvent("shop-goods-tap", SHOP_TYPE.new_comer, 10001)
		self:onClickPurchase()
	end)
end

function P:onStart()
	self._cfg = tpl_icebreaker_pack[10001]

	local rewards = ShopModel:getRewardsListWithType(self._cfg.props)
	for i = 1, 3 do
		local item = self.itemList[i]
		if i == 1 then
			self._skinCfg = tpl_character_skin[rewards[i].id]
			bee.setIconInAtlas(self:find("SkinIcon", item), tpl_props[self._skinCfg.avatar].icon)
		else
			PropItem:create(item, rewards[i]):bindTips()
		end
	end

	self._pidCfg = ShopModel:getPidData(self._cfg.buy_id)
	bee.setText(self.PriceText, ShopModel:getPriText(self._pidCfg))

	if self._skinCfg then
		bee.setText(self.SkinNameText, _T(self._skinCfg.name))
		bee.setText(self.RoleNameText, _T(tpl_character[self._skinCfg.role].name))
	end

	self:refreshUI()
end

function P:onClickPreview()
	UiManager:showUI("CharacterMainGarments", {data = CharacterModel:getRoleData(self._skinCfg.role), selectId = self._skinCfg.id})
end

function P:onClickPurchase()
	if ShopModel:isBoughtIceBreak() then
		return
	end
	Game:playSound("ui_button_confirm")
	ShopModel:pay(self._cfg)
end

function P:refreshUI()
	local isBougnt = ShopModel:isBoughtIceBreak()
	self.PurchaseButton:SetActive(not isBougnt)
	self.BoughtText:SetActive(isBougnt)
end

return P