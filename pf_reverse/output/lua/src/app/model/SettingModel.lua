local P = class("SettingModel", BaseModel)

function P:ctor()
    self.saveData = {
        preAction = true,
        autoByin = false,
        cardValue = true,
        showBB = false, -- 显示bb
        showCard = true, -- 主动秀牌
        saveGame = false,
        hideChat = false,
        hideInvite = false,
        autoSwitch = false, -- 自动切换牌桌
        betCustomize = false, -- 自定义下注
        betPrecise = false, -- 精准下注
        raiseKind = 2, -- 加注类型 1底池加注 2倍数加注

        betPkValues2 = {3, 5, 7, 10}, -- pk 默认 bet 刻度
        betOmahaValues = {3, 5, 7, 10}, -- omaha 默认 bet 刻度
        raisePkValues = {1, 6, 11, 13}, -- pk 默认 raise 刻度
        raiseOmahaValues = {1, 6, 11, 21}, -- omaha 默认 raise 刻度
        raisePotPkValues = {3, 5, 7, 10}, -- pk 底池加注 默认刻度
        raisePotOmahaValues = {3, 5, 7, 10}, -- omaha 底池加注 默认刻度

        -- 语音设置`
        globalVolume = 1, -- 全局音量
        globalVolumeOn = true,    -- 全局音量开

        lobbyBGM = 1,
        lobbyBGMOn = true,

        ingameBGM = 1,
        ingameBGMOn = true,

        soundVolume = 1,
        soundVolumeOn = true,

        roleInVolume = 1,   -- 角色局内语音
        roleInVolumeOn = true,

        roleOutVolume = 1,   -- 角色局外语音
        roleOutVolumeOn = true,

        roleVoiceOffs = {},  -- 自定义角色语音关闭列表

        -- 震动
        vibrateUI = false,
        vibrateInGame = true,
        vibrateOutGame = true,

        -- 角色
        roleShowStarDlg = true,  -- 角色收藏对话框显示

        cloud = {
            -- sysunlocks .. uid = {id, id},    -- 系统解锁动画
            -- sysunlockReds .. uid = {id, id},  -- 系统解锁红点

            -- 玩家自定义下注刻度
            -- customizeLobbyBet .. uid = {},  -- 大厅 PK
            -- customizeLobbyOmahaBet .. uid = {},  -- 大厅 Omaha
            -- customizeSngBet .. uid = {},  -- SNG
            -- customizeFriendBet .. uid = {},  -- 好友

            -- 牌桌设置开关
            -- tableSetting .. uid = {}
        },
    }

    P.super.ctor(self)

    self._unlockSys = {}
    self._cdKeys = {}   -- cd keys
    self._tmpTags = {}  -- 临时 tags
    self._scrapPlayers = {} -- 桌子上爆衣的玩家列表
    
    self._sysunlocks = nil
    -- self._sysunlockReds = nil

    self._customizeLobbyBet = nil
    self._customizeLobbyOmahaBet = nil
    self._customizeSngBet = nil
    self._customizeFriendBet = nil
    self._tableSetting = nil
end

function P:afterInit()
    if self.saveData.betOmahaValues[#self.saveData.betOmahaValues] ~= POKER_BET_DEFAULT_VALUES[#POKER_BET_DEFAULT_VALUES] then
        self.saveData.betOmahaValues[#self.saveData.betOmahaValues] = POKER_BET_DEFAULT_VALUES[#POKER_BET_DEFAULT_VALUES]
    end
    if self.saveData.betPkValues then
        self.saveData.betPkValues2 = self.saveData.betPkValues
        self.saveData.betPkValues = nil
        if self.saveData.betPkValues2[#self.saveData.betPkValues2] >= 9 and self.saveData.betPkValues2[#self.saveData.betPkValues2] < #POKER_BET_STEP then
            self.saveData.betPkValues2[#self.saveData.betPkValues2] = self.saveData.betPkValues2[#self.saveData.betPkValues2] + 1
        end
        self:onSave()
    end
end

function P:afterLogin()
    self._sysunlocks = self:getCloudKeyData("sysunlocks")
    -- self._sysunlockReds = self:getCloudKeyData("sysunlockReds")

    self._customizeLobbyBet = self:getCloudKeyData("customizeLobbyBet")
    self:initDefaultBets(self._customizeLobbyBet)
    self._customizeLobbyOmahaBet = self:getCloudKeyData("customizeLobbyOmahaBet")
    self:initDefaultBets(self._customizeLobbyOmahaBet)
    self._customizeSngBet = self:getCloudKeyData("customizeSngBet")
    self:initDefaultBets(self._customizeSngBet)
    self._customizeFriendBet = self:getCloudKeyData("customizeFriendBet")
    self:initDefaultBets(self._customizeFriendBet)

    self._tableSetting = self:getCloudKeyData("tableSetting")
    if not next(self._tableSetting) then
        self._tableSetting.preAction = self.saveData.preAction
        self._tableSetting.autoByin = self.saveData.autoByin
        self._tableSetting.showBB = self.saveData.showBB
        self._tableSetting.showCard = self.saveData.showCard
        self._tableSetting.saveGame = self.saveData.saveGame
        self._tableSetting.hideChat = self.saveData.hideChat
        self._tableSetting.hideInvite = self.saveData.hideInvite
        self._tableSetting.autoSwitch = self.saveData.autoSwitch
        self._tableSetting.betPrecise = self.saveData.betPrecise
    end

    if self._tableSetting.cardValue == nil then
        self._tableSetting.cardValue = self.saveData.cardValue
    end
end

function P:initDefaultBets(customizeBets)
    if not next(customizeBets) then
        customizeBets.betPkValues2 = clone(self.saveData.betPkValues2)
        customizeBets.betOmahaValues = clone(self.saveData.betOmahaValues)
        customizeBets.raisePkValues = clone(self.saveData.raisePkValues)
        customizeBets.raiseOmahaValues = clone(self.saveData.raiseOmahaValues)
        customizeBets.raisePotPkValues = clone(self.saveData.raisePotPkValues)
        customizeBets.raisePotOmahaValues = clone(self.saveData.raisePotOmahaValues)

        customizeBets.betCustomize = self.saveData.betCustomize
        customizeBets.raiseKind = self.saveData.raiseKind
    end
end

function P:getCustomizeBets(gameType)
    if GF.isFriendsRoom(gameType) then
        return self._customizeFriendBet
    elseif GF.isSNG(gameType) then
        return self._customizeSngBet
    elseif GF.isOmahaGame(gameType) then
        return self._customizeLobbyOmahaBet
    end
    return self._customizeLobbyBet
end

function P:isPreAction()
    return self._tableSetting.preAction
end

function P:setPreAction(flag)
    self._tableSetting.preAction = flag
    self:onSave()
end

function P:isAutoByin()
    return self._tableSetting.autoByin
end

function P:setAutoByin(flag)
    self._tableSetting.autoByin = flag
    self:onSave()
end

function P:isShowBB()
    return self._tableSetting.showBB
end

function P:setShowBB(flag)
    if self._tableSetting.showBB == flag then
        return
    end
    self._tableSetting.showBB = flag
    self:onSave()
    bee.emit(EventDef.evt_refreshShowBB)
end

function P:isShowCard()
    return self._tableSetting.showCard
end

function P:setShowCard(flag)
    self._tableSetting.showCard = flag
    self:onSave()
end

function P:isCardValue()
    return self._tableSetting.cardValue
end

function P:setCardValue(flag)
    self._tableSetting.cardValue = flag
    self:onSave()
end

function P:isSaveGame()
    return self._tableSetting.saveGame
end

function P:setSaveGame(flag)
    self._tableSetting.saveGame = flag
    self:onSave()
end

function P:isHideChat()
    return self._tableSetting.hideChat
end

function P:setHideChat(flag)
    self._tableSetting.hideChat = flag
    self:onSave()
end

function P:isHideInvite()
    return self._tableSetting.hideInvite
end

function P:setHideInvite(flag)
    self._tableSetting.hideInvite = flag
    self:onSave()
end

function P:isAutoSwitch()
    return self._tableSetting.autoSwitch
end

function P:setAutoSwitch(flag)
    self._tableSetting.autoSwitch = flag
    self:onSave()
end

function P:isBetCustomize(gameType)
    return self:getCustomizeBets(gameType).betCustomize
end

function P:setBetCustomize(flag, gameType)
    self:getCustomizeBets(gameType).betCustomize = flag
    self:onSave()
end

function P:isBetPrecise()
    return self._tableSetting.betPrecise
end

function P:setBetPrecise(flag)
    self._tableSetting.betPrecise = flag
    self:onSave()
end

function P:getRaiseKind(notDefault, gameType)
    if not notDefault and not self:isBetCustomize(gameType) then
        return 2
    end
    return self:getCustomizeBets(gameType).raiseKind
end

function P:setRaiseKind(kind, gameType)
    self:getCustomizeBets(gameType).raiseKind = kind
    self:onSave()
end

function P:getBetStep(isOmaha)
    if isOmaha then
        return OMAHA_BET_STEP
    end
    return POKER_BET_STEP
end

function P:getRaiseStep(isOmaha, kind)
    if not kind then
        kind = self._tableSetting.raiseKind
    end
    if isOmaha then
        if kind == 1 then
            return OMAHA_RAISE_POT_STEP
        end
        return OMAHA_RAISE_STEP
    end
    if kind == 1 then
        return POKER_RAISE_POT_STEP
    end
    return POKER_RAISE_STEP
end

function P:getBetPkValues(gameType, isCheckCustom)
    if (isCheckCustom and not self:isBetCustomize(gameType)) or GuideManager:isInGuide() then
        return POKER_BET_DEFAULT_VALUES
    end
    if GF.isOmahaGame(gameType) then
        return self:getCustomizeBets(gameType).betOmahaValues
    end
    return self:getCustomizeBets(gameType).betPkValues2
end

function P:setBetPkValue(index, value, gameType)
    if GF.isOmahaGame(gameType) then
        self:getCustomizeBets(gameType).betOmahaValues[index] = value
        self:onSave()
        return
    end
    self:getCustomizeBets(gameType).betPkValues2[index] = value
    self:onSave()
end

function P:getRaisePkValues(gameType, isCheckCustom, kind)
    if not kind then
        kind = self._tableSetting.raiseKind
    end
    if (isCheckCustom and not self:isBetCustomize(gameType)) or GuideManager:isInGuide() then
        if kind == 1 then
            return POKER_RAISE_POT_DEFAULT_VALUES
        end
        return GF.isOmahaGame(gameType) and OMAHA_RAISE_DEFAULT_VALUES or POKER_RAISE_DEFAULT_VALUES
    end
    if GF.isOmahaGame(gameType) then
        if kind == 1 then
            return self:getCustomizeBets(gameType).raisePotOmahaValues
        end
        return self:getCustomizeBets(gameType).raiseOmahaValues
    end
    if kind == 1 then
        return self:getCustomizeBets(gameType).raisePotPkValues
    end
    return self:getCustomizeBets(gameType).raisePkValues
end

function P:setRaisePkValue(index, value, kind, gameType)
    if GF.isOmahaGame(gameType) then
        if kind == 1 then
            self:getCustomizeBets(gameType).raisePotOmahaValues[index] = value
        else
            self:getCustomizeBets(gameType).raiseOmahaValues[index] = value
        end
        return
    end
    if kind == 1 then
        self:getCustomizeBets(gameType).raisePotPkValues[index] = value
    else
        self:getCustomizeBets(gameType).raisePkValues[index] = value
    end
    self:onSave()
end

function P:isColorGameUnlock()
    return tpl_system_info[101].level <= PlayerModel:getCurLevel() and self:isShowColorGame()
end

function P:isShowColorGame()
    return true
end

function P:isSysUnlockAnim(id, notRemove)
    for k, v in ipairs(self._sysunlocks) do
        if v == id then
            if not notRemove then
                table.remove(self._sysunlocks, k)
                self:onSave()
            end
            return true
        end
    end
    return false
end

function P:getSysUnlockRed()
    if #self._sysunlockReds > 0 then
        return table.remove(self._sysunlockReds, 1)
    end
    return nil
end

function P:isSysUnlock(id)
    return self._unlockSys[id] ~= nil
end

function P:setUnlockSys(sys)
    self._unlockSys = {}
    for _, v in ipairs(sys) do
        self._unlockSys[v] = v
    end
end

function P:addUnlockSys(sys)
    for _, v in ipairs(sys) do
        self._unlockSys[v] = v
    end
end

function P:isRoleShowStarDlg()
    return self.saveData.roleShowStarDlg
end

function P:setRoleShowStarDlg(flag)
    self.saveData.roleShowStarDlg = flag
    self:onSave()
end

function P:addVipLevelUpPop(oldLevel)
    if bee.isInGame() or bee.isInStart() then
        LocalStore:setBoolForKey("vip_level_up_pop" .. PlayerModel:getUid(), true)
        LocalStore:setIntegerForKey("vip_level_up_old_level" .. PlayerModel:getUid(), oldLevel)
        return
    end
    bee.showUiTask("VIPUpgrade", {oldLevel = oldLevel}, POP_TAG.Reward)
    bee.runTask()
end

function P:addLevelUpPop()
    if bee.isInGame() or bee.isInStart() then
        LocalStore:setBoolForKey("level_up_pop" .. PlayerModel:getUid(), true)
        local levels = LocalStore:getTableData("level_up_reward_level" .. PlayerModel:getUid()) or {}
        table.insert(levels, PlayerModel:getCurLevel())
        LocalStore:saveTableData("level_up_reward_level" .. PlayerModel:getUid(), levels)
        return
    end
    bee.showUiTask("LevelUpgrade", nil, nil, LOBBY_POP_PRIORITY.LevelUpgrade)
    bee.runTask()
    self:checkNewUnlockSys()
    if PlayerModel:getCurLevel() % tpl_constdata.Score_Level == 0 then
        SdkHelper:startAppReview()
    end
end

function P:checkAutoPop()
    if LocalStore:getBoolForKey("level_up_pop" .. PlayerModel:getUid(), false) then
        LocalStore:setBoolForKey("level_up_pop" .. PlayerModel:getUid(), false)
        local levels = LocalStore:getTableData("level_up_reward_level" .. PlayerModel:getUid())
        LocalStore:deleteValueForKey("level_up_reward_level" .. PlayerModel:getUid())
        if levels then
            bee.showUiTask("LevelUpgrade", {levels = levels}, nil, LOBBY_POP_PRIORITY.LevelUpgrade)
            for _, v in ipairs(levels) do
                if v % tpl_constdata.Score_Level == 0 then
                    SdkHelper:startAppReview()
                    break
                end
            end
        end
    end
    if LocalStore:getBoolForKey("vip_level_up_pop" .. PlayerModel:getUid(), false) then
        LocalStore:setBoolForKey("vip_level_up_pop" .. PlayerModel:getUid(), false)
        local oldLevel = LocalStore:getIntegerForKey("vip_level_up_old_level" .. PlayerModel:getUid(), VipModel:getVipLevel() - 1)
        bee.showUiTask("VIPUpgrade", {oldLevel = oldLevel}, nil, LOBBY_POP_PRIORITY.VipUp)
    end
    self:checkNewUnlockSys()
end

function P:checkNewUnlockSys()
    local ids = nil
    for _, v in ipairs(tpl_system_info_list) do
        if v.level > 0 and v.level <= PlayerModel:getCurLevel() and not self:isSysUnlock(v.id) then
            if not ids then
                ids = {v.id}
            else
                table.insert(ids, v.id)
            end
            table.addValue(self._sysunlocks, v.id)
            -- table.addValue(self._sysunlockReds, v.id)
        end
    end
    if ids then
        Net:sendReq("pb.UnlockNewModuleREQ", {ids = ids})
        self:onSave()

        bee.emit(EventDef.evt_refreshSysunlock)
    end
end

function P:getLobbyBGMVolume()
    if self.saveData.globalVolumeOn and self.saveData.lobbyBGMOn then
        return self.saveData.globalVolume * self.saveData.lobbyBGM
    end
    return 0
end

function P:getIngameBGMVolume()
    if self.saveData.globalVolumeOn and self.saveData.ingameBGMOn then
        return self.saveData.globalVolume * self.saveData.ingameBGM
    end
    return 0
end

function P:getSoundVolume()
    if self.saveData.globalVolumeOn and self.saveData.soundVolumeOn then
        return self.saveData.globalVolume * self.saveData.soundVolume
    end
    return 0
end

function P:getRoleInVolume(role_id)
    if self.saveData.globalVolumeOn and self.saveData.roleInVolumeOn and self:isRoleVolumeOn(role_id) then
        return self.saveData.globalVolume * self.saveData.roleInVolume
    end
    return 0
end

function P:getRoleOutVolume(role_id)
    if self.saveData.globalVolumeOn and self.saveData.roleOutVolumeOn and self:isRoleVolumeOn(role_id) then
        return self.saveData.globalVolume * self.saveData.roleOutVolume
    end
    return 0
end

function P:setRoleVolumeOn(role_id, flag)
    if flag then
        for k, v in ipairs(self.saveData.roleVoiceOffs) do
            if v == role_id then
                table.remove(self.saveData.roleVoiceOffs, k)
                break
            end
        end
    else
        for _, v in ipairs(self.saveData.roleVoiceOffs) do
            if v == role_id then
                return
            end
        end
        table.insert(self.saveData.roleVoiceOffs, role_id)
    end
end

function P:isRoleVolumeOn(role_id)
    for _, v in ipairs(self.saveData.roleVoiceOffs) do
        if v == role_id then
            return false
        end
    end
    return true
end

function P:setIsCanVibrate(kind, flag)
    if kind == VibrateKind.UI then
        self.saveData.vibrateUI = flag
    elseif kind == VibrateKind.InGame then
        self.saveData.vibrateInGame = flag
    else
        self.saveData.vibrateOutGame = flag
    end
    self:onSave()
end

function P:isCanVibrate(kind)
    if kind == VibrateKind.UI then
        return self.saveData.vibrateUI
    elseif kind == VibrateKind.InGame then
        return self.saveData.vibrateInGame
    end
    return self.saveData.vibrateOutGame
end

-- 是否暂停刷新金币
function P:setIsStopRefreshGold(flag)
    self._isStopRefreshGold = flag
    if not flag then
        bee.emit(EventDef.evt_refreshTopInfo)
    end
end

function P:isStopRefreshGold()
    return self._isStopRefreshGold
end

-- 获取 key 的 cd 时间
function P:getKeyCD(key)
    local cd = self._cdKeys[key]
    if cd then
        local dt = cd.dt - (os.time() - cd.st)
        if dt > 0 then
            return dt
        end
        self._cdKeys[key] = nil
    end
    return 0
end

function P:setKeyCD(key, dt)
    self._cdKeys[key] = {
        key = key,
        dt = dt,
        st = os.time(),
    }
end

function P:addTag(tag)
    self._tmpTags[tag] = tag
end

-- 是否有设置了标记，访问过后立即删除
function P:hasTag(tag)
    local flag = self._tmpTags[tag] ~= nil
    self._tmpTags[tag] = nil
    return flag
end

function P:setScrapPlayer(data, uid, flag)
    self._scrapPlayers[data:getTid() .. uid] = flag
end

function P:clearScrapPlayers()
    self._scrapPlayers = {}
end

function P:isScrapPlayer(data, uid)
    return self._scrapPlayers[data:getTid() .. uid]
end

function P:isOnlineTagValid(tag)
    local key = "_onlineTags" .. PlayerModel:getUid()
    if not self[key] then
        self[key] = {}
    end
    if self[key][tag] then
        return false
    end
    self[key][tag] = true
    return true
end

function Pevt_videoPlayerError(msg)
    G_VIDEO_ERROR_MSG = msg
end

