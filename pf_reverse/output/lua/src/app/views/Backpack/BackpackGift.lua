local P = class("BackpackGift", UiDialog)

function P:onAwake()
	local Panel = self:find("AnimRoot/Center/Panel")

	self.CloseButton = self:find("CloseButton", Panel)
	
	self.ItemList = self:find("ItemList", Panel)
	self.Item1 = self:find("ItemList/Item1", Panel)
	self.TitleText = self:find("TitleText", Panel)
	self.Item1:SetActive(false)

	self.CharacterCont = self:find("BottomCont/CharacterCont", Panel)
	self.AvatarSelect = self:find("AvatarSelect", self.CharacterCont)
	self.ImageIcon = self:find("AvatarSelect/Mask/ImageIcon", self.CharacterCont)
	self.AddIcon = self:find("AvatarSelect/AddIcon", self.CharacterCont)
	self.ExchangeCont = self:find("BottomCont/ExchangeCont", Panel)
	self.CountTips = self:find("CountTips", self.ExchangeCont)
	self.ConfirmButton = self:find("ConfirmButton", self.ExchangeCont)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.ConfirmButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickUse()
	end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end)
    bee.addClick(self.AvatarSelect, function()
		local params = {}
		params.major_type = GMajorType.ROLE
		params.cur_using = self._selectedCharacter
		params.saveCb = function(roleId)
			self._selectedCharacter = roleId
			self:setCharacterShow()
			self.selectItemList:refreshShowingUi()
		end
		params.closeCb = function()
		end
    	UiManager:showUI("LobbyDecorationSelect", params)
	end)
end

local ROW_COUNT = 4
function P:onStart()
	self._id = self._params.id
	self._selectedList = {}
	self._selectedCharacter = self._params.characterId
	self._isInit = true

	local cfg = tpl_props[self._id]

	self.CharacterCont:SetActive(cfg.type == GPropKind.OptionalBox)

	if cfg.batchUse == 1 then
		self._maxCount = ItemModel:getItemNumById(self._id)
	else
		self._maxCount = 1
	end

	if self._params.isAutoSelect then
	end

	bee.setText(self.TitleText, _T(cfg.name))
	
	local rowPos = {}
	for i = 1, ROW_COUNT do
		if i == 1 then
			table.insert(rowPos, 180)
		else
			table.insert(rowPos, 360 * i + 15 * (i - 1) - 180)
		end
	end
	self.selectItemList = UiListEx:create(self.ItemList)
	self.selectItemList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.Item1)
	end)
	self.selectItemList:setRefreshFunc(function(data, item, isInit, index)
		self:setItem(item, data, isInit, index)
	end)
	self.selectItemList:setRowCount(ROW_COUNT)
	self.selectItemList:setRowPostions(rowPos)
	self.selectItemList:setWidth(285)

	self:setCharacterShow()
	self:setCountTextShow()
	self._isInit = false
end

function P:setItem(item, data, isInit, index)
	local PlusButton = self:find("PlusButton", item)
	local MinusButton = self:find("MinusButton", item)
	local InputFieldCount = self:find("InputFieldCount", item)
	local PropItemObj = self:find("PropItem", item)
	local RoleItemObj = self:find("RoleItem", item)
	local Favorite = self:find("Favorite", item)

	InputFieldCount:GetComponent("InputField").contentType = CU.UI.InputField.ContentType.IntegerNumber

	if data.major_type == GMajorType.PROP then
		PropItemObj:SetActive(true)
		RoleItemObj:SetActive(false)
		local p = PropItem:create(PropItemObj, data)
		p:hideNum()
		p:bindTips()
	else
		PropItemObj:SetActive(false)
		RoleItemObj:SetActive(true)
		RoleItem:create(RoleItemObj, data):bindDetail()
	end

	if not self._selectedList[data.id] then
		self._selectedList[data.id] = {major_type = data.major_type, num = 0}
	end

	Favorite:SetActive(data.isFavorite)
	if data.isFavorite and self._isInit then
		self:autoSetCharacterGift(data)
	end

	bee.setText(InputFieldCount, self._selectedList[data.id].num, "InputField")

	bee.removeAllClick(PlusButton)
	bee.addClick(PlusButton, function()
		local selectedCount = self:_getSelectedCount()
		if selectedCount + 1 > self._maxCount then
			UiManager:showToast(_T("LAB_SHOP_COMMON_19"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedList[data.id].num = self._selectedList[data.id].num + 1
		bee.setText(InputFieldCount, self._selectedList[data.id].num, "InputField")
		self:setCountTextShow()
	end)
	bee.removeAllClick(MinusButton)
	bee.addClick(MinusButton, function()
		if self._selectedList[data.id].num - 1 < 0 then
			UiManager:showToast(_T("LAB_SHOP_COMMON_20"))
			return
		end
		Game:playSound("ui_button_confirm")
		self._selectedList[data.id].num = self._selectedList[data.id].num - 1
		bee.setText(InputFieldCount, self._selectedList[data.id].num, "InputField")
		self:setCountTextShow()
	end)

	InputFieldCount:GetComponent("InputField").onEndEdit:RemoveAllListeners()
	InputFieldCount:GetComponent("InputField").onEndEdit:AddListener(function()
		local inputCount = tonumber(bee.getText(InputFieldCount, "InputField"))
		if not inputCount then
			inputCount = 0
		end
		if inputCount < 0 then
			inputCount = 0
		end
		local selectedCount = self:_getSelectedCount()
		if (selectedCount - self._selectedList[data.id].num + inputCount) > self._maxCount then
			self._selectedList[data.id].num = self._selectedList[data.id].num + self._maxCount - selectedCount
		else
			self._selectedList[data.id].num = inputCount
		end

		bee.setText(InputFieldCount, self._selectedList[data.id].num, "InputField")
		self:setCountTextShow()
	end)
end

function P:_getSelectedCount()
	local count = 0
	for k,v in pairs(self._selectedList) do
		count = count + v.num
	end
	return count
end

function P:setCountTextShow()
	bee.setText(self.CountTips, _F("LAB_BACKPACK_DES_27", self:_getSelectedCount(), self._maxCount))
end

function P:onClickUse()
	local useCount = self:_getSelectedCount()
	if useCount <= 0 then
		UiManager:showToast(_T("LAB_BACKPACK_DES_30"))
		return
	end
	Game:playSound("ui_button_confirm")
	local item = ItemModel:getItem(self._id)
	local rewards = {}
	for k, v in pairs(self._selectedList) do
		if v.num > 0 then
			table.insert(rewards, {major_type = v.major_type, item_id = k, item_num = v.num})
		end
	end
	ItemModel:reqUseTreasureBox(item.item_uniq_id, useCount, rewards)
	self:hideUI()
end

function P:setCharacterShow()
	if self._selectedCharacter then
		self.ImageIcon:SetActive(true)
		self.AddIcon:SetActive(false)
		local roleCfg = tpl_character[self._selectedCharacter]
		local propCfg = tpl_props[roleCfg.avatar]
		bee.setIconInAtlas(self.ImageIcon, propCfg.icon)
	else
		self.ImageIcon:SetActive(false)
		self.AddIcon:SetActive(true)
	end

	local cfg = tpl_props[self._id]
	local datas = ShopModel:getRewardsListWithType(cfg.values)
	if self._selectedCharacter then
		local loves = tpl_character[self._selectedCharacter].loves
		for i = 1, #loves, 2 do
			for k, v in pairs(datas) do
				if loves[i] == v.item_id then
					v.isFavorite = true
				end
			end
		end
	end
	table.sort(datas, function(a, b)
		local sumA = 100
		local sumB = 100

		if a.isFavorite then
			sumA = sumA + 10
		end
		if b.isFavorite then
			sumB = sumB + 10
		end

		if a.item_id < b.item_id then
			sumA = sumA + 1
		else
			sumB = sumB + 1
		end

		return sumA > sumB
	end)

	self.selectItemList:setDatas(datas)
end

-- 自动选择觉醒所需数量
function P:autoSetCharacterGift(data)
	local role = CharacterModel:getRole(self._selectedCharacter)
	local curLv = role:getBondLevel()
	local curExp = role:getBondExp()
	local needExp = 0
	for i = curLv, (Config.AWAKEN_LEVEL - 1) do
		if i == curLv then
			if tpl_character_level[i]["point_" .. role.role_id] then
				needExp = needExp + tpl_character_level[i]["point_" .. role.role_id] - curExp
			else
				needExp = needExp + tpl_character_level[i].point - curExp
			end
		else
			if tpl_character_level[i]["point_" .. role.role_id] then
				needExp = needExp + tpl_character_level[i]["point_" .. role.role_id]
			else
				needExp = needExp + tpl_character_level[i].point
			end
		end
	end

	local roleCfg = tpl_character[self._selectedCharacter]
	local propCfg = tpl_props[data.item_id]
	local addExp = propCfg.values[1]
	for i = 1, #roleCfg.loves, 2 do
		if roleCfg.loves[i] == data.item_id then
			addExp = addExp + roleCfg.loves[i + 1]
			break
		end
	end
	for i = 1, #roleCfg.special, 2 do
		if roleCfg.special[i] == data.item_id then
			addExp = addExp + roleCfg.special[i + 1]
			break
		end
	end

	local needCount = math.floor(needExp / addExp)
	local curCount = ItemModel:getItemNumById(data.item_id)
	needCount = math.max((needCount - curCount), 0)
	self._selectedList[data.id].num = math.min(needCount, self._maxCount)
end

return P