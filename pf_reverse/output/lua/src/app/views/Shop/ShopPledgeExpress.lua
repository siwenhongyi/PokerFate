local P = class("ShopPledgeExpress", UiDialog)

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")

	local Center = self:find("Center", self.AnimRoot)
	self.CharacterBg = self:find("CharacterBgMask/CharacterBg", Center)
	self.CharacterImg = self:find("CharacterImgMask/CharacterImg", Center)
	self.TipsText = self:find("shop_pledge_title_bg/TipsText", Center)
	self.Item1 = self:find("Item1", Center)
	self.Item1:SetActive(false)
	self.ItemListObj = self:find("ItemList", Center)
	self.ItemCont = self:find("ItemCont", Center)
	self.InfoButton = self:find("shop_pledge_title_bg/InfoButton", Center)
	self.PurchaseButton = self:find("PurchaseButton", Center)
	self.PriText = self:find("PriText", self.PurchaseButton)
	self.AttireButton = self:find("AttireButton", Center)
	self.CloseButton = self:find("CloseButton", Center)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.InfoButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("CommonTextTipUD", {text = _T("TAB_OATH_EXPRESS_PACK_3"), target = self.InfoButton})
		bee.logEvent("character-bond-oathexpresstips")
	end)
	-- bee.addClick(self.AttireButton, function()
	-- 	Game:playSound("ui_button_confirm")
	-- 	UiManager:showUI("CommonTextTipUD", {text = _T("TAB_OATH_EXPRESS_PACK_5"), target = self.AttireButton})
	-- 	bee.logEvent("character-bond-oathexpresstips")
	-- end)
end

function P:onStart()
	local characterId = self._params.id
	local characterCfg = tpl_character[characterId]
	local skinCfg
	for k, v in pairs(tpl_character_skin) do
		if v.role == characterId and v.kind == 1 then
			skinCfg = v
			break
		end
	end

	local giftCfg, shopCfg = ShopModel:getCharacterGiftCfg(characterId)
	local itemDatas = ShopModel:getRewardsList(shopCfg.props)

	if skinCfg.image_with_fg then
		self.CharacterBg:SetActive(true)
		bee.setIcon(self.CharacterBg, skinCfg.image_with_fg, nil, true)
	else
		self.CharacterBg:SetActive(false)
	end
	bee.setIcon(self.CharacterImg, skinCfg.image, nil, true)
	self.CharacterBg.transform.localPosition = bee.v3(giftCfg.bg_offset[1], giftCfg.bg_offset[2], 0)
	self.CharacterBg.transform.localScale = bee.v3(giftCfg.bg_offset[3], giftCfg.bg_offset[3], 1)
	self.CharacterImg.transform.localPosition = bee.v3(giftCfg.image_offset[1], giftCfg.image_offset[2], 0)
	self.CharacterImg.transform.localScale = bee.v3(giftCfg.image_offset[3], giftCfg.image_offset[3], 1)
	bee.setText(self.TipsText, _F("TAB_OATH_EXPRESS_PACK_2", _T(characterCfg.name)))

	if #itemDatas >= 5 then
		self.itemList = UiListEx:create(self.ItemListObj)
		self.itemList:setCreateFunc(function()
			return CU.GameObject.Instantiate(self.Item1)
		end)
		self.itemList:setRefreshFunc(function(data, item)
			self:setRewardItem(item, data)
		end)
		self.itemList:setWidth(178)
		self.itemList:setDatas(itemDatas)
	else
		for k, v in pairs(itemDatas) do
			local item = CU.GameObject.Instantiate(self.Item1)
			item.transform:SetParent(self.ItemCont.transform)
			item.transform.localPosition = bee.v3(0, 0, 0)
			item.transform.localScale = bee.v3(1, 1, 1)
			self:setRewardItem(item, v)
			item:SetActive(true)
		end
	end

	local pidCfg = ShopModel:getPidData(shopCfg.buy_id)
	bee.setText(self.PriText, ShopModel:getPriText(pidCfg))

	bee.addClick(self.PurchaseButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("ShopPurchasePackage", {data = {cfg = shopCfg}, buyCb = function()
			ShopModel:setShopPledgeGiftRole(self._params.id)
			self:hideUI()
		end})
	end)
end

function P:setRewardItem(item, data)
	local PropItemObj = self:find("PropItem", item)
	PropItem:create(PropItemObj, data):bindTips()
end

return P