local P = class("LobbyAdjustment", UiFullView)

local MinSize = 0.5
local MaxSize = 2

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)
	local Right = self:find("Right", AnimRoot)
	local Left = self:find("Left", AnimRoot)
	local LeftTop = self:find("LeftTop", AnimRoot)

	local LeftButton = self:find("LeftButton", Left)
	self.CharacterButton = self:find("CharacterButton", LeftButton)
	self.GarmentButton = self:find("GarmentButton", LeftButton)

	self.SceneImg = self:find("SceneImg", AnimRoot)
	self.ImageFg = self:find("ImageFg", AnimRoot)
	self.CharacterImage = self:find("CharacterImage", Center)

	self.MainCtrl = self:find("MainCtrl", Right)
	self.UsingTag = self:find("UsingTag", self.MainCtrl)

	self.AvatarCont = self:find("AvatarCont", self.MainCtrl)
	self.AvatarIcon = self:find("AvatarFrame/avatar_frame_01_mask/icon", self.AvatarCont)
	self.TitleCont = self:find("TitleCont", self.MainCtrl)
	self.TitleDefIcon = self:find("defIcon", self.TitleCont)
	self.TitleIcon = self:find("icon", self.TitleCont)
	self.FrameCont = self:find("FrameCont", self.MainCtrl)
	self.FrameDefIcon = self:find("avatar_frame_01", self.FrameCont)
	self.FrameIcon = self:find("icon", self.FrameCont)
	self.SceneCont = self:find("SceneCont", self.MainCtrl)
	self.SceneIcon = self:find("icon", self.SceneCont)
	self.CardFaceCont = self:find("CardFaceCont", self.MainCtrl)
	self.CardFaceIcon = self:find("icon", self.CardFaceCont)
	self.CardBackCont = self:find("CardBackCont", self.MainCtrl)
	self.CardBackIcon = self:find("icon", self.CardBackCont)
	self.MusicCont = self:find("MusicCont", self.MainCtrl)
	self.MusicIcon = self:find("Icon/MusicIcon", self.MusicCont)
	self.CycleIcon = self:find("CycleIcon", self.MusicCont)
	self.RandomIcon = self:find("RandomIcon", self.MusicCont)
	self.MusicCountText = self:find("MusicCountText", self.MusicCont)

	self.CharacterSizeCont = self:find("CharacterSizeCont", self.MainCtrl)
	self.SizeResetButton = self:find("ResetButton", self.CharacterSizeCont)
	self.SizeSlider = self:find("SizeSlider", self.CharacterSizeCont)
	self.SizeMinText = self:find("MinText", self.SizeSlider)
	self.SizeMaxText = self:find("MaxText", self.SizeSlider)
	self.SizeCurSizeText = self:find("Handle/Handle/CurTips/CurSizeText", self.SizeSlider)
	self.CharacterRotateCont = self:find("CharacterRotateCont", self.MainCtrl)
	self.RotateResetButton = self:find("ResetButton", self.CharacterRotateCont)
	self.RotateSlider = self:find("RotateSlider", self.CharacterRotateCont)
	self.RotateMinText = self:find("MinText", self.RotateSlider)
	self.RotateMaxText = self:find("MaxText", self.RotateSlider)
	self.RotateCurSizeText = self:find("Handle/Handle/CurTips/CurRotateText", self.RotateSlider)

	self.RightButtonList = self:find("RightButtonList", self.MainCtrl)
	self.UseButton = self:find("UseButton", self.RightButtonList)
	self.SaveButton = self:find("SaveButton", self.RightButtonList)

	self.ItemCtrl = self:find("ItemCtrl", Right)
	self.TitleName = self:find("Title", self.ItemCtrl)
	self.RandomButton = self:find("RandomButton", self.ItemCtrl)
	self.CircleButton = self:find("CircleButton", self.ItemCtrl)
	self.ViewButton = self:find("ViewButton", self.ItemCtrl)
	self.ChooseToggle = self:find("ChooseToggle", self.ItemCtrl)
	self.ItemList = self:find("ItemList", self.ItemCtrl)
	self.ItemRoot = self:find("Items", self.ItemList)
	self.CancleButton = self:find("CancleButton", self.ItemCtrl)
	self.ConfirmButton = self:find("ConfirmButton", self.ItemCtrl)

	self.SceneItem = self:find("SceneItem", self.ItemRoot)
	self.MusicItem = self:find("MusicItem", self.ItemRoot)
	self.AvatarItem = self:find("AvatarItem", self.ItemRoot)
	self.FrameItem = self:find("FrameItem", self.ItemRoot)
	self.TitleItem = self:find("TitleItem", self.ItemRoot)
	self.CardFaceItem = self:find("CardFaceItem", self.ItemRoot)
	self.CardBackItem = self:find("CardBackItem", self.ItemRoot)

	self._oriPosX = PlayerModel.CharacterDefaultPosX
	self._oriPosY = PlayerModel.CharacterDefaultPosY
	self._oriSize = PlayerModel.CharacterDefaultPosSize
	self._oriRot = 0

	self._rotLimit = 180
	self.skinCfg = nil

	self.ItemType = {
		Scene = 1,
		Music = 2,
		Avatar = 3,
		Frame = 4,
		Title = 5,
		CardFace = 6,
		CardBack = 7,
	}
	self.sltedType = nil
	self.ItemDic = {
		[self.ItemType.Scene] = self.SceneItem,
		[self.ItemType.Music] = self.MusicItem,
		[self.ItemType.Avatar] = self.AvatarItem,
		[self.ItemType.Frame] = self.FrameItem,
		[self.ItemType.Title] = self.TitleItem,
		[self.ItemType.CardFace] = self.CardFaceItem,
		[self.ItemType.CardBack] = self.CardBackItem,
	}

	self.BackButton = self:find("BackButton", LeftTop)
	bee.addClick(self.BackButton, function()
		self:onClickClose()
	end)

	bee.addValueChanged(self.SizeSlider, function(val)
	    local s = val * (MaxSize - MinSize) + MinSize
	    local size = math.floor(s * 100)
		if math.abs(self._character_size - size) > 1 then
			self._character_size = size / 100
		end
	    self.CharacterImage.transform.localScale = bee.v3(self._character_size, self._character_size, 1)
	    bee.setText(self.SizeCurSizeText, (self._character_size * 100) .. "%")
	    -- self._character_size = size / 100
    end, "Slider")

    bee.addClick(self.SizeResetButton, function()
    	self._character_x = self._oriPosX
    	self._character_y = self._oriPosY
    	self._character_size = self._oriSize
    	self:setCharacterShow(self._skin_id)
	end)

	bee.addValueChanged(self.RotateSlider, function(val)
	    local s = val * (self._rotLimit * 2) - self._rotLimit
		s = math.ceil(s * 100) / 100
		if math.abs(self._character_rot - s) > 0.02 then
			self._character_rot = s
		end
		-- local defRot = self.skinCfg.spine_rotation or 0
		self.CharacterImage.transform.localEulerAngles = bee.v3(0, 0, self._character_rot)
		bee.setText(self.RotateCurSizeText, self._character_rot .. "°")
    end, "Slider")

    bee.addClick(self.RotateResetButton, function()
		self._character_rot = self._oriRot
    	self.CharacterImage.transform.localEulerAngles = bee.v3(0, 0, 0)
		bee.setText(self.RotateCurSizeText, "0°")
		bee.setSliderValue(self.RotateSlider, 0.5)
	end)

	bee.addClick(self.CharacterButton, function()
		self:onClickCharacterButton()
	end)
	bee.addClick(self.GarmentButton, function()
		self:onClickSkin()
	end)

	bee.addClick(self.AvatarCont, function ()
		self:onClickAvatar()
	end)
	bee.addClick(self.TitleCont, function ()
		self:onClickTitle()
	end)
	bee.addClick(self.FrameCont, function ()
		self:onClickFrame()
	end)
	bee.addClick(self.SceneCont, function()
		self:onClickScene()
	end)
	bee.addClick(self.CardFaceCont, function()
		self:onClickCardFace()
	end)
	bee.addClick(self.CardBackCont, function()
		self:onClickCardBack()
	end)
	bee.addClick(self.MusicCont, function()
		self:onClickMusic()
	end)

	bee.addClick(self.RandomButton, function ()
		self:onMusicRandomToCircle()
	end)
	bee.addClick(self.CircleButton, function ()
		self:onMusicCircleToRandom()
	end)
	bee.addClick(self.ViewButton, function ()
		self:onMusicPlay()
	end)
	bee.addClick(self.ChooseToggle, function ()
		self:onMusicChoose()
	end)

	bee.addClick(self.CancleButton, function ()
		self:cancleEvent()
	end)
	bee.addClick(self.ConfirmButton, function ()
		self:confirmEvent()
	end)

	bee.addClick(self.UseButton, function()
		self:UseScheme()
	end)
	bee.addClick(self.SaveButton, function()
		self:SaveScheme()
	end)

	Game:pauseBGM()
end

function P:onStart()
	self._scheme_id = self._params and self._params.scheme_id
	local schemeInfo = DecorationModel:getLobbySchemeInfoById(self._scheme_id, true)
	self._skin_id = schemeInfo.skin_id
	self._scene_id = schemeInfo.lobby_scene_id
	self._scene_cache_id = self._scene_id
	self._bgm_list = {}
	for k,v in pairs(schemeInfo.lobby_bgm_list) do
		table.insert(self._bgm_list, v)
	end
	self._bgm_cache_list = clone(self._bgm_list)
	self._bgm_cache_id = self._bgm_cache_list[1]
	self._avatar_id = schemeInfo.avatar
	self._avatar_cache_id = self._avatar_id
	self._title_id = schemeInfo.title
	self._title_cache_id = self._title_id
	self._frame_id = schemeInfo.frame
	self._frame_cache_id = self._frame_id
	self._cardface_id = schemeInfo.card_front
	self._cardface_cache_id = self._cardface_id
	self._cardback_id = schemeInfo.card_back
	self._cardback_cache_id = self._cardback_id

	if schemeInfo.property_list and next(schemeInfo.property_list) then
		self._character_x = schemeInfo.property_list[1] / 10
		self._character_y = schemeInfo.property_list[2] / 10
		self._character_size = schemeInfo.property_list[3] / 100
		self._character_rot = schemeInfo.property_list[5] and (schemeInfo.property_list[5] / 100) or self._oriRot
		self._music_tag = schemeInfo.property_list[4] or MusicTag.Order
	else
		self._music_tag = MusicTag.Order
		self._character_x = self._oriPosX
		self._character_y = self._oriPosY
		self._character_size = self._oriSize
		self._character_rot = self._oriRot
	end

	bee.setText(self.SizeMinText, MinSize * 100 .. "%")
	bee.setText(self.SizeMaxText, MaxSize * 100 .. "%")

	self:setCharacterShow(self._skin_id)
	self:setSceneShow(self._scene_id)
	self:setMusicShow()
	self:setAvatarShow(self._avatar_id)
	self:setFrameShow(self._frame_id)
	self:setTitleShow(self._title_id)
	self:setCardFaceShow(self._cardface_id)
	self:setCardBackShow(self._cardback_id)

	if DecorationModel:isLobbySchemeRandom() then
		self.UsingTag:SetActive(false)
		self.UseButton:SetActive(false)
	else
		if schemeInfo.scheme_id == DecorationModel:getLobbySpecifySchemeId() then
			self.UsingTag:SetActive(true)
			self.SaveButton:SetActive(false)
		else
			self.UsingTag:SetActive(false)
			self.SaveButton:SetActive(true)
		end
	end

	self:showMusic()
	self.schemeInfo = schemeInfo

	self:initItemScroll()
	self:switchView(true)
end

function P:setCharacterShow(skinId, isReset)
	if not self._characterCls then
		self._characterCls = ObjectPool:getCls(self.CharacterImage)
		self._characterCls:setShowReal(true)
	end

    self.skinCfg = tpl_character_skin[skinId]
    self._characterCls:setRole(CharacterModel:getRole(self.skinCfg.role))
    self._characterCls:setSkin(self.skinCfg)

	local rot = 0
    local origin_pos = bee.v3(0, 0, 0)
    if self.skinCfg.lobby_pos then
        origin_pos.x, origin_pos.y = self.skinCfg.lobby_pos[1], self.skinCfg.lobby_pos[2]
		self._characterCls:getRoleSpine().transform.localPosition = origin_pos
	else
		self._characterCls:getRoleSpine().transform.localPosition = bee.v3zero
    end
	if isReset then
		self.CharacterImage.transform.localPosition = bee.v3(self._oriPosX, self._oriPosY, 0)
	    self.CharacterImage.transform.localScale = bee.v3(self._oriSize, self._oriSize, 1)
		self.CharacterImage.transform.localEulerAngles = bee.v3(0, 0, self._oriRot)
	else
	    self.CharacterImage.transform.localPosition = bee.v3(self._character_x, self._character_y, 0)
	    self.CharacterImage.transform.localScale = bee.v3(self._character_size, self._character_size, 1)
		self.CharacterImage.transform.localEulerAngles = bee.v3(0, 0, self._character_rot)
	end

	local val = (self._character_size - MinSize) / (MaxSize - MinSize)
	bee.setSliderValue(self.SizeSlider, val)
	bee.setText(self.SizeCurSizeText, self._character_size * 100 .. "%")
	local rval = (self._character_rot + self._rotLimit) / (self._rotLimit * 2)
	bee.setSliderValue(self.RotateSlider, rval)
	bee.setText(self.RotateCurSizeText, self._character_rot .. "°")
	
	-- self:setSceneShow(self._scene_id)
end

function P:setAvatarShow(avatarId)
	if avatarId == nil or avatarId == 0 then
		avatarId = tpl_character_skin[self._skin_id].avatar
	end
	local avatarCfg = tpl_props[avatarId]
	bee.setIconInAtlas(self.AvatarIcon, avatarCfg.icon)
end

function P:setTitleShow(titleId)
	if titleId == nil or titleId == 0 then
		self.TitleIcon:SetActive(false)
		self.TitleDefIcon:SetActive(true)
	else
		self.TitleIcon:SetActive(true)
		self.TitleDefIcon:SetActive(false)
		local titleCfg = tpl_props[titleId]
		bee.setIconInAtlas(self.TitleIcon, titleCfg.icon)
	end
end

function P:setFrameShow(frameId)
	if frameId == nil or frameId == 0 then
		self.FrameIcon:SetActive(false)
		self.FrameDefIcon:SetActive(true)
	else
		self.FrameIcon:SetActive(true)
		self.FrameDefIcon:SetActive(false)
		local frameCfg = tpl_props[frameId]
		bee.setIconInAtlas(self.FrameIcon, frameCfg.icon)
	end
end

function P:setSceneShow(propId)
	local propCfg = tpl_props[propId]
	local sceneId = propCfg.mapId
	-- local skin = tpl_character_skin[self._skin_id]
	-- if skin and skin.lobby_item and tpl_props[skin.lobby_item] then
	-- 	sceneId = tpl_props[skin.lobby_item].mapId
	-- end
	-- local sceneCfg = tpl_hall_scene[sceneId]
	-- bee.setIcon(self.SceneImg, sceneCfg.bg_image)
	GF.setLobbyImage(sceneId, self.SceneImg, self.ImageFg)
	bee.setIconInAtlas(self.SceneIcon, propCfg.icon)
end

function P:setCardFaceShow(cardfaceId)
	if cardfaceId == nil or cardfaceId == 0 then
		cardfaceId = ItemModel:getDefaultDecoration(GPropKind.CardFace)
	end
	self.CardFaceIcon:SetActive(true)
	local titleCfg = tpl_props[cardfaceId]
	bee.setIconInAtlas(self.CardFaceIcon, titleCfg.icon)
end

function P:setCardBackShow(cardbackId)
	if cardbackId == nil or cardbackId == 0 then
		cardbackId = ItemModel:getDefaultDecoration(GPropKind.CardBack)
	end
	if tpl_card_back[cardbackId] ~= nil then
	 	local groupList = get_tpl_subKey(tpl_props_list, "type", 205)
		for _,v in pairs(groupList) do
			if v.mapId == cardbackId then
				cardbackId = v.id
			end
		end
	end
	self.CardFaceIcon:SetActive(true)
	local titleCfg = tpl_props[cardbackId]
	bee.setIconInAtlas(self.CardBackIcon, titleCfg.icon)
end

function P:setMusicShow()
	local propCfg = tpl_props[self._bgm_list[1]]
	local musicCfg = tpl_sound[tostring(propCfg.mapId)]
	bee.setIconInAtlas(self.MusicIcon, musicCfg.cd_image)
	self.CycleIcon:SetActive(self._music_tag == MusicTag.Order)
	self.RandomIcon:SetActive(self._music_tag == MusicTag.Random)
	local musicCount = #self._bgm_list
	bee.setText(self.MusicCountText, musicCount)
end

function P:onDrag(e)
    local pos = self.CharacterImage.transform.localPosition
    pos.x, pos.y = pos.x + e.delta.x, pos.y + e.delta.y
    self.CharacterImage.transform.localPosition = pos

    self._character_x = self.CharacterImage.transform.localPosition.x
    self._character_y = self.CharacterImage.transform.localPosition.y
end

function P:initItemScroll()
	-- local ROW_COUNT = 4
	-- local rowPos = {}
	-- for i = 1, ROW_COUNT do
	-- 	table.insert(rowPos, ((i - 1) * 180) - 270)
	-- end

	self.rowCount2 = 2
	self.rowPos2 = {-180, 180}

	self.rowCount4 = 4
	self.rowPos4 = {}
	for i = 1, self.rowCount4 do
		table.insert(self.rowPos4, ((i - 1) * 180) - 270)
	end

	self.itemScroll = UiListEx:create(self.ItemList)
	self.itemScroll:setCreateFunc(function()
		local item = CU.GameObject.Instantiate(self.ItemDic[self.sltedType])
		item.gameObject:SetActive(true)
		return item
	end)
	self.itemScroll:setRefreshFunc(function(data, item)
		self:setPropItemShow(item, data)
	end)
	-- self.itemScroll:setRowCount(ROW_COUNT)
	-- self.itemScroll:setRowPostions(rowPos)
	-- self.itemScroll:setWidth(200)
end

function P:onClickCharacterButton()
	local params = {}
	params.major_type = GMajorType.ROLE
	local skinCfg = tpl_character_skin[self._skin_id]
	params.cur_using = skinCfg.role
	params.clickCb = function(roleId)
		local role = CharacterModel:getRole(roleId)
		self:setCharacterShow(role:getSkinData().id, true)
	end
	params.saveCb = function(roleId)
		self._character_x = self._oriPosX
		self._character_y = self._oriPosY
		self._character_size = self._oriSize
		self._character_rot = self._oriRot
		local role = CharacterModel:getRole(roleId)
		self._skin_id = role:getSkinData().id
		self:setCharacterShow(self._skin_id)
		UiManager:showToast(_T("LAB_CUSTOM_15"))
	end
	params.closeCb = function()
		self:setCharacterShow(self._skin_id)
	end
	UiManager:showUI("LobbyDecorationSelect", params)
end

function P:onClickSkin()
	local params = {}
	params.cur_using = self._skin_id
	params.saveCb = function(skinId)
		self._skin_id = skinId
		self:setCharacterShow(self._skin_id)
		UiManager:showToast(_T("LAB_CUSTOM_15"))
	end
	UiManager:showUI("LobbySkinSelect", params)
end

function P:switchView(sw)
	self.MainCtrl:SetActive(sw)
	self.ItemCtrl:SetActive(not sw)
end
function P:switchAnother(sw)
	self.RandomButton:SetActive(sw)
	self.CircleButton:SetActive(sw)
	self.ViewButton:SetActive(sw)
	self.ChooseToggle:SetActive(sw)
	local rectTran = self.ItemList:GetComponent("RectTransform")
	rectTran.sizeDelta = bee.v2(716, sw and 661 or 760)
end

function P:setItemListRowPos(num, width)
	if num == 2 then
		self.itemScroll:setRowCount(self.rowCount2)
		self.itemScroll:setRowPostions(self.rowPos2)
	elseif num == 4 then
		self.itemScroll:setRowCount(self.rowCount4)
		self.itemScroll:setRowPostions(self.rowPos4)
	end
	self.itemScroll:setWidth(width or 200)
end


function P:onClickAvatar()
	-- bee.setText(self.TitleName, _T("LAB_DECOR_PLAN_20"))
	self:switchView(false)
	self:switchAnother(false)
	self:setItemListRowPos(4)
	self.sltedType = self.ItemType.Avatar
	local ownedList = self:getDatas(GPropKind.Avatar)
	for _,v in pairs(ownedList) do
		v.__kind = "avatar"
	end
	self.itemScroll:setDatas(ownedList)
	self:setItemName(self._avatar_id)
end

function P:onClickTitle()
	-- bee.setText(self.TitleName, _T("LAB_DECOR_PLAN_22"))
	self:switchView(false)
	self:switchAnother(false)
	self:setItemListRowPos(2, 150)
	self.sltedType = self.ItemType.Title
	local ownedList = self:getDatas(GPropKind.Title)
	table.insert(ownedList, 1, {id = 0})
	for _,v in pairs(ownedList) do
		v.__kind = "title"
	end
	self.itemScroll:setDatas(ownedList)
	self:setItemName(self._title_id)
end

function P:onClickFrame()
	-- bee.setText(self.TitleName, _T("LAB_DECOR_PLAN_21"))
	self:switchView(false)
	self:switchAnother(false)
	self:setItemListRowPos(4)
	self.sltedType = self.ItemType.Frame
	local ownedList = self:getDatas(GPropKind.FrameAvatar)
	table.insert(ownedList, 1, {id = 0})
	for _,v in pairs(ownedList) do
		v.__kind = "frame"
	end
	self.itemScroll:setDatas(ownedList)
	self:setItemName(self._frame_id)
end

function P:onClickScene()
	-- bee.setText(self.TitleName, _T("LAB_CUSTOM_11"))
	self:switchView(false)
	self:switchAnother(false)
	self:setItemListRowPos(4)
	self.sltedType = self.ItemType.Scene
	local ownedList = ItemModel:getAllShowItems(14, true)
	for _,v in pairs(ownedList) do
		v.__kind = "Scene"
	end
	self.itemScroll:setDatas(ownedList)
	self:setItemName(self._scene_id)
end
function P:onClickScene2()
	local params = {}
	params.major_type = GMajorType.PROP
	params.cur_using = self._scene_id
	params.clickCb = function(sceneId)
		self:setSceneShow(sceneId)
	end
	params.saveCb = function (sceneId)
		self._scene_id = sceneId
		self:setSceneShow(self._scene_id)
		UiManager:showToast(_T("LAB_CUSTOM_16"))
	end
	params.closeCb = function()
		self:setSceneShow(self._scene_id)
	end
	UiManager:showUI("LobbyDecorationSelect", params)
end

function P:onClickCardFace()
	self:switchView(false)
	self:switchAnother(false)
	self:setItemListRowPos(4)
	self.sltedType = self.ItemType.CardFace
	local ownedList = self:getDatas(GPropKind.CardFace)
	for _,v in pairs(ownedList) do
		v.__kind = "cardface"
	end
	self.itemScroll:setDatas(ownedList)
	self:setItemName(self._cardface_id)
end

function P:onClickCardBack()
	self:switchView(false)
	self:switchAnother(false)
	self:setItemListRowPos(4)
	self.sltedType = self.ItemType.CardBack
	local ownedList = self:getDatas(GPropKind.CardBack)
	for _,v in pairs(ownedList) do
		v.__kind = "cardback"
	end
	self.itemScroll:setDatas(ownedList)
	self:setItemName(self._cardback_id)
end

function P:onClickMusic()
	-- bee.setText(self.TitleName, _T("LAB_DECOR_PLAN_13"))
	self:switchView(false)
	self:switchAnother(true)
	self.CircleButton:SetActive(self._music_tag == MusicTag.Order)
	self.RandomButton:SetActive(self._music_tag == MusicTag.Random)
	self:checkMusicAllSelect()
	self:setItemListRowPos(4)
	self.sltedType = self.ItemType.Music
	-- local ownedList = ItemModel:getAllShowItems(8, true)
	-- self.itemScroll:setDatas(ownedList)
	self:onShowMusic()
	self:setItemName(self._bgm_cache_id)
end
function P:onClickMusicOld()
	local params = {}
	params.list = ItemModel:getAllShowItems(8, true)
	local selectData
	params.selectList = {}
	for k, v in pairs(params.list) do
		local isIn = false
		for k1, v1 in pairs(self._bgm_list) do
			if v1 == v.id then
				selectData = v.id
				isIn = true
				break
			end
		end
		params.selectList[v.id] = isIn
	end
	params.data = ItemModel:getItem(selectData)
	params.cycleType = self._music_tag
	params.saveCb = function(selected, tag)
		self._music_tag = tag
		self._bgm_list = {}
		for k,v in pairs(selected) do
			if v then
				table.insert(self._bgm_list, k)
			end
		end
		self:setMusicShow()
		self:showMusic()
	end
	params.closeCb = function()
		self:showMusic()
	end
	bee.stopSound("")
	UiManager:showUI("MusicSelect", params)
end

function P:onShowMusic()
	local ownMusiclist = ItemModel:getAllShowItems(8, true)
	for _,v in pairs(ownMusiclist) do
		v.__kind = "music"
	end
	self.itemScroll:setDatas(ownMusiclist)
end


function P:setPropItemShow(item, data)
	if self.sltedType == self.ItemType.Avatar then
		self:setAvatarItemShow(item, data)
	elseif self.sltedType == self.ItemType.Title then
		self:setTitleItemShow(item, data)
	elseif self.sltedType == self.ItemType.Frame then
		self:setFrameItemShow(item, data)
	elseif self.sltedType == self.ItemType.Scene then
		self:setSceneItemShow(item, data)
	elseif self.sltedType == self.ItemType.CardFace then
		self:setCardFaceItemShow(item, data)
	elseif self.sltedType == self.ItemType.CardBack then
		self:setCardBackItemShow(item, data)
	elseif self.sltedType == self.ItemType.Music then
		self:setMusicItemShow(item, data)
	end
end
function P:setAvatarItemShow(item, data)
	local isSlt = data.id == self._avatar_cache_id
	self:find("decoration_avatar_selected", item):SetActive(isSlt)
	bee.setIconInAtlas(self:find("avatar_frame_01_mask/icon", item), tpl_props[data.id].icon)
	bee.addClick(item, function ()
		if self._avatar_cache_id ~= data.id then
			self._avatar_cache_id = data.id
			self:setItemName(data.id)
			local items = self.itemScroll:getDatas()
			for _,v in pairs(items) do
				if not bee.isNull(v.node) then
					self:find("decoration_avatar_selected", v.node):SetActive(v.data.id == self._avatar_cache_id)
				end
			end
		end
	end, true)
end
function P:setTitleItemShow(item, data)
	local isSlt = data.id == self._title_cache_id
	self:find("decoration_title_selected", item):SetActive(isSlt)
	local defIcon = self:find("defIcon", item)
	local icon = self:find("icon", item)
	if data.id == nil or data.id == 0 then
		defIcon:SetActive(true)
		icon:SetActive(false)
	else
		defIcon:SetActive(false)
		icon:SetActive(true)
		bee.setIconInAtlas(icon, tpl_props[data.id].icon)
	end
	bee.addClick(item, function ()
		if self._title_cache_id ~= data.id then
			self._title_cache_id = data.id
			self:setItemName(data.id)
			local items = self.itemScroll:getDatas()
			for _,v in pairs(items) do
				if not bee.isNull(v.node) then
					self:find("decoration_title_selected", v.node):SetActive(v.data.id == self._title_cache_id)
				end
			end
		end
	end, true)
end
function P:setFrameItemShow(item, data)
	local isSlt = data.id == self._frame_cache_id
	self:find("selected", item):SetActive(isSlt)
	local defIcon = self:find("defIcon", item)
	local icon = self:find("icon", item)
	if data.id == nil or data.id == 0 then
		defIcon:SetActive(true)
		icon:SetActive(false)
	else
		defIcon:SetActive(false)
		icon:SetActive(true)
		bee.setIconInAtlas(icon, tpl_props[data.id].icon)
	end
	bee.addClick(item, function ()
		if self._frame_cache_id ~= data.id then
			self._frame_cache_id = data.id
			self:setItemName(data.id)
			local items = self.itemScroll:getDatas()
			for _,v in pairs(items) do
				if not bee.isNull(v.node) then
					self:find("selected", v.node):SetActive(v.data.id == self._frame_cache_id)
				end
			end
		end
	end, true)
end
function P:setSceneItemShow(item, data)
	local isSlt = data.id == self._scene_cache_id
	self:find("selected", item):SetActive(isSlt)
	bee.setIconInAtlas(self:find("icon", item), tpl_props[data.id].icon)
	bee.addClick(item, function ()
		if self._scene_cache_id ~= data.id then
			self._scene_cache_id = data.id
			self:setItemName(data.id)
			local propCfg = tpl_props[self._scene_cache_id]
			--bee.setIcon(self.SceneImg, tpl_hall_scene[propCfg.mapId].bg_image)
			GF.setLobbyImage(propCfg.mapId, self.SceneImg, self.ImageFg)
			local items = self.itemScroll:getDatas()
			for _,v in pairs(items) do
				if not bee.isNull(v.node) then
					self:find("selected", v.node):SetActive(v.data.id == self._scene_cache_id)
				end
			end
		end
	end, true)
end
function P:setCardFaceItemShow(item, data)
	local isSlt = data.id == self._cardface_cache_id
	self:find("selected", item):SetActive(isSlt)
	local icon = self:find("icon", item)
	-- if data.id == nil or data.id == 0 then
	-- 	data.id = ItemModel:getDefaultDecoration(GPropKind.CardFace)
	-- end
	bee.setIconInAtlas(icon, tpl_props[data.id].icon)
	bee.addClick(item, function ()
		if self._cardface_cache_id ~= data.id then
			self._cardface_cache_id = data.id
			self:setItemName(data.id)
			local items = self.itemScroll:getDatas()
			for _,v in pairs(items) do
				if not bee.isNull(v.node) then
					self:find("selected", v.node):SetActive(v.data.id == self._cardface_cache_id)
				end
			end
		end
	end, true)
end
function P:setCardBackItemShow(item, data)
	local isSlt = data.id == self._cardback_cache_id
	self:find("selected", item):SetActive(isSlt)
	local icon = self:find("icon", item)
	-- if data.id == nil or data.id == 0 then
	-- 	data.id = ItemModel:getDefaultDecoration(GPropKind.CardFace)
	-- end
	bee.setIconInAtlas(icon, tpl_props[data.id].icon)
	bee.addClick(item, function ()
		if self._cardback_cache_id ~= data.id then
			self._cardback_cache_id = data.id
			self:setItemName(data.id)
			local items = self.itemScroll:getDatas()
			for _,v in pairs(items) do
				if not bee.isNull(v.node) then
					self:find("selected", v.node):SetActive(v.data.id == self._cardback_cache_id)
				end
			end
		end
	end, true)
end
function P:setMusicItemShow(item, data)
	local isSlt = self._bgm_cache_id == data.id
	self:find("selected", item):SetActive(isSlt)
	bee.setIconInAtlas(self:find("icon", item), tpl_props[data.id].icon)
	local inList = table.keyof(self._bgm_cache_list, data.id)
	local sltIcon = self:find("SelectToggle/lobby_music_01_fg", item)
	sltIcon:SetActive(inList ~= nil)
	local order = self:find("Order", item)
	if self._music_tag == MusicTag.Order then
		if inList ~= nil then
			order:SetActive(true)
			bee.setText(self:find("Value", order), inList)
		else
			order:SetActive(false)
		end
	else
		order:SetActive(false)
	end

	bee.addClick(item, function ()
		self._bgm_cache_id = data.id
		self:setItemName(data.id)
		local inList = table.keyof(self._bgm_cache_list, data.id)
		local sltIcon = self:find("SelectToggle/lobby_music_01_fg", item)
		if inList ~= nil then
			if #self._bgm_cache_list > 1 then
				table.removebyvalue(self._bgm_cache_list, data.id)
				sltIcon:SetActive(false)
			end
		else
			table.insert(self._bgm_cache_list, data.id)
			sltIcon:SetActive(true)
		end
		self:checkMusicAllSelect()

		local items = self.itemScroll:getDatas()
		for _,v in pairs(items) do
			if not bee.isNull(v.node) then
				self:find("selected", v.node):SetActive(v.data.id == self._bgm_cache_id)
				local order = self:find("Order", v.node)
				if self._music_tag == MusicTag.Order then
					local inList = table.keyof(self._bgm_cache_list, v.data.id)
					if inList ~= nil then
						order:SetActive(true)
						bee.setText(self:find("Value", order), inList)
					else
						order:SetActive(false)
					end
				end
			end
		end
	end, true)
end

function P:getDatas(kind)
    local ct = bee.getServerTime()
    local datas = {}
    local tbs = get_tpl_subKey(tpl_props_list, "type", kind)
    for _, v in ipairs(tbs) do
        local d = ItemModel:getItem(v.id)
        if d and d.bagShow == 1 and (not d.time_start or d.time_start <= ct or PlayerModel:isEventWhite()) then
            table.insert(datas, d)
        end
    end
    return datas
end

function P:cancleEvent()
	if self.sltedType == self.ItemType.Scene then
		if self._scene_cache_id ~= self._scene_id then
			self._scene_cache_id = self._scene_id
			self:setSceneShow(self._scene_id)
		end
	elseif self.sltedType == self.ItemType.Music then
		if self._bgm_cache_list ~= self._bgm_list then
			self._bgm_cache_list = self._bgm_list
			self:setMusicShow()
		end
	elseif self.sltedType == self.ItemType.Avatar then
		if self._avatar_cache_id ~= self._avatar_id then
			self._avatar_cache_id = self._avatar_id
			self:setAvatarShow(self._avatar_id)
		end
	elseif self.sltedType == self.ItemType.Frame then
		if self._frame_cache_id ~= self._frame_id then
			self._frame_cache_id = self._frame_id
			self:setFrameShow(self._frame_id)
		end
	elseif self.sltedType == self.ItemType.Title then
		if self._title_cache_id ~= self._title_id then
			self._title_cache_id = self._title_id
			self:setTitleShow(self._title_id)
		end
	elseif self.sltedType == self.ItemType.CardFace then
		if self._cardface_cache_id ~= self._cardface_id then
			self._cardface_cache_id = self._cardface_id
			self:setCardFaceShow(self._cardface_id)
		end
	elseif self.sltedType == self.ItemType.CardBack then
		if self._cardback_cache_id ~= self._cardback_id then
			self._cardback_cache_id = self._cardback_id
			self:setCardBackShow(self._cardback_id)
		end
	end
	self:switchView(true)
	self.itemScroll:moveToYItem(1, false)
	self.itemScroll:clear()
	-- self.itemScroll:clearCaches()
end
function P:confirmEvent()
	if self.sltedType == self.ItemType.Scene then
		if self._scene_cache_id ~= self._scene_id then
			self._scene_id = self._scene_cache_id
			self:setSceneShow(self._scene_id)
		end
	elseif self.sltedType == self.ItemType.Music then
		if self._bgm_cache_list ~= self._bgm_list then
			self._bgm_list = clone(self._bgm_cache_list)
			self:setMusicShow()
			bee.stopSound("")
			self:showMusic()
		end
	elseif self.sltedType == self.ItemType.Avatar then
		if self._avatar_cache_id ~= self._avatar_id then
			self._avatar_id = self._avatar_cache_id
			self:setAvatarShow(self._avatar_id)
		end
	elseif self.sltedType == self.ItemType.Frame then
		if self._frame_cache_id ~= self._frame_id then
			self._frame_id = self._frame_cache_id
			self:setFrameShow(self._frame_id)
		end
	elseif self.sltedType == self.ItemType.Title then
		if self._title_cache_id ~= self._title_id then
			self._title_id = self._title_cache_id
			self:setTitleShow(self._title_id)
		end
	elseif self.sltedType == self.ItemType.CardFace then
		if self._cardface_cache_id ~= self._cardface_id then
			self._cardface_id = self._cardface_cache_id
			self:setCardFaceShow(self._cardface_id)
		end
	elseif self.sltedType == self.ItemType.CardBack then
		if self._cardback_cache_id ~= self._cardback_id then
			self._cardback_id = self._cardback_cache_id
			self:setCardBackShow(self._cardback_id)
		end
	end
	self:switchView(true)
	self.itemScroll:clear()
	self.itemScroll:clearCaches()
end

function P:onMusicRandomToCircle()
	self.RandomButton:SetActive(false)
	self.CircleButton:SetActive(true)
	self._music_tag = MusicTag.Order
	self:onShowMusic()
	bee.logEvent("style-preset-music-mode", SchemeTag.Lobby, 1)
end
function P:onMusicCircleToRandom()
	self.RandomButton:SetActive(true)
	self.CircleButton:SetActive(false)
	self._music_tag = MusicTag.Random
	self:onShowMusic()
	bee.logEvent("style-preset-music-mode", SchemeTag.Lobby, 2)
end
function P:onMusicPlay()
	local list, index = {}, 1
	for k, v in ipairs(self._bgm_cache_list) do
		list[#list+1] = {item_id = v, cfg = tpl_props[v]}
		if self._bgm_cache_id == v then
			index = k
		end
	end
	
	UiManager:showUI("BackpackMusic", {data = list[index], list = list})
end
function P:onMusicChoose()
	local isAll = self:checkMusicAllSelect()
	if isAll then
		local onlyOne = self._bgm_cache_list[1]
		self._bgm_cache_list = {onlyOne}
		self:onShowMusic()
		self:find("common_checkbox_01_fg", self.ChooseToggle):SetActive(false)
	else
		local ownedList = ItemModel:getAllShowItems(8, true)
		local count = #ownedList
		for i = 1, count do
			local id = ownedList[i].id
			if table.keyof(self._bgm_cache_list, id) == nil then
				table.insert(self._bgm_cache_list, id)
			end
		end
		self:onShowMusic()
		self:find("common_checkbox_01_fg", self.ChooseToggle):SetActive(true)
	end
end
function P:checkMusicAllSelect()
	local ownedList = ItemModel:getAllShowItems(8, true)
	local isAll = #self._bgm_cache_list == #ownedList
	self:find("common_checkbox_01_fg", self.ChooseToggle):SetActive(isAll)
	return isAll
end

--设置道具名
function P:setItemName(id)
	if self.sltedType == self.ItemType.Avatar then
		bee.setText(self.TitleName, _F("LAB_DECOR_PLAN_34", _T(tpl_props[id].name)))
	elseif self.sltedType == self.ItemType.Title then
		if id == 0 then
			bee.setText(self.TitleName, _T("LAB_DECOR_PLAN_27"))
		else
			bee.setText(self.TitleName, _T(tpl_props[id].name))
		end
	elseif self.sltedType == self.ItemType.Frame then
		if id == 0 then
			bee.setText(self.TitleName, _T("LAB_DECOR_PLAN_35"))
		else
			bee.setText(self.TitleName, _T(tpl_props[id].name))
		end
	else
		bee.setText(self.TitleName, _T(tpl_props[id].name))
	end
end

function P:UseScheme()
	local data = self:getLatestData(true)
	DecorationModel:requestSaveDecorationScheme(data)
		-- self._scheme_id, self._skin_id, self._scene_id, self._bgm_list, self._avatar_id, self._frame_id, self._title_id, self._cardface_id, self._cardback_id, property_list, true)
	self:cloeUI()
end

function P:SaveScheme()
	local data = self:getLatestData(false)
	DecorationModel:requestSaveDecorationScheme(data)
		-- self._scheme_id, self._skin_id, self._scene_id, self._bgm_list, self._avatar_id, self._frame_id, self._title_id, self._cardface_id, self._cardback_id, property_list)
	self:cloeUI()
end

function P:getLatestData(isUse)
	local property_list = {}
	property_list[1] = math.floor(self._character_x * 10)
	property_list[2] = math.floor(self._character_y * 10)
	property_list[3] = self._character_size * 100
	property_list[4] = self._music_tag
	property_list[5] = self._character_rot * 100
	local saveData = {
		scheme_id = self._scheme_id,
		skin_id = self._skin_id,
		scene_id = self._scene_id,
		bgm_list = self._bgm_list,
		avatar_id = self._avatar_id,
		frame_id = self._frame_id,
		title_id = self._title_id,
		cardface_id = self._cardface_id,
		cardback_id = self._cardback_id,
		property_list = property_list,
		isUse = isUse,
	}
	return saveData
end

function P:showMusic()
	if SettingModel:getLobbyBGMVolume() <= 0 then
		return
	end
	self._isPlaying = true
	self._musicIndex = nil
	self:switchMusic()
end

function P:switchMusic()
    self._time = 0
    if self._music_tag == MusicTag.Order then
        if self._musicIndex then
            self._musicIndex = math.min(self._musicIndex + 1, #self._bgm_list)
        else
            self._musicIndex = 1
        end
        self:playMusic(self._bgm_list[self._musicIndex])
    else
        local rand = math.random(#self._bgm_list)
        self:playMusic(self._bgm_list[rand])
    end
end

function P:playMusic(key, volume)
	key = tpl_props[key].mapId
    local d = tpl_sound[tostring(key)]
    if d then
		local v = SettingModel:getSoundVolume()
        bee.playSound(d.path, false, v)
        self._length = ResManager:GetSound(d.path).length
    end
end

function P:onUpdate(dt)
    if self._time then
        self._time = self._time + dt
        if self._time >= self._length then
            self:switchMusic()
        end
    end
end

function P:checkIsChange()
	if self._skin_id ~= self.schemeInfo.skin_id then
		return true
	end
	if self._scene_id ~= self.schemeInfo.lobby_scene_id then
		return true
	end
	if self._avatar_id ~= self.schemeInfo.avatar then
		return true
	end
	if self._frame_id ~= self.schemeInfo.frame then
		return true
	end
	if self._title_id ~= self.schemeInfo.title then
		return true
	end
	if self._cardface_id ~= self.schemeInfo.card_front then
		return true
	end
	if self._cardback_id ~= self.schemeInfo.card_back then
		return true
	end

	if self.schemeInfo.property_list ~= nil then
		if self.schemeInfo.property_list[1] ~= math.floor(self._character_x * 10) then
			return true
		end
		if self.schemeInfo.property_list[2] ~= math.floor(self._character_y * 10) then
			return true
		end
		if self.schemeInfo.property_list[3] ~= math.floor(self._character_size * 100) then
			return true
		end
		if self.schemeInfo.property_list[4] ~= self._music_tag then
			return true
		end
		if self.schemeInfo.property_list[5] ~=  self._character_rot * 100 then
			return true
		end
	else
		if PlayerModel.CharacterDefaultPosX ~= self._character_x then
			return true
		end
		if PlayerModel.CharacterDefaultPosY ~= self._character_y then
			return true
		end
		if PlayerModel.CharacterDefaultPosSize ~= self._character_size then
			return true
		end
		if self._music_tag ~= MusicTag.Order then
			return true
		end
		if self._character_rot ~= 0 then
			return true
		end
	end
	if not DecorationModel:isSameBgmList(self._bgm_list, self.schemeInfo.lobby_bgm_list) then
		return true
	end
	return false
end

function P:onClickClose()
	-- 判断是否有修改
	if self:checkIsChange() then
		local params = {}
		params.text = _T("LAB_CUSTOM_9")
		params.onSure = function()
			self:cloeUI()
		end
		UiManager:showTip(params)
	else
		self:cloeUI()
	end
end

function P:cloeUI()
	if self._isPlaying then
		bee.stopSound("")
        Game:resumeBGM()
	end
	self:hideUI()
end

function P:evt_gameBlur(flag, name)
    self:evt_uiBlur(flag, name)
end

return P