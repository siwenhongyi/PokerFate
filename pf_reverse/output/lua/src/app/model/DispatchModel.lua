local P = class("DispatchModel", BaseModel)

P.EventStatus = {
    NoDispatch = 0,     -- 事务没有被派遣
    Dispatching = 1,    -- 事务派遣中
    Finish = 2,         -- 已完成但未领取奖励
    Claimed = 3,        -- 事务已领取奖励
}

function P:ctor()
    self.saveData = {}
    P.super.ctor(self)

    self.LEVEL_NAME = {"B", "A", "S", "SS", "SSS"}

    self._camp_list = {}
    self._role_list = {}
    self._event_list = {}

    self._record_list = {}
    self._record_origin_list = nil  -- 历史原始记录

    self.bond_rec_times = 0

    self._pass_info = {
        has_pass_card = nil,
        level = 0,
        item_num = 0,
        ordinary = {}, -- 已领取的普通奖励数组
        advanced = {},  -- 已领取的高级奖励数组
    }
end

function P:afterLogin()
    self:reqEventList()
    self:reqDispatchTaskList()
    self._record_origin_list = nil
    self._pass_info.has_pass_card = nil
    self._pass_info.item_num = 0
    self._pass_info.level = 0
    self:reqPassInfo()
end

function P:isOpenDispatch()
    local openTime = tpl_constdata.Dispatch_Start
    if PlayerModel:isEventWhite() then
        openTime = tpl_constdata.Dispatch_Start_Whitelist
    end
    local closeTime = tpl_constdata.Dispatch_End
    local curTime = bee.getServerTime()
    return curTime >= openTime and curTime <= closeTime
end

function P:setLastCampInt(campInt)
    self.saveData["last_camp_int" .. PlayerModel:getUid()] = campInt
    self:onSave()
end

function P:getLastCampInt()
    return self.saveData["last_camp_int" .. PlayerModel:getUid()]
end

-- 大厅图标状态
function P:getDispatchIconStatus()
    local isDispatching = false
    for _, campEvents in pairs(self._event_list) do
        for _, events in pairs(campEvents) do
            for _, e in pairs(events) do
                if e.end_ts and e.end_ts > 0 and e.end_ts <= bee.getServerTime() then
                    return DispatchModel.EventStatus.Finish
                elseif e.status == DispatchModel.EventStatus.Dispatching then
                    isDispatching = true
                end
            end
        end
    end
    if isDispatching then
        return DispatchModel.EventStatus.Dispatching
    else
        return DispatchModel.EventStatus.NoDispatch
    end
end

-- 播放剧情
function P:playStory(event, cb)
    local kind = #tpl_constdata.Dispatch_Reward_Level
    for k, v in ipairs(tpl_constdata.Dispatch_Reward_Level) do
        if not event.base_reward_up or event.base_reward_up <= v then
            kind = k
            break
        end
    end

    local role = CharacterModel:getRole(event.role_id)
    local skinCfg = role:getSkinData()
    local d = skinCfg.plot_dispatch
    if d and d[kind] then
        UiManager:showUI("Story", {id = d[kind], hideScene = true, fastSkip = true, bg = "BackGround/Dispatch/bg_dispatch_main_02.png", hideCb = function()
            if cb then
                cb(event)
            end
        end})
    else
        if cb then cb(event) end
    end
end

-- 显示好感提升
function P:showBondUp(event)
    local start_ts = 0
    if event then
        start_ts = event.start_ts
    end
    if self._RoleOverBondChangeRSP and self._RoleOverBondChangeRSP.over_info.over_bond_inc > 0 then
        local favorSign = LocalStore:isDailyTagValidCrossDay("role_favor" .. PlayerModel:getUid(), true)
        if favorSign then
            local role = CharacterModel:getRole(event.role_id)
            self._RoleOverBondChangeRSP.over_info.skin_id = role:getSkinData().id
            self._RoleOverBondChangeRSP.over_info.from = "Dispatch"
            self._RoleOverBondChangeRSP.over_info.start_ts = start_ts
            -- UiManager:showUI("IngameFeedback", {info = self._RoleOverBondChangeRSP.over_info})
            bee.showUiTask("IngameFeedback", {info = self._RoleOverBondChangeRSP.over_info}, nil, LOBBY_POP_PRIORITY.Reward)
        end
    elseif self._RoleBondChangeRSP and self._RoleBondChangeRSP.bond_inc > 0 then
        local favorSign = LocalStore:isDailyTagValidCrossDay("role_favor" .. PlayerModel:getUid(), true)
        if favorSign then
            local role = CharacterModel:getRole(event.role_id)
            bee.showUiTask("IngameBondsUp", {info = {
                role_id = event.role_id,
                bond_inc = self._RoleBondChangeRSP.bond_inc,
                cur_bond_level = self._RoleBondChangeRSP.level,
                old_bond_level = self._RoleBondChangeRSP.level + (self._RoleBondChangeRSP.bond_inc > self._RoleBondChangeRSP.bond_exp and -1 or 0),
                win_hands = 1,
                skin_id = role:getSkinData().id,
                from = "Dispatch",
                start_ts = start_ts,
            }}, nil, LOBBY_POP_PRIORITY.Reward)
        end
    end
end

function P:getLevelName(level)
    return self.LEVEL_NAME[level]
end

function P:getCampLevel(camp_id)
    for _, v in pairs(self._camp_list) do
        if v.camp_id == camp_id then
            return v.camp_level
        end
    end
    return 0
end

function P:setCampLevel(camp_id, level)
    for _, v in pairs(self._camp_list) do
        if v.camp_id == camp_id then
            v.camp_level = level
            return
        end
    end
end

function P:getEvent(event_id)
    for _, events in pairs(self._event_list) do
        if events[event_id] then
            return events[event_id]
        end
    end
    return nil
end

function P:getBondCount()
    return self.bond_rec_times
end

function P:getEggReward(event)
    local eventInfo = tpl_event_info[event.event_id]
    if eventInfo.reward_bonus_item then
        local roleCfg = tpl_character[event.role_id]
        local isBonus = roleCfg.campInt == eventInfo.campInt
        if isBonus then
            local bonusAdd = eventInfo.reward_bonus or 0
            local roleInfo = tpl_character_info[event.role_star]
            if roleInfo then
                bonusAdd = bonusAdd + roleInfo.reward_bonus
            end
            return eventInfo.reward_bonus_item, bonusAdd
        end
    end
    return nil, nil
end

function P:getRole(role_id)
    return self._role_list[role_id]
end

function P:addRoleExp(role_id, exp)
    local r = self:getRole(role_id)
    if not r then
        r = {
            role_id = role_id,
            role_star = 1,
            exp = 0,
            remain_dispatch_times = self:getRoleDispatchMaxTimes(role_id),
        }
        self._role_list[role_id] = r
    end
    if r then
        r.exp = r.exp + exp
        local d = tpl_character_info[r.role_star + 1]
        if d and r.exp >= d.star_exp then
            r.exp = r.exp - d.star_exp
            r.role_star = r.role_star + 1
            return true
        end
    end
    return false
end

-- 解锁/升级事务所
function P:upgradeCamp(camp_id, cb)
    local level = DispatchModel:getCampLevel(camp_id) + 1
    if level > 1 and not LocalStore:isDailyTagValidCrossDay("DispatchModel_upgradeCamp" .. PlayerModel:getUid(), true) then
        if not bee.checkCd("Unlock/afk/upCampLevel", 0.5) then
            return
        end
        local d = tpl_camp_info[level]

        local cost = camp_id == 0 and d.quality_up_cost1 or d.quality_up_cost2
        local item = ItemModel:getItem(GPropId.CampDispatchUpgrade, true)
        if item.num < cost then
            UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(item.name)))
            return
        end
        Net:post("afk/upCampLevel", {camp_id = camp_id, item_num = cost}, function(d)
            if 0 == d.code then
                DispatchModel:setCampLevel(camp_id, level)
                if 1 == level then
                    UiManager:showToast(_F("LAB_DISPATCH_50", _T(tpl_camp_detail[camp_id].camp_name)))
                else
                    UiManager:showUI("DispatchLevel", {camp_id = camp_id})
                end
                
                if cb then
                    cb()
                end
                DispatchModel:reqEventList(nil, true)
            end
        end)
    else
        UiManager:showUI("DispatchUnlock", {camp_id = camp_id, cb = cb})
    end
end

function P:refreshReddot()
    local seasonNum = 0
    for i = 0, self._pass_info.level do
        if table.indexof(self._pass_info.ordinary, i) < 0 or (self._pass_info.has_pass_card and table.indexof(self._pass_info.advanced, i) < 0) then
            seasonNum = 1
            break;
        end
    end
    RedManager:addTagWithNum(seasonNum, RedTag.DispatchSeasonPass)
    bee.emit("evt_updateLobbyDispatchAnim")
end

function P:reqEventList(rec_item, immediately)
    if not self:isOpenDispatch() then
        return
    end
    Net:post("afk/eventList", {rec_item = rec_item, immediately = immediately}, function(data)
        if data.code ~= 0 then
            return
        end

        self._camp_list = {}        -- 阵营列表
        if data.camp_list then
            for k, v in pairs(data.camp_list) do
                self._camp_list[v.camp_id] = v
            end
        end

        self._role_list = {}        -- 角色列表
        if data.role_list then
            for k, v in pairs(data.role_list) do
                self._role_list[v.role_id] = v
            end
        end

        self._event_list = {}       -- 委托事件列表
        if data.event_list then
            for k, v in pairs(data.event_list) do
                local eventInfo = tpl_event_info[v.event_id]
                if not self._event_list[eventInfo.campInt] then
                    self._event_list[eventInfo.campInt] = {}
                end
                if not self._event_list[eventInfo.campInt][v.event_id] then
                    self._event_list[eventInfo.campInt][v.event_id] = {}
                end
                table.insert(self._event_list[eventInfo.campInt][v.event_id], v)
            end
        end

        self:sortEventList()

        self._remain_free_refresh_times = data.remain_free_refresh_times
        self._remain_free_dispatch_times = data.remain_free_dispatch_times
        self._exp_reward = data.exp_reward
        self._bond_reward = data.bond_reward
        self.bond_rec_times = data.bond_rec_times

        if data.first_open and GuideManager:checkGuidePlayed(23002) then
            -- 获得普通派遣道具，未播放新手引导时不播放获得弹窗
            UiManager:showUI("BackpackClaimResult", {items = {{id = GPropId.OrdinaryDispatch, num = tpl_constdata.Dispatch_Free_Num}}})
        end

        bee.emit("evt_dispatchEventList")
    end)
end

function P:sortEventList()
    for _, campEvents in pairs(self._event_list) do
        for _, events in pairs(campEvents) do
            table.sort( events, function(a, b) return a.end_ts < b.end_ts end)
        end
    end
end

function P:setEventEndTime(id, end_ts)
    for _, campEvents in pairs(self._event_list) do
        for _, events in pairs(campEvents) do
            for _, e in pairs(events) do
                if e.id == id then
                    e.end_ts = end_ts
                    break
                end
            end
        end
    end
end

function P:reqRecordList(cb, isStart)
    if isStart then
        self._record_origin_list = nil
        self._record_list = {}
    end
    local skip = self._record_origin_list and #self._record_origin_list or 0
    Net:post("afk/recentlyList", {t = 1, skip = skip, limit = 20}, function(data)
        if data.code ~= 0 then
            return
        end

        if self._record_origin_list and #self._record_origin_list > skip then
            return
        end

        -- 根据 start_ts 和 event_id 合并记录，合并的数据放到 roles 里
        local merged = {}
        local rawList = data.event_list or {}
        if not self._record_origin_list then
            self._record_origin_list = rawList
        else
            for _, v in ipairs(rawList) do
                table.insert(self._record_origin_list, v)
            end
        end
        
        local record_list = {}
        for _, v in ipairs(rawList) do
            local key = v.start_ts .. "_" .. v.event_id
            if not merged[key] then
                merged[key] = v
                v.roles = {}
                table.insert(self._record_list, v)
                table.insert(record_list, v)
            end
            table.insert(merged[key].roles, v)
        end

        if cb then
            cb(record_list)
        end
    end)
end

function P:reqRecReward(event, cb)
    self._RoleBondChangeRSP, self._RoleOverBondChangeRSP = nil, nil
    Net:post("afk/recReward", {id = event.id}, function(data)
        if data.code ~= 0 then
            return
        end
        self.bond_rec_times = data.bond_rec_times
        local roleData = self:getDispatchRoleData(event.role_id)
        if roleData then
            event.role_star = roleData.role_star
        end
        self:addRoleExp(event.role_id, data.star_exp)

        self._showRewardEvent = clone(event)
        self._showRewardData = clone(data)

        self:reqEventList(nil, true)

        if cb then
            cb(event)
        end
    end)
end

function P:showRecReward()
    if not self._showRewardEvent then
        return
    end
    if not self._showRewardData then
        return
    end

    local event = self._showRewardEvent
    local data = self._showRewardData

    -- 道具奖励
    local items = {}
    if data.exp and data.exp > 0 then
        table.insert(items, {id = GPropId.ExpDispatch, num = data.exp})
    end
    if data.bond and data.bond > 0 then
        table.insert(items, {id = GPropId.BondDispatch, num = data.bond})
    end
    if data.star_exp and data.star_exp > 0 then
        table.insert(items, {id = GPropId.RoleDispatchExp, num = data.star_exp})
    end
    if data.camp_quality and data.camp_quality > 0 then
        table.insert(items, {id = GPropId.CampDispatchUpgrade, num = data.camp_quality})
    end
    if data.reward_bonus then
        for i = 1, #data.reward_bonus, 2 do
            local decompose_item = {id = data.reward_bonus[i], num = data.reward_bonus[i + 1]}
            table.insert(items, {id = GPropId.DispatchBonus, num = 0, decompose_item = decompose_item, is_decompose = true})
        end
    end
    if next(items) then
        self._showRewardEvent = nil
        self._showRewardData = nil
        bee.showUiTask("BackpackClaimResult", {items = items, cb = function()
            -- 牌手星级
            local roleData = self:getDispatchRoleData(event.role_id)
            if roleData.role_star ~= event.role_star then
                bee.showUiTask("DispatchStar", roleData, nil, LOBBY_POP_PRIORITY.Reward)
            end

            -- 牌手好感度
            if event.bond then
                self:showBondUp(event)
            end

            -- 角色等级
            if LocalStore:getBoolForKey("level_up_pop" .. PlayerModel:getUid(), false) then
                LocalStore:setBoolForKey("level_up_pop" .. PlayerModel:getUid(), false)
                bee.showUiTask("LevelUpgrade", {cb = function()
                    SettingModel:checkNewUnlockSys()
                end}, nil, LOBBY_POP_PRIORITY.Reward) 
            end

            bee.runTask()
        end}, nil, LOBBY_POP_PRIORITY.Reward)
    else
        return
    end

    bee.runTask()
end

-- 普通派遣剩余次数
function P:getRemainOrdinaryTimes()
    return self._remain_free_dispatch_times or 0
end

-- 免费刷新剩余次数
function P:getRemainFreeRefreshTimes()
    return self._remain_free_refresh_times or 0
end

-- 该阵营是否可刷新
function P:getCampIsCanRefresh(campId)
    local campLevel = self:getCampLevel(campId)
    local maxEventLevel = tpl_camp_info[campLevel].event_id
    local maxEventCount = 0
    for k, v in pairs(get_tpl_subKey(tpl_event_info_list, "campInt", campId)) do
        if v.event_level <= maxEventLevel then
            maxEventCount = maxEventCount + 1
        end
    end

    local dispatchCount = 0
    for k,v in pairs(self:getCampEventList(campId)) do
        if v[1].status == P.EventStatus.Dispatching or v[1].status == P.EventStatus.Finish then
            dispatchCount = dispatchCount + 1
        end
    end
    if dispatchCount >= math.min(tpl_constdata.Dispatch_Event_Num, maxEventCount) then
        return false
    end
    return true
end

function P:checkRefreshCamp(campId, cb)
    local campLevel = self:getCampLevel(campId)
    local maxEventLevel = tpl_camp_info[campLevel].event_id
    local eventList = self:getCampEventList(campId)

    -- 判断是否有最高级事务未派遣
    for k, v in pairs(eventList) do
        local eventCfg = tpl_event_info[v[1].event_id]
        if eventCfg.event_level == maxEventLevel and v[1].status == DispatchModel.EventStatus.NoDispatch then
            UiManager:showTip({
                text = _T("LAB_DISPATCH_122"),
                onSure = function()
                    self:requestRefreshCamp(campId, cb)
                end
            })
            return
        end
    end

    -- 判断事务所解锁的最高级事务都已刷新到列表里
    local maxLevelEventCount = 0
    for k, v in pairs(get_tpl_subKey(tpl_event_info_list, "campInt", campId)) do
        if v.event_level == maxEventLevel then
            maxLevelEventCount = maxLevelEventCount + 1
        end
    end
    local count = 0
    for k,v in pairs(eventList) do
        local eventCfg = tpl_event_info[v[1].event_id]
        if eventCfg.event_level == maxEventLevel then
            count = count + 1
        end
    end
    if count >= maxLevelEventCount then
        UiManager:showTip({
            text = _T("LAB_DISPATCH_123"),
            onSure = function()
                self:requestRefreshCamp(campId, cb)
            end
        })
        return
    end

    self:requestRefreshCamp(campId, cb)
end

function P:requestRefreshCamp(campId, cb)
    local itemId
    if self:getRemainFreeRefreshTimes() > 0 then
        itemId = 0
    else
        itemId = GPropId.RefreshDispatch
        if ItemModel:getItemNumById(itemId) <= 0 then
            UiManager:showToast(_T("LAB_COMMON_TIPS_1"))
            return
        end
    end
    Net:post("afk/refresh", {camp_id = campId, item_id = itemId}, function(data)
        if data.code ~= 0 then
            return
        end
        bee.logEvent("dispatch-refresh", campId, itemId == 0 and 1 or 2)
        if cb then
            cb()
        end
        self:reqEventList(nil, true)
    end)
end

function P:getCampData(campId)
    if not self._camp_list[campId] then
        return {
            camp_id = campId,
            camp_level = 0,
            refresh_able = false,
        }
    end
    return self._camp_list[campId]
end

function P:getCampEventList(campId)
    return self._event_list[campId]
end

function P:getCampEventIsCanReward(campId)
    if not self._event_list[campId] then
        return false
    end
    for _, events in pairs(self._event_list[campId]) do
        for _, e in pairs(events) do
            if e.status == DispatchModel.EventStatus.Finish then
                return true
            end
        end
    end
    return false
end

-- 角色每天可派遣次数
function P:getRoleDispatchMaxTimes(role_id)
    local roleData = CharacterModel:getRole(role_id)
    if not roleData then
        return 0
    end

    return tpl_constdata.Dispatch_Ordinary_Character_Num + (roleData:getOwnSkinCount() - 1) * tpl_constdata.Dispatch_Ordinary_Skin_Num
end

-- 派遣角色数据
function P:getDispatchRoleData(role_id)
    if self._role_list[role_id] then
        return self._role_list[role_id]
    else
        return {
            role_id = role_id,
            role_star = 1,
            exp = 0,
            remain_dispatch_times = self:getRoleDispatchMaxTimes(role_id),
            remain_advanced_dispatch_times = tpl_constdata.Dispatch_Advanced_Num,
        }
    end
end

-- 角色是否派遣中
function P:getRoleDispatchingEvent(role_id)
    for _, events in pairs(self._event_list) do
        for _, e in pairs(events) do
            for _, v in pairs(e) do
                if v.role_id == role_id and v.end_ts > bee.getServerTime() then
                    return v
                end
            end
        end
    end
    return nil
end

function P:evt_RoleBondChangeRSP(msg)
    self._RoleBondChangeRSP = msg
end

function P:evt_RoleOverBondChangeRSP(msg)
    self._RoleOverBondChangeRSP = msg
end

-- 未派遣时间显示
function P:getDispatchTimeText1(dt)
    dt = math.floor(dt)
    local h = math.floor(dt / 3600)
    local m = math.floor((dt % 3600) / 60)
    local s = dt % 60

    if h > 0 then
        return _F("LAB_SHOP_COMMON_26", h, m)
    elseif m > 0 then
        if s > 0 then
            return _F("LAB_SHOP_COMMON_25", m) .. _F("LAB_TIME_SECONDS", s)
        else
            return _F("LAB_SHOP_COMMON_25", m)
        end
    else
        return _F("LAB_TIME_SECONDS", s)
    end
end

-- 派遣中时间显示
function P:getDispatchTimeText2(dt)
    local h = math.floor(dt / 3600)
    local m = math.floor((dt % 3600) / 60)
    local s = dt % 60
    return string.format("%d:%02d:%02d", h, m, s)
end

function P:reqDispatch(event_id, roles, item_id)
    local params = {}
    params.event_id = event_id
    params.role_id_arr = roles
    params.item_id = item_id
    params.avatar_arr = {}
    params.skin_id_arr = {}
    for i, v in ipairs(roles) do
        local role = CharacterModel:getRole(v)
        local skinCfg = role:getSkinData()
        table.insert(params.avatar_arr, tpl_props[skinCfg.avatar].id)
        table.insert(params.skin_id_arr, skinCfg.id)
    end
    Net:post("afk/dispatch", params, function(data)
        if data.code ~= 0 then
            return
        end

        self:reqEventList(nil, true)
    end)
end

function P:isCanRewardExp()
    return self._exp_reward
end

function P:isCanRewardBond()
    return self._bond_reward
end

function P:setSkipPlot(isOn)
    self.saveData["isSkipPlot" .. PlayerModel:getUid()] = isOn
    self:onSave()
end

function P:getSkipPlot()
    if not self.saveData["isSkipPlot" .. PlayerModel:getUid()] then
        return false
    else
        return self.saveData["isSkipPlot" .. PlayerModel:getUid()]
    end
end

--------------------- 通行证 ---------------------------
function P:getPassInfo()
    return self._pass_info
end

function P:addPassExp(exp)
    self._pass_info.item_num = self._pass_info.item_num + exp
    if self._pass_info.item_num > 0 then
        for i = self._pass_info.level, #tpl_passcard_info_list do
            if i > 0 then
                if tpl_passcard_info_list[i].level_up_cost <= self._pass_info.item_num then
                    self._pass_info.level = tpl_passcard_info_list[i].level
                else
                    break
                end
            end
        end
    end
end

function P:reqPassInfo(force, cb)
    if not force and self._pass_info.has_pass_card ~= nil then
        return
    end
    Net:post("afk/passCardData", {t = 1, immediately = force}, function(data)
        if data.code ~= 0 then
            return
        end

        self._pass_info.has_pass_card = data.has_pass_card
        self._pass_info.ordinary = data.data.ordinary
        self._pass_info.advanced = data.data.advanced
        self._pass_info.item_num = 0
        self._pass_info.level = 0
        self:addPassExp(data.item_num or 0)

        if cb then
            cb()
        end
        bee.emit("evt_passCardData")
        self:refreshReddot()
    end)
end

-- 请求领取通行证奖励
function P:reqPassReward(level, advanced, all, cb)
    Net:post("afk/recPassCardReward", {level = level, advanced = advanced, all = all}, function(data)
        if data.code ~= 0 then
            return
        end

        if data.data then
            self._pass_info.ordinary = data.data.ordinary
            self._pass_info.advanced = data.data.advanced
        end

        UiManager:showUI("BackpackClaimResult", {items = data.item_list})

        if cb then
            cb()
        end
        self:refreshReddot()
    end)
end

function P:evt_ItemChangeRSP(msg)
    for _, v in ipairs(msg.item_list) do
        if v.item_id == GPropId.CampDispatchUpgrade then
            bee.once(1, function()
                self:reqPassInfo(true)
            end)
            break
        end
    end
end

-- ==================== 派遣成就奖励 ====================

function P:reqDispatchTaskList()
    if not self:isOpenDispatch() then
        return
    end
    Net:post("task/dispatchTaskList", nil, function(data)
        if data.code ~= 0 then
            return
        end

        self._task_list = data.list
        self._season_reward = data.season_reward
        self:refreshTaskRedTag()
        bee.emit("evt_updateDispatchTask")
    end)
end

function P:refreshTaskRedTag()
    if not self._task_list then
        return
    end
    local totalCount = 0
    local completedCount = 0
    local waitReceivedCount = 0
    for k, v in pairs(self._task_list) do
        totalCount = totalCount + 1
        if v.status ~= TaskStatus.InProgress then
            completedCount = completedCount + 1
            if v.status == TaskStatus.Completed then
                waitReceivedCount = waitReceivedCount + 1
            end
        end
    end

    local isCompleteSeason = completedCount >= totalCount
    if isCompleteSeason and not self._season_reward then
        waitReceivedCount = waitReceivedCount + 1
    end

    RedManager:addTagWithNum(waitReceivedCount, RedTag.DispatchReward)
    bee.emit("evt_updateLobbyDispatchAnim")
end

function P:getTaskList()
    return self._task_list or {}
end

function P:seasonRewardIsReward()
    return self._season_reward
end

function P:reqRecDispatchTaskRw(ids)
    Net:post("task/recDispatchTaskRw", {id_arr = ids}, function(data)
        if data.code ~= 0 then
            return
        end
        UiManager:showUI("BackpackClaimResult", {items = data.item_list})
        self:reqDispatchTaskList()
    end) 
end

function P:reqRecSeasonReward(ids)
    Net:post("afk/recSeasonReward", {id_arr = ids}, function(data)
        if data.code ~= 0 then
            return
        end
        self._season_reward = data.season_reward
        UiManager:showUI("BackpackClaimResult", {items = data.item_list})
        self:reqDispatchTaskList()
    end)
end

function P:evt_NoticeBRC(params)
    if params.type == tpl_PushConsts.DISPATCH_TASK_REFRESH.code then
        self:reqDispatchTaskList()
    end
end

return P