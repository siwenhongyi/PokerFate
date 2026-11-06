local P = class("DecorationDetails", UiFullView)

function P:onAwake()
    self.ItemType = {
        Role = 1,
        Title = 2,
        BackGround = 3,
        Face = 4,
        CardBack = 5,
        Allin = 6,
        NameCard = 7,
        OpenCard = 8,
        Music = 9,
        Emoji = 10,
        Avatar = 11,
        Frame = 12,
    }
    self.sltedType = nil

    self.BackButton = self:find("AnimRoot/LeftTop/BackButton")

    local Center = self:find("AnimRoot/Center")
    self.SchemeNameGo = self:find("SchemeName", Center)
    self.SchemeName = self:find("Name", self.SchemeNameGo)
    self.EditButton = self:find("EditButton", self.SchemeNameGo)
    local Left = self:find("LeftList", Center)
    self.ItemDic = {}
    self.CharacterItem = {}
    self.CharacterItem.btn = self:find("Character", Left)
    self.CharacterItem.icon = self:find("Character/avatar_frame_01_mask/icon", Left)
    self.CharacterItem.slt = self:find("Character/selected", Left)
    bee.addClick(self.CharacterItem.btn, function() self:changeEditor(self.ItemType.Role) end, true)
    self.ItemDic[self.ItemType.Role] = self.CharacterItem
    self.TitleItem = self:initIconItem("Title", Left, self.ItemType.Title)
    self.TitleItem.defIcon = self:find("Title/defIcon", Left)
    self.AvatarItem = {}
    self.AvatarItem.btn = self:find("Avatar", Left)
    self.AvatarItem.icon = self:find("Avatar/avatar_frame_01_mask/icon", Left)
    self.AvatarItem.slt = self:find("Avatar/selected", Left)
    bee.addClick(self.AvatarItem.btn, function() self:changeEditor(self.ItemType.Avatar) end, true)
    self.ItemDic[self.ItemType.Avatar] = self.AvatarItem
    self.FrameItem = self:initIconItem("Frame", Left, self.ItemType.Frame)
    self.FrameItem.defIcon = self:find("Frame/deficon", Left)
    self.TableItem = self:initIconItem("Table", Left, self.ItemType.BackGround)
    self.FaceItem = self:initIconItem("Face", Left, self.ItemType.Face)
    self.BackItem = self:initIconItem("Back", Left, self.ItemType.CardBack)
    self.AllInItem = self:initIconItem("AllIn", Left, self.ItemType.Allin)
    self.NameplateItem = self:initIconItem("Nameplate", Left, self.ItemType.NameCard)
    self.OpencardItem = self:initIconItem("Opencard", Left, self.ItemType.OpenCard)
    self.MusicItem = self:initIconItem("Music", Left, self.ItemType.Music)
    self.MusicItem.cycle = self:find("Music/Cycle", Left)
    self.MusicItem.random = self:find("Music/Random", Left)
    self.MusicItem.count = self:find("Music/Value", Left)
    self.EmojisItem = self:initIconItem("Emojis", Left, self.ItemType.Emoji)
    self.EmojisItem.empty = self:find("Emojis/decoration_emoji_empty", Left)

    self.Buttons = self:find("Buttons", Center)
    self.SaveAndUseButton = self:find("Buttons/SaveAndUse", Center)
    self.SaveOnlyButton = self:find("Buttons/SaveOnly", Center)
    self.UseButton = self:find("UseButton", Center)
    self.SaveButton = self:find("SaveButton", Center)
    self.Using = self:find("Using", Center)

    self.ItemName = self:find("ItemName", Center)
    self.TipButton = self:find("TipButton", self.ItemName)
    self.Tips = self:find("Tips", Center)
    self.MusicRandomButton = self:find("MusicRandomButton", Center)
    self.MusicCircleButton = self:find("MusicCircleButton", Center)
    self.ViewButton = self:find("ViewButton", Center)
    self.ChooseToggle = self:find("ChooseToggle", Center)
    self.ItemScroll = self:find("ItemScroll", Center)

    local itemRoot = self:find("Items", Center)
    itemRoot:SetActive(false)
    self.BaseCharacter = self:find("Character", itemRoot)
    self.BaseTitle = self:find("Title", itemRoot)
    self.BaseAvatar = self:find("Avatar", itemRoot)
    self.BaseFrame = self:find("Frame", itemRoot)
    self.BaseTable = self:find("Table", itemRoot)
    self.BaseFace = self:find("Face", itemRoot)
    self.BaseBack = self:find("Back", itemRoot)
    self.BaseAllIn = self:find("AllIn", itemRoot)
    self.BaseNameplate = self:find("Nameplate", itemRoot)
    self.Opencard = self:find("Opencard", itemRoot)
    self.BaseMusic = self:find("Music", itemRoot)
    self.BaseEmoji = self:find("Emoji", itemRoot)
    self.BaseItemDis = {
        [self.ItemType.Role] = self.BaseCharacter,
        [self.ItemType.Title] = self.BaseTitle,
        [self.ItemType.BackGround] = self.BaseTable,
        [self.ItemType.Face] = self.BaseFace,
        [self.ItemType.CardBack] = self.BaseBack,
        [self.ItemType.Allin] = self.BaseAllIn,
        [self.ItemType.NameCard] = self.BaseNameplate,
        [self.ItemType.OpenCard] = self.BaseFace,
        [self.ItemType.Music] = self.BaseMusic,
        [self.ItemType.Emoji] = self.BaseEmoji,
        [self.ItemType.Avatar] = self.BaseAvatar,
        [self.ItemType.Frame] = self.BaseFrame,
    }
    self.sltedId = 0
    self.sltedMusicId = 0
    self.sltedEmojiId = 0

    bee.addClick(self.BackButton, function ()
        Game:playSound("ui_button_confirm")
        self:onClickClose()
    end)
    bee.addClick(self.SchemeNameGo, function ()
        Game:playSound("ui_button_confirm")
        self:showEditorNamePanel()
    end)
    bee.addClick(self.EditButton, function ()
        Game:playSound("ui_button_confirm")
        self:showEditorNamePanel()
    end)

    bee.addClick(self.MusicRandomButton, function()
        Game:playSound("ui_tab_switch_1")
        self:MusicRandomToCircle()
    end)
    bee.addClick(self.MusicCircleButton, function()
        Game:playSound("ui_tab_switch_1")
        self:MusicCircleToRandom()
    end)
    bee.addClick(self.ViewButton, function()
        Game:playSound("ui_button_confirm")
        self:ViewEvent()
    end)
    bee.addClick(self.ChooseToggle, function()
        Game:playSound("ui_tab_switch_1")
        self:ChooseEvent()
    end)

    bee.addClick(self.SaveOnlyButton, function ()
        Game:playSound("ui_button_confirm")
        self:SaveEvent()
    end)
    bee.addClick(self.SaveButton, function ()
        Game:playSound("ui_button_confirm")
        self:SaveEvent()
    end)
    bee.addClick(self.SaveAndUseButton, function ()
        Game:playSound("ui_button_confirm")
        DecorationModel._ingame_scheme_use = true
        self:SaveEvent()
    end)

    bee.addClick(self.TipButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonTextTipUD", {text = _T("LAB_DECOR_PLAN_16"), target = self.TipButton})
        bee.logEvent("style-preset-emotes-tips")
    end)
end

function P:onShow()
    self.baseScheme = self._params and self._params.scheme or DecorationModel:getDefaultInGameScheme()
    self.subType = self._params and self._params.subType or 1
    self.scheme = clone(self.baseScheme)
    bee.setText(self.SchemeName, self.scheme.name)
    self:setEditorPos()
    self:refreshLeftUI()
    self:refreshButtons()

    self:initItemScroll()
    self:changeEditor(self.subType)
end

function P:initIconItem(path, root, itemType)
    local item = {}
    item.btn = self:find(path, root)
    item.icon = self:find(path .. "/icon", root)
    item.slt = self:find(path .. "/selected", root)
    bee.addClick(item.btn, function() self:changeEditor(itemType) end, true)
    self.ItemDic[itemType] = item
    return item
end

function P:initItemScroll()
    self.rowCount3 = 3
	self.rowPos3 = {-310, 0, 310}

	self.rowCount5 = 5
	self.rowPos5 = {}
	for i = 1, self.rowCount5 do
		table.insert(self.rowPos5, ((i - 1) * 190) - 380)
	end

	self.itemScroll = UiListEx:create(self.ItemScroll)
	self.itemScroll:setCreateFunc(function()
		local item = CU.GameObject.Instantiate(self.BaseItemDis[self.sltedType])
		item.gameObject:SetActive(true)
		return item
	end)
	self.itemScroll:setRefreshFunc(function(data, item)
		self:setPropItemShow(item, data)
	end)
end

function P:showEditorNamePanel()
    UiManager:showUI("DecorationPanel", {id = self.scheme.scheme_id, name = self.scheme.name})
end

function P:refreshLeftUI()
    local data = self.scheme
    local skinCfg = tpl_character_skin[data.skin_id[1]]
	ItemModel:setItemIcon(self.CharacterItem.icon, skinCfg.avatar)
    local titleId = data.title and data.title[1] or 0
    if titleId == nil or titleId == 0 then
        self.TitleItem.icon:SetActive(false)
        self.TitleItem.defIcon:SetActive(true)
    else
        self.TitleItem.icon:SetActive(true)
        self.TitleItem.defIcon:SetActive(false)
        ItemModel:setItemIcon(self.TitleItem.icon, titleId)
    end
    ItemModel:setItemIcon(self.AvatarItem.icon, data.avatar)
    if data.frame == nil or data.frame == 0 then
        self.FrameItem.icon:SetActive(false)
    else
        self.FrameItem.icon:SetActive(true)
        ItemModel:setItemIcon(self.FrameItem.icon, data.frame)
    end
    ItemModel:setItemIcon(self.TableItem.icon, data.table[1])
    ItemModel:setItemIcon(self.FaceItem.icon, data.card_front[1])
    ItemModel:setItemIcon(self.BackItem.icon, data.card_back[1])
    ItemModel:setItemIcon(self.AllInItem.icon, data.all_in_animation[1])
    ItemModel:setItemIcon(self.NameplateItem.icon, data.show_card[1])
    ItemModel:setItemIcon(self.OpencardItem.icon, data.open_card[1])

	local musicList = data.bgm_list
	local musicId = tpl_props[musicList[1]].mapId
	local musicCfg = tpl_sound[tostring(musicId)]
	bee.setIconInAtlas(self.MusicItem.icon, musicCfg.cd_image)
	bee.setText(self.MusicItem.count, #musicList)
    local musicType = data.rand % 2
    self.MusicItem.cycle:SetActive(musicType == 0)
    self.MusicItem.random:SetActive(musicType == 1)

    if data.emojis and #data.emojis > 0 then
        self.EmojisItem.icon:SetActive(true)
        self.EmojisItem.empty:SetActive(false)
        bee.setIconInAtlas(self.EmojisItem.icon, tpl_emoji[data.emojis[1]].emoji)
    else
        self.EmojisItem.icon:SetActive(false)
        self.EmojisItem.empty:SetActive(true)
    end
end

--编辑种类变动
function P:changeEditor(type)
    for k,v in pairs(self.ItemDic) do
        v.slt:SetActive(k == type)
    end

    self.itemScroll:moveToYItem(1, false)
    self.itemScroll:clear()
    -- self.itemScroll:clearCaches()
    if type == self.ItemType.Role then
        self:onClickRole()
    elseif type == self.ItemType.Title then
        self:onClickTitle()
    elseif type == self.ItemType.Avatar then
        self:onClickAvatar()
    elseif type == self.ItemType.Frame then
        self:onClickFrame()
    elseif type == self.ItemType.BackGround then
        self:onClickBackGround()
    elseif type == self.ItemType.Face then
        self:onClickFace()
    elseif type == self.ItemType.CardBack then
        self:onClickCardBack()
    elseif type == self.ItemType.Allin then
        self:onClickAllin()
    elseif type == self.ItemType.NameCard then
        self:onClickNameCard()
    elseif type == self.ItemType.OpenCard then
        self:onClickOpenCard()
    elseif type == self.ItemType.Music then
        self:onClickMusic()
    elseif type == self.ItemType.Emoji then
        self:onClickEmoji()
    end
    self:setItemName()

    self.TipButton:SetActive(type == self.ItemType.Emoji)
end
--角色
function P:onClickRole()
    self:switchViewBtn()
    self:setItemListRowPos(5)
    self.sltedType = self.ItemType.Role
    self:setSkinDatas()
end
function P:setSkinDatas()
    local ownedRoleList = CharacterModel:getOwnedCharacters()
    local ownedList = {}
    for _,v in pairs(ownedRoleList) do
        for _,sv in pairs(v.skin_info.owned_skin_ids) do
            table.insert(ownedList, {id = sv, __kind = "skin"})
        end
    end
    table.sort(ownedList, function(a, b) return a.id < b.id end)
    self.sltedId = self.scheme.skin_id[1]
	self.itemScroll:setDatas(ownedList)
    self:setItemName()
end
--称号
function P:onClickTitle()
    self:switchViewBtn()
    self:setItemListRowPos(3, 132)
    self.sltedType = self.ItemType.Title
    self:setTitleDatas()
end
function P:setTitleDatas()
    local ownedList = self:getDatas(GPropKind.Title)
	table.insert(ownedList, 1, {id = 0, __kind = "title"})
    self.sltedId = self.scheme.title and self.scheme.title[1] or 0
	self.itemScroll:setDatas(ownedList)
    self:setItemName()
end
--头像
function P:onClickAvatar()
    self:switchViewBtn()
    self:setItemListRowPos(5)
    self.sltedType = self.ItemType.Avatar
    self:setAvatarDatas()
end
function P:setAvatarDatas()
    local ownedRoleList = CharacterModel:getOwnedCharacters()
    local ownedList = {}
    for _,v in pairs(ownedRoleList) do
        for _,sv in pairs(v.skin_info.owned_skin_ids) do
            local avatarId = tpl_character_skin[sv].avatar
            table.insert(ownedList, {id = avatarId, __kind = "avatar"})
        end
    end
    table.sort(ownedList, function(a, b) return a.id < b.id end)
    self.sltedId = self.scheme.avatar
	self.itemScroll:setDatas(ownedList)
    self:setItemName()
end
--头像框
function P:onClickFrame()
    self:switchViewBtn()
    self:setItemListRowPos(5)
    self.sltedType = self.ItemType.Frame
    self:setFrameDatas()
end
function P:setFrameDatas()
    local ownedList = self:getDatas(GPropKind.FrameAvatar)
    self.sltedId = self.scheme.frame or 0
    local cloneOwnedList = clone(ownedList)
    table.insert(cloneOwnedList, 1, {id = 0, __kind = GPropKind.FrameAvatar})
	self.itemScroll:setDatas(cloneOwnedList)
    self:setItemName()
end
--背景
function P:onClickBackGround()
    self:switchViewBtn()
    self:setItemListRowPos(5)
    self.sltedType = self.ItemType.BackGround
    self:setBackGroundDatas()
end
function P:setBackGroundDatas()
    local ownedList = self:getDatas(GPropKind.Table)
    self.sltedId = self.scheme.table[1]
	self.itemScroll:setDatas(ownedList)
    self:setItemName()
end
--牌面
function P:onClickFace()
    self:switchViewBtn()
    self:setItemListRowPos(5)
    self.sltedType = self.ItemType.Face
    self:setFaceDatas()
end
function P:setFaceDatas()
    local ownedList = self:getDatas(GPropKind.CardFace)
    self.sltedId = self.scheme.card_front[1]
	self.itemScroll:setDatas(ownedList)
    self:setItemName()
end
--牌背
function P:onClickCardBack()
    self:switchViewBtn()
    self:setItemListRowPos(5)
    self.sltedType = self.ItemType.CardBack
    self:setCardBackDatas()
end
function P:setCardBackDatas()
    local ownedList = self:getDatas(GPropKind.CardBack)
    self.sltedId = self.scheme.card_back[1]
	self.itemScroll:setDatas(ownedList)
    self:setItemName()
end
--allin
function P:onClickAllin()
    self:switchViewBtn()
    self:setItemListRowPos(5)
    self.sltedType = self.ItemType.Allin
    self:setAllinDatas()
end
function P:setAllinDatas()
    local ownedList = self:getDatas(GPropKind.AllInEff)
    self.sltedId = self.scheme.all_in_animation[1]
	self.itemScroll:setDatas(ownedList)
    self:setItemName()
end
--铭牌
function P:onClickNameCard()
    self:switchViewBtn()
    self:setItemListRowPos(5)
    self.sltedType = self.ItemType.NameCard
    self:setNameCardDatas()
end
function P:setNameCardDatas()
    local ownedList = self:getDatas(GPropKind.NameplateEff)
    self.sltedId = self.scheme.show_card[1]
	self.itemScroll:setDatas(ownedList)
    self:setItemName()
end
-- allin 秀牌
function P:onClickOpenCard()
    self:switchViewBtn()
    self:setItemListRowPos(5)
    self.sltedType = self.ItemType.OpenCard
    self:setOpenCardDatas()
end
function P:setOpenCardDatas()
    local ownedList = self:getDatas(GPropKind.AllinShowEff)
    self.sltedId = self.scheme.open_card[1]
	self.itemScroll:setDatas(ownedList)
    self:setItemName()
end
--音乐
function P:onClickMusic()
    self:switchMusicBtn()
    self:setItemListRowPos(5)
    self.sltedType = self.ItemType.Music
    self:switchChooseBtn()
    self:setMusicDatas()
end
function P:setMusicDatas()
    local ownedList = ItemModel:getAllShowItems(9, true)
    if self.sltedMusicId == 0 then
        self.sltedMusicId = self.scheme.bgm_list[1]
    end
    for _, v in ipairs(ownedList) do
        v.__kind = "music"
    end
	self.itemScroll:setDatas(ownedList)
    self:setItemName()
end
--表情
function P:onClickEmoji()
    self:setItemListRowPos(5)
    self.sltedType = self.ItemType.Emoji
    self:setEmojiDatas()
    self:switchEmojiBtn()
end
function P:setEmojiDatas()
    local unlockList = DecorationModel:getAllUnlockEmoji()
    self.sltedId = self.scheme.emojis and self.scheme.emojis[1] or unlockList[1].id
    -- if self.sltedId == nil then
    --     self.sltedId = 
    -- end
    for _, v in ipairs(unlockList) do
        v.__kind = "emoji"
    end
    self.itemScroll:setDatas(unlockList)
    self:setItemName()
end

--设置道具名
function P:setItemName()
    if self.sltedType == self.ItemType.Role then
        local skinCfg = tpl_character_skin[self.sltedId]
        local roleCfg = tpl_character[skinCfg.role]
        local name = _F("LAB_DECOR_PLAN_28", _T(roleCfg.name), _T(skinCfg.name))
        bee.setText(self.ItemName, name)
    elseif self.sltedType == self.ItemType.Avatar then
        bee.setText(self.ItemName, _F("LAB_DECOR_PLAN_34", _T(tpl_props[self.sltedId].name)))
    elseif self.sltedType == self.ItemType.Frame then
        if self.sltedId == 0 then
            bee.setText(self.ItemName, _T("LAB_DECOR_PLAN_35"))
        else
            bee.setText(self.ItemName, _T(tpl_props[self.sltedId].name))
        end
    elseif self.sltedType == self.ItemType.Emoji then
        local count = self.scheme.emojis and #self.scheme.emojis or 0
        bee.setText(self.ItemName, _F("LAB_DECOR_PLAN_15", count, DecorationModel.MaxEmojiCount))
    elseif self.sltedType == self.ItemType.Title then
        if self.sltedId == 0 or self.sltedId == nil then
            bee.setText(self.ItemName, _T("LAB_DECOR_PLAN_27"))
        else
            bee.setText(self.ItemName, _T(tpl_props[self.sltedId].name))
        end
    elseif self.sltedType == self.ItemType.Music then
        bee.setText(self.ItemName, _T(tpl_props[self.sltedMusicId].name))
    elseif tpl_props[self.sltedId] then
        bee.setText(self.ItemName, _T(tpl_props[self.sltedId].name))
    else
        bee.setText(self.ItemName, "")
    end
end


function P:switchViewBtn()
    self.ViewButton:SetActive(true)
    self.ChooseToggle:SetActive(false)
    self.MusicRandomButton:SetActive(false)
    self.MusicCircleButton:SetActive(false)
end
function P:switchMusicBtn()
    self.ViewButton:SetActive(true)
    self.ChooseToggle:SetActive(true)
    self:switchMusicBtn2()
end
function P:switchMusicBtn2()
    local musicType = self.scheme.rand % 2
    self.MusicRandomButton:SetActive(musicType == 1)
    self.MusicCircleButton:SetActive(musicType == 0)

    self:switchChooseBtn()
end
function P:switchEmojiBtn()
    self.ViewButton:SetActive(false)
    self.ChooseToggle:SetActive(true)
    self.MusicRandomButton:SetActive(false)
    self.MusicCircleButton:SetActive(false)

    self:switchChooseBtn()
end

function P:setItemListRowPos(num, width)
	if num == 3 then
		self.itemScroll:setRowCount(self.rowCount3)
		self.itemScroll:setRowPostions(self.rowPos3)
	elseif num == 5 then
		self.itemScroll:setRowCount(self.rowCount5)
		self.itemScroll:setRowPostions(self.rowPos5)
	end
	self.itemScroll:setWidth(width or 172)
    self.itemScroll:setTopBottom(10, 0)
end

function P:getDatas(kind)
    local ct = bee.getServerTime()
    local datas = {}
    local tbs = get_tpl_subKey(tpl_props_list, "type", kind)
    for _, v in ipairs(tbs) do
        local d = ItemModel:getItem(v.id)
        if d and d.bagShow == 1 and (not d.time_start or d.time_start <= ct or PlayerModel:isEventWhite() or bee.isDev) then
            d.__kind = kind
            table.insert(datas, d)
        end
    end
    return datas
end

--设置Item
function P:setPropItemShow(item, data)
    if self.sltedType == self.ItemType.Role then
        self:setRoleItemShow(item, data)
    elseif self.sltedType == self.ItemType.Title then
        self:setTitleItemShow(item, data)
    elseif self.sltedType == self.ItemType.Avatar then
        self:setAvatarItemShow(item, data)
    elseif self.sltedType == self.ItemType.Frame then
        self:setFrameItemShow(item, data)
    elseif self.sltedType == self.ItemType.BackGround then
        self:setBackGroundItemShow(item, data)
    elseif self.sltedType == self.ItemType.Face then
        self:setFaceItemShow(item, data)
    elseif self.sltedType == self.ItemType.CardBack then
        self:setCardBackItemShow(item, data)
    elseif self.sltedType == self.ItemType.Allin then
        self:setAllInItemShow(item, data)
    elseif self.sltedType == self.ItemType.NameCard then
        self:setNameCardItemShow(item, data)
    elseif self.sltedType == self.ItemType.OpenCard then
        self:setOpenCardItemShow(item, data)
    elseif self.sltedType == self.ItemType.Music then
        self:setMusicItemShow(item, data)
    elseif self.sltedType == self.ItemType.Emoji then
        self:setEmojiItemShow(item, data)
    end
end
--角色
function P:setRoleItemShow(item, data)
    local icon = self:find("avatar_frame_01_mask/icon", item)
    bee.setIcon(icon, tpl_props[tpl_character_skin[data.id].avatar].icon)
    local slted = self:find("decoration_avatar_selected", item)
    slted:SetActive(data.id == self.sltedId)
    bee.addClick(item, function ()
        if data.id ~= self.sltedId then
            self.sltedId = data.id
            self.scheme.skin_id = {data.id}
            self:refreshLeftUI()
            self:setSkinDatas()
            self:setItemName()
        end
    end, true)
end
--标题
function P:setTitleItemShow(item, data)
    local icon = self:find("icon", item)
    local defIcon = self:find("defIcon", item)
    if data.id == 0 then
        icon:SetActive(false)
        defIcon:SetActive(true)
    else
        icon:SetActive(true)
        defIcon:SetActive(false)
        bee.setIcon(icon, tpl_props[data.id].icon)
    end
    local slted = self:find("selected", item)
    slted:SetActive(data.id == self.sltedId)
    bee.addClick(item, function ()
        if data.id ~= self.sltedId then
            self.sltedId = data.id
            self.scheme.title = {data.id}
            self:refreshLeftUI()
            self:setTitleDatas()
        end
    end, true)
end
--头像
function P:setAvatarItemShow(item, data)
    local icon = self:find("avatar_frame_01_mask/icon", item)
    bee.setIcon(icon, tpl_props[data.id].icon)
    local slted = self:find("selected", item)
    slted:SetActive(data.id == self.sltedId)
    bee.addClick(item, function ()
        if data.id ~= self.sltedId then
            self.sltedId = data.id
            self.scheme.avatar = data.id
            self:refreshLeftUI()
            self:setAvatarDatas()
        end
    end, true)
end
--头像框
function P:setFrameItemShow(item, data)
    local icon = self:find("icon", item)
    local defIcon = self:find("defIcon", item)
    if data.id == 0 then
        icon:SetActive(false)
        defIcon:SetActive(true)
    else
        icon:SetActive(true)
        defIcon:SetActive(false)
        bee.setIcon(icon, tpl_props[data.id].icon)
    end
    local slted = self:find("selected", item)
    slted:SetActive(data.id == self.sltedId)
    bee.addClick(item, function ()
        if data.id ~= self.sltedId then
            self.sltedId = data.id
            self.scheme.frame = data.id
            self:refreshLeftUI()
            self:setFrameDatas()
        end
    end, true)
end

--背景
function P:setBackGroundItemShow(item, data)
    local icon = self:find("icon", item)
    bee.setIcon(icon, tpl_props[data.id].icon)
    local slted = self:find("selected", item)
    slted:SetActive(data.id == self.sltedId)
    bee.addClick(item, function ()
        if data.id ~= self.sltedId then
            self.sltedId = data.id
            self.scheme.table = {data.id}
            self:refreshLeftUI()
            self:setBackGroundDatas()
        end
    end, true)
end
--牌面
function P:setFaceItemShow(item, data)
    local icon = self:find("icon", item)
    bee.setIcon(icon, tpl_props[data.id].icon)
    local slted = self:find("selected", item)
    slted:SetActive(data.id == self.sltedId)
    bee.addClick(item, function ()
        if data.id ~= self.sltedId then
            self.sltedId = data.id
            self.scheme.card_front = {data.id}
            self:refreshLeftUI()
            self:setFaceDatas()
        end
    end, true)
end
--牌背
function P:setCardBackItemShow(item, data)
    local icon = self:find("icon", item)
    bee.setIcon(icon, tpl_props[data.id].icon)
    local slted = self:find("selected", item)
    slted:SetActive(data.id == self.sltedId)
    bee.addClick(item, function ()
        if data.id ~= self.sltedId then
            self.sltedId = data.id
            self.scheme.card_back = {data.id}
            self:refreshLeftUI()
            self:setCardBackDatas()
        end
    end, true)
end
--Allin
function P:setAllInItemShow(item, data)
    local icon = self:find("icon", item)
    bee.setIcon(icon, tpl_props[data.id].icon)
    local slted = self:find("selected", item)
    slted:SetActive(data.id == self.sltedId)
    bee.addClick(item, function ()
        if data.id ~= self.sltedId then
            self.sltedId = data.id
            self.scheme.all_in_animation = {data.id}
            self:refreshLeftUI()
            self:setAllinDatas()
        end
    end, true)
end
--铭牌
function P:setNameCardItemShow(item, data)
    local icon = self:find("icon", item)
    bee.setIcon(icon, tpl_props[data.id].icon)
    local slted = self:find("selected", item)
    slted:SetActive(data.id == self.sltedId)
    bee.addClick(item, function ()
        if data.id ~= self.sltedId then
            self.sltedId = data.id
            self.scheme.show_card = {data.id}
            self:refreshLeftUI()
            self:setNameCardDatas()
        end
    end, true)
end
--allin 秀牌
function P:setOpenCardItemShow(item, data)
    local icon = self:find("icon", item)
    bee.setIcon(icon, tpl_props[data.id].icon)
    local slted = self:find("selected", item)
    slted:SetActive(data.id == self.sltedId)
    bee.addClick(item, function ()
        if data.id ~= self.sltedId then
            self.sltedId = data.id
            self.scheme.open_card = {data.id}
            self:refreshLeftUI()
            self:setOpenCardDatas()
        end
    end, true)
end
--音乐
function P:setMusicItemShow(item, data)
    local icon = self:find("icon", item)
    bee.setIcon(icon, tpl_props[data.id].icon)
    local slted = self:find("common_item_grid_m_selected", item)
    slted:SetActive(data.id == self.sltedMusicId)
    local index = table.keyof(self.scheme.bgm_list, data.id)
    local sltIcon = self:find("SelectToggle/lobby_music_01_fg", item)
    sltIcon:SetActive(index ~= nil)
    local musicType = self.scheme.rand % 2
    local order = self:find("Order", item)
    order:SetActive(false)
    if musicType == 0 and index ~= nil then
        order:SetActive(true)
        bee.setText(self:find("1", order), index)
    end

    bee.addClick(item, function ()
        self.sltedMusicId = data.id
        local inList = table.keyof(self.scheme.bgm_list, data.id) ~= nil
        if inList then
            if #self.scheme.bgm_list > 1 then
                table.removebyvalue(self.scheme.bgm_list, data.id)
            end
        else
            table.insert(self.scheme.bgm_list, data.id)
        end
        self:refreshLeftUI()
        self:setMusicDatas()
        self:switchChooseBtn()
    end, true)
end
--表情
function P:setEmojiItemShow(item, data)
    local icon = self:find("icon", item)
    bee.setIcon(icon, tpl_emoji[data.id].emoji)
    local slted = self:find("decoration_emoji_selected", item)
    slted:SetActive(self.sltedEmojiId == data.id)
    local index = table.keyof(self.scheme.emojis, data.id)
    local sltIcon = self:find("SelectToggle/lobby_music_01_fg", item)
    sltIcon:SetActive(index ~= nil)
    local order = self:find("Order", item)
    order:SetActive(false)
    if index ~= nil then
        order:SetActive(true)
        bee.setText(self:find("1", order), index)
    end

    bee.addClick(item, function ()
        self.sltedEmojiId = data.id
        local inList = table.keyof(self.scheme.emojis, data.id) ~= nil
        if inList then
            table.removebyvalue(self.scheme.emojis, data.id)
        else
            if not self:checkEmojiSelectMax() then
                table.insert(self.scheme.emojis, data.id)
            else
                UiManager:showToast(_F("LAB_DECOR_PLAN_TIPS_10", DecorationModel.MaxEmojiCount))
            end
        end
        self:refreshLeftUI()
        self:setEmojiDatas()
        self:switchChooseBtn()
    end, true)
end

--音乐随机
function P:MusicRandomToCircle()
    self.scheme.rand = 0
    self:refreshLeftUI()
    self:switchMusicBtn2()
    self:setMusicDatas()
    bee.logEvent("style-preset-music-mode", SchemeTag.Ingame, 1)
end
--音乐循环
function P:MusicCircleToRandom()
    self.scheme.rand = 1
    self:refreshLeftUI()
    self:switchMusicBtn2()
    self:setMusicDatas()
    bee.logEvent("style-preset-music-mode", SchemeTag.Ingame, 2)
end

function P:ViewEvent()
    if self.sltedType == self.ItemType.Role then
        local ownedRoleList = CharacterModel:getOwnedCharacters()
        local skinCfg = tpl_character_skin[self.sltedId]
        local role = nil
        for _,v in pairs(ownedRoleList) do
            if v.role_id == skinCfg.role then
                role = v
            end
            break
        end
        UiManager:showUI("BackpackPreview", {role = role, skin = skinCfg, scheme = DecorationModel:convertToInGameScheme(self.scheme)})
    elseif self.sltedType == self.ItemType.Title then
        if self.sltedId == 0 then
            UiManager:showUI("BackpackPreview", {noTitle = true, scheme = DecorationModel:convertToInGameScheme(self.scheme)})
        else
            local itemData = {item_id = self.sltedId, cfg = tpl_props[self.sltedId]}
            UiManager:showUI("BackpackPreview", {data = itemData, scheme = DecorationModel:convertToInGameScheme(self.scheme)})
        end
    elseif self.sltedType == self.ItemType.CardBack or self.sltedType == self.ItemType.Face
		or self.sltedType == self.ItemType.BackGround or self.sltedType == self.ItemType.NameCard 
        or self.sltedType == self.ItemType.OpenCard 
        then
        local itemData = {item_id = self.sltedId, cfg = tpl_props[self.sltedId]}
		UiManager:showUI("BackpackPreview", {data = itemData, scheme = DecorationModel:convertToInGameScheme(self.scheme)})
	elseif self.sltedType == self.ItemType.Allin then
		-- local themeInfo = DecorationModel:getCurScheme()
		local skinCfg = tpl_character_skin[self.scheme.skin_id[1]]
		UiManager:showUI(GameModel:getAllinUiName(self.sltedId), {role = CharacterModel:getRoleData(skinCfg.role), skin = skinCfg, title = self.scheme.title[1]})
	elseif self.sltedType == self.ItemType.Music then
        local itemData = {item_id = self.sltedMusicId, cfg = tpl_props[self.sltedMusicId]}
        local itemSubDatas = {}
		UiManager:showUI("BackpackMusic", {data = itemData, list = itemSubDatas[itemData.cfg.type]})
    elseif self.sltedType == self.ItemType.Avatar or self.sltedType == self.ItemType.Frame then
        UiManager:showUI("BackpackHistoryPreview", {scheme = DecorationModel:convertToInGameScheme(self.scheme)})
	end
end

function P:ChooseEvent()
    if self.sltedType == self.ItemType.Music then
        local isAll = self:checkMusicSelectAll()
        if not isAll then
            local ownedList = ItemModel:getAllShowItems(9, true)
            for _,v in pairs(ownedList) do
                if table.keyof(self.scheme.bgm_list, v.id) == nil then
                    table.insert(self.scheme.bgm_list, v.id)
                end
            end
        else
            local bgm = self.scheme.bgm_list[1]
            self.scheme.bgm_list = {bgm}
        end
        self:refreshLeftUI()
        self:setMusicDatas()
        self:switchChooseBtn()
    elseif self.sltedType == self.ItemType.Emoji then
        local isMax = self:checkEmojiSelectMax()
        if not isMax then
            local unlockList = DecorationModel:getAllUnlockEmoji()
            for _,v in pairs(unlockList) do
                if table.keyof(self.scheme.emojis, v.id) == nil then
                    table.insert(self.scheme.emojis, v.id)
                end
                if self:checkEmojiSelectMax() then
                    break
                end
            end
        else
            self.scheme.emojis = {}
        end
        self:refreshLeftUI()
        self:setEmojiDatas()
        self:switchChooseBtn()
    end
end
function P:switchChooseBtn()
    if self.sltedType == self.ItemType.Music then
        local isAll = self:checkMusicSelectAll()
        self:find("common_checkbox_03_fg", self.ChooseToggle):SetActive(isAll)
    elseif self.sltedType == self.ItemType.Emoji then
        local isMax = self:checkEmojiSelectMax()
        self:find("common_checkbox_03_fg", self.ChooseToggle):SetActive(isMax)
    end
end
function P:checkMusicSelectAll()
    local ownedList = ItemModel:getAllShowItems(9, true)
    local isAll = #self.scheme.bgm_list == #ownedList
    return isAll
end
function P:checkEmojiSelectMax()
    return #self.scheme.emojis >= DecorationModel.MaxEmojiCount
end


--按钮刷新
function P:refreshButtons()
    if DecorationModel:isInGameSchemeRandom() then
        self.Using:SetActive(false)
        self.Buttons:SetActive(false)
        self.UseButton:SetActive(false)
        self.SaveButton:SetActive(true)
    else
        self.Using:SetActive(false)
        self.UseButton:SetActive(false)
        self.SaveButton:SetActive(false)
        if self.scheme.scheme_id == DecorationModel:getInGameSpecifySchemeId() then
            self.Buttons:SetActive(true)
            self.SaveAndUseButton:SetActive(true)
            self.SaveOnlyButton:SetActive(false)
        else
            self.Buttons:SetActive(true)
            self.SaveAndUseButton:SetActive(true)
            self.SaveOnlyButton:SetActive(true)
        end
    end
end

--保存
function P:SaveEvent()
    if self.scheme.name == nil or self.scheme.name == "" then
        local index = #DecorationModel:getInGameSchemeList() + 1
        self.scheme.name = _F("LAB_DECOR_PLAN_8", index)
    end
    DecorationModel:requestSaveInGameDecorationScheme(self.scheme)
    if not DecorationModel._ingame_scheme_use then
        UiManager:showToast(_T("LAB_DECOR_PLAN_TIPS_9"))
    end
    self:hideUI()
end

--名字变更
function P:evt_changeSchemeNameCallback(msg)
    self.scheme.name = msg.name
    bee.setText(self.SchemeName, msg.name)
    self:setEditorPos()
end
--新方案名字变更
function P:evt_changeNewSchemeNameCallback(msg)
    self.scheme.name = msg.name
    bee.setText(self.SchemeName, msg.name)
    self:setEditorPos()
end 
function P:setEditorPos()
    local t = self.SchemeName:GetComponent("Text")
    local width = t.preferredWidth
    if width < 360 then
        self.EditButton.transform.localPosition = bee.v3(190, -3.5, 0)
    else
        local dif = (width - 360) * 0.5
        self.EditButton.transform.localPosition = bee.v3(190 + dif, -3.5, 0)
    end
end

--检测是否有变动
function P:checkSchemeChange()
    local change = false
    if self.baseScheme.rand ~= self.scheme.rand then
        change = true
    end
    if not self:checkListConsis(self.baseScheme.skin_id, self.scheme.skin_id) then
        change = true
    end
    if self.baseScheme.title == nil then
        self.baseScheme.title = {}
    end
    if self.scheme.title == nil then
        self.scheme.title = {}
    end
    if not self:checkListConsis(self.baseScheme.title, self.scheme.title) then
        change = true
    end
    if not self:checkListConsis(self.baseScheme.table, self.scheme.table) then
        change = true
    end
    if not self:checkListConsis(self.baseScheme.card_back, self.scheme.card_back) then
        change = true
    end
    if not self:checkListConsis(self.baseScheme.card_front, self.scheme.card_front) then
        change = true
    end
    if not self:checkListConsis(self.baseScheme.all_in_animation, self.scheme.all_in_animation) then
        change = true
    end
    if not self:checkListConsis(self.baseScheme.show_card, self.scheme.show_card) then
        change = true
    end
    if not self:checkListConsis(self.baseScheme.bgm_list, self.scheme.bgm_list) then
        change = true
    end
    if not self:checkListConsis(self.baseScheme.emojis, self.scheme.emojis) then
        change = true
    end
    return change
end
function P:checkListConsis(a, b)
    if #a ~= #b then
        return false
    end
    local count = #a
    for i = 1, count do
        if a[i] ~= b[i] then
            return false
        end
    end

    return true
end

function P:onClickClose()
    if self:checkSchemeChange() then
		local params = {}
		params.text = _T("LAB_CUSTOM_9")
		params.onSure = function()
			self:hideUI()
		end
		UiManager:showTip(params)
	else
		self:hideUI()
	end
end

function P:evt_gameBlur(flag, name)
    self:evt_uiBlur(flag, name)
end

return P