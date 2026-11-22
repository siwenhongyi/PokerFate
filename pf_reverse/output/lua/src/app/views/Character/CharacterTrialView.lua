local P = class("CharacterTrialView", UiDialog)

function P:onAwake()
	local Panel = self:find("AnimRoot/Center/Panel")
	self.RoleItem = self:find("RoleItem", Panel)
	self.CharacterRow = self:find("CharacterRow", Panel)
	self.CharacterScrollView = self:find("CharacterScrollView", Panel)
	self.CloseButton = self:find("CloseButton", Panel)
	self.ConfirmButton = self:find("ConfirmButton", Panel)
	self.RoleItem:SetActive(false)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.ConfirmButton, function()
		self:hideUI()
	end)
end

function P:onStart()
	self._trialList = {}
	if self._params and self._params.role_id then
		table.insert(self._trialList, {id = self._params.role_id})
	end
	self:setCharacterList()
end

function P:evt_characterTimeEnd(msg)
	if msg and msg.role_id then
		table.insert(self._trialList, {id = msg.role_id})
		self:setCharacterList()
	end
end

function P:setCharacterList()
	-- 筛选重复项
	local list = {}
	for k,v in pairs(self._trialList) do
		local isIn = false
		for k1, v1 in pairs(list) do
			if v1.id == v.id then
				isIn = true
				break
			end
		end
		if not isIn then
			table.insert(list, v)
		end
	end
	self._trialList = list

	local roleCount = #self._trialList
	if roleCount <= 4 then
		self.CharacterRow:SetActive(true)
		self.CharacterScrollView:SetActive(false)
		self:setCharacterRow()
	else
		self.CharacterRow:SetActive(false)
		self.CharacterScrollView:SetActive(true)
		self:setCharacterScrollView()
	end
end

function P:setCharacterRow()
	if self._characterRowItems then
		for k,v in pairs(self._characterRowItems) do
			CU.GameObject.Destroy(v)
		end
	end
	self._characterRowItems = {}

	for i,v in ipairs(self._trialList) do
		local copyItem = CU.GameObject.Instantiate(self.RoleItem)
		copyItem.transform:SetParent(self.CharacterRow.transform)
		copyItem.transform.localPosition = bee.v3(0, 0, 0)
		copyItem.transform.localScale = bee.v3(1, 1, 1)
		copyItem:SetActive(true)

		self:setRoleItem(copyItem, v)
		table.insert(self._characterRowItems, copyItem)
	end
end

function P:setCharacterScrollView()
	if not self.characterList then
		self.characterList = UiListEx:create(self.CharacterScrollView)
		self.characterList:setCreateFunc(function()
			return CU.GameObject.Instantiate(self.RoleItem)
		end)
		self.characterList:setRefreshFunc(function(data, item)
			self:setRoleItem(item, data)
		end)
		self.characterList:setWidth(190)
	end

	self.characterList:setDatas(self._trialList)
end

function P:setRoleItem(item, data)
	local role_id = data.id
	local AvatarIcon = self:find("AvatarIcon", item)
	local roleCfg = tpl_character[role_id]
	local avatarCfg = tpl_props[roleCfg.avatar]
	bee.setIconInAtlas(AvatarIcon, avatarCfg.icon)
end

return P