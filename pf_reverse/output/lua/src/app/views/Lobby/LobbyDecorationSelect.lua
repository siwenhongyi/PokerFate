local P = class("LobbyDecorationSelect", UiDialog)

function P:onAwake()
	local Panel = self:find("AnimRoot/Center/Panel")

	self.TitleText = self:find("TitleText", Panel)
	self.ItemScene = self:find("ItemScene", Panel)
	self.ItemPlayer = self:find("ItemPlayer", Panel)
	self.ItemListObj = self:find("ItemList", Panel)
	self.ConfirmButton = self:find("ConfirmButton", Panel)
	self.ConfirmButton2 = self:find("ConfirmButton2", Panel)
	self.CloseButton = self:find("CloseButton", Panel)
	self.ItemScene:SetActive(false)
	self.ItemPlayer:SetActive(false)
	self.ConfirmButton:SetActive(false)
	self.ConfirmButton2:SetActive(true)

	bee.addClick(self.CloseButton, function()
		self:onClickClose()
	end)
	bee.addClick(self.ConfirmButton, function()
		self:onClickConfirm()
	end)
end

function P:onStart()
	self._select_type = self._params.major_type
	self._clickCb = self._params.clickCb
	self._closeCb = self._params.closeCb
	self._saveCb = self._params.saveCb
	self._curUsing = self._params.cur_using
	self._selected = self._curUsing

	self:initItemList()

	if self._select_type == GMajorType.ROLE then
		bee.setText(self.TitleText, _T("LAB_CUSTOM_10"))
		self:setRoleList()
	else
		bee.setText(self.TitleText, _T("LAB_CUSTOM_11"))
		self:setSceneList()
	end
end

local ROW_COUNT = 5
function P:initItemList()
	local rowPos = {}
	for i = 1, ROW_COUNT do
		if i == 1 then
			table.insert(rowPos, 90)
		else
			table.insert(rowPos, 200 * i - 90)
		end
	end

	self.itemList = UiListEx:create(self.ItemListObj)
	self.itemList:setCreateFunc(function()
		if self._select_type == GMajorType.ROLE then
			return CU.GameObject.Instantiate(self.ItemPlayer)
		else
			return CU.GameObject.Instantiate(self.ItemScene)
		end
	end)
	self.itemList:setRefreshFunc(function(data, item)
		if self._select_type == GMajorType.ROLE then
			self:setRoleItem(item, data)
		else
			self:setSceneItem(item, data)
		end
	end)
	self.itemList:setRowCount(ROW_COUNT)
	self.itemList:setRowPostions(rowPos)
	self.itemList:setWidth(180)
end

function P:setRoleList()
	local ownedList = CharacterModel:getOwnedCharacters()
	self.itemList:setDatas(ownedList)
end

function P:setSceneList()
	local ownedList = ItemModel:getAllShowItems(14, true)
	self.itemList:setDatas(ownedList)
end

function P:setRoleItem(item, data)
	local info = data.info

	local CharacterAvatar = self:find("CharacterMask/CharacterAvatar", item)
	local Selected = self:find("Selected", item)
	local UsingTag = self:find("UsingTag", item)
	local NewTag = self:find("NewTag", item)

	Selected:SetActive(self._selected == info.id)
	UsingTag:SetActive(self._curUsing == info.id)
	NewTag:SetActive(CharacterModel:isNewRole(info.id))

	local role = CharacterModel:getRole(info.id)
	local skinCfg = role:getSkinData()
	bee.setIconInAtlas(CharacterAvatar, tpl_props[skinCfg.avatar].icon)

	bee.removeAllClick(item)
	bee.addClick(item, function()
		if self._selected == info.id then
			return
		end
		if self._clickCb then
			self._clickCb(info.id)
		end
		self._selected = info.id
		self.ConfirmButton:SetActive(self._selected ~= self._curUsing)
		self.ConfirmButton2:SetActive(not self.ConfirmButton.activeSelf)
		self:refreshRoleItem()
	end)
end

function P:setSceneItem(item, data)
	local ItemIcon = self:find("ItemIcon", item)
	local Selected = self:find("Selected", item)
	local UsingTag = self:find("UsingTag", item)

	local propCfg = tpl_props[data.item_id]
	bee.setIconInAtlas(ItemIcon, propCfg.icon)

	Selected:SetActive(self._selected == data.item_id)
	UsingTag:SetActive(self._curUsing == data.item_id)

	bee.removeAllClick(item)
	bee.addClick(item, function()
		if self._selected == data.item_id then
			return
		end
		if self._clickCb then
			self._clickCb(data.item_id)
		end
		self._selected = data.item_id
		self.ConfirmButton:SetActive(self._selected ~= self._curUsing)
		self.ConfirmButton2:SetActive(not self.ConfirmButton.activeSelf)
		self:refreshSceneItem()
	end)
end

function P:refreshRoleItem()
	for k,v in pairs(self.itemList:getShows()) do
		local Selected = self:find("Selected", self.itemList:getNode(v))
		Selected:SetActive(self.itemList:getData(v).info.id == self._selected)
	end
end

function P:refreshSceneItem()
	for k,v in pairs(self.itemList:getShows()) do
		local Selected = self:find("Selected", self.itemList:getNode(v))
		Selected:SetActive(self.itemList:getData(v).item_id == self._selected)
	end
end

function P:onClickClose()
	if self._closeCb then
		self._closeCb()
	end
	self:hideUI()
end

function P:onClickConfirm()
	if self._saveCb then
		self._saveCb(self._selected)
	end
	self:hideUI()
end

return P