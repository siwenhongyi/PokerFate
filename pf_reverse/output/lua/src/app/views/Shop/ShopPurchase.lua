local P = class("ShopPurchase", UiDialog)

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")

	local Center = self:find("Center", self.AnimRoot)

	self.CloseButton = self:find("CloseButton", Center)
	self.SkinIcon = self:find("Mask/SkinIcon", Center)
	self.TabSSR = self:find("TabSSR", Center)
	self.TabSR = self:find("TabSR", Center)
	self.SkinNameText = self:find("SkinNameText", Center)
	self.RoleNameText = self:find("RoleNameText", Center)

	self.PurchaseButton = self:find("PurchaseButton", Center)
	self.CurrencyIcon = self:find("CurrencyIcon", self.PurchaseButton)
	self.PriceText = self:find("PriceText", self.PurchaseButton)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.PurchaseButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickPurchase()
	end)
end

function P:onStart()
	self._skinInfo = self._params.info

	local cfg = self._skinInfo.cfg

	local skinCfg = tpl_character_skin[cfg.role_skin]
	local roleCfg = tpl_character[skinCfg.role]
	bee.setText(self.SkinNameText, _T(skinCfg.name))
	bee.setText(self.RoleNameText, _T(roleCfg.name))

	local currencyCfg = tpl_props[cfg.pri[1]]
	bee.setIconInAtlas(self.CurrencyIcon, currencyCfg.icon)
	bee.setText(self.PriceText, cfg.pri[2])

	bee.setIcon(self.SkinIcon, skinCfg.image_with_bg or skinCfg.image, true)
	if cfg.image_offset_window then
		local posInfo = cfg.image_offset_window
		self.SkinIcon.transform.localPosition = bee.v3(posInfo[1], posInfo[2], 0)
		self.SkinIcon.transform.localScale = bee.v3(posInfo[3], posInfo[3], 1)
	end
	self.TabSSR:SetActive(skinCfg.rank == 2)
	self.TabSR:SetActive(skinCfg.rank == 1)
end

function P:onClickPurchase()
	local cfg = self._skinInfo.cfg
	bee.logEvent("shop-goods-tap", cfg.shop_type, cfg.id)
	-- 购买
	local purchaseSkin = function()
		Game:playSound("ui_button_confirm")
		local pri = cfg.pri[2]
		local ownCount = ItemModel:getItemNumById(cfg.pri[1])
		if ownCount >= pri then
			ShopModel:buyWithProp(cfg.shop_type, cfg.id)
			self:hideUI()
		else
			UiManager:showTip({
			multi = true,
	        text = _F("LAB_SHOP_ROLE_SKIN_10", _T(tpl_props[cfg.pri[1]].name)),
	        onSure = function()
	            -- 跳转
	            local propCfg = tpl_props[cfg.pri[1]]
	            ItemModel:jumpView(propCfg.accesses[1])
	            self:hideUI()
	        end
	    })
		end
	end

	-- 判断角色是否已拥有
	local skinCfg = tpl_character_skin[cfg.role_skin]
	if not CharacterModel:getRoleIsOwn(skinCfg.role) then
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

