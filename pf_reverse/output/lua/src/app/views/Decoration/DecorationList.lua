local P = class("DecorationList", UiFullView)

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", AnimRoot)
    self.Left = self:find("Left", AnimRoot)
    self.LeftTop = self:find("LeftTop", AnimRoot)

    self.BackButton = self:find("BackButton", self.LeftTop)
    self.ReGuideButton = self:find("ReGuideButton", self.LeftTop)

    local Tab = self:find("TAB/TabToggle", self.Left)
    self.firEnter = true
    self.LobbyToggle = self:find("Tab01Toggle", Tab)
    
    self.LobbyText = self:find("Text", self.LobbyToggle)
    self.InGameToggle = self:find("Tab02Toggle", Tab)
    
    self.InGameText = self:find("Text", self.InGameToggle)

    self.TipButton = self:find("common_button_info_07", self.Center)
    self.TipObj = self:find("Tips", AnimRoot)
    self.TipCloseButton = self:find("Mask", self.TipObj)

    self.RandomButton = self:find("RandomButton", self.Center)
    self.DesignatedButton = self:find("DesignatedButton", self.Center)

    self.LobbyRoot = self:find("Lobby", self.Center)
    self.LobbyScroll = self:find("LobbyList", self.LobbyRoot)
    self.LobbyItem = self:find("item1", self.LobbyScroll)
    self.LobbyItem:SetActive(false)
    self.LobbyList = nil

    self.InGameRoot = self:find("Ingame", self.Center)
    self.InGameScroll = self:find("IngameList", self.InGameRoot)
    self.InGameItem = self:find("Item1", self.InGameScroll)
    self.InGameItem:SetActive(false)
    self.InGameList = nil

    --当前选中的方案类型
    self.curToggle = nil
    --方案变更sign
    self.changeSchemeSign = false

    bee.addClick(self.BackButton, function ()
        Game:playSound("ui_button_confirm")
        self:hideUI()
        bee.logEvent("style-preset-return")
    end)

    bee.addClick(self.ReGuideButton, function ()
        Game:playSound("ui_button_confirm")
        self:reGuide()
    end)

    bee.addClick(self.TipButton, function ()
        Game:playSound("ui_button_confirm")
        -- self.TipObj:SetActive(true)
        local lab = self.curToggle == SchemeTag.Lobby and "LAB_DECOR_PLAN_TIPS_1" or "LAB_DECOR_PLAN_TIPS_2"
        UiManager:showUI("CommonTextTipUD", {text = _T(lab), target = self.TipButton})
        bee.logEvent("style-preset-tips", self.curToggle)
        -- bee.setText(self:find("Text", self.TipObj), _T(lab))
    end)
    bee.addClick(self.TipCloseButton, function ()
        self.TipObj:SetActive(false)
    end)

    bee.addClick(self.RandomButton, function()
        Game:playSound("ui_button_confirm")
        self:exchangeRandomType(SchemeRandomTag.NoRandom)
    end)
    bee.addClick(self.DesignatedButton, function ()
        Game:playSound("ui_button_confirm")
        self:exchangeRandomType(SchemeRandomTag.Random)
    end)

    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.Decoration)
end

function P:onStart()
    self:initScrollList()

    bee.onCheck(self.LobbyToggle, function(isOn) self:setLobbyData(isOn) end)
    bee.onCheck(self.InGameToggle, function(isOn) self:setInGameData(isOn) end)

    self.toggle = self._params and self._params.jump.sub_page[1] or SchemeTag.Lobby
    if self.toggle == SchemeTag.Lobby then
        bee.setToggle(self.LobbyToggle, true)
        self:setLobbyData(true)
    else
        bee.setToggle(self.InGameToggle, true)
        self:setInGameData(true)
    end
end

function P:initScrollList()
    --大厅Scroll
    self.LobbyList = UiListEx:create(self.LobbyScroll)
	self.LobbyList:setCreateFunc(function()
		local item = CU.GameObject.Instantiate(self.LobbyItem)
		item.gameObject:SetActive(true)
		return item
	end)
	self.LobbyList:setRefreshFunc(function(data, item)
		self:setLobbyItems(item, data)
	end)
    self.LobbyList:setWidth(230)

    --对局Scroll
    self.InGameList = UiListEx:create(self.InGameScroll)
	self.InGameList:setCreateFunc(function()
		local item = CU.GameObject.Instantiate(self.InGameItem)
		item.gameObject:SetActive(true)
		return item
	end)
	self.InGameList:setRefreshFunc(function(data, item)
		self:setInGameItems(item, data)
	end)
    self.InGameList:setWidth(368)

    self:refreshDecorationCount()
end

function P:onShow()
    self:schemeGuide()
end

--大厅
function P:setLobbyData(isOn)
    if not isOn then
        return
    end
    if self.curToggle == SchemeTag.Lobby then
        return
    end
    self.curToggle = SchemeTag.Lobby

    self.LobbyRoot:SetActive(true)
    self.InGameRoot:SetActive(false)
    local isRandom = DecorationModel:isLobbySchemeRandom()
    self.RandomButton:SetActive(isRandom)
    self.DesignatedButton:SetActive(not isRandom)
    self:createLobbyShowData()
    if self.firEnter then
        self.firEnter = false
        return
    end
    bee.logEvent("style-preset-tag", 1)
end

--对局
function P:setInGameData(isOn)
    if not isOn then
        return
    end
    if self.curToggle == SchemeTag.Ingame then
        return
    end
    self.curToggle = SchemeTag.Ingame

    self.LobbyRoot:SetActive(false)
    self.InGameRoot:SetActive(true)
    local isRandom = DecorationModel:isInGameSchemeRandom()
    self.RandomButton:SetActive(isRandom)
    self.DesignatedButton:SetActive(not isRandom)
    self:createInGameShowData()
    bee.logEvent("style-preset-tag", 2)
end

--设置大厅方案Item
function P:setLobbyItems(item, data)
    if data and next(data) then
		self:setNormalLobbyItem(item, data)
	else
		self:setEmptyLobbyItem(item, data)
	end
end
function P:setNormalLobbyItem(item, data)
    local Empty = self:find("Empty", item)
    local Normal = self:find("Normal", item)
    Empty:SetActive(false)
    Normal:SetActive(true)
    item.name = "item" .. (data.index or 0)

    local TabButton = self:find("Tab", Normal)
    local IndexText = self:find("Tab/Value", Normal)
    local TabName = self:find("Tab/Name", Normal)
    local CopyButton = self:find("Copy", Normal)
	local DeleteButton = self:find("DeleteButton", Normal)
	local CharacterIcon = self:find("Character/avatar_frame_01_mask/icon", Normal)
	local SceneIcon = self:find("SceneIcon", Normal)
	local MusicGo = self:find("Music", Normal)
	local MusicIcon = self:find("icon", MusicGo)
	local CycleIcon = self:find("Cycle", MusicGo)
	local RandomIcon = self:find("Random", MusicGo)
	local MusicCountText = self:find("Value", MusicGo)
    local AvatarGo = self:find("AvatarFrame", Normal)
    local AvatarIcon = self:find("avatar_frame_01_mask/icon", AvatarGo)
    local AvatarFrame = self:find("icon", AvatarGo)
    local TitleIcon = self:find("Title/icon", Normal)
    local NoTitleIcon = self:find("Title/noneIcon", Normal)
    local CardFaceIcon = self:find("Face/icon", Normal)
    local CardBackIcon = self:find("Back/icon", Normal)

	local UseButton = self:find("UseButton", Normal)
	local Using = self:find("Using", Normal)
    local JoinRandomButton = self:find("JoinRandomButton", Normal)
    local CancelRandomButton = self:find("CancelRandomButton", Normal)
	local Selected = self:find("decoration_item_01_selected", Normal)

	local curId = DecorationModel:getLobbySpecifySchemeId()

    bee.addClick(TabButton, function ()
        UiManager:showUI("DecorationPanel", {type = 1, id = data.scheme_id, name = data.name})
    end, true)
	bee.setText(IndexText, data.index)
    local name = self:getSubName(TabName, data.name)
    bee.setText(TabName, name)
    CS.Utils.ForceRebuildLayoutImmediate(TabName)
    bee.addClick(CopyButton, function ()
        self:copyScheme(data)
    end, true)

	local skinCfg = tpl_character_skin[data.skin_id]
	ItemModel:setItemIcon(CharacterIcon, skinCfg.avatar)
	ItemModel:setItemIcon(SceneIcon, data.lobby_scene_id)
    local faceId = data.card_front ~= 0 and data.card_front or ItemModel:getDefaultDecoration(GPropKind.CardFace)
    ItemModel:setItemIcon(CardFaceIcon, faceId)
    local backId = data.card_back ~= 0 and data.card_back or ItemModel:getDefaultDecoration(GPropKind.CardBack)
    ItemModel:setItemIcon(CardBackIcon, backId)

	local musicList = data.lobby_bgm_list
	local musicId = tpl_props[musicList[1]].mapId
	local musicCfg = tpl_sound[tostring(musicId)]
	if musicCfg then
		bee.setIcon(MusicIcon, musicCfg.cd_image)
	end
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

    if data.avatar == nil or data.avatar == 0 then
        local avatar = tpl_character_skin[data.skin_id].avatar
        ItemModel:setItemIcon(AvatarIcon, avatar)
    else
        ItemModel:setItemIcon(AvatarIcon, data.avatar)
    end
    if data.frame == nil or data.frame == 0 then
        AvatarFrame:SetActive(false)
    else
        AvatarFrame:SetActive(true)
        ItemModel:setItemIcon(AvatarFrame, data.frame)
    end
    if data.title == nil or data.title == 0 then
        TitleIcon:SetActive(false)
        NoTitleIcon:SetActive(true)
    else
        TitleIcon:SetActive(true)
        NoTitleIcon:SetActive(false)
        ItemModel:setItemIcon(TitleIcon, data.title)
    end


    if not DecorationModel._lobby_israndom then
        Selected:SetActive(curId == data.scheme_id)
        DeleteButton:SetActive(data.scheme_id ~= curId)
        Using:SetActive(curId == data.scheme_id)
        UseButton:SetActive(curId ~= data.scheme_id)
        JoinRandomButton:SetActive(false)
        CancelRandomButton:SetActive(false)
    else
        Selected:SetActive(false)
        local inRandom = DecorationModel:checkLobbySchemeInRandom(data.scheme_id)
        DeleteButton:SetActive(not inRandom)
        JoinRandomButton:SetActive(not inRandom)
        CancelRandomButton:SetActive(inRandom)
        Using:SetActive(false)
        UseButton:SetActive(false)
    end

	bee.addClick(Normal, function()
		UiManager:showUI("LobbyAdjustment", {scheme_id = data.scheme_id})
	end, true)

	bee.addClick(DeleteButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showTip({
        text = _T("LAB_CUSTOM_5"),
        onSure = function()
            	DecorationModel:requestDeleteDCSchemeREQ(data.scheme_id, SchemeTag.Lobby)
	        end
	    })
	end, true)

    bee.addClick(JoinRandomButton, function ()
        Game:playSound("ui_button_confirm")
        DecorationModel:lobbyRandomSchemeCtrl(data.scheme_id, true)
    end, true)

    bee.addClick(CancelRandomButton, function ()
        Game:playSound("ui_button_confirm")
        DecorationModel:lobbyRandomSchemeCtrl(data.scheme_id, false)
    end, true)

	bee.addClick(UseButton, function()
		Game:playSound("ui_button_confirm")
		DecorationModel:setSchemeInfo(SchemeTag.Lobby, data.scheme_id)
    	-- bee.logEvent("lobby-custom-change")
	end, true)
end
function P:setEmptyLobbyItem(item, data)
    local Empty = self:find("Empty", item)
    local Normal = self:find("Normal", item)
    Empty:SetActive(true)
    Normal:SetActive(false)

	bee.addClick(Empty, function()
		Game:playSound("ui_button_confirm")
        local vipTip = self:checkVipTip()
        if vipTip then return end
		UiManager:showUI("LobbyAdjustment")
        bee.logEvent("style-preset-create", SchemeTag.Lobby)
	end, true)
end

--设置对局方案Item
function P:setInGameItems(item, data)
    if data and next(data) then
		self:setNormalInGameItem(item, data)
	else
		self:setEmptyInGameItem(item, data)
	end
end
function P:setNormalInGameItem(item, data)
    local Empty = self:find("Empty", item)
    local Normal = self:find("Normal", item)
    Empty:SetActive(false)
    Normal:SetActive(true)

    local TabButton = self:find("Tab", Normal)
    local IndexText = self:find("Tab/Value", Normal)
    local TabName = self:find("Tab/Name", Normal)
    local CopyButton = self:find("Copy", Normal)
	local DeleteButton = self:find("DeleteButton", Normal)
    local CharacterGo = self:find("Character", Normal)
	local CharacterIcon = self:find("Character/avatar_frame_01_mask/icon", Normal)
    local TitleBGo = self:find("Title", Normal)
    local TitleDefIcon = self:find("Title/defIcon", Normal)
    local TitleIcon = self:find("Title/icon", Normal)
    local AvatarGo = self:find("AvatarFrame", Normal)
    local AvatarIcon = self:find("AvatarFrame/avatar_frame_01_mask/icon", Normal)
    local AvatarFrameIcon = self:find("AvatarFrame/icon", Normal)
    local BackGroundIcon = self:find("background_icon", Normal)
    local FaceGo = self:find("Face", Normal)
    local FaceIcon = self:find("Face/icon", Normal)
    local CardBackGo= self:find("Back", Normal)
    local CardBackIcon = self:find("Back/icon", Normal)
    local AllInIcon = self:find("allin_icon", Normal)
    local NameplateGo = self:find("Nameplate", Normal)
    local NameplateIcon = self:find("Nameplate/icon", Normal)
    local OpencardGo = self:find("Opencard", Normal)
    local OpencardIcon = self:find("Opencard/icon", Normal)
    local MusicGo = self:find("Music", Normal)
	local MusicIcon = self:find("icon", MusicGo)
	local CycleIcon = self:find("Cycle", MusicGo)
	local RandomIcon = self:find("Random", MusicGo)
	local MusicCountText = self:find("Value", MusicGo)
    local EmojisGo = self:find("Emojis", Normal)
    local EmojisIcon = self:find("Emojis/icon", Normal)
    local EmojiEmpty = self:find("Emojis/decoration_emoji_empty", Normal)

	local UseButton = self:find("UseButton", Normal)
	local Using = self:find("Using", Normal)
    local JoinRandomButton = self:find("JoinRandomButton", Normal)
    local CancelRandomButton = self:find("CancelRandomButton", Normal)
	local Selected = self:find("decoration_item_01_selected", Normal)

	local curId = DecorationModel:getInGameSpecifySchemeId()

    bee.addClick(TabButton, function ()
        UiManager:showUI("DecorationPanel", {type = 2, id = data.scheme_id, name = data.name})
    end, true)
	bee.setText(IndexText, data.index)
    local name = self:getSubName(TabName, data.name)
    bee.setText(TabName, name)
    CS.Utils.ForceRebuildLayoutImmediate(TabName)
    bee.addClick(CopyButton, function ()
        self:copyScheme(data)
    end, true)

	local skinCfg = tpl_character_skin[data.skin_id[1]]
	ItemModel:setItemIcon(CharacterIcon, skinCfg.avatar)
    local titleId = data.title[1]
    if titleId == nil or titleId == 0 then
        TitleIcon:SetActive(false)
        TitleDefIcon:SetActive(true)
    else
        TitleIcon:SetActive(true)
        TitleDefIcon:SetActive(false)
        ItemModel:setItemIcon(TitleIcon, titleId)
    end
    ItemModel:setItemIcon(AvatarIcon, data.avatar)
    if data.frame == nil or data.frame == 0 then
        AvatarFrameIcon:SetActive(false)
    else
        AvatarFrameIcon:SetActive(true)
        ItemModel:setItemIcon(AvatarFrameIcon, data.frame)
    end
    ItemModel:setItemIcon(BackGroundIcon, data.table[1])
    ItemModel:setItemIcon(FaceIcon, data.card_front[1])
    ItemModel:setItemIcon(CardBackIcon, data.card_back[1])
    ItemModel:setItemIcon(AllInIcon, data.all_in_animation[1])
    ItemModel:setItemIcon(NameplateIcon, data.show_card[1])
    ItemModel:setItemIcon(OpencardIcon, data.open_card[1])

	local musicList = data.bgm_list
	local musicId = tpl_props[musicList[1]].mapId
	local musicCfg = tpl_sound[tostring(musicId)]
	if musicCfg then
		bee.setIcon(MusicIcon, musicCfg.cd_image)
	end
	bee.setText(MusicCountText, #musicList)
    local musicType = data.rand % 2
    CycleIcon:SetActive(musicType == 0)
    RandomIcon:SetActive(musicType == 1)

    if data.emojis and #data.emojis > 0 then
        EmojisIcon:SetActive(true)
        EmojiEmpty:SetActive(false)
        bee.setIcon(EmojisIcon, tpl_emoji[data.emojis[1]].emoji)
    else
        EmojisIcon:SetActive(false)
        EmojiEmpty:SetActive(true)
    end

    if not DecorationModel._ingame_israndom then
        Selected:SetActive(curId == data.scheme_id)
        DeleteButton:SetActive(data.scheme_id ~= curId)
        Using:SetActive(curId == data.scheme_id)
        UseButton:SetActive(curId ~= data.scheme_id)
        JoinRandomButton:SetActive(false)
        CancelRandomButton:SetActive(false)
    else
        Selected:SetActive(false)
        local inRandom = DecorationModel:checkInGameSchemeInRandom(data.scheme_id)
        DeleteButton:SetActive(not inRandom)
        JoinRandomButton:SetActive(not inRandom)
        CancelRandomButton:SetActive(inRandom)
        Using:SetActive(false)
        UseButton:SetActive(false)
    end

	bee.addClick(Normal, function()
		UiManager:showUI("DecorationDetails", {scheme = data})
	end, true)

	bee.addClick(DeleteButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showTip({
        text = _T("LAB_DECOR_PLAN_19"),
        onSure = function()
            	DecorationModel:requestDeleteDCSchemeREQ(data.scheme_id, SchemeTag.Ingame)
	        end
	    })
	end, true)

    bee.addClick(JoinRandomButton, function ()
        Game:playSound("ui_button_confirm")
        DecorationModel:inGameRandomSchemeCtrl(data.scheme_id, true)
    end, true)

    bee.addClick(CancelRandomButton, function ()
        Game:playSound("ui_button_confirm")
        DecorationModel:inGameRandomSchemeCtrl(data.scheme_id, false)
    end, true)

	bee.addClick(UseButton, function()
		Game:playSound("ui_button_confirm")
		DecorationModel:setSchemeInfo(SchemeTag.Ingame, data.scheme_id)
    	-- bee.logEvent("lobby-custom-change")
	end, true)

    bee.addClick(CharacterGo, function ()
        UiManager:showUI("DecorationDetails", {scheme = data, subType = 1})
    end, true)
    bee.addClick(TitleBGo, function ()
        UiManager:showUI("DecorationDetails", {scheme = data, subType = 2})
    end, true)
    bee.addClick(AvatarGo, function ()
        UiManager:showUI("DecorationDetails", {scheme = data, subType = 11})
    end, true)
    bee.addClick(BackGroundIcon, function ()
        UiManager:showUI("DecorationDetails", {scheme = data, subType = 3})
    end, true)
    bee.addClick(FaceGo, function ()
        UiManager:showUI("DecorationDetails", {scheme = data, subType = 4})
    end, true)
    bee.addClick(CardBackGo, function ()
        UiManager:showUI("DecorationDetails", {scheme = data, subType = 5})
    end, true)
    bee.addClick(AllInIcon, function ()
        UiManager:showUI("DecorationDetails", {scheme = data, subType = 6})
    end, true)
    bee.addClick(NameplateGo, function ()
        UiManager:showUI("DecorationDetails", {scheme = data, subType = 7})
    end, true)
    bee.addClick(OpencardGo, function()
        UiManager:showUI("DecorationDetails", {scheme = data, subType = 8})
    end, true)
    bee.addClick(MusicGo, function ()
        UiManager:showUI("DecorationDetails", {scheme = data, subType = 9})
    end, true)
    bee.addClick(EmojisGo, function ()
        UiManager:showUI("DecorationDetails", {scheme = data, subType = 10})
    end, true)
end
function P:setEmptyInGameItem(item, data)
    local Empty = self:find("Empty", item)
    local Normal = self:find("Normal", item)
    Empty:SetActive(true)
    Normal:SetActive(false)

	bee.addClick(Empty, function()
		Game:playSound("ui_button_confirm")
        local vipTip = self:checkVipTip()
        if vipTip then return end
		UiManager:showUI("DecorationDetails")
        bee.logEvent("style-preset-create", SchemeTag.Ingame)
	end, true)
end

--设置方案后回调
function P:evt_SchemeInfoCallback(msg)
    if self.changeSchemeSign then
        self.changeSchemeSign = false
        local lab = msg.mod_type == SchemeRandomTag.Random and "LAB_DECOR_PLAN_TIPS_4" or "LAB_DECOR_PLAN_TIPS_3"
        UiManager:showToast(_T(lab))
    end

    if msg.type ~= self.curToggle then
        return
    end
    self.RandomButton:SetActive(msg.mod_type == SchemeRandomTag.Random)
    self.DesignatedButton:SetActive(msg.mod_type == SchemeRandomTag.NoRandom)
    if self.curToggle == SchemeTag.Lobby then
        -- bee.emit("evt_changeScheme")
        bee.emit("evt_updateScheme")
    elseif self.curToggle == SchemeTag.Ingame then
        -- bee.emit("evt_changeInGameScheme", {modType = msg.mod_type})
        bee.emit("evt_updateInGameScheme", {modType = msg.mod_type})
    end
end

--切换随机和指定
function P:exchangeRandomType(randomType)
    self.changeSchemeSign = true
    if randomType == SchemeRandomTag.Random then
        DecorationModel:setSchemeInfos(self.curToggle)
    else
        DecorationModel:setSchemeInfo(self.curToggle)
    end
    bee.logEvent("style-preset-mode", self.curToggle, randomType + 1)
end

--名字变更
function P:evt_changeSchemeNameCallback(msg)
    if self.curToggle == SchemeTag.Lobby and msg.type == 1 then
        local items = self.LobbyList:getDatas()
        for _,v in pairs(items) do
            if not bee.isNull(v.node) and v.data.scheme_id == msg.id then
                v.data.name = msg.name
                local nameGo = self:find("Normal/Tab/Name", v.node)
                local name = self:getSubName(nameGo, msg.name)
                bee.setText(nameGo, name)
                CS.Utils.ForceRebuildLayoutImmediate(nameGo)
                break
            end
        end
    elseif self.curToggle == SchemeTag.Ingame and msg.type == 2 then
        local items = self.InGameList:getDatas()
        for _,v in pairs(items) do
            if not bee.isNull(v.node) and v.data.scheme_id == msg.id then
                v.data.name = msg.name
                local nameGo = self:find("Normal/Tab/Name", v.node)
                local name = self:getSubName(nameGo, msg.name)
                bee.setText(nameGo, name)
                CS.Utils.ForceRebuildLayoutImmediate(nameGo)
                break
            end
        end
    end
end

--大厅装饰更新
function P:evt_updateScheme()
    self:createLobbyShowData()
end
-- function P:evt_changeScheme()
-- 	self:createLobbyShowData()
-- end
function P:createLobbyShowData()
    local schemeBase = DecorationModel:getLobbySchemeList()
    local scheme = clone(schemeBase)
    for k, v in ipairs(scheme) do
        v.index = k
    end
    local listCount = #scheme
    local limitCount, maxCount = self:getVipLimitData(SchemeTag.Lobby)
    bee.setText(self.LobbyText, _F("LAB_DECOR_PLAN_2", listCount, limitCount))
	if listCount < maxCount and next(scheme[listCount]) then
		table.insert(scheme, {})
	end
    self.LobbyList:setDatas(scheme)
end

function P:evt_updateInGameScheme()
    self:createInGameShowData()
end
-- function P:evt_changeInGameScheme()
--     self:createInGameShowData()
-- end
function P:createInGameShowData()
    local schemeBase = DecorationModel:getInGameSchemeList()
    local scheme = clone(schemeBase)
    local listCount = #scheme
    local limitCount, maxCount = self:getVipLimitData(SchemeTag.Ingame)
    bee.setText(self.InGameText, _F("LAB_DECOR_PLAN_3", listCount, limitCount))
	if listCount < maxCount and next(scheme[listCount]) then
		table.insert(scheme, {})
	end
    self.InGameList:setDatas(scheme)
end

--获取Vip数据
function P:getVipLimitData(dtype)
    local vipLv = VipModel:getVipLevel()
    local limitCount = dtype == SchemeTag.Lobby and tpl_vip_level[vipLv].lobby_limit or tpl_vip_level[vipLv].ingame_limit
    local maxVipLv = VipModel:getMaxLevel()
    local maxCount = dtype == SchemeTag.Lobby and tpl_vip_level[maxVipLv].lobby_limit or tpl_vip_level[maxVipLv].ingame_limit
    return limitCount, maxCount
end

--检测Vip提示
function P:checkVipTip()
    local schemeCount = 0
    local limitCount, maxCount = self:getVipLimitData(self.curToggle)
    if self.curToggle == SchemeTag.Lobby then
        schemeCount = #DecorationModel:getLobbySchemeList()
    elseif self.curToggle == SchemeTag.Ingame then
        schemeCount = #DecorationModel:getInGameSchemeList()
    end

    if schemeCount < limitCount then
        return false
    end

    if schemeCount >= limitCount and schemeCount < maxCount then
        UiManager:showTip({
            text = _T("LAB_DECOR_PLAN_32"),
            sureStr = _T("LAB_CONFIRM"),
            cancelStr = _T("LAB_CANCEL"),
            onSure = function()
                ItemModel:jumpView(4005)
            end,
            onCancel = function()
            end,
        })
        return true
    end

    if schemeCount >= maxCount then
        UiManager:showToast(_T("LAB_DECOR_PLAN_33"))
        return true
    end
end

--克隆方案
function P:copyScheme(data)
    local vipTip = self:checkVipTip()
    if vipTip then return end
    if self.curToggle == SchemeTag.Lobby then
        DecorationModel:copyLobbyScheme(data)
    elseif self.curToggle == SchemeTag.Ingame then
        DecorationModel:copyInGameScheme(data)
    end
end

function P:getSubName(text, str)
    local t = text:GetComponent("Text")
    t.text = str
    local name = str
    if t.preferredWidth > 210 then
        name = ""
        local charCount = string.utf8len(str)
        for i = 1, charCount do
            name = string.utf8sub(str, 1, i)
            t.text = name
            if t.preferredWidth > 210 then
                name = name .. "..."
                break
            end
        end
    end
    return name
end

--刷新方案数量与上限
function P:refreshDecorationCount()
    local lobbySchemes = DecorationModel:getLobbySchemeList()
    local lobbyLimitCount = self:getVipLimitData(SchemeTag.Lobby)
    bee.setText(self.LobbyText, _F("LAB_DECOR_PLAN_2", #lobbySchemes, lobbyLimitCount))
    local ingameSchemes = DecorationModel:getInGameSchemeList()
    local ingameLimitCount = self:getVipLimitData(SchemeTag.Ingame)
    bee.setText(self.InGameText, _F("LAB_DECOR_PLAN_3", #ingameSchemes, ingameLimitCount))
end

function P:evt_refreshVipLevel()
   self:refreshDecorationCount()
end

function P:evt_gameBlur(flag, name)
    self:evt_uiBlur(flag, name)
end

--引导
function P:schemeGuide()
    GuideManager:startSystemGuide(19001, 0.65)
end

function P:reGuide()
    bee.setToggle(self.LobbyToggle, true)
    self:setLobbyData(true)
    self.LobbyList:moveToYItem(1, false)
    GuideManager:startSystemGuide(19001, 0, 0)
end

return P
