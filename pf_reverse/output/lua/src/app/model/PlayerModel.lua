local P = class("PlayerModel", BaseModel)

local hpSaveTag = -1

P.CharacterDefaultPosX = -265
P.CharacterDefaultPosY = -12
P.CharacterDefaultPosSize = 1

function P:ctor(logic)
    self._loginData = nil -- 登录数据

    self.saveData = {
        _username   = "",
        _uid        = 0,

        _rt         = bee.getServerTime(), -- 注册时间
        _ot         = 0, -- 玩家在线时长
        _usedGm     = nil, -- 是否使用过 gm 工具

        _errRedeem  = {},   -- 错误兑换码记录
        _redeemLimitTime = 0,   -- 兑换码限制时间
    }

    P.super.ctor(self)

    self._name       = ""
    self._diamond    = 0
    self._gold       = 0 -- 金币O
    self._level      = 1
    self._exp        = 0 -- 经验

    self._avatar = ""
    self._frame = 0
    self._country = ""
    self._sex = ""
    self._ptsys = ""
    self._title = 0

    self._declaration = ""  -- 个人宣言
    self._favorite_roles = {}    -- 喜爱的角色皮肤列表
    -- 战绩
    self._achievements = {
        holdem_firepower = 0,   --  德州扑克火力值
        sng_champion = 0,   --  SNG冠军次数
        mtt_champion = 0,   --  MTT冠军次数
        omaha_firepower = 0,    --  奥马哈火力值
    }
    self._blockUids = {}    -- 屏蔽聊天的玩家列表

    self._isLogin = false -- 是否已经登录
    self._isNewUser = false -- 是否新玩家

    self._curRecord = 0     -- 当前收藏数量
    self._recordNum = 10    -- 可收藏的记录上限

    self.activeDay = LocalStore:getIntegerForKey("my_active_day", 0)
    self.timeSpend = LocalStore:getIntegerForKey("my_day_game_time", 0)
    self._startTime = scheduler.timeSpend
    
    if LocalStore:isDailyTagValid("player_active") then
        self:addActiveDay()
    end
end

function P:afterInit()
    self._scheme_list = {}
    self._using_decoration_scheme = nil
end

bee.schedule(300, function()
    if PlayerModel then
        PlayerModel:checkTimeSpend()
    end
end)

function P:clearDatas()
    self:setGreetingFlag(false)
    self._scheme_list = {}
    self._using_decoration_scheme = nil
    self._rand_dc_scheme_flag = nil
end

function P:addActiveDay()
    self.activeDay = self.activeDay + 1
    LocalStore:setIntegerForKey("my_active_day", self.activeDay)
end

function P:checkTimeSpend()
end


function P:evt_onApplicationPause()
    self:checkTimeSpend()
end

function P:updateCloudData()
    P.super.updateCloudData(self)
    if not self.saveData._ot then
        self.saveData._ot = 0
    end
    self._otStartTime = scheduler.timeSpend
end

function P:onLoginSuccess(msg)
    self._loginData = msg
    self:setIsLogin(true)

    if not msg.lastLoginInfo then
        bee.log("game-signin")
    else
        bee.log("game-login")
    end

    -- MobileNotificationsManager:init()
end

function P:isLogin()
    return self._isLogin
end

function P:setIsLogin(flag)
    self._isLogin = flag
    -- if flag then
    --     PayHelper:checkPurchase()
    -- end
end

function P:getUid()
    return self.saveData._uid
end

function P:setUid(uid, showUid)
    if self.saveData._uid ~= uid or self.saveData._showUid ~= showUid then
        self.saveData._uid, self.saveData._showUid = uid, showUid
        self:onSave()
    end
end

function P:getShowUid()
    return self.saveData._showUid
end

function P:getStoveGUID()
    return self._stove_guid or 0
end

function P:setStoveGUID(guid)
    self._stove_guid = guid
end

function P:isStoveAccount()
    return G_CHNL_ID == 5 or G_CHNL_ID == 6 or G_CHNL_ID == 8
end

function P:setRdkey(rdkey)
    self.saveData.rdkey = rdkey
    self:onSave()
end

function P:getRdkey()
    return self.saveData.rdkey
end

function P:setAuthorization(authorization)
    self.saveData.authorization = authorization
    self:onSave()
end

function P:setAutoLogin(flag)
    self.saveData._autoLogin = flag
    self:onSave()
end

function P:isAutoLogin()
    return self.saveData._autoLogin
end

function P:getAuthorization()
    return self.saveData.authorization
end

function P:setLoginType(t)
    if t ~= self.saveData._loginType then
        self.saveData._loginType = t
        self:onSave()
    end
end

function P:getLoginType()
    return self.saveData._loginType
end

function P:setLoginToken(t)
    if t ~= self.saveData._loginToken then
        self.saveData._loginToken = t
        self:onSave()
    end
end

function P:getLoginToken()
    return self.saveData._loginToken
end

function P:getName()
    return self._name
end

function P:setName(name)
    self._name = name
end

function P:getAvatar()
    return self._avatar
end

function P:getAvatarIcon(avatar_id)
    local d = tpl_props[avatar_id or self._avatar]
    if d then
        return d.icon
    end
    return "Avatar[avatar_1001_01_list]"
end

function P:getGender()
    return self._sex
end

function P:getFrame()
    return self._frame
end

function P:getTitle()
    return self._title
end

function P:setIP(ip)
    self.saveData.ip = ip
end

function P:getIP()
    return self.saveData.ip
end

function P:setIsGuest(flag)
    self._isGuest = flag
end

function P:isGuest()
    return self._isGuest
end

function P:getCurId()
    if self._login_region then
        local d = tpl_shop_location[self._login_region]
        return d and d.cur_id or 1
    end
    return 1
end

function P:setLoginRegion(login_region)
    self._login_region = login_region
end

function P:getLoginRegion()
    return self._login_region or "Japan"
end

function P:getCountry()
    return self._country
end

function P:setIsDeleted(flag)
    self._isdeleted = flag
end

function P:isDeleted()
    return self._isdeleted
end

function P:setIsCanPay(flag)
    self._isCanPay = flag
end

function P:isCanPay()
    return self._isCanPay
end

function P:getDeclaration()
    return self._declaration
end

function P:getFavoriteRoles()
    return self._favorite_roles
end

function P:sortFavoriteRoles(roles)
    -- roles = roles or self._favorite_roles
    -- for _, v in ipairs(roles) do
    --     local d = tpl_character_skin[v.skin_id]
    --     v.score = 10000 - d.role
    --     if d.role == CharacterModel:getUsingRoleId() then
    --         v.score = 99999999
    --     else
    --         local r = CharacterModel:getRole(d.role)
    --         if r and r.is_star then
    --             v.score = v.score + 1000000
    --         end
    --         v.score = v.score + r:getBondLevel() * 100000
    --     end
    -- end
    -- table.sort(roles, function(a, b)
    --     return a.score > b.score
    -- end)
end

function P:getAchievements()
    return self._achievements
end

function P:isBlockChat(uid)
    if nil == FriendModel:getBlockedInfo(uid) then
        for _, v in ipairs(self._blockUids) do
            if v.uid == uid and v.block_end_time > bee.getServerTime() then
                return true
            end
        end
    end
    return false
end

function P:setInfo(msg)
    self._name = msg.brief.name
    self._avatar = msg.brief.avatar
    self._frame = msg.brief.frame
    self._title = msg.brief.title
    self._level = msg.brief.level
    self._user_type = msg.brief.user_type
    self._country = msg.country
    self._sex = msg.sex
    self._ptsys = msg.plat
    self._exp = msg.exp
    self._declaration = msg.declaration
    self._favorite_roles = msg.favorite_roles
    self._register_time = msg.register_time
    self._auth_cert_url = msg.auth_cert_url
    self._auth_cert_time = msg.auth_cert_time
    -- 动特效
    if msg.brief.animations then
        for k, v in pairs(msg.brief.animations) do
            self:setAnimationInfo(v)
        end
    end

    if self._scheme_list then
        CharacterModel:updateUsingRole()
    end
end

-- 动画特效
function P:setAnimationInfo(animInfo)
    if animInfo.ftype == ACTION_TYPE.AllInEff then
        self._allin_eff = animInfo.item_id
    elseif animInfo.ftype == ACTION_TYPE.NameplateEff then
        self._nameplate_eff = animInfo.item_id
    elseif animInfo.ftype == ACTION_TYPE.CardFace then
        self._card_face = animInfo.item_id
    end
end

-- 是否新注册用户 hour默认是 24 小时
function P:isNewer(hour)
    return bee.getServerTime() - self:getRegisterTime() <= (hour or 24) * 3600
end

function P:setRegisterTime(rt)
    self.saveData._rt = rt
end

function P:getRegisterTime()
    return self._register_time or bee.getServerTime()
end

function P:addGold(gold)
    self._gold = self._gold + gold
end

function P:setGold(gold)
    self._gold = gold
end

function P:getGold()
    return self._gold
end

function P:addDiamond(diamond)
    self._diamond = self._diamond + diamond
end

function P:setDiamond(diamond)
    self._diamond = diamond
end

function P:getDiamond()
    return self._diamond
end

function P:getCurLevel()
    return self._level
end

-- 获取all in特效
function P:getAllInEff()
    return self._allin_eff or ItemModel:getDefaultDecoration(GPropKind.AllInEff)
end

-- 获取铭牌特效
function P:getNameplateEff()
    return self._nameplate_eff or ItemModel:getDefaultDecoration(GPropKind.NameplateEff)
end

function P:getCardFace()
    return self._card_face or ItemModel:getDefaultDecoration(GPropKind.CardFace)
end

function P:setCurLevel(level)
    local oldLvl = self._level
    self._level = level
    if oldLvl ~= level then
        SettingModel:addLevelUpPop()
    end
end

function P:getExp()
    return self._exp
end

function P:getExpPercent()
    local d = tpl_level[self._level + 1]
    if d and d.xp_up > 0 then
        return self._exp / d.xp_up
    end
    return 0
    
end

function P:setExp(exp)
    self._exp = exp
end

function P:getUserType()
    return self._user_type
end

function P:getTodayHands()
    return self._todayHands or 0
end

function P:getTodaySngHands()
    return self._todaySngHands or 0
end

function P:setTodayHands(hands, sng_hands)
    self._todayHands = hands
    self._todaySngHands = sng_hands
end

function P:getCurRecord()
    return self._curRecord
end

function P:setCurRecord(num)
    self._curRecord = num
    return num
end

function P:reqCurRecord()
    Net:post("/collCard/collNum", {t = 1}, function(data)
        if 0 == data.code then
            self._curRecord = data.coll_num
            self._recordNum = data.limit_num
        end
    end)
end

function P:getRecentHistoryLimit()
    return VipModel:getRecentHistoryLimit()
end

function P:getRecordNum()
    return VipModel:getSheetLimit()
end

function P:setUsedGm(flag)
    if flag ~= self.saveData._usedGm then
        self.saveData._usedGm = flag
        self:onSave()
    end
end

function P:isUsedGm()
    return self.saveData._usedGm
end

function P:onSave()
    P.super.onSave(self)
    self:_checkOnlineTime()
end

function P:_checkOnlineTime()
    if scheduler.timeSpend - self._otStartTime >= 1 then
        self.saveData._ot = self.saveData._ot + scheduler.timeSpend - self._otStartTime
        self._otStartTime = scheduler.timeSpend
        return true
    end
    return false
end

function P:setLoginEmail(email)
    self.saveData._loginEmail = email
    self:onSave()
end

function P:getLoginEmail()
    return self.saveData._loginEmail
end

function P:setBindEmail(email)
    self._bindEmail = email
end

function P:getBindEmail()
    return self._bindEmail or ""
end

function P:setRegChnl(chnl)
    self._reg_chnl = chnl
end

function P:getRegChnl()
    return self._reg_chnl
end

function P:setIsWhite(flag)
    self._isWhite = flag
end

function P:isWhite()
    return self._isWhite
end

function P:setIsEventWhite(flag)
    self._is_event_white = flag
end

function P:isEventWhite()
    return self._is_event_white
end

function P:setLoginPw(pw)
    self.saveData._loginPw = pw
    self:onSave()
end

function P:getLoginPw()
    return self.saveData._loginPw
end

function P:setTestDeviceID(id)
    self.saveData._testDeviceId = id
    self:onSave()
end

function P:getTestDeviceID()
    if bee.isRelease then
        return
    end
    return self.saveData._testDeviceId
end

function P:setNotAutoLogin(flag)
    self._notAutoLogin = flag
end

function P:getNotAutoLogin()
    return self._notAutoLogin
end

-- 推特登录
function P:setXToken(val)
    self.saveData._XToken = val
    self:onSave()
end

function P:setXSecret(val)
    self.saveData._XSecret = val
    self:onSave()
end

function P:getXToken()
    return self.saveData._XToken
end

function P:getXSecret()
    return self.saveData._XSecret
end

function P:getAuthCertUrl()
    return self._auth_cert_url
end

function P:getAuthTime()
    return self._auth_cert_time
end

-- 本次登录是否已播欢迎语
function P:isPlayedGreeting()
    return self._isPlayedGreeting 
end

function P:setGreetingFlag(flag)
    self._isPlayedGreeting = flag
end

-- ======================= 装扮 =======================

function P:getCurCardBack()
    if 0 == ItemModel.using_card_back or not tpl_props[ItemModel.using_card_back] then
        return tpl_constdata.DefaultCardBack
    end
    return tpl_props[ItemModel.using_card_back].mapId
end

function P:getCurCardBackImage()
    local cardBackId = self:getCurCardBack()
    return tpl_card_back[cardBackId].image
end

function P:getCurCardTable()
    if 0 == ItemModel.using_table or not tpl_props[ItemModel.using_table] then
        return tpl_constdata.DefaultCardTable
    end
    return tpl_props[ItemModel.using_table].mapId
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

function P:getCurMusicBattle()
    if 0 == ItemModel.using_battle_music or not tpl_props[ItemModel.using_battle_music] then
        return tpl_constdata.DefaultMusicBattle
    end
    return tpl_props[ItemModel.using_battle_music].mapId
end

function P:getCurLobbyScene()
    local schemeInfo = self:getCurScheme(true)
    return tpl_props[schemeInfo.lobby_scene_id].mapId
end

function P:getCurAllInEff()
    return tpl_props[self:getAllInEff()].mapId
end

function P:getCurNameplateEff()
    return tpl_props[self:getNameplateEff()].mapId
end

function P:getCurCardFace()
    return tpl_props[self:getCardFace()].mapId
end

function P:setPayUser(flag)
    self.saveData._isPayUser = tonumber(flag) == 1
    self:onSave()
end

function P:getIsPayUser(flag)
    return self.saveData._isPayUser
end

function P:evt_serverTimeCrossDay()
    self._todayHands = 0
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
]]
function P:evt_GetDCSchemeRSP(msg)
    self._scheme_list = {}
    table.sort(msg.scheme_list, function(a, b) return a.create_at < b.create_at end)
    for i,v in ipairs(msg.scheme_list) do
        v.index = i
        table.insert(self._scheme_list, v)
    end
    -- 装饰方案
    self._using_decoration_scheme = msg.using_decoration_scheme
    self._rand_dc_scheme_flag = msg.rand_dc_scheme_flag
    CharacterModel:updateUsingRole()
    bee.emit("evt_initScheme")
end

function P:evt_SwitchRoleSkinRSP(msg)
    self:requestDecorationScheme()
end

-- 保存装饰方案
function P:requestSaveDecorationScheme(scheme_id, skin_id, scene_id, bgm_list, property_list, isSave)
    local args = {}
    if not scheme_id then
        args.operation_type = 0
    else
        args.operation_type = 1
        args.scheme_id = scheme_id
    end
    args.skin_id = skin_id
    args.lobby_scene_id = scene_id
    args.lobby_bgm_list = bgm_list
    args.property_list = property_list
    args.set_as_using = isSave
    Net:sendReq("pb.SaveDCSchemeREQ", args)
end

-- 使用大厅bgm
function P:useLobbyBgm(id)
    local curScheme = self:getCurScheme()
    local args = {}
    args.scheme_id = curScheme.scheme_id
    args.skin_id = curScheme.skin_id
    args.lobby_scene_id = curScheme.lobby_scene_id
    args.lobby_bgm_list = {id}
    args.property_list = curScheme.property_list
    args.operation_type = 1
    Net:sendReq("pb.SaveDCSchemeREQ", args)
end

-- 使用大厅背景
function P:useLobbyScene(id)
    local curScheme = self:getCurScheme()
    local args = {}
    args.scheme_id = curScheme.scheme_id
    args.skin_id = curScheme.skin_id
    args.lobby_scene_id = id
    args.lobby_bgm_list = curScheme.lobby_bgm_list
    args.property_list = curScheme.property_list
    args.operation_type = 1
    Net:sendReq("pb.SaveDCSchemeREQ", args)
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
    for k,v in pairs(self._scheme_list) do
        -- 已有主题，直接替换
        if v.scheme_id == msg.scheme.scheme_id then
            -- 判断是否有新bgm
            isNewBgm = not self:isSameBgmList(v.lobby_bgm_list, msg.scheme.lobby_bgm_list)

            for k1, v1 in pairs(msg.scheme) do
                v[k1] = v1
            end
            isNew = false
            break
        end
    end
    if isNew then
        msg.scheme.index = #self._scheme_list + 1
        -- 新增主题
        table.insert(self._scheme_list, msg.scheme)
    end
    
    if msg.set_as_using and msg.scheme.scheme_id ~= PlayerModel:getCurSchemeId() then
        self:requestChangeScheme(msg.scheme.scheme_id)
    end

    if msg.scheme.scheme_id == PlayerModel:getCurSchemeId() then
        CharacterModel:updateUsingRole()
        if isNewBgm then
            Game:playLobbyBGM()
        end
    end


    bee.emit("evt_updateScheme", msg.scheme)
end

-- 切换装饰方案
function P:requestChangeScheme(scheme_id)
    Net:sendReq("pb.ChangeUsingDCSchemeREQ", {scheme_id = scheme_id})
end

function P:evt_ChangeUsingDCSchemeRSP(msg)
    if msg.code ~= 0 then
        return
    end
    self._using_decoration_scheme = msg.scheme_id
    CharacterModel:updateUsingRole()
    bee.emit("evt_changeScheme")
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

-- 删除装饰方案
function P:requestDeleteDCSchemeREQ(scheme_id)
    Net:sendReq("pb.DeleteDCSchemeREQ", {scheme_id = scheme_id})
end

function P:evt_DeleteDCSchemeRSP(msg)
    if msg.code ~= 0 then
        return
    end

    local list = {}
    local index
    for k,v in pairs(self._scheme_list) do
        if v.scheme_id == msg.scheme_id then
            index = k
            break
        end
    end
    if index then
        table.remove(self._scheme_list, index)
    end
    table.sort(self._scheme_list, function(a, b) return a.create_at < b.create_at end)

    for i,v in ipairs(self._scheme_list) do
        v.index = i
    end

    bee.emit("evt_changeScheme")
end

-- 获取装饰方案列表
function P:getDecorationSchemeList()
    return self._scheme_list or {}
end

-- 获取当前装饰方案
function P:getCurSchemeId()
    return self._using_decoration_scheme
end

function P:getCurScheme(initDefault)
    return self:getSchemeInfoById(self._using_decoration_scheme, initDefault)
end

-- 是否随机装饰方案
function P:isRandomDecorationScheme()
    return self._rand_dc_scheme_flag == 1
end

function P:getSchemeInfoById(id, initDefault)
    local schemeList = self:getDecorationSchemeList()
    for k, v in pairs(schemeList) do
        if id == v.scheme_id then
            return v
        end
    end

    if initDefault then
        -- 默认方案
        local defaultInfo = {}
        local role = CharacterModel:getRoleData(tpl_constdata.DefaultCharacter)
        defaultInfo.skin_id = role and role:getSkinData().id or 1001
        defaultInfo.lobby_scene_id = ItemModel:getDefaultDecoration(GPropKind.LobbyScene)
        defaultInfo.lobby_bgm_list = {ItemModel:getDefaultDecoration(GPropKind.MusicLobby)}
        defaultInfo.property_list = {}
        defaultInfo.property_list[1] = PlayerModel.CharacterDefaultPosX * 10
        defaultInfo.property_list[2] = PlayerModel.CharacterDefaultPosY * 10
        defaultInfo.property_list[3] = PlayerModel.CharacterDefaultPosSize * 100
        defaultInfo.property_list[4] = MusicTag.Order

        return defaultInfo
    end
end

-- ======================= 兑换码 =======================

-- 错误兑换码记录
function P:recordErrorRedeemCode()
    local curTime = bee.getServerTime()

    if #self.saveData._errRedeem >= tpl_constdata.Gift_Code_Failed_Count then
        local t1 = table.remove(self.saveData._errRedeem)
        if curTime - t1 < tpl_constdata.Gift_Code_Time_Failed then
            self.saveData._redeemLimitTime = curTime + tpl_constdata.Gift_Code_Time_Limit
        end
    end

    table.insert(self.saveData._errRedeem, curTime)
    self:onSave()
end

-- 兑换码
function P:requestRedeemCodeExchange(code, succCb, errCb, limitCb)
    if bee.getServerTime() < self.saveData._redeemLimitTime then
        if limitCb then
            bee.logEvent("giftCode-successful", code, 2)
            limitCb()
        end
        return
    end

    Net:post("redemption/exchange", {code = code}, function(data)
        if data.code ~= 0 then
            self:recordErrorRedeemCode()
            if errCb then
                bee.logEvent("giftCode-successful", code, 0)
                errCb(data.code)
            end
            return
        end

        if succCb then
            succCb()
        end
        bee.logEvent("giftCode-successful", code, 1)

        ShopModel:showRewardView(data.item_list)
    end)
end

return P
