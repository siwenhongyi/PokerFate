local P = class("ShopPurchaseGiftsSkin", UiDialog)

function P:onAwake()
	local Panel = self:find("AnimRoot/Center/Panel")
	self.CloseButton = self:find("CloseButton", Panel)
	self.SkinIcon = self:find("Mask/SkinIcon", Panel)
	self.PackageList = self:find("PackageList", Panel)
	self.Item1 = self:find("PackageList/Item1", Panel)
	self.Item1:SetActive(false)
	self.LeftTimeText = self:find("LeftTime/LeftTimeText", Panel)
	self.PurchaseButton = self:find("PurchaseButton", Panel)
	self.OriPri = self:find("PriCont/OriPri", self.PurchaseButton)
	self.CurPri = self:find("PriCont/CurPri", self.PurchaseButton)
	self.Discount = self:find("Discount", self.PurchaseButton)
	self.DiscountText = self:find("DiscountText", self.Discount)
	self.TabSSR = self:find("TabSSR", Panel)
	self.TabSR = self:find("TabSR", Panel)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.PurchaseButton, function()
		self:onClickPurchase()
	end)
end

function P:onStart()
	local cfg = self._params.cfg

	-- 皮肤展示
	local skinCfg = tpl_character_skin[cfg.role_skin]
	bee.setIcon(self.SkinIcon, skinCfg.image_with_bg or skinCfg.image, true)
	if cfg.image_offset_window then
		local posInfo = cfg.image_offset_window
		self.SkinIcon.transform.localPosition = bee.v3(posInfo[1], posInfo[2], 0)
		self.SkinIcon.transform.localScale = bee.v3(posInfo[3], posInfo[3], 1)
	end
	self.TabSSR:SetActive(skinCfg.rank == 2)
	self.TabSR:SetActive(skinCfg.rank == 1)

	-- 道具列表
	self.packageList = UiListEx:create(self.PackageList)
	self.packageList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.Item1)
	end)
	self.packageList:setRefreshFunc(function(data, item)
		self:setItemProp(item, data)
	end)
	self.packageList:setWidth(100)

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
	table.insert(rewards, 1, {major_type = GMajorType.ROLE_SKIN, id = cfg.role_skin, num = 1})
	self.packageList:setDatas(rewards)

	-- 购买信息
	-- 已拥有该服饰
	if CharacterModel:isOwnedSkin(cfg.role_skin) then
		self.OriPri:SetActive(false)
		self.Discount:SetActive(false)

		bee.setIconInAtlas(self:find("Icon", self.CurPri), tpl_props[cfg.pri2[1]].icon)
		bee.setText(self:find("PriText", self.CurPri), cfg.pri2[2] .. _T("LAB_SHOP_COMMON_4"))
	else
		if cfg.original_pri then
			self.OriPri:SetActive(true)

			bee.setIconInAtlas(self:find("Icon", self.OriPri), tpl_props[cfg.original_pri[1]].icon)
			bee.setText(self:find("PriText", self.OriPri), cfg.original_pri[2])

			bee.setIconInAtlas(self:find("Icon", self.CurPri), tpl_props[cfg.pri[1]].icon)
			bee.setText(self:find("PriText", self.CurPri), cfg.pri[2])

			if cfg.discount and cfg.discount > 0 then
				self.Discount:SetActive(true)
				bee.setText(self.DiscountText, cfg.discount .. "%")
			else
				self.Discount:SetActive(false)
			end
		else
			self.OriPri:SetActive(false)
			self.Discount:SetActive(false)

			bee.setIconInAtlas(self:find("Icon", self.CurPri), tpl_props[cfg.pri[1]].icon)
			bee.setText(self:find("PriText", self.CurPri), cfg.pri[2])
		end
	end

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
end

function P:setItemProp(item, data)
	local Avatar = self:find("Avatar", item)
	local PropItemObj = self:find("PropItem", item)
	local NameText = self:find("NameText", item)
	local OwnTag = self:find("OwnTag", item)
	local UnOwnTag = self:find("UnOwnTag", item)

	local isOwn
	if data.major_type == GMajorType.ROLE_SKIN then
		Avatar:SetActive(true)
		PropItemObj:SetActive(false)
		local skinCfg = tpl_character_skin[data.id]
		local avatarCfg = tpl_props[skinCfg.avatar]
        bee.setIconInAtlas(self:find("avatar_frame_01_mask/AvatarIcon", Avatar), avatarCfg.icon)
        bee.setText(NameText, _T(skinCfg.name))
        isOwn = CharacterModel:isOwnedSkin(skinCfg.id)
	else
		Avatar:SetActive(false)
		PropItemObj:SetActive(true)
		PropItem:create(PropItemObj, data):bindTips()
		bee.setText(NameText, _T(tpl_props[data.id].name))
		isOwn = ItemModel:isOwned(data.id)
	end
	OwnTag:SetActive(isOwn)
	UnOwnTag:SetActive(not isOwn)
end

function P:onClickPurchase()
	local cfg = self._params.cfg
	-- 购买
	local purchaseSkin = function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("shop-goods-tap", cfg.shop_type, cfg.id)
		local pri
		if CharacterModel:isOwnedSkin(cfg.role_skin) then
			pri = cfg.pri2 
		else
			pri = cfg.pri
		end
		local ownCount = ItemModel:getItemNumById(pri[1])
		if ownCount >= pri[2] then
			ShopModel:buyWithProp(cfg.shop_type, cfg.id)
			self:hideUI()
		else
			UiManager:showTip({
			multi = true,
	        text = _F("LAB_SHOP_ROLE_SKIN_10", _T(tpl_props[cfg.pri[1]].name)),
	        onSure = function()
	            -- 跳转
	            local propCfg = tpl_props[pri[1]]
	            ItemModel:jumpView(propCfg.accesses[1])
	            self:hideUI()
	        end
	    })
		end
	end

	-- 判断角色是否已拥有
	local skinCfg = tpl_character_skin[cfg.role_skin]
	if CharacterModel:isOwnedSkin(skinCfg.id) then
		purchaseSkin()
	elseif not CharacterModel:getRoleIsOwn(skinCfg.role) then
		-- 二次确认弹窗
		UiManager:showTip({
	        text = _F("LAB_SHOP_ROLE_SKIN_6", _T(skinCfg.name)),
	        multi = true,
	        onSure = function()
	            purchaseSkin()
	        end
	    })
	else
		purchaseSkin()
	end
end

return P