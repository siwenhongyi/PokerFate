local P = class("LobbyAdjustment", UiBase)

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
	self.CharacterImage = self:find("CharacterImage", Center)

	self.UsingTag = self:find("UsingTag", Right)
	self.SceneCont = self:find("SceneCont", Right)
	self.SceneItem = self:find("SceneItem", self.SceneCont)
	self.SceneNameText = self:find("SceneNameText", self.SceneCont)
	self.SceneEditButton = self:find("SceneEditButton", self.SceneCont)
	self.MusicCont = self:find("MusicCont", Right)
	self.MusicNameText = self:find("MusicNameText", self.MusicCont)
	self.MusicIcon = self:find("Icon/MusicIcon", self.MusicCont)
	self.MusicEditButton = self:find("MusicEditButton", self.MusicCont)
	self.CycleIcon = self:find("CycleIcon", self.MusicCont)
	self.RandomIcon = self:find("RandomIcon", self.MusicCont)
	self.MusicCountText = self:find("MusicCountText", self.MusicCont)
	self.CharacterSizeCont = self:find("CharacterSizeCont", Right)
	self.ResetButton = self:find("ResetButton", self.CharacterSizeCont)
	self.SizeSlider = self:find("SizeSlider", self.CharacterSizeCont)
	self.MinText = self:find("MinText", self.SizeSlider)
	self.MaxText = self:find("MaxText", self.SizeSlider)
	self.CurSizeText = self:find("Handle/Handle/CurTips/CurSizeText", self.SizeSlider)
	self.RightButtonList = self:find("RightButtonList", Right)
	self.UseButton = self:find("UseButton", self.RightButtonList)
	self.SaveButton = self:find("SaveButton", self.RightButtonList)

	self._oriPosX = PlayerModel.CharacterDefaultPosX
	self._oriPosY = PlayerModel.CharacterDefaultPosY
	self._oriSize = PlayerModel.CharacterDefaultPosSize

	self.BackButton = self:find("BackButton", LeftTop)
	bee.addClick(self.BackButton, function()
		self:onClickClose()
	end)

	bee.addValueChanged(self.SizeSlider, function(val)
	    local s = val * (MaxSize - MinSize) + MinSize
	    local size = math.floor(s * 100)
	    self.CharacterImage.transform.localScale = bee.v3(size / 100, size / 100, 1)
	    bee.setText(self.CurSizeText, size .. "%")
	    self._character_size = size / 100
    end, "Slider")

    bee.addClick(self.ResetButton, function()
    	self._character_x = self._oriPosX
    	self._character_y = self._oriPosY
    	self._character_size = self._oriSize
    	self:setCharacterShow(self._skin_id)
	end)

	bee.addClick(self.CharacterButton, function()
		self:onClickCharacterButton()
	end)
	bee.addClick(self.GarmentButton, function()
		self:onClickSkin()
	end)
	bee.addClick(self.SceneCont, function()
		self:onClickScene()
	end)
	bee.addClick(self.SceneEditButton, function()
		self:onClickScene()
	end)
	bee.addClick(self.MusicCont, function()
		self:onClickMusic()
	end)
	bee.addClick(self.MusicEditButton, function()
		self:onClickMusic()
	end)

	bee.addClick(self.UseButton, function()
		self:UseScheme()
	end)
	bee.addClick(self.SaveButton, function()
		self:SaveScheme()
	end)

	CS.SoundManager.Instance:PauseMusic()
end

function P:onStart()
	self._scheme_id = self._params and self._params.scheme_id
	local schemeInfo = PlayerModel:getSchemeInfoById(self._scheme_id, true)
	self._skin_id = schemeInfo.skin_id
	self._scene_id = schemeInfo.lobby_scene_id
	self._bgm_list = {}
	for k,v in pairs(schemeInfo.lobby_bgm_list) do
		table.insert(self._bgm_list, v)
	end
	if schemeInfo.property_list and next(schemeInfo.property_list) then
		self._music_tag = schemeInfo.property_list[4] or MusicTag.Order
		self._character_x = schemeInfo.property_list[1] / 10
		self._character_y = schemeInfo.property_list[2] / 10
		self._character_size = schemeInfo.property_list[3] / 100
	else
		self._music_tag = MusicTag.Order
		self._character_x = self._oriPosX
		self._character_y = self._oriPosY
		self._character_size = self._oriSize
	end

	bee.setText(self.MinText, MinSize * 100 .. "%")
	bee.setText(self.MaxText, MaxSize * 100 .. "%")

	self:setCharacterShow(self._skin_id)
	self:setSceneShow(self._scene_id)
	self:setMusicShow()

	if schemeInfo.scheme_id == PlayerModel:getCurSchemeId() then
		self.UsingTag:SetActive(true)
		self.SaveButton:SetActive(false)
	else
		self.UsingTag:SetActive(false)
		self.SaveButton:SetActive(true)
	end

	self:showMusic()
	self.schemeInfo = schemeInfo
end

function P:setCharacterShow(skinId, isReset)
	if not self._characterCls then
		self._characterCls = ObjectPool:getCls(self.CharacterImage)
	end

    local skinCfg = tpl_character_skin[skinId]
    self._characterCls:setRole(CharacterModel:getRole(skinCfg.role))
    self._characterCls:setSkin(skinCfg)

	if isReset then
		self.CharacterImage.transform.localPosition = bee.v3(self._oriPosX, self._oriPosY, 0)
	    self.CharacterImage.transform.localScale = bee.v3(self._oriSize, self._oriSize, 1)
	else
	    self.CharacterImage.transform.localPosition = bee.v3(self._character_x, self._character_y, 0)
	    self.CharacterImage.transform.localScale = bee.v3(self._character_size, self._character_size, 1)
	end

    if skinCfg.spine_rotation then
        self.CharacterImage.transform.localEulerAngles = bee.v3(0, 0, skinCfg.spine_rotation)
    else
        self.CharacterImage.transform.localEulerAngles = bee.v3zero
    end

	local val = (self._character_size - MinSize) / (MaxSize - MinSize)
	bee.setSliderValue(self.SizeSlider, val)
	bee.setText(self.CurSizeText, self._character_size * 100 .. "%")
end

function P:setSceneShow(sceneId)
	local propCfg = tpl_props[sceneId]
	local sceneCfg = tpl_hall_scene[propCfg.mapId]
	bee.setIcon(self.SceneImg, sceneCfg.bg_image)
	bee.setIconInAtlas(self.SceneItem, sceneCfg.bg_small)
	bee.setText(self.SceneNameText, _T(propCfg.name))
end

function P:setMusicShow()
	local propCfg = tpl_props[self._bgm_list[1]]
	local musicCfg = tpl_sound[tostring(propCfg.mapId)]
	bee.setText(self.MusicNameText, _T(propCfg.name))
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

function P:onClickScene()
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

function P:onClickMusic()
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

function P:UseScheme()
	local property_list = {}
	property_list[1] = math.floor(self._character_x * 10)
	property_list[2] = math.floor(self._character_y * 10)
	property_list[3] = self._character_size * 100
	property_list[4] = self._music_tag
	PlayerModel:requestSaveDecorationScheme(self._scheme_id, self._skin_id, self._scene_id, self._bgm_list, property_list, true)
	self:cloeUI()
end

function P:SaveScheme()
	local property_list = {}
	property_list[1] = math.floor(self._character_x * 10)
	property_list[2] = math.floor(self._character_y * 10)
	property_list[3] = self._character_size * 100
	property_list[4] = self._music_tag
	PlayerModel:requestSaveDecorationScheme(self._scheme_id, self._skin_id, self._scene_id, self._bgm_list, property_list)
	self:cloeUI()
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
        bee.playSound(d.path)
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
	if not self.schemeInfo.property_list then
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
	end
	if not PlayerModel:isSameBgmList(self._bgm_list, self.schemeInfo.lobby_bgm_list) then
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
		CS.SoundManager.Instance:UnPauseMusic()
	end
	self:hideUI()
end

