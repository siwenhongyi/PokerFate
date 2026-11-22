local P = class("SpiritCatStyleActivate", UiDialog)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)

	self.CharacterImage = self:find("CharacterImageRaw", Center)
	self.PreviewButton = self:find("Outfit/Nameplate/PreviewButton", Center)
	self.RoleNameText = self:find("Outfit/Nameplate/RoleNameText", Center)
	self.SkinNameText = self:find("Outfit/Nameplate/SkinNameText", Center)

	local Right = self:find("Right", Center)
	self.ObtainListObj = self:find("Main/ObtainList", Right)
	self.RewardItem = self:find("Main/RewardItem", Right)
	self.RewardItem:SetActive(false)
	self.Title = self:find("Title", Right)
	self.TimeText = self:find("Time/TimeText", Right)
	self.ActiveButton = self:find("ActiveButton", Right)

	bee.addClick(self.PreviewButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("battle-pass-open-link", BattlePassModel:getCurPassId())
		UiManager:showUI("CharacterMainGarments", {data = CharacterModel:getRoleData(self._skinCfg.role), selectId = self._skinCfg.id})
	end)

	bee.addClick(self.ActiveButton, function()
		self:hideUI()
		bee.logEvent("battle-pass-open", BattlePassModel:getCurPassId())
		BattlePassModel:activeBattlePass()
	end)
end

function P:onStart()
	self:setOutfitCont()
	self:setRewardList()

	local curLanguage = LanguageManager:getLanguage()
	for i = 1, self.Title.transform.childCount do
		local t = self.Title.transform:GetChild(i - 1)
		t.gameObject:SetActive(t.name == curLanguage)
	end
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
	self._characterCls:setRoleOffset(bee.v3zero, bee.v3(0.59, 0.59, 1))

	bee.setText(self.SkinNameText, _T(skinCfg.name))
	bee.setText(self.RoleNameText, _T(tpl_character[skinCfg.role].name))

	-- 结束时间
	local dt = cfg.time_end - bee.getServerTime()
	bee.setText(self.TimeText, _F("LAB_TIME_DES", "<color=#FDF2B4>" .. TimeHelp:getTimeLeftStr(dt) .. "</color>"))
	self:schedule(1, function()
		dt = cfg.time_end - bee.getServerTime()
		if dt > 0 then
			bee.setText(self.TimeText, _F("LAB_TIME_DES", "<color=#FDF2B4>" .. TimeHelp:getTimeLeftStr(dt) .. "</color>"))
		else
			bee.setText(self.TimeText, "<color=#FDF2B4>" .. _T("LAB_BACKPACK_DES_21") .. "</color>")
		end
	end)
end

function P:setRewardList()
	if not self.obtainList then
		self.obtainList = UiListEx:create(self.ObtainListObj)
		self.obtainList:setCreateFunc(function()
			return CU.GameObject.Instantiate(self.RewardItem)
		end)
		self.obtainList:setRefreshFunc(function(data, item)
			self:setRewardItem(item, data)
		end)
		self.obtainList:setRowCount(5)
		self.obtainList:setRowPostions({-258, -129, 0, 129, 258})
		self.obtainList:setWidth(130)
		self.obtainList:setTopBottom(10, 0)
	end

	local list = {}
	local levelCfg = BattlePassModel:getBattlePassLevelCfg()
	for i, v in ipairs(levelCfg) do
		if v.level ~= -1 then
			for k1, v1 in pairs(ShopModel:getRewardsList(v.rewards_1)) do
				if not list[v1.id] then
					list[v1.id] = clone(v1)
					list[v1.id].typeSort = ItemModel:_getTypeSort(tpl_props[v1.id].type)
				else
					list[v1.id].num = list[v1.id].num + v1.num
				end
			end
			for k1, v1 in pairs(ShopModel:getRewardsList(v.rewards_2)) do
				if not list[v1.id] then
					list[v1.id] = clone(v1)
					list[v1.id].typeSort = ItemModel:_getTypeSort(tpl_props[v1.id].type)
				else
					list[v1.id].num = list[v1.id].num + v1.num
				end
			end
		end
	end

	local shopCfg = BattlePassModel:getPassShopCfg(2)
	for i,v in ipairs(ShopModel:getRewardsList(shopCfg.rewards)) do
		if not list[v.id] then
			list[v.id] = clone(v)
			list[v.id].typeSort = ItemModel:_getTypeSort(tpl_props[v.id].type)
		else
			list[v.id].num = list[v.id].num + v.num
		end
	end
	for i,v in ipairs(ShopModel:getRewardsList(shopCfg.rewards2)) do
		if not list[v.id] then
			list[v.id] = clone(v)
			list[v.id].typeSort = ItemModel:_getTypeSort(tpl_props[v.id].type)
		else
			list[v.id].num = list[v.id].num + v.num
		end
	end

	local showList = {}
	for k, v in pairs(list) do
		table.insert(showList, v)
	end
	table.sort(showList, function(a, b) return a.typeSort < b.typeSort end)
	self.obtainList:setDatas(showList)
end

function P:setRewardItem(item, data)
	PropItem:create(self:find("PropItem", item), data):bindTips()
end


return P