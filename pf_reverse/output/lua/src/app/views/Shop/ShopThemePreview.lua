local P = class("ShopThemePreview", UiFullView)

local PublicCard = {[1] = {'a', 's'}, [2] = {'k', 'h'}, [3] = {'q', 'c'}, [4] = {'j', 'd'}, [5] = {'10', 's'}}

local PreviewType = {
	Lobby = 1,
	Table = 2,
}

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")

	self.PKTable3D = self:find("PKTable3D", self.AnimRoot)
	self.LobbyCont = self:find("LobbyCont", self.AnimRoot)
	self.UI = self:find("UI", self.AnimRoot)

	-- 大厅预览
	self.LobbyImg = self:find("LobbyImg", self.LobbyCont)
	self.CharacterImage = self:find("CharacterImage", self.LobbyCont)
	self.ZoomSlider = self:find("ZoomSlider", self.LobbyCont)
	self.PanelTouch = self:find("PanelTouch", self.PanelTouch)

	-- 牌桌预览
    self.BgPublic = self:find("BgTable/BgPublic", self.PKTable3D)
    self.TableCardList = {}
    self.SeatNodeList = {}
    for i = 1, 6 do
        self.TableCardList[i] = self:find("BgTable/TableCard" .. i, self.PKTable3D)
        self.SeatNodeList[i] = self:find("SeatNode" .. i, self.PKTable3D)
        self:find("TableInfo" .. i, self.PKTable3D):SetActive(false)
    end
    self.PlayerHead = self:find("PlayerHead", self.PKTable3D)
    self.PlayerOther = self:find("PlayerOther", self.PKTable3D)
    self.PlayerOther:SetActive(false)
    self.TextPot = self:find("BgPot/TextPot", self.PKTable3D)
    bee.setText(self.TextPot, _N(1000000000))

    self:find("ImageCardUI", self.PKTable3D):SetActive(false)
    self:find("BgTip", self.PKTable3D):SetActive(false)
    self:find("BgWaitBBTip", self.PKTable3D):SetActive(false)
    self:find("BgPayBBTip", self.PKTable3D):SetActive(false)
    -- 牌桌
    self.ImageBg = self:find("ImageBg", self.PKTable3D)
    self.ImageTable = self:find("ImageTable", self.PKTable3D)

    -- UI
	self.NameText = self:find("SceneTitle/NameText", self.UI)
	self.PurchaseButton = self:find("PurchaseButton", self.UI)
	self.OwnedButton = self:find("OwnedButton", self.UI)
	self.CurPriIcon = self:find("CurPriIcon", self.PurchaseButton)
	self.CurPriText = self:find("CurPriText", self.PurchaseButton)
	self.OriPriIcon = self:find("OriPriIcon", self.PurchaseButton)
	self.OriPriText = self:find("OriPriText", self.PurchaseButton)
	self.Discount = self:find("Discount", self.UI)
	self.DiscountText = self:find("DiscountText", self.Discount)
	self.HideButton = self:find("HideButton", self.UI)
	self.LobbyButton = self:find("Switch/LobbyButton", self.UI)
	self.TableButton = self:find("Switch/TableButton", self.UI)
	self.PlayButton = self:find("Bgm/PlayButton", self.UI)
	self.StopButton = self:find("Bgm/StopButton", self.UI)
	self.BgmNameText = self:find("Bgm/BgmNameText", self.UI)
	self.BgmIcon = self:find("Bgm/shop_bgm_top_bg_01", self.UI)
	self.BackButton = self:find("BackButton", self.UI)
	self.Currency = self:find("Currency", self.UI)
	self.Icon = self:find("Icon", self.Currency)
	self.CountText = self:find("CountText", self.Currency)
	self.PlayButton:SetActive(false)

	self.ClickMask = self:find("ClickMask", self.AnimRoot)
	self.ClickMask:SetActive(false)

	bee.addClick(self.BackButton, function()
		self:hideUI()
	end)
	bee.addClick(self.LobbyButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickLobby()
	end)
	bee.addClick(self.TableButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickTable()
	end)
	bee.addClick(self.HideButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("shop-theme-preview-ui", self._curPreviewType == PreviewType.Lobby and 0 or 1)
		self.UI:SetActive(false)
		self.ZoomSlider:SetActive(false)
		self.ClickMask:SetActive(true)
	end)
	bee.addClick(self.ClickMask, function()
		self.UI:SetActive(true)
		self.ZoomSlider:SetActive(true)
		self.ClickMask:SetActive(false)
	end)
	bee.addClick(self.Currency, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("shop-theme-preview-add", self._curPreviewType == PreviewType.Lobby and 0 or 1)
		ItemModel:jumpView(tpl_props[self.data.consumeId].accesses[1])
		self:hideUI()
	end)
	bee.addClick(self.PlayButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickPlayButton()
	end)
	bee.addClick(self.StopButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickStopButton()
	end)
	bee.addClick(self.PurchaseButton, function()
		Game:playSound("ui_button_confirm")
		bee.logEvent("shop-theme-preview-buy", self._curPreviewType == PreviewType.Lobby and 0 or 1)
		self:onClickPurchase()
	end)
	bee.addClick(self.OwnedButton, function()
		UiManager:showToast(_T("TAB_SHOP_THEME_10"))
	end)

	bee.addValueChanged(self.ZoomSlider, function(val)
        local s = val * 1.5 + 0.5
        self.CharacterImage.transform.localScale = bee.v3(s, s, s)
    end, "Slider")
end

function P:onDestroy()
	bee.stopSound("")
    Game:resumeBGM()
end

function P:onStart()
	Game:pauseBGM()
	
	self.data = self._params.data
	self._curPreviewType = PreviewType.Lobby
	self._isPlaying = true

	for k,v in pairs(self.data.items) do
		if v.cfg.type == GPropKind.LobbyScene then
			self.lobbyProp = v.cfg
		elseif v.cfg.type == GPropKind.MusicLobby then
			self.lobbyMusicProp = v.cfg
		elseif v.cfg.type == GPropKind.Table then
			self.tableProp = v.cfg
		elseif v.cfg.type == GPropKind.MusicTable then
			self.tableMusicProp = v.cfg
		end
	end

	self:refreshSwitch()
end

function P:evt_ItemChangeRSP()
	self:setUICont()
end

function P:initLobbyCont()
	if self._lobbyIsInit then
		return
	end
	self._lobbyIsInit = true

	local sceneCfg = tpl_hall_scene[self.lobbyProp.mapId]
	bee.setIcon(self.LobbyImg, sceneCfg.bg_image)

	local s = 1
	bee.setSliderValue(self.ZoomSlider, (s - 0.5) / 1.5)
    self.CharacterImage.transform.localScale = bee.v3(s, s, s)

	bee.invoke(self.CharacterImage, "setRole", CharacterModel:getUsingRole(), false)
end

function P:initTableCont()
	if self._tableIsInit then
		return
	end
	self._tableIsInit = true

    self:initBgPublic()
    self:initTableCard()
    self:initTableBg()
    self:initPlayerInfo()
end

-- 公共牌显示
function P:initBgPublic()
    local card = self:find("PreviewImg", self.BgPublic)
    local cfg = tpl_card[tpl_props[PlayerModel:getCardFace()].mapId]
    bee.setIcon(card, "backpackpreview_" .. cfg.image, "BackpackPreview")
end

-- 手牌显示
function P:initTableCard()
    for i = 1, 6 do
        self:find("ImageButton", self.TableCardList[i]):SetActive(false)

        local cardBackId = PlayerModel:getCurCardBack()
        local cardBack = self:find("BgCard", self.TableCardList[i])
        if i == 3 then
            cardBack:SetActive(false)
            local BgCard1 = self:find("BgCard/BgCard1", self.PlayerHead)
            self:find("BgHandType2", BgCard1):SetActive(false)
            self:find("BgHandType", BgCard1):SetActive(false)
            self:find("ImageWin", BgCard1):SetActive(false)
            self:find("ImageLose", BgCard1):SetActive(false)
            bee.setIconInAtlas(self:find("ImageCard1", BgCard1), tpl_card_back[cardBackId].image)
            bee.setIconInAtlas(self:find("ImageCard2", BgCard1), tpl_card_back[cardBackId].image)
        else
            cardBack:SetActive(true)
            bee.setIcon(self:find("ImageCard1", cardBack), tpl_card_back[cardBackId].preview_res)
            bee.setIcon(self:find("ImageCard2", cardBack), tpl_card_back[cardBackId].preview_res)
        end
    end
end

-- 牌桌显示
function P:initTableBg()
    local tableCfg = tpl_card_table[self.tableProp.mapId]
    bee.setSpriteImg(self.ImageTable, tableCfg.image)
    bee.setSpriteImg(self.ImageBg, tableCfg.bg_image)
end

-- 角色显示
function P:initPlayerInfo()
    local curRole = CharacterModel:getCurRole()
    local showRoleSkin = curRole:getSkinData() or get_tpl_subKey(tpl_character_skin_list, "role", tpl_constdata.DefaultCharacter)[1]

    for i = 1, 6 do
        if i == 3 then
            self:setPlayerInfo(self.PlayerHead, showRoleSkin, i)
        else
            local PlayerOtherObj = CU.GameObject.Instantiate(self.PlayerOther)
            PlayerOtherObj.transform:SetParent(self.SeatNodeList[i].transform)
            PlayerOtherObj.transform.localPosition = bee.v3(0, 0, 0)
            PlayerOtherObj.transform.localScale = self.PlayerOther.transform.localScale
            PlayerOtherObj:SetActive(true)
            self:setPlayerInfo(PlayerOtherObj, showRoleSkin, i)
        end
    end
end

function P:setPlayerInfo(playerItem, showRoleSkin, index)
    local isMe = index == 3
    self:find("BgFold", playerItem):SetActive(false)
    self:find("BgBet", playerItem):SetActive(false)
    self:find("BgChat", playerItem):SetActive(false)
    self:find("Eff_Countdown", playerItem):SetActive(false)
    self:find("BgStatus", playerItem):SetActive(false)
    self:find("BgRole/BgName/ImageUserType", playerItem):SetActive(false)
    self:find("BgRole/Eff_poker_role_sg", playerItem):SetActive(false)
    self:find("ImageTag", playerItem):SetActive(false)

    local ImageRole = self:find("BgRole/Ani_role/ImageRole", playerItem)
    local BgAllin = self:find("BgRole/BgAllin", playerItem)
    local ImageLevel = self:find("BgRole/BgName/ImageLevel", playerItem)
    local TextName = self:find("BgRole/BgName/TextName", playerItem)
    local ImageTitle = self:find("BgRole/ImageTitle", playerItem)
    local ImageUerType = self:find("BgRole/BgName/ImageUserType", playerItem)
    local ImageFg = self:find("BgRole/ImageFg", playerItem)
    local TextChip = self:find("BgRole/BgChip/TextChip", playerItem)
    local TextChipPurple = self:find("BgRole/BgChip/TextChipPurple", playerItem)
    local TextChipGreen = self:find("BgRole/BgChip/TextChipGreen", playerItem)
    local TextChipBlue = self:find("BgRole/BgChip/TextChipBlue", playerItem)

    self:setRoleImg(ImageRole, showRoleSkin, isMe)
    if isMe then
        bee.setTextCut(TextName, PlayerModel:getName(), 460)
    else
        bee.setTextCut(TextName, _T("LAB_COMMON_1"), 460)
    end
    bee.setText(TextChip, _N(PlayerModel:getGold()))
    bee.setIcon(ImageLevel, tpl_level[PlayerModel:getCurLevel()].icon)

    if self._cfg and self._cfg.type == GPropKind.Title then
        ImageTitle:SetActive(true)
        bee.setIconInAtlas(ImageTitle, self._cfg.icon, true)
    else
        GF.setTitleImage(ImageTitle, PlayerModel:getTitle(), true, true)
    end

    local nameplateEffId = PlayerModel:getNameplateEff()
    if self._cfg and self._cfg.type == GPropKind.NameplateEff then
        nameplateEffId = self._cfg.id
    end

    if index == 5 then
        -- 主播
        ImageUerType:SetActive(true)
        bee.setIcon(ImageUerType, "InGame[ingame_player_other02_streamer]")
        bee.setIcon(ImageFg, "InGame[ingame_player_other_fg_02]")
        bee.setTextCut(TextName, _T("LAB_BACKPACK_DES_40"), 460)
        TextChipPurple:SetActive(false)
        TextChipGreen:SetActive(false)
        TextChipBlue:SetActive(true)
        bee.setText(TextChipBlue, _N(PlayerModel:getGold()))
        AnimationMgr:playUIEffect(GameModel:getAllinEffectName(USER_TYPE.Streamer + 1, nameplateEffId), BgAllin.transform, nil, -1)
    elseif index == 1 then
        -- 开发者
        ImageUerType:SetActive(true)
        bee.setIcon(ImageUerType, "InGame[ingame_player_other03_developer]")
        bee.setIcon(ImageFg, "InGame[ingame_player_other_fg_01]")
        bee.setTextCut(TextName, _T("LAB_BACKPACK_DES_39"), 460)
        TextChipPurple:SetActive(false)
        TextChipGreen:SetActive(true)
        TextChipBlue:SetActive(false)
        bee.setText(TextChipGreen, _N(PlayerModel:getGold()))
        AnimationMgr:playUIEffect(GameModel:getAllinEffectName(USER_TYPE.Developer + 1, nameplateEffId), BgAllin.transform, nil, -1)
    else
        ImageUerType:SetActive(false)
        if isMe then
            bee.setTextCut(TextName, PlayerModel:getName(), 460)
            bee.setText(TextChip, _N(PlayerModel:getGold()))
            AnimationMgr:playUIEffect(GameModel:getAllinEffectName(0, nameplateEffId), BgAllin.transform, nil, -1)
        else
            TextChipGreen:SetActive(false)
            TextChipBlue:SetActive(false)
            TextChipPurple:SetActive(true)
            bee.setText(TextChipPurple, _N(PlayerModel:getGold()))
            bee.setTextCut(TextName, _T("LAB_COMMON_1"), 460)
            AnimationMgr:playUIEffect(GameModel:getAllinEffectName(USER_TYPE.Normal + 1, nameplateEffId), BgAllin.transform, nil, -1)
        end
    end
end

function P:setRoleImg(ImageRole, showRoleSkin, isMe)
    local table_avatar = showRoleSkin.table_avatar or showRoleSkin.table_avatar_pic
    if string.find(table_avatar, "/") then
        self._roleSpine = bee.createObj(table_avatar)
        self._roleSpine.transform:SetParent(ImageRole.transform, false)
        ImageRole:GetComponent("Image").enabled = false
        if not isMe then
            self._roleSpine.transform.localScale = Config.ROLE_OTHER_SCALE
        end
        local sp = self:find("Mask", self._roleSpine).transform:GetChild(0).gameObject
        bee.invoke(sp, "setHideAttachments", showRoleSkin.id)
    else
        bee.setIcon(ImageRole, table_avatar)
        ImageRole:GetComponent("Image").enabled = true
    end
end

function P:setUICont()
	if self._curPreviewType == PreviewType.Lobby then
		bee.setText(self.NameText, _T(self.lobbyProp.name))
		self:setMusicCont(self.lobbyMusicProp)
	else
		bee.setText(self.NameText, _T(self.tableProp.name))
		self:setMusicCont(self.tableMusicProp)
	end

	if ShopModel:getThemeIsOwn(self.data.id) then
		self.OwnedButton:SetActive(true)
		self.PurchaseButton:SetActive(false)
		self.Discount:SetActive(false)
	else
		self.OwnedButton:SetActive(false)
		self.PurchaseButton:SetActive(true)
		self.Discount:SetActive(true)
		-- 价格
		bee.setIconInAtlas(self.OriPriIcon, tpl_props[self.data.consumeId].icon)
		bee.setIconInAtlas(self.CurPriIcon, tpl_props[self.data.consumeId].icon)
		bee.setText(self.OriPriText, self.data.oriPri)
		bee.setText(self.CurPriText, self.data.pri)
		bee.setText(self.DiscountText, ((1000 - self.data.discount) / 10) .. "%")
	end

	bee.setIconInAtlas(self.Icon, tpl_props[self.data.consumeId].icon)
	bee.setText(self.CountText, ItemModel:getItemNumById(self.data.consumeId))
end

function P:setMusicCont(cfg)
	bee.setText(self.BgmNameText, _F("TAB_SHOP_THEME_NAME_" .. cfg.type, _T(cfg.name)))

	self.audioPath = tpl_sound[tostring(cfg.mapId)].path
	self.audio = ResManager:GetSound(self.audioPath)

	bee.stopSoundByIndex(self._playIndex)
	if self._isPlaying then
		self._playIndex = bee.playSound(self.audioPath)
		self._playingPath = self.audioPath
	end
	self:startToPlay()
end

function P:onClickLobby()
	if self._curPreviewType == PreviewType.Lobby then
		return
	end
	bee.logEvent("shop-theme-preview-switch", 0)
	self._curPreviewType = PreviewType.Lobby
	bee.stopSoundByIndex(self._playIndex)
	self:refreshSwitch()
end

function P:onClickTable()
	if self._curPreviewType == PreviewType.Table then
		return
	end
	bee.logEvent("shop-theme-preview-switch", 1)
	self._curPreviewType = PreviewType.Table
	bee.stopSoundByIndex(self._playIndex)
	self:refreshSwitch()
end

function P:refreshSwitch()
	self:find("On", self.LobbyButton):SetActive(self._curPreviewType == PreviewType.Lobby)
	self:find("Off", self.LobbyButton):SetActive(self._curPreviewType ~= PreviewType.Lobby)
	self:find("On", self.TableButton):SetActive(self._curPreviewType == PreviewType.Table)
	self:find("Off", self.TableButton):SetActive(self._curPreviewType ~= PreviewType.Table)

	if self._curPreviewType == PreviewType.Lobby then
		self:initLobbyCont()
		self:setUICont()
		self.LobbyCont:SetActive(true)
		self.PKTable3D:SetActive(false)
	else
		self:initTableCont()
		self:setUICont()
		self.LobbyCont:SetActive(false)
		self.PKTable3D:SetActive(true)
	end
end

function P:onClickPlayButton()
	self.StopButton:SetActive(true)
	self.PlayButton:SetActive(false)
	self._isPlaying = true
	bee.unPauseSound(self._playIndex)

	if self._audioPath ~= self._playingPath then
		self._playIndex = bee.playSound(self.audioPath)
		self._playingPath = self.audioPath
	end

	self:startToPlay()
end

function P:onClickStopButton()
	self.StopButton:SetActive(false)
	self.PlayButton:SetActive(true)
	self._isPlaying = false
	bee.pauseSound(self._playIndex)

	self:stopToPlay()
end

function P:_stopAct()
    if self._loopAct then
        self._loopAct:kill()
        self._loopAct = nil
    end
end

function P:startToPlay()
    self:_stopAct()
    self._loopAct = bee.tween(self.BgmIcon)
    : by(30, {rotate = bee.v3(0, 0, -360)}, {rotate = DT.RotateMode.FastBeyond360})
    : ease(DT.Ease.Linear)
    : loop(-1)
    : link()
end

function P:stopToPlay()
    self:_stopAct()
end

function P:onDrag(e)
    local pos = self.CharacterImage.transform.localPosition
    pos.x, pos.y = pos.x + e.delta.x, pos.y + e.delta.y
    self.CharacterImage.transform.localPosition = pos
end

function P:onClickPurchase()
	UiManager:showUI("ShopPurchaseTheme", {data = self.data})
end

return P