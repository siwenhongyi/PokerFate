local P = class("LobbyCustomization", UiDialog)

function P:onAwake()
	local Panel = self:find("AnimRoot/Center/Panel")

	self.TitleText = self:find("TitleText", Panel)
	self.CloseButton = self:find("CloseButton", Panel)
	self.DecorationItem = self:find("DecorationItem", Panel)
	self.ItemListObj = self:find("ItemList", Panel)
	self.CheckToggle = self:find("CheckToggle", Panel)
	self.InfoButton = self:find("InfoButton", Panel)
	self.DecorationItem:SetActive(false)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)

	bee.addValueChanged(self.CheckToggle, function(isOn)
		Game:playSound("ui_button_disabled")
		if isOn then
			PlayerModel:requestUpdateDCSchemeRandFlag(1)
    		bee.logEvent("lobby-custom-random")
		else
			PlayerModel:requestUpdateDCSchemeRandFlag(0)
		end
	end)

	bee.addClick(self.InfoButton, function()
		UiManager:showUI("CommonTextTipUD", {text = _T("LAB_CUSTOM_8"), target = self.InfoButton})
    	bee.logEvent("lobby-custom-random-tips")
	end)
end

function P:onStart()
	self:initItemList()
	self:setItemList()

	if PlayerModel:isRandomDecorationScheme() then
		bee.setCheck(self.CheckToggle)
	else
		bee.setUncheck(self.CheckToggle)
	end
end

function P:evt_updateScheme()
	self:setItemList()
end

function P:evt_changeScheme()
	self:setItemList()
end

function P:initItemList()
	self.itemList = UiListEx:create(self.ItemListObj)
	self.itemList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.DecorationItem)
	end)
	self.itemList:setRefreshFunc(function(data, item)
		self:setDecorationItem(item, data)
	end)
	self.itemList:setWidth(360)
end

function P:setItemList()
	local list = {}
	for k,v in pairs(PlayerModel:getDecorationSchemeList()) do
		table.insert(list, v)
	end
	local listCount = #list
	if listCount < tpl_constdata.Custom_limit then
		table.insert(list, {})
	end
	self.itemList:setDatas(list)

	local curSchemeInfo = PlayerModel:getCurScheme()
	if curSchemeInfo then
		self.itemList:moveToYItem(curSchemeInfo.index)
	end

	bee.setText(self.TitleText, _F("LAB_CUSTOM_3", listCount, tpl_constdata.Custom_limit))
end

function P:setDecorationItem(item, data)
	if data and next(data) then
		self:setNormalItem(item, data)
	else
		self:setEmptyItem(item, data)
	end
end

function P:setEmptyItem(item, data)
	local Empty = self:find("Empty", item)
	local Normal = self:find("Normal", item)

	Empty:SetActive(true)
	Normal:SetActive(false)

	local AddButton = self:find("AddButton", Empty)
	bee.removeAllClick(Empty)
	bee.addClick(Empty, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("LobbyAdjustment")
    	bee.logEvent("lobby-custom-add")
	end)
	bee.removeAllClick(AddButton)
	bee.addClick(AddButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("LobbyAdjustment")
    	bee.logEvent("lobby-custom-add")
	end)
end

function P:setNormalItem(item, data)
	local Empty = self:find("Empty", item)
	local Normal = self:find("Normal", item)

	Empty:SetActive(false)
	Normal:SetActive(true)

	local IndexText = self:find("IndexBg/IndexText", Normal)
	local DeleteButton = self:find("DeleteButton", Normal)
	local CharacterButton = self:find("CharacterButton", Normal)
	local CharacterAvatar = self:find("CharacterMask/CharacterAvatar", CharacterButton)
	local SceneButton = self:find("SceneButton", Normal)
	local MusicButton = self:find("MusicButton", Normal)
	local MusicIcon = self:find("MusicIcon", MusicButton)
	local CycleIcon = self:find("CycleIcon", MusicButton)
	local RandomIcon = self:find("RandomIcon", MusicButton)
	local MusicCountText = self:find("MusicCountText", MusicButton)
	local UseButton = self:find("UseButton", Normal)
	local Using = self:find("Using", Normal)
	local Selected = self:find("Selected", Normal)

	local curId = PlayerModel:getCurSchemeId()

	bee.setText(IndexText, data.index)
	DeleteButton:SetActive(data.scheme_id ~= curId)

	local skinCfg = tpl_character_skin[data.skin_id]
	bee.setIconInAtlas(CharacterAvatar, tpl_props[skinCfg.avatar].icon)

	bee.setIconInAtlas(SceneButton, tpl_props[data.lobby_scene_id].icon)

	local musicList = data.lobby_bgm_list
	local musicId = tpl_props[musicList[1]].mapId
	local musicCfg = tpl_sound[tostring(musicId)]
	bee.setIconInAtlas(MusicIcon, musicCfg.cd_image)
	bee.setText(MusicCountText, #musicList)
	if data.property_list and next(data.property_list) then
		if not data.property_list[4] then
			data.property_list[4] = MusicTag.Order
		end
		CycleIcon:SetActive(data.property_list[4] == MusicTag.Order)
		RandomIcon:SetActive(data.property_list[4] == MusicTag.Random)
	else
		CycleIcon:SetActive(true)
		RandomIcon:SetActive(false)
	end

	Selected:SetActive(curId == data.scheme_id)
	Using:SetActive(curId == data.scheme_id)
	UseButton:SetActive(curId ~= data.scheme_id)

	bee.removeAllClick(Normal)
	bee.addClick(Normal, function()
		UiManager:showUI("LobbyAdjustment", {scheme_id = data.scheme_id})
	end)

	bee.removeAllClick(DeleteButton)
	bee.addClick(DeleteButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showTip({
        text = _T("LAB_CUSTOM_5"),
        onSure = function()
            	PlayerModel:requestDeleteDCSchemeREQ(data.scheme_id)
	        end
	    })
	end)

	bee.removeAllClick(UseButton)
	bee.addClick(UseButton, function()
		Game:playSound("ui_button_confirm")
		PlayerModel:requestChangeScheme(data.scheme_id)
    	bee.logEvent("lobby-custom-change")
	end)
end

