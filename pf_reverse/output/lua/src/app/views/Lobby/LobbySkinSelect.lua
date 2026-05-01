local P = class("LobbySkinSelect", UiBase)

function P:onAwake()
	local Center = self:find("AnimRoot/Center")
	local Right = self:find("AnimRoot/Right")
	local LeftTop = self:find("AnimRoot/LeftTop")

	self.CampIcon = self:find("CampIcon", Center)
	self.CharacterImage = self:find("CharacterImage", Center)

	self.NameText = self:find("NameText", Right)
	self.CVNameText = self:find("CVNameText", Right)
	self.GarmentsList = self:find("GarmentsList", Right)
	self.Item1 = self:find("Item1", Right)
	self.ConfirmButton = self:find("ConfirmButton", Right)
	self.Item1:SetActive(false)
	self.ConfirmButton:SetActive(false)

	self.BackButton = self:find("BackButton", LeftTop)

	bee.addClick(self.BackButton, function()
		self:onClickClose()
	end)
	bee.addClick(self.ConfirmButton, function()
		self:onClickConfirm()
	end)
end

function P:onStart()
	self._saveCb = self._params.saveCb
	self._curUsing = self._params.cur_using
	self._selected = self._curUsing

	self:setCharacterShow()
	self:initGarmentsList()
end

function P:initGarmentsList()
	self.garmentList = UiListEx:create(self.GarmentsList)
	self.garmentList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.Item1)
	end)
	self.garmentList:setRefreshFunc(function(data, item)
		self:setSkinItem(item, data)
	end)
	self.garmentList:setWidth(210)

	local skinData = self._role:getOwnedSkins()
	self.garmentList:setDatas(skinData)
end

function P:setSkinItem(item, data)
	local ImageSkin = self:find("Mask/ImageSkin", item)
	local TextName = self:find("TextName", item)
	local UsingTag = self:find("UsingTag", item)
	local Selected = self:find("Selected", item)

    bee.setIcon(ImageSkin, data.image_with_bg or data.image, true)
    if data.hanger_offset then
        ImageSkin.transform.localPosition = bee.v3(data.hanger_offset[1], data.hanger_offset[2])
        ImageSkin.transform.localScale = bee.v3(data.hanger_offset[3], data.hanger_offset[3], data.hanger_offset[3])
    end
    bee.setText(TextName, _T(data.name))
    UsingTag:SetActive(data.id == self._curUsing)
    Selected:SetActive(data.id == self._selected)

    bee.removeAllClick(item)
    bee.addClick(item, function()
    	if data.id == self._selected then
    		return
    	end

    	self._selected = data.id
    	self:setCharacterShow()
    	self:refreshItem()

    	self.ConfirmButton:SetActive(self._curUsing ~= data.id)
	end)
end

function P:refreshItem()
	for k,v in pairs(self.garmentList:getShows()) do
		local Selected = self:find("Selected", self.garmentList:getNode(v))
		Selected:SetActive(self.garmentList:getData(v).id == self._selected)
	end
end

function P:setCharacterShow()
	local skinCfg = tpl_character_skin[self._selected]
	if not self._characterCls then
		self._characterCls = ObjectPool:getCls(self.CharacterImage)
		self._characterCls:setRole(CharacterModel:getRole(skinCfg.role))

		self._role = CharacterModel:getRole(skinCfg.role)
		local roleCfg = tpl_character[skinCfg.role]
		bee.setText(self.NameText, _T(roleCfg.name))
		bee.setText(self.CVNameText, "CV: " .. _T(roleCfg.cv))
		bee.setIcon(self.CampIcon, "Character[character_analysis_bg_camp_" .. self._role.info.campInt .. "]")
	end
    self._characterCls:setSkin(skinCfg)
end

function P:onClickConfirm()
	if self._saveCb then
		self._saveCb(self._selected)
	end
	self:hideUI()
end

function P:onClickClose()
	self:hideUI()
end

return P