local P = class("ShopSkin", UiBase)

function P:onAwake()
	P.super.onAwake(self)

	local Garments = self:find("Garments")
	self.GarmentsList = self:find("GarmentsList", Garments)
	self.SkinItem = self:find("SkinItem", Garments)
	self.SkinItem:SetActive(false)
	self.SkinArrowLeft = self:find("SkinArrowLeft", Garments)
	self.SkinArrowRight = self:find("SkinArrowRight", Garments)

	self.TagSSR = self:find("TagSSR")
	self.TagSR = self:find("TagSR")
	self.SkinNameText = self:find("SkinNameText")
	self.NameText = self:find("NameText")
	self.CharacterImage = self:find("CharacterImageRaw")
	self.TipEff = self:find("TipEff")
	self.TipEff:SetActive(false)
	self.AllinButton = self:find("AllinButton")
	self.ExplosionButton = self:find("ExplosionButton")
	self.IngameButton = self:find("IngameButton")
	self.DetailButton = self:find("DetailButton")

	self.PurchaseGreyButton = self:find("PurchaseGreyButton")
	self.PurchaseButton = self:find("PurchaseButton")
	self.CurrencyIcon = self:find("Cont/CurrencyIcon/CurrencyIcon", self.PurchaseButton)
	self.CountText = self:find("Cont/CountText", self.PurchaseButton)
	self.PurchaseTips = self:find("PurchaseTips")
	self.OriCountText = self:find("OriCountText", self.PurchaseTips)
	self.OriCurrencyIcon = self:find("OriCurrencyIcon", self.PurchaseTips)
	self.DiscountTag = self:find("DiscountTag")
	self.DiscountText = self:find("DiscountText", self.DiscountTag)

	self._nodeCache = NodeCache:create()

	bee.addClick(self.SkinArrowLeft, function()
		Game:playSound("ui_tab_switch_1")
		self:onClickArrow(-1)
	end)
	bee.addClick(self.SkinArrowRight, function()
		Game:playSound("ui_tab_switch_1")
		self:onClickArrow(1)
	end)

	bee.addClick(self.DetailButton, function()
		local cfg =  self._skins[self._selectIndex].cfg
		local skinCfg = tpl_character_skin[cfg.role_skin]
		bee.logEvent("shop-outfit_info", skinCfg.id)
		UiManager:showUI("CharacterMainProfile", {data = CharacterModel:getRoleData(skinCfg.role)})
		Game:playSound("ui_button_confirm")
	end)
	bee.addClick(self.AllinButton, function()
		local cfg =  self._skins[self._selectIndex].cfg
		local skinCfg = tpl_character_skin[cfg.role_skin]
		bee.logEvent("shop-outfit_all_in", skinCfg.id)
		UiManager:showUI(GameModel:getAllinUiName(), {role = CharacterModel:getRoleData(skinCfg.role), skin = skinCfg})
        Game:playSound("ui_button_confirm")
	end)
	bee.addClick(self.ExplosionButton, function()
		self:onClickExplosionButton()
	end)
	bee.addClick(self.IngameButton, function()
		local cfg =  self._skins[self._selectIndex].cfg
		local skinCfg = tpl_character_skin[cfg.role_skin]
		bee.logEvent("shop-outfit_ingame", skinCfg.id)
        UiManager:showUI("BackpackPreview", {role = CharacterModel:getRoleData(skinCfg.role), skin = skinCfg})
        Game:playSound("ui_button_confirm")
	end)

	bee.addClick(self.PurchaseButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickPurchase()
	end)
	bee.addClick(self.PurchaseGreyButton, function()
		UiManager:showToast(_T("LAB_SHOP_ROLE_SKIN_14"))
	end)
end

function P:onStart()
	self:initSkinLit()
end

function P:onDestroy()
	self:refreshRedTag(self._selectIndex)
end

function P:selectItem(id)
	self._jumpId = id
end

local Space = 150
local SpaceRate = (1 - 0.88) / Space
function P:initSkinLit()
	self._skins = ShopModel:getShopSkinList(true)
	self._skinCount = #self._skins
	self._itemsTras, self._positions = {}, {}
	self._curPos, self._maxPos = 0, 0

	for i, v in ipairs(self._skins) do
		local item = self._nodeCache:getItem("SkinItem", self.SkinItem, self.GarmentsList.transform)
		item:SetActive(true)

		table.insert(self._itemsTras, item.transform)
		table.insert(self._positions, bee.v3((i - 1) * Space, 0, 0))

		self:refreshSkinItem(item, v)
		if self._jumpId and self._jumpId == v.cfg.role_skin then
			self._curIndex = i
			self._jumpId = nil
		end
		if v.index == self._curIndex then
			self._curPos = -(self._curIndex - 1) * Space
		end
	end
	self.node:SetActive(#self._skins > 0)

	self._maxPos = -(#self._itemsTras - 1) * Space
	self:refreshItems(self._curPos)
end

function P:refreshSkinItem(item, data)
	local cfg = data.cfg

	local SkinImg = self:find("CharacterMask/SkinImg", item)
	local Mask = self:find("Mask", item)
	local TagEvent = self:find("TagEvent", item)
	local TimeBg = self:find("TimeBg", item)
	local TimeText = self:find("TimeBg/TimeText", item)
	local NewTag = self:find("NewTag", item)

	local skinId = cfg.role_skin
	local skinCfg = tpl_character_skin[skinId]
	bee.setIcon(SkinImg, skinCfg.image_with_bg or skinCfg.image, true)
    if skinCfg.hanger_offset then
        SkinImg.transform.localPosition = bee.v3(skinCfg.hanger_offset[1], skinCfg.hanger_offset[2])
        SkinImg.transform.localScale = bee.v3(skinCfg.hanger_offset[3], skinCfg.hanger_offset[3], skinCfg.hanger_offset[3])
    end

    NewTag:SetActive(ShopModel:isShowNewTag(cfg))

	if cfg.time_end then
		TimeBg:SetActive(true)

		local leftTime = cfg.time_end - bee.getServerTime()
		if leftTime > 0 then
			bee.setText(TimeText, ShopModel:getShopTimeText(leftTime))
			self:schedule(1, function()
				leftTime = leftTime - 1
				if leftTime > 0 then
					bee.setText(TimeText, ShopModel:getShopTimeText(leftTime))
				else
					bee.setText(TimeText, _T("LAB_BACKPACK_DES_21"))
				end
			end)
		else
			bee.setText(TimeText, _T("LAB_BACKPACK_DES_21"))
		end
	else
		TimeBg:SetActive(false)
	end

	bee.addClick(item, function()
		if not self._isDraged then
			Game:playSound("ui_tab_switch_1")
			for i,v in ipairs(self._skins) do
				if v == data and i ~= self._curIndex then
					local to = -(i - 1) * Space
					bee.Tween.toFloat(self._curPos, to, 0.2, function(v)
						self._curPos = v
						self:refreshItems(self._curPos)
						self:refreshSelectSkin()
					end)
					break
				end
			end
		end
	end)
end

function P:refreshItems(offsetX)
	if offsetX then
		for i, v in ipairs(self._positions) do
			v.x = (i - 1) * Space + offsetX
		end
	end
	local midTrans, midIndex, minDis = nil, 1, 999999
	for i, v in ipairs(self._itemsTras) do
		v.transform.localPosition = self._positions[i]
		if math.abs(self._positions[i].x) < minDis then
			midTrans, midIndex, minDis = v, i, math.abs(self._positions[i].x)
		end
	end
	if midTrans then
		for i,v in ipairs(self._itemsTras) do
			local s = 1 - SpaceRate * math.abs(self._positions[i].x)
			v.localScale = bee.v3(s, s, s)
		end
		midTrans:SetAsLastSibling()
		for i = 1, midIndex - 1 do
			self._itemsTras[i]:SetSiblingIndex(i - 1)
		end
		for i = #self._itemsTras, midIndex + 1, -1 do
			self._itemsTras[i]:SetSiblingIndex(#self._itemsTras - 2)
		end
		self._curTrans = midTrans
		self._curIndex = midIndex

		self:refreshSelectSkin()
	end
	for i,v in ipairs(self._itemsTras) do
		self:find("Mask", v.gameObject):SetActive(i ~= self._curIndex)
		self:find("Selected", v.gameObject):SetActive(i == self._curIndex)
	end

	if self._curIndex == 1 then
		self.SkinArrowLeft:SetActive(false)
		self.SkinArrowRight:SetActive(true)
	elseif self._curIndex == self._skinCount then
		self.SkinArrowLeft:SetActive(true)
		self.SkinArrowRight:SetActive(false)
	else
		self.SkinArrowLeft:SetActive(true)
		self.SkinArrowRight:SetActive(true)
	end
end

function P:refreshSelectSkin()
	if self._selectIndex == self._curIndex then
		return
	end
	if self._selectIndex and self._selectIndex ~= self._curIndex then
		self:refreshRedTag(self._selectIndex)
	end
    self._selectIndex = self._curIndex
    self:refreshSelectSkinInfo()
end

function P:refreshSelectSkinInfo()
	local skinInfo = self._skins[self._selectIndex]
	local cfg = skinInfo.cfg
	
	if skinInfo.isOwn then
		self.DiscountTag:SetActive(false)
		self.PurchaseTips:SetActive(false)
		self.PurchaseButton:SetActive(false)
		self.PurchaseGreyButton:SetActive(true)
	else
		self.PurchaseGreyButton:SetActive(false)
		self.PurchaseButton:SetActive(true)
		if cfg.discount and cfg.discount > 0 then
			self.DiscountTag:SetActive(true)
			self.PurchaseTips:SetActive(true)

			bee.setText(self.OriCountText, cfg.original_pri[2])
			bee.setText(self.DiscountText, cfg.discount .. "%")
			bee.setIconInAtlas(self.OriCurrencyIcon, tpl_props[cfg.original_pri[1]].icon)
		else
			self.DiscountTag:SetActive(false)
			self.PurchaseTips:SetActive(false)
		end
	end

	local skinCfg = tpl_character_skin[cfg.role_skin]
	local roleCfg = tpl_character[skinCfg.role]
	if not self._characterCls then
		self._characterCls = ObjectPool:getCls(self.CharacterImage)
		self._characterCls:createRoleCanvas()
	end
	self._characterCls:setRole(CharacterModel:getRoleData(skinCfg.role), true)
	self._characterCls:setSkin(skinCfg, true)
    self._characterCls:initSpecialInteraction(function()
    	self:onClickSpecialInteraction()
	end)
    self:initTipEff()

	bee.setText(self.SkinNameText, _T(skinCfg.name))
	bee.setText(self.NameText, _T(roleCfg.name))
	self.TagSSR:SetActive(skinCfg.rank == 2)
	self.TagSR:SetActive(skinCfg.rank == 1)

	local posInfo = cfg.image_offset_main
	self.CharacterImage.transform.localPosition = bee.v3(posInfo[1], posInfo[2], 1)
	self.CharacterImage.transform.localScale = bee.v3(posInfo[3], posInfo[3], 1)

	bee.setIconInAtlas(self.CurrencyIcon, tpl_props[cfg.pri[1]].icon)
	bee.setText(self.CountText, cfg.pri[2])
end

function P:onPointerDown(e)
	self._isDraged = nil
end

function P:onDrag(e)
	local x = e.delta.x
	self._curPos = self._curPos + x
	if self._curPos > 0 then
		self._curPos = 0
	elseif self._curPos < self._maxPos then
		self._curPos = self._maxPos
	end
	self:refreshItems(self._curPos)
end

function P:onEndDrag(e)
	local x = self._curTrans.localPosition.x
	if x ~= 0 then
		local pos = self._curPos
		self._alignTween = bee.Tween.toFloat(x, 0, 0.2, function(v)
			self._curPos = pos + v - x
			self:refreshItems(self._curPos)
			if 0 == v then
				self._alignTween = nil
				self:refreshSelectSkin()
			end
		end)
	end
	self:once(0.1, function()
		self._isDraged = nil
	end)
end

function P:onClickArrow(dir)
	if self._isDraged then
		return
	end

	local to = -(self._curIndex - 1 + dir) * Space
	bee.Tween.toFloat(self._curPos, to, 0.2, function (v)
		self._curPos = v
		self:refreshItems(self._curPos)
		self:refreshSelectSkin()
	end)
end

function P:onClickPurchase()
	self:refreshRedTag(self._selectIndex)
	UiManager:showUI("ShopPurchase", {info = self._skins[self._selectIndex]})
end

function P:refreshUI()
	-- 刷新当前已拥有状态(不更新排序)
	for k, v in pairs(self._skins) do
		v.isOwn = CharacterModel:isOwnedSkin(v.cfg.role_skin)
	end
	self:refreshSelectSkinInfo()
end

function P:refreshRedTag(index)
	ShopModel:setNewItem(self._skins[index].cfg)
	local trans = self._itemsTras[index]
	if not bee.isNull(trans) then
		self:find("NewTag", trans):SetActive(false)
	end
end

function P:initTipEff()
	if self._firstTipTag then
		scheduler:removeTag(self._firstTipTag)
		self._firstTipTag = nil
	end
	if self._tipsTag then
		scheduler:removeTag(self._tipsTag)
		self._tipsTag = nil
	end
	if self._stopTipTag then
		scheduler:removeTag(self._stopTipTag)
		self._stopTipTag = nil
	end

	local skinCfg = tpl_character_skin[self._skins[self._selectIndex].cfg.role_skin]
	if not skinCfg.special_click_voice then
		self.TipEff:SetActive(false)
		return
	end

	self._skinEffList = {}
	for i = 1, #skinCfg.special_click_voice, 2 do
		table.insert(self._skinEffList, skinCfg.special_click_voice[i])
	end
	
	self._skinTipsMaxIndex = #self._skinEffList
	self._skinTipsIndex = 1

	self._firstTipTag = self:once(0.2, function()
		local posObj1 = self:find(self._skinEffList[self._skinTipsIndex], self._characterCls:getRoleSpine())
		if posObj1 then
			self.TipEff:SetActive(true)
			self.TipEff.transform.position = posObj1.transform.position
		else
			self.TipEff:SetActive(false)
		end

		self._tipsTag = self:schedule(5, function()
			self._skinTipsIndex = self._skinTipsIndex + 1
			if self._skinTipsIndex > self._skinTipsMaxIndex then
				self._skinTipsIndex = 1
			end

			local posObj = self:find(self._skinEffList[self._skinTipsIndex], self._characterCls:getRoleSpine())
			if posObj then
				self.TipEff:SetActive(true)
				self.TipEff.transform.position = posObj.transform.position
			else
				self.TipEff:SetActive(false)
			end
		end)
	end)
end

function P:stopTipEff()
	self.TipEff:SetActive(false)
	if self._tipsTag then
		scheduler:removeTag(self._tipsTag)
		self._tipsTag = nil
	end
end

function P:beginTipEff()
	if not self._skinEffList then
		return
	end
	if self._tipsTag then
		scheduler:removeTag(self._tipsTag)
		self._tipsTag = nil
	end
	if self._stopTipTag then
		scheduler:removeTag(self._stopTipTag)
		self._stopTipTag = nil
	end

	local posObj1 = self:find(self._skinEffList[self._skinTipsIndex], self._characterCls:getRoleSpine())
	if posObj1 then
		self.TipEff:SetActive(true)
		self.TipEff.transform.position = posObj1.transform.position
	else
		self.TipEff:SetActive(false)
	end

	self._tipsTag = self:schedule(5, function()
		self._skinTipsIndex = self._skinTipsIndex + 1
		if self._skinTipsIndex > self._skinTipsMaxIndex then
			self._skinTipsIndex = 1
		end

		local posObj = self:find(self._skinEffList[self._skinTipsIndex], self._characterCls:getRoleSpine())
		if posObj then
			self.TipEff:SetActive(true)
			self.TipEff.transform.position = posObj.transform.position
		else
			self.TipEff:SetActive(false)
		end
	end)
end

function P:onClickExplosionButton()
	if not bee.checkCd("shop_skin_show_explosion", 3) then
		UiManager:showToast(_T("ERR_MSG_FREQUENT"))
		return
	end

	local cfg =  self._skins[self._selectIndex].cfg
	local skinCfg = tpl_character_skin[cfg.role_skin]
	bee.logEvent("shop-outfit_bust", skinCfg.id)
	self._characterCls:switchIdle()
	self._characterCls:playScrap()
	Game:playSound("ui_button_confirm")

	self:stopTipEff()
	self._stopTipTag = self:once(7, function()
		self:beginTipEff()
	end)
end

function P:onClickSpecialInteraction()
	self:stopTipEff()
	if self._stopTipTag then
		scheduler:removeTag(self._stopTipTag)
		self._stopTipTag = nil
	end
	self._stopTipTag = self:once(10, function()
		self:beginTipEff()
	end)
end

