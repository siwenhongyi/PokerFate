local P = class("DecorationModel", BaseModel)
DecorationModel = P

function P:ctor()
    P.super.ctor(self)

    --大厅装饰 方案列表
	self._lobby_scheme_list = {}
    --大厅装饰 是否随机
    self._lobby_israndom = false
    --大厅装饰 随机方案
    self._lobby_random_schemes = {}
    --大厅装饰 指定方案
    self._lobby_specify_scheme = nil
    --大厅装饰 当前方案
    self._lobby_using_scheme = nil


    --对局装饰 方案列表
    self._ingame_scheme_list = {}
    --对局装饰 是否随机
    self._ingame_israndom = false
    --对局装饰 随机方案
    self._ingame_random_schemes = {}
    --对局装饰 指定方案
    self._ingame_specify_scheme = nil
    --对局装饰保存并使用标签
    self._ingame_scheme_use = false

    --可选择表情最大数量
    self.MaxEmojiCount = 3

    --旧数据
    self._scheme_list = {}
    self._using_decoration_scheme = nil
    self._rand_dc_scheme_flag = nil
end

function P:afterLogin()
    self._lobby_using_scheme = nil
end

function P:getCurCardBack(scheme)
    if not scheme then
        scheme = self:getDefaultInGameCurScheme()
    end
    return tpl_props[scheme.card_back].mapId
end

function P:getCurCardBackImage(scheme)
    local cardBackId = self:getCurCardBack(scheme)
    return tpl_card_back[cardBackId].image
end

function P:getCurCardTable(scheme)
    if not scheme then
        scheme = self:getDefaultInGameCurScheme()
    end
    return tpl_props[scheme.table].mapId
end

function P:getCurMusicLobby()
    -- if 0 == ItemModel.using_lobby_music or not tpl_props[ItemModel.using_lobby_music] then
    --     return tpl_constdata.DefaultMusicHall
    -- end
    -- return tpl_props[ItemModel.using_lobby_music].mapId
    local schemeInfo = self:getCurScheme(true)
    local list = {}
    for k,v in pairs(schemeInfo.lobby_bgm_list) do
        table.insert(list, tpl_props[v].mapId)
    end
    return list
end

function P:getLobbyMusicTag()
    local schemeInfo = self:getCurScheme(true)
    return schemeInfo.property_list[4]
end

function P:getCurMusicBattle(scheme)
    if not scheme then
        scheme = self:getDefaultInGameCurScheme()
    end
    local list = {}
    for _, v in ipairs(scheme.bgm_list) do
        table.insert(list, tpl_props[v].mapId)
    end
    return list
end

function P:getCurLobbyScene()
    local schemeInfo = self:getCurScheme(true)
    return tpl_props[schemeInfo.lobby_scene_id].mapId
end

function P:getCurCardFace(scheme)
    if not scheme then
        scheme = self:getDefaultInGameCurScheme()
    end
    return tpl_props[scheme.card_front].mapId
end

-- 装饰方案
function P:requestDecorationScheme()
    Net:sendReq("pb.GetDCSchemeREQ", {})
end

--[[
    DCSchemeItem.property_list 是自定义列表
    property_list[1] = 角色位置x
    property_list[2] = 角色位置y
    property_list[3] = 角色缩放
    property_list[4] = 音乐播放标志 EnumConfig.MusicTag
    property_list[5] =角色角度
]]
function P:evt_GetDCSchemeRSP(msg)
    --大厅装饰
    self._lobby_scheme_list = {}
    table.sort(msg.scheme_list, function(a, b) return a.create_at < b.create_at end)
    for i,v in ipairs(msg.scheme_list) do
        v.index = i
        if v.card_front == nil or v.card_front == 0 then
            v.card_front = ItemModel:getDefaultDecoration(GPropKind.CardFace)
        end
        if v.card_back == nil or v.card_back == 0 then
            v.card_back = ItemModel:getDefaultDecoration(GPropKind.CardBack)
        end
        table.insert(self._lobby_scheme_list, v)
    end
    self._lobby_israndom = msg.rand_dc_scheme_flag == 1
    self._lobby_random_schemes = msg.lobby_rand_schemes
    self._lobby_specify_scheme = msg.lobby_specify_scheme
    self._lobby_using_scheme = msg.using_decoration_scheme

    --对局装饰
    self._ingame_scheme_list = {}
    table.sort(msg.room_scheme_list, function(a, b) return a.create_at < b.create_at end)
    for i,v in ipairs(msg.room_scheme_list) do
        v.index = i
        if v.avatar == nil or v.avatar == 0 then
            v.avatar =  tpl_character_skin[v.skin_id[1]].avatar
        end
        table.insert(self._ingame_scheme_list, v)
    end
    self._ingame_israndom = msg.room_mode == 1
    self._ingame_random_schemes = msg.room_rand_schemes
    self._ingame_specify_scheme = msg.room_specify_scheme

    -- 装饰方案
    -- self._using_decoration_scheme = msg.using_decoration_scheme
    -- self._rand_dc_scheme_flag = msg.rand_dc_scheme_flag

    CharacterModel:updateUsingRole()
    bee.emit("evt_initScheme")
end

function P:evt_SwitchRoleSkinRSP(msg)
    self:requestDecorationScheme()
end

-- 保存装饰方案
function P:requestSaveDecorationScheme(data) -- scheme_id, skin_id, scene_id, bgm_list, avatar_id, frame_id, title_id, cardface_id, cardback_id, property_list, isUse)
    local args = {}
    if not data.scheme_id then
        args.operation_type = 0
        local index = #self._lobby_scheme_list + 1
        args.name = _F("LAB_DECOR_PLAN_29", index)
    else
        args.operation_type = 1
        args.scheme_id = data.scheme_id
    end
    args.skin_id = data.skin_id
    args.lobby_scene_id = data.scene_id
    args.avatar = data.avatar_id
    args.frame = data.frame_id
    args.title = data.title_id
    args.card_front = data.cardface_id
    args.card_back = data.cardback_id
    args.lobby_bgm_list = data.bgm_list
    args.property_list = data.property_list
    args.set_as_using = data.isUse
    Net:sendReq("pb.SaveDCSchemeREQ", args, function ()
        if not data.isUse then
            UiManager:showToast(_T("LAB_DECOR_PLAN_TIPS_9"))
        else
            UiManager:showToast(_T("LAB_DECOR_PLAN_TIPS_7"))
        end
    end)
end
function P:requestSaveDecorationScheme2(scheme)
    scheme.index = nil
    scheme.operation_type = scheme.scheme_id == nil and 0 or 1
    Net:sendReq("pb.SaveDCSchemeREQ", scheme)
end

--克隆大厅方案
function P:copyLobbyScheme(data)
    local args = clone(data)
    local index = #self._lobby_scheme_list + 1
    args.name = _F("LAB_DECOR_PLAN_29", index)
    args.scheme_id = nil
    Net:sendReq("pb.SaveDCSchemeREQ", args, function ()
        UiManager:showToast(_T("LAB_DECOR_PLAN_31"))
    end)
end

-- 使用大厅bgm
function P:useLobbyBgm(id)
    local args = self:changeCurScheme()
    args.lobby_bgm_list = {id}
    Net:sendReq("pb.SaveDCSchemeREQ", args)
end
-- 使用大厅背景
function P:useLobbyScene(id)
    local args = self:changeCurScheme()
    args.lobby_scene_id = id
    Net:sendReq("pb.SaveDCSchemeREQ", args)
end
--使用大厅头像
function P:useLobbyAvatar(id)
    local args = self:changeCurScheme()
    local oldAvatar = args.avatar
    args.avatar = id
    Net:sendReq("pb.SaveDCSchemeREQ", args, function ()
        PlayerModel._avatarOld = oldAvatar
        bee.emit("evt_ChangeAvatarRSP")
    end)
end
--使用大厅头像框
function P:useLobbyFrame(id)
    local args = self:changeCurScheme()
    local oldFrame = args.frame
    args.frame = id
    Net:sendReq("pb.SaveDCSchemeREQ", args, function ()
        PlayerModel._frameOld = oldFrame
        bee.emit("evt_ChangeFrameRSP")
    end)
end
--使用大厅称号
function P:useLobbyTitle(id)
    local args = self:changeCurScheme()
    local oldTitle = args.title
    args.title = id
    Net:sendReq("pb.SaveDCSchemeREQ", args, function ()
        PlayerModel._titleOld = oldTitle
        bee.emit("evt_ChangeTitleRSP")
    end)
end
--修改大厅当前方案
function P:changeCurScheme()
    local curScheme = self:getCurScheme()
    local args = {}
    args.scheme_id = curScheme.scheme_id
    args.skin_id = curScheme.skin_id
    args.lobby_scene_id = curScheme.lobby_scene_id
    args.avatar = curScheme.avatar
    args.frame = curScheme.frame
    args.title = curScheme.title
    args.lobby_bgm_list = curScheme.lobby_bgm_list
    args.property_list = curScheme.property_list
    args.operation_type = 1
    return args
end

--修改对局皮肤
function P:useInGameSkin(id, cb)
    local args = self:changeCurInGameScheme()
    local oldSkin = args.scheme.skin_id[1]
    args.scheme.skin_id = {id}
    Net:sendReq("pb.SaveRoomDCSchemeREQ", args, function ()
        bee.emit("evt_ChangeInGameSkin", {oldSkin = oldSkin, curSkin = id})
    end)
    if cb then
        cb(oldSkin)
    end
end
--修改对局头像
function P:useInGameAvatar(id)
    local args = self:changeCurInGameScheme()
    local oldAvatar = args.scheme.avatar
    args.scheme.avatar = id
    Net:sendReq("pb.SaveRoomDCSchemeREQ", args, function ()
        bee.emit("evt_ChangeAvatarInGameRSP", {id = id, oldId = oldAvatar})
    end)
end
--修改对局头像框
function P:useInGameFrame(id)
    local args = self:changeCurInGameScheme()
    local oldFrame = args.scheme.frame
    args.scheme.frame = id
    Net:sendReq("pb.SaveRoomDCSchemeREQ", args, function ()
        bee.emit("evt_ChangeFrameInGameRSP", {id = id, oldId = oldFrame})
    end)
end
--修改对局称号
function P:useInGameTitle(id)
    local args = self:changeCurInGameScheme()
    local oldTitle = args.scheme.title[1] or 0
    args.scheme.title = {id}
    Net:sendReq("pb.SaveRoomDCSchemeREQ", args, function ()
        bee.emit("evt_ChangeTitleInGameRSP", {id = id, oldId = oldTitle})
    end)
end
--修改对局当前方案
function P:changeCurInGameScheme()
    local curScheme = self:getInGameSchemeInfoById(self._ingame_specify_scheme)
    local args = {}
    args.scheme = clone(curScheme)
    args.operation_type = 1
    return args
end

function P:isSameBgmList(list1, list2)
    if #list1 ~= #list2 then
        return false
    end

    for k, v in pairs(list1) do
        local isIn = false
        for k1, v1 in pairs(list2) do
            if v == v1 then
                isIn = true
                break
            end
        end
        if not isIn then
            return false
        end
    end
    return true
end

function P:evt_SaveDCSchemeRSP(msg)
    if msg.code ~= 0 then
        return
    end

    bee.logEvent("lobby-custom-edit")

    local isNew = true
    local isNewBgm
    for k,v in pairs(self._lobby_scheme_list) do
        -- 已有主题，直接替换
        if v.scheme_id == msg.scheme.scheme_id then
            -- 判断是否有新bgm
            isNewBgm = not self:isSameBgmList(v.lobby_bgm_list, msg.scheme.lobby_bgm_list)

            for k1, v1 in pairs(msg.scheme) do
                v[k1] = v1
            end
            if msg.scheme.frame == 0 then
                v.frame = 0
            end
            if msg.scheme.title == 0 then
                v.title = 0
            end
            isNew = false
            break
        end
    end
    if isNew then
        msg.scheme.index = #self._lobby_scheme_list + 1
        -- 新增主题
        table.insert(self._lobby_scheme_list, msg.scheme)
    end
    
    if msg.set_as_using and msg.scheme.scheme_id ~= DecorationModel:getCurLobbySchemeId() then
        self:setSchemeInfo(SchemeTag.Lobby, msg.scheme.scheme_id)
        --self:requestChangeScheme(msg.scheme.scheme_id)
    end

    if msg.scheme.scheme_id == DecorationModel:getCurLobbySchemeId() then
        CharacterModel:updateUsingRole()
        if isNewBgm then
            Game:playLobbyBGM()
        end
    end

    bee.emit("evt_updateScheme", msg.scheme)
end

--保存对局装饰方案
function P:requestSaveInGameDecorationScheme(scheme)
    local args = {}
    if scheme.scheme_id == nil then
        args.operation_type = 0
    else
        args.operation_type = 1
    end
    args.scheme = scheme
    Net:sendReq("pb.SaveRoomDCSchemeREQ", args)
end
--克隆对局方案
function P:copyInGameScheme(data)
    local args = {}
    local scheme = clone(data)
    local index = #self._ingame_scheme_list + 1
    scheme.name = _F("LAB_DECOR_PLAN_8", index)
    scheme.index = nil
    scheme.scheme_id = nil
    scheme.create_at = nil

    args.operation_type = 0
    args.scheme = scheme
    Net:sendReq("pb.SaveRoomDCSchemeREQ", args, function ()
        UiManager:showToast(_T("LAB_DECOR_PLAN_31"))
    end)
end
function P:evt_SaveRoomDCSchemeRSP(msg)
    if msg.code ~= 0 then
        return
    end
    
    local isNew = true
    for k,v in pairs(self._ingame_scheme_list) do
        -- 已有主题，直接替换
        if v.scheme_id == msg.scheme.scheme_id then
            for k1, v1 in pairs(msg.scheme) do
                v[k1] = v1
            end
            if msg.scheme.emojis == nil or #msg.scheme.emojis == 0 then
                v.emojis = {}
            end
            if msg.scheme.title == nil or #msg.scheme.title == 0 then
                v.title = {}
            end
            if msg.scheme.frame == nil or msg.scheme.frame == 0 then
                v.frame = 0
            end
            if msg.scheme.rand == nil or msg.scheme.rand == 0 then
                v.rand = 0
            end
            isNew = false
            break
        end
    end
    if isNew then
        msg.scheme.index = #self._ingame_scheme_list + 1
        -- 新增主题
        table.insert(self._ingame_scheme_list, msg.scheme)
    end

    if self._ingame_scheme_use then
        self._ingame_scheme_use = false
        self:setSchemeInfo(SchemeTag.Ingame, msg.scheme.scheme_id)
    end

    bee.emit("evt_updateInGameScheme", {scheme = msg.scheme})
end

-- 获取大厅装饰方案列表
function P:getLobbySchemeList()
    return self._lobby_scheme_list or {}
end

function P:getLobbyCurSchemeList()
    local result = {}
    local idList = {}
    
    if self._lobby_israndom then
        idList = self._lobby_random_schemes or {}
    else
        if self._lobby_specify_scheme and self._lobby_specify_scheme ~= 0 then
            table.insert(idList, self._lobby_specify_scheme)
        end
    end

    for _, sid in ipairs(idList) do
        local schemeInfo = self:getLobbySchemeInfoById(sid)
        if schemeInfo then
            table.insert(result, schemeInfo)
        end
    end

    if #result == 0 then
        result[1] = self:getDefaultLobbyScheme()
    end

    return result
end

-- 获取大厅指定装饰方案
function P:getLobbySpecifySchemeId()
    return self._lobby_specify_scheme
end
-- 获取大厅随机列表装饰方案
function P:getLobbyRandomSchemeList()
    return self._lobby_random_schemes
end
-- 判定大厅方案是否在随机列表
function P:checkLobbySchemeInRandom(schemeId)
    return table.keyof(self._lobby_random_schemes, schemeId) ~= nil
end
-- 大厅方案加入、移除随机列表
function P:lobbyRandomSchemeCtrl(schemeId, isJoin)
    local list = clone(self._lobby_random_schemes)
    if isJoin then
        table.insert(list, schemeId)
        self:setSchemeInfos(SchemeTag.Lobby, list)
    else
        if #list <= 1 then
            UiManager:showToast(_T("LAB_DECOR_PLAN_TIPS_5"))
            return
        end
        table.removebyvalue(list, schemeId)
        self:setSchemeInfos(SchemeTag.Lobby, list)
    end
end
-- 大厅方案是否随机
function P:isLobbySchemeRandom()
    return self._lobby_israndom
end
-- 获取大厅当前装饰方案
function P:getCurLobbySchemeId()
    return self._lobby_using_scheme
end

-- 获取对局装饰方案列表
function P:getInGameSchemeList()
    return self._ingame_scheme_list or {}
end
-- 获取对局指定装饰方案
function P:getInGameSpecifySchemeId()
    return self._ingame_specify_scheme
end
-- 获取对局随机列表装饰方案
function P:getInGameRandomSchemeList()
    return self._ingame_random_schemes
end
-- 判定对局方案是否在随机列表
function P:checkInGameSchemeInRandom(schemeId)
    return table.keyof(self._ingame_random_schemes, schemeId) ~= nil
end
-- 对局方案加入、移除随机列表
function P:inGameRandomSchemeCtrl(schemeId, isJoin)
    local list = clone(self._ingame_random_schemes)
    if isJoin then
        table.insert(list, schemeId)
        self:setSchemeInfos(SchemeTag.Ingame, list)
    else
        if #list <= 1 then
            UiManager:showToast(_T("LAB_DECOR_PLAN_TIPS_5"))
            return
        end
        table.removebyvalue(list, schemeId)
        self:setSchemeInfos(SchemeTag.Ingame, list)
    end
end
-- 对局方案是否随机
function P:isInGameSchemeRandom()
    return self._ingame_israndom
end

--提交方案
function P:setSchemeInfo(tag, sid)
    local schemeId
    if tag == SchemeTag.Lobby then
        schemeId = sid or self:getLobbySpecifySchemeId()
    elseif tag == SchemeTag.Ingame then
        schemeId = sid or self:getInGameSpecifySchemeId()
    end
    local args = {type = tag, mod_type = SchemeRandomTag.NoRandom, schemes = {schemeId}}
    Net:sendReq("pb.SetSchemeInfoREQ", args)
end
function P:setSchemeInfos(tag, schemeIds)
    local args = {type = tag, mod_type = SchemeRandomTag.Random}
    if schemeIds then
        args.schemes = schemeIds
    end
    Net:sendReq("pb.SetSchemeInfoREQ", args)
end
function P:evt_SetSchemeInfoRSP(msg)
    if msg.code ~= 0 then
        return
    end
    if msg.type == SchemeTag.Lobby then
        if msg.mod_type == SchemeRandomTag.NoRandom then
            self._lobby_israndom = false
            self._lobby_specify_scheme = msg.schemes[1]
            self._lobby_using_scheme = msg.schemes[1]
            CharacterModel:updateUsingRole()
            Game:playLobbyBGM()
        else
            self._lobby_israndom = true
            if msg.schemes ~= nil and #msg.schemes > 0 then
                self._lobby_random_schemes = msg.schemes
            end
        end
    elseif msg.type == SchemeTag.Ingame then
        if msg.mod_type == SchemeRandomTag.NoRandom then
            self._ingame_israndom = false
            self._ingame_specify_scheme = msg.schemes[1]
        else
            self._ingame_israndom = true
            if msg.schemes ~= nil and #msg.schemes > 0 then
                self._ingame_random_schemes = msg.schemes
            end
        end
    end
    bee.emit("evt_SchemeInfoCallback", msg)
end

function P:getCurScheme(initDefault)
    if self._lobby_using_scheme ~= "" then
        local schemeList = self:getLobbySchemeList()
        for _,v in pairs(schemeList) do
            if self._lobby_using_scheme == v.scheme_id then
                return v
            end
        end
    end
    return self:getDefaultLobbyScheme()
end

function P:getLobbySchemeInfoById(id, initDefault)
    local schemeList = self:getLobbySchemeList()
    for k, v in pairs(schemeList) do
        if id == v.scheme_id then
            if v.card_front == nil or v.card_front == 0 then
                v.card_front = ItemModel:getDefaultDecoration(GPropKind.CardFace)
            end
            if v.card_back == nil or v.card_back == 0 then
                v.card_back = ItemModel:getDefaultDecoration(GPropKind.CardBack)
            end
            return v
        end
    end

    if initDefault then
        return self:getDefaultLobbyScheme()
    end
end

function P:getInGameSchemeInfoById(id, initDefault)
    local schemeList = self:getInGameSchemeList()
    for k, v in pairs(schemeList) do
        if id == v.scheme_id then
            return v
        end
    end

    if initDefault then
        return self:getDefaultInGameScheme()
    end
end

function P:getDefaultLobbyScheme()
    local defaultInfo = {}
    local role = CharacterModel:getRoleData(tpl_constdata.DefaultCharacter)
    defaultInfo.skin_id = role and role:getSkinData().id or 1001
    defaultInfo.avatar = tpl_constdata.DefaultAvatar
    defaultInfo.title = 0
    defaultInfo.frame = 0
    defaultInfo.card_front = ItemModel:getDefaultDecoration(GPropKind.CardFace)
    defaultInfo.card_back = ItemModel:getDefaultDecoration(GPropKind.CardBack)
    defaultInfo.lobby_scene_id = ItemModel:getDefaultDecoration(GPropKind.LobbyScene)
    defaultInfo.lobby_bgm_list = {ItemModel:getDefaultDecoration(GPropKind.MusicLobby)}
    defaultInfo.property_list = {}
    defaultInfo.property_list[1] = PlayerModel.CharacterDefaultPosX * 10
    defaultInfo.property_list[2] = PlayerModel.CharacterDefaultPosY * 10
    defaultInfo.property_list[3] = PlayerModel.CharacterDefaultPosSize * 100
    defaultInfo.property_list[4] = MusicTag.Order
    defaultInfo.property_list[5] = 0
    return defaultInfo
end

function P:getDefaultInGameScheme()
    local defaultInfo = {}
    local role = CharacterModel:getRoleData(tpl_constdata.DefaultCharacter)
    defaultInfo.name = ""
    defaultInfo.rand = 0
    defaultInfo.avatar = tpl_constdata.DefaultAvatar
    defaultInfo.frame = 0
    defaultInfo.skin_id = {role and role:getSkinData().id or 1001}
    defaultInfo.title = nil
    defaultInfo.table = {ItemModel:getDefaultDecoration(GPropKind.Table)}
    defaultInfo.card_front = {ItemModel:getDefaultDecoration(GPropKind.CardFace)}
    defaultInfo.card_back = {ItemModel:getDefaultDecoration(GPropKind.CardBack)}
    defaultInfo.all_in_animation = {ItemModel:getDefaultDecoration(GPropKind.AllInEff)}
    defaultInfo.show_card = {ItemModel:getDefaultDecoration(GPropKind.NameplateEff)}
    defaultInfo.bgm_list = {ItemModel:getDefaultDecoration(GPropKind.MusicTable)}
    defaultInfo.emojis = {}
    defaultInfo.open_card = {ItemModel:getDefaultDecoration(GPropKind.AllinShowEff)}
    return defaultInfo
end

--获取当前解锁的所有表情
function P:getAllUnlockEmoji()
    local ownedRoleList = CharacterModel:getOwnedCharacters()
    table.sort(ownedRoleList, function(a, b) return a.role_id < b.role_id end)
    local unlockList = {}
    for _,v in pairs(ownedRoleList) do
        local emojis = get_tpl_subKey(tpl_emoji_list, "role", v.role_id)
        if emojis then
            for _, ev in ipairs(emojis) do
                if ev.unlock <= v:getBondLevel() then
                    table.insert(unlockList, {id = ev.id})
                end
            end
        end
    end
    return unlockList
end

function P:getRandomSchemeAttr(attr)
    if attr and #attr > 0 then
        return attr[math.random(#attr)]
    end
    return nil
end

-- 把大厅中使用的局内配置转换成桌内使用的配置
function P:convertToInGameScheme(scheme)
    return {
        name = scheme.name,
        rand = scheme.rand,
        skin_id = self:getRandomSchemeAttr(scheme.skin_id),
        title = self:getRandomSchemeAttr(scheme.title),
        table = self:getRandomSchemeAttr(scheme.table),
        card_back = self:getRandomSchemeAttr(scheme.card_back),
        card_front = self:getRandomSchemeAttr(scheme.card_front),
        all_in_animation = self:getRandomSchemeAttr(scheme.all_in_animation),
        show_card = self:getRandomSchemeAttr(scheme.show_card),
        bgm_list = scheme.bgm_list,
        emojis = scheme.emojis,
        open_card = self:getRandomSchemeAttr(scheme.open_card),
        avatar = scheme.avatar,
        frame = scheme.frame,
    }
end

function P:getInGameCurSchemeList()
    local result = {}
    local idList = {}
    
    if self._ingame_israndom then
        idList = self._ingame_random_schemes or {}
    else
        if self._ingame_specify_scheme and self._ingame_specify_scheme ~= 0 then
            table.insert(idList, self._ingame_specify_scheme)
        end
    end

    for _, sid in ipairs(idList) do
        local schemeInfo = self:getInGameSchemeInfoById(sid)
        if schemeInfo then
            table.insert(result, schemeInfo)
        end
    end

    if #result == 0 then
        result[1] = self:getDefaultInGameScheme()
    end

    return result
end

-- 获取当前应用在局内的配置
function P:getInGameCurScheme()
    if GameModel.data then
        local inGameScheme = GameModel.data:getIngameScheme()
        if inGameScheme.avatar == nil or inGameScheme.avatar == 0 then
            inGameScheme.avatar = tpl_character_skin[inGameScheme.skin_id].avatar
        end
        return inGameScheme
    end
    local result = {}
    local idList = {}
    
    if self._ingame_israndom then
        idList = self._ingame_random_schemes or {}
    else
        if self._ingame_specify_scheme and self._ingame_specify_scheme ~= 0 then
            table.insert(idList, self._ingame_specify_scheme)
        end
    end

    for _, sid in ipairs(idList) do
        local schemeInfo = self:getInGameSchemeInfoById(sid)
        if schemeInfo then
            table.insert(result, schemeInfo)
        end
    end

    if #result > 0 then
        local scheme = result[math.random(#result)]
        if scheme.avatar == nil or scheme.avatar == 0 then
            scheme.avatar = tpl_character_skin[scheme.skin_id].avatar
        end
        return self:convertToInGameScheme(scheme)
    end

    return self:getDefaultInGameCurScheme()
end

-- 获取在桌内使用的默认配置
function P:getDefaultInGameCurScheme()
    if not self._ingame_cur_scheme then
        self._ingame_cur_scheme = {}
        local role = CharacterModel:getRoleData(tpl_constdata.DefaultCharacter)
        self._ingame_cur_scheme.name = ""
        self._ingame_cur_scheme.rand = 0
        self._ingame_cur_scheme.avatar = ItemModel:getDefaultDecoration(GPropKind.Avatar)
        self._ingame_cur_scheme.frame = 0
        self._ingame_cur_scheme.skin_id = role and role:getSkinData().id or 1001
        self._ingame_cur_scheme.title = nil
        self._ingame_cur_scheme.table = ItemModel:getDefaultDecoration(GPropKind.Table)
        self._ingame_cur_scheme.card_front = ItemModel:getDefaultDecoration(GPropKind.CardFace)
        self._ingame_cur_scheme.card_back = ItemModel:getDefaultDecoration(GPropKind.CardBack)
        self._ingame_cur_scheme.all_in_animation = ItemModel:getDefaultDecoration(GPropKind.AllInEff)
        self._ingame_cur_scheme.show_card = ItemModel:getDefaultDecoration(GPropKind.NameplateEff)
        self._ingame_cur_scheme.bgm_list = {ItemModel:getDefaultDecoration(GPropKind.MusicTable)}
        self._ingame_cur_scheme.emojis = {}
        self._ingame_cur_scheme.open_card = ItemModel:getDefaultDecoration(GPropKind.AllinShowEff)
    end
    return self._ingame_cur_scheme
end


-- 删除装饰方案
function P:requestDeleteDCSchemeREQ(scheme_id, type)
    Net:sendReq("pb.DeleteDCSchemeREQ", {scheme_id = scheme_id, type = type})
end
function P:evt_DeleteDCSchemeRSP(msg)
    if msg.code ~= 0 then
        return
    end

    if msg.type == SchemeTag.Lobby then
        local list = {}
        local index
        for k,v in pairs(self._lobby_scheme_list) do
            if v.scheme_id == msg.scheme_id then
                index = k
                break
            end
        end
        if index then
            table.remove(self._lobby_scheme_list, index)
        end
        table.sort(self._lobby_scheme_list, function(a, b) return a.create_at < b.create_at end)

        for i,v in ipairs(self._lobby_scheme_list) do
            v.index = i
        end

        if msg.specify_scheme ~= nil and msg.specify_scheme ~= "" then
            self._lobby_specify_scheme = msg.specify_scheme
        end
        if msg.rand_schemes ~= nil and #msg.rand_schemes > 0 then
            self._lobby_random_schemes = msg.rand_schemes
        end
        if msg.using_decoration_scheme ~= nil and msg.using_decoration_scheme ~= "" then
            self._lobby_using_scheme = msg.using_decoration_scheme
        end
        bee.emit("evt_updateScheme")
        -- bee.emit("evt_changeScheme")
    else
        local list = {}
        local index
        for k,v in pairs(self._ingame_scheme_list) do
            if v.scheme_id == msg.scheme_id then
                index = k
                break
            end
        end
        if index then
            table.remove(self._ingame_scheme_list, index)
        end
        table.sort(self._ingame_scheme_list, function(a, b) return a.create_at < b.create_at end)

        for i,v in ipairs(self._ingame_scheme_list) do
            v.index = i
        end

        if msg.specify_scheme ~= nil and msg.specify_scheme ~= "" then
            self._ingame_specify_scheme = msg.specify_scheme
        end
        if msg.rand_schemes ~= nil and #msg.rand_schemes > 0 then
            self._ingame_random_schemes = msg.rand_schemes
        end
        bee.emit("evt_updateInGameScheme")
        -- bee.emit("evt_changeInGameScheme")
    end
end

function P:changeSchemeName(schemeType, name, schemeId)
    Net:sendReq("pb.SetSchemeNameREQ", {name = name, scheme_id = schemeId, operation_type = schemeType})
end
function P:evt_SetSchemeNameRSP(msg)
    if msg.code ~= 0 then
        return
    end

    if msg.operation_type == 1 then
        for _,v in pairs(self._lobby_scheme_list) do
            if v.scheme_id == msg.scheme_id then
                v.name = msg.name
                break
            end
        end
    elseif msg.operation_type == 2 then
        for _,v in pairs(self._ingame_scheme_list) do
            if v.scheme_id == msg.scheme_id then
                v.name = msg.name
                break
            end
        end
    end
    bee.emit("evt_changeSchemeNameCallback", {name = msg.name, id = msg.scheme_id, type = msg.operation_type})
end

-------查询装饰是否在方案中

--装饰是否在方案中
function P:checkSchemeAttr(tag, inSpecify, attrName, itemId)
    local schemeIds = self:getSchemeIds(tag, inSpecify)
    for _,v in pairs(schemeIds) do
        local scheme = self:getScheme(tag, v)
        if scheme then
            local attrValue = scheme[attrName]
            if type(attrValue) == "table" then
                if table.keyof(attrValue, itemId) ~= nil then
                    return true
                end
            else
                if attrValue == itemId then
                    return true
                end
            end
        end
    end
    return false
end

--获得方案ids
function P:getSchemeIds(tag, inSpecify)
    local ids = {}
    if tag == SchemeTag.Lobby then
        if inSpecify then
            if self._lobby_specify_scheme and self._lobby_specify_scheme ~= 0 then
                ids[1] = self._lobby_specify_scheme
            end
        else
            ids = self._lobby_random_schemes or {}
        end
    elseif tag == SchemeTag.Ingame then
        if inSpecify then
            if self._ingame_specify_scheme and self._ingame_specify_scheme ~= 0 then
                ids[1] = self._ingame_specify_scheme
            end
        else
            ids = self._ingame_random_schemes or {}
        end
    end
    return ids
end

--获得方案
function P:getScheme(tag, id)
    if tag == SchemeTag.Lobby then
        return self:getLobbySchemeInfoById(id)
    elseif tag == SchemeTag.Ingame then
        return self:getInGameSchemeInfoById(id)
    end
    return nil
end


--角色是否在方案中
function P:checkRoleInScheme(tag, inSpecify, roleId)
    local schemeIds = self:getSchemeIds(tag, inSpecify)
    for _,v in pairs(schemeIds) do
        local scheme = self:getScheme(tag, v)
        if scheme then
            local cacheSkinIds = scheme.skin_id
            local skinIds = type(cacheSkinIds) == "table" and cacheSkinIds or {cacheSkinIds}
            for _, skinId in ipairs(skinIds) do
                local cfg = tpl_character_skin[skinId]
                if cfg and cfg.role == roleId then
                    return true
                end
            end
        end
    end
    return false
end

--皮肤是否在方案中
function P:checkSkinInScheme(tag, inSpecify, skinId)
    return self:checkSchemeAttr(tag, inSpecify, "skin_id", skinId)
end

--头像是否在方案中
function P:checkAvatarInScheme(tag, inSpecify, avatarId)
    return self:checkSchemeAttr(tag, inSpecify, "avatar", avatarId)
end
--头像框是否在方案中
function P:checkFrameInScheme(tag, inSpecify, frameId)
    return self:checkSchemeAttr(tag, inSpecify, "frame", frameId)
end
--称号是否在方案中
function P:checkTitleInScheme(tag, inSpecify, titleId)
    return self:checkSchemeAttr(tag, inSpecify, "title", titleId)
end


--获取对应模式下的角色和皮肤
function P:getSkinCfgInScheme()
    local isRandom = self:isInGameSchemeRandom()
    local skinCfg = nil
    if not isRandom then
        local themeInfo = self:getInGameCurScheme()
        skinCfg = tpl_character_skin[themeInfo.skin_id]
    else
        local skinList = {}
        local ids = self:getInGameRandomSchemeList()
        for _,v in pairs(ids) do
            local scheme = self:getInGameSchemeInfoById(v)
            for _,sv in pairs(scheme.skin_id) do
                table.insert(skinList, sv)
            end
        end
        local randomIndex = math.random(1, #skinList)
        local skinId = skinList[randomIndex]
        skinCfg = tpl_character_skin[skinId]
    end
    return skinCfg
end

--获取指定模式下的装饰内容
function P:getDecorationInScheme(tag, inSpecify, attrName)
    local schemeIds = self:getSchemeIds(tag, inSpecify)
    local values = {}
    for _,v in pairs(schemeIds) do
        local scheme = self:getScheme(tag, v)
        if scheme then
            local attrValue = scheme[attrName]
            if type(attrValue) == "table" then
                for _,v in pairs(attrValue) do
                    table.insert(values, v)
                end
            else
                table.insert(values, attrValue)
            end
        end
    end
    return values
end

function P:evt_SchemeChangeBRC(msg)
    if msg.scheme_list and #msg.scheme_list > 0 then
        for _,v in pairs(msg.scheme_list) do
            for sk,sv in pairs(self._lobby_scheme_list) do
                if sv.scheme_id == v.scheme_id then
                    self._lobby_scheme_list[sk] = v
                end
            end
        end
    end
    if msg.room_scheme_list and #msg.room_scheme_list > 0 then
        for _,v in pairs(msg.room_scheme_list) do
            for sk,sv in pairs(self._ingame_scheme_list) do
                if sv.scheme_id == v.scheme_id then
                    self._ingame_scheme_list[sk] = v
                end
            end
        end
    end
end

--#region 废弃协议

-- 是否随机装饰方案
function P:isRandomDecorationScheme()
    return self._rand_dc_scheme_flag == 1
end

-- 旧装饰方案 
function P:requestChangeScheme(scheme_id)
    Net:sendReq("pb.ChangeUsingDCSchemeREQ", {scheme_id = scheme_id})
end

function P:evt_ChangeUsingDCSchemeRSP(msg)
    if msg.code ~= 0 then
        return
    end
    self._using_decoration_scheme = msg.scheme_id
    CharacterModel:updateUsingRole()
    -- bee.emit("evt_changeScheme")
    bee.emit("evt_updateScheme")
    Game:playLobbyBGM()
end

-- 切换方案是否随机
function P:requestUpdateDCSchemeRandFlag(flag)
    Net:sendReq("pb.UpdateDCSchemeRandFlagREQ", {random_scheme_flag = flag})
end

function P:evt_UpdateDCSchemeRandFlagRSP(msg)
    if msg.code ~= 0 then
        return
    end
    self._rand_dc_scheme_flag = msg.random_scheme_flag
end

--#endregion

return P