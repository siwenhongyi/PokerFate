local P = class("SpiritCatStyleBuy", UiDialog)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)
	self.RightTop = self:find("RightTop", AnimRoot)
	self.LeftTop = self:find("LeftTop", AnimRoot)

	self.CharacterImage = self:find("Bg/CharacterImageRaw", Center)
	self.PreviewButton = self:find("Outfit/Nameplate/PreviewButton", Center)
	self.RoleNameText = self:find("Outfit/Nameplate/RoleNameText", Center)
	self.SkinNameText = self:find("Outfit/Nameplate/SkinNameText", Center)

	self.RewardItem = self:find("RewardItem", Center)
	self.RewardItem:SetActive(false)

	self.Pay1 = self:find("Pay1", Center)
	self.Rewards1 = self:find("Rewards1", self.Pay1)
	self.ObtainList1 = self:find("Rewards2/ObtainList1", self.Pay1)
	self.BuyButton1 = self:find("BuyButton1", self.Pay1)
	self.BoughtButton1 = self:find("BoughtButton1", self.Pay1)

	self.Pay2 = self:find("Pay2", Center)
	self.Rewards3 = self:find("Rewards3", self.Pay2)
	self.ObtainList2 = self:find("Rewards4/ObtainList2", self.Pay2)
	self.BuyButton2 = self:find("BuyButton2", self.Pay2)
	self.BoughtButton2 = self:find("BoughtButton2", self.Pay2)

	self.TimeText = self:find("Time/TimeText", self.RightTop)
	self.InfoButton = self:find("InfoButton", self.LeftTop)
	self.BackButton = self:find("BackButton", self.LeftTop)

	bee.addClick(self.BackButton, function()
		self:hideUI()
	end)

	bee.addClick(self.PreviewButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("battle-pass-buy-link", BattlePassModel:getCurPassId())
		UiManager:showUI("CharacterMainGarments", {data = CharacterModel:getRoleData(self._skinCfg.role), selectId = self._skinCfg.id})
	end)

	bee.addClick(self.BuyButton1, function()
		Game:playSound("ui_button_confirm")
		self:onClickBuyButton1()
	end)
	bee.addClick(self.BuyButton2, function()
		Game:playSound("ui_button_confirm")
		self:onClickBuyButton2()
	end)

    bee.addClick(self.InfoButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SpiritCatStyleRule", {text = _T("TAB_BATTLE_PASS_5")})
    end)
end

function P:onStart()
	self:setOutfitCont()
	self:setPay1Cont()
	self:setPay2Cont()
end

function P:setOutfitCont()
	local cfg = tpl_battle_pass_info[BattlePassModel:getCurPassId()]
	if not cfg then
		return
	end
	local skinCfg = tpl_character_skin[cfg.skin]
	self._skinCfg = skinCfg
	if not skinCfg then
		return
	end
	if not self._characterCls then
		self._characterCls = ObjectPool:getCls(self.CharacterImage)
		self._characterCls:setShowReal(true)
		self._characterCls:createRoleCanvas()
	end
	self._characterCls:setShowReal(true)
	self._characterCls:setRole(CharacterModel:getRoleData(skinCfg.role), true)
	self._characterCls:setSkin(skinCfg, true)
	self._characterCls:setRoleOffset(bee.v3zero, bee.v3(0.8, 0.8, 1))

	bee.setText(self.SkinNameText, _T(skinCfg.name))
	bee.setText(self.RoleNameText, _T(tpl_character[skinCfg.role].name))

	-- 结束时间
	local dt = cfg.time_end - bee.getServerTime()
	bee.setText(self.TimeText, TimeHelp:getTimeLeftStr(dt))
	self:schedule(1, function()
		dt = cfg.time_end - bee.getServerTime()
		if dt > 0 then
			bee.setText(self.TimeText, TimeHelp:getTimeLeftStr(dt))
		else
			bee.setText(self.TimeText, _T("LAB_BACKPACK_DES_21"))
		end
	end)
end

function P:setPay1Cont()
	local cfg = BattlePassModel:getPassShopCfg(1)
	local isBought = BattlePassModel:isBoughtPass(1)

	-- 立即获得奖励
	local r1 = ShopModel:getRewardsList(cfg.rewards)
	for i = 1, #r1 do
		local item = self:find("RewardItem" .. i, self.Rewards1)
		if item then
			PropItem:create(self:find("PropItem", item), r1[i]):bindTips()
			self:find("Claimed", item):SetActive(isBought)
		end
	end

	if not self.obtainList1 then
		self.obtainList1 = UiListEx:create(self.ObtainList1)
		self.obtainList1:setCreateFunc(function()
			return CU.GameObject.Instantiate(self.RewardItem)
		end)
		self.obtainList1:setRefreshFunc(function(data, item)
			self:setRewardItem(item, data)
		end)
		self.obtainList1:setRowCount(3)
		self.obtainList1:setRowPostions({-130, 0, 130})
		self.obtainList1:setWidth(115)
	end

	-- 升级可获得奖励
	local r2 = BattlePassModel:getTotalPaidRewards()
	self.obtainList1:setDatas(r2)

	self.BuyButton1:SetActive(not isBought)
	self.BoughtButton1:SetActive(isBought)

	local pidCfg = ShopModel:getPidData(cfg.buy_id)
	bee.setText(self:find("PriText", self.BuyButton1), ShopModel:getPriText(pidCfg))
end

function P:setRewardItem(item, data)
	PropItem:create(self:find("PropItem", item), data):bindTips()
end

function P:setPay2Cont()
	local cfg = BattlePassModel:getPassShopCfg(2)
	local isBought1 = BattlePassModel:isBoughtPass(1)
	local isBought2 = BattlePassModel:isBoughtPass(2)
	local isBought3 = BattlePassModel:isBoughtPass(3)

	-- 立即获得奖励
	local r1 = ShopModel:getRewardsList(cfg.rewards)
	local r1Count = #r1
	for i = 1, r1Count do
		local item = self:find("RewardItem" .. i, self.Rewards3)
		if item then
			PropItem:create(self:find("PropItem", item), r1[i]):bindTips()
			self:find("Claimed", item):SetActive(isBought1)
		end
	end

	-- 典藏奖励
	local r2 = ShopModel:getRewardsList(cfg.rewards2)
	for i = 1, #r2 do
		local item = self:find("RewardItem" .. i + r1Count, self.Rewards3)
		if item then
			PropItem:create(self:find("PropItem", item), r2[i]):bindTips()
		end
	end

	if not self.obtainList2 then
		self.obtainList2 = UiListEx:create(self.ObtainList2)
		self.obtainList2:setCreateFunc(function()
			return CU.GameObject.Instantiate(self.RewardItem)
		end)
		self.obtainList2:setRefreshFunc(function(data, item)
			self:setRewardItem(item, data)
		end)
		self.obtainList2:setRowCount(3)
		self.obtainList2:setRowPostions({-130, 0, 130})
		self.obtainList2:setWidth(115)
	end

	-- 升级可获得奖励
	local r3 = BattlePassModel:getTotalPaidRewards()
	self.obtainList2:setDatas(r3)

	if not isBought1 then
		self.BuyButton2:SetActive(true)
		self.BoughtButton2:SetActive(false)
		local pidCfg = ShopModel:getPidData(cfg.buy_id)
		bee.setText(self:find("PriText", self.BuyButton2), ShopModel:getPriText(pidCfg))
	elseif isBought2 then
		self.BuyButton2:SetActive(false)
		self.BoughtButton2:SetActive(true)	
	elseif isBought1 and not isBought3 then
		self.BuyButton2:SetActive(true)
		self.BoughtButton2:SetActive(false)
		local shopCfg = BattlePassModel:getPassShopCfg(3)
		local pidCfg = ShopModel:getPidData(shopCfg.buy_id)
		bee.setText(self:find("PriText", self.BuyButton2), ShopModel:getPriText(pidCfg))
	else
		self.BuyButton2:SetActive(false)
		self.BoughtButton2:SetActive(true)
	end
end

function P:onClickBuyButton1()
	
	local shopCfg = BattlePassModel:getPassShopCfg(3)
	local pidCfg = ShopModel:getPidData(shopCfg.buy_id)
	
	local params = {}
	params.text = _F("TAB_BATTLE_PASS_28", ShopModel:getPriText(pidCfg))
	params.onSure = function()
		bee.logEvent("battle-pass-tips-buy", BattlePassModel:getCurPassId())
		local cfg = BattlePassModel:getPassShopCfg(1)
		ShopModel:pay(cfg)
	end
	bee.logEvent("battle-pass-buy", BattlePassModel:getCurPassId(), 1)
	UiManager:showUI("SpiritCatStyleTip", params)
end

function P:onClickBuyButton2()
	local isBought1 = BattlePassModel:isBoughtPass(1)
	local shopCfg
	if isBought1 then
		bee.logEvent("battle-pass-buy", BattlePassModel:getCurPassId(), 3)
		shopCfg = BattlePassModel:getPassShopCfg(3)
	else
		bee.logEvent("battle-pass-buy", BattlePassModel:getCurPassId(), 2)
		shopCfg = BattlePassModel:getPassShopCfg(2)
	end
	ShopModel:pay(shopCfg)
end

function P:evt_updateShopLimit()
	self:hideUI()
end

function P:hideUI()
    P.super.hideUI(self)
    if self._is_show then
		self:hideTopUI()
	end
end

function P:hideTopUI()
    self.LeftTop:SetActive(false)
    self.RightTop:SetActive(false)
end

return P