local P = class("ThemeModel", require("app.model.activity.ActivityBase"))
ThemeModel = P

function P:ctor()
	self.saveData = {}
	P.super.ctor(self, ActivityId.Theme, ActivityType.TimeLimit)

    self._start_time = 0
    self._end_time = 0
    self._curPlotId = nil
    self._rewardedPlots = nil
    self._pointRewardList = nil
    self._tasks = nil

    self.ExpandData = {
        [ActivityId.HotSpring] = {path = "views/HotSpring", lobbybtn = "LobbyHotSpring", mainview = "HotSpringHall", reddot = "HotSpring", addition = "HotSpringAddition", reward = "GalaReward"},
        [ActivityId.GalaSeason] = {path = "views/GalaSeason", lobbybtn = "LobbyGalaSeason", mainview = "GalaSeasonMain", reddot = "GalaSeason", addition = "GalaAddition", reward = "GalaReward"},
        [ActivityId.School] = {path = "views/School", lobbybtn = "LobbySchool", mainview = "SchoolMain", reddot = "School", addition = "SchoolAddition", reward = "SchoolReward"},
        [ActivityId.BunnyGirl] = {path = "views/BunnyGirl", lobbybtn = "LobbyBunnyGirl", mainview = "BunnyGirl", reddot = "BunnyGirl", addition = "BunnyGirlAddition", reward = "BunnyGirlReward"},
        [ActivityId.Sports] = {path = "views/Sports", lobbybtn = "LobbySports", mainview = "SportsMain", reddot = "Sports", addition = "SportsAddition", reward = "SportsReward"},
        [ActivityId.Sayaka] = {path = "views/Sayaka", lobbybtn = "LobbySayaka", mainview = "SayakaMain", reddot = "Sayaka", addition = "SayakaAddition", reward = "SayakaReward"},
        [ActivityId.Matsuri] = {path = "views/Matsuri", lobbybtn = "LobbyMatsuri", mainview = "MatsuriMain", reddot = "Matsuri", addition = "MatsuriAddition", reward = "MatsuriReward"},
        [ActivityId.Racing] = {path = "views/Racing", lobbybtn = "LobbyRacing", mainview = "RacingMain", reddot = "Racing", addition = "RacingAddition", reward = "RacingReward"},
        [ActivityId.Fantasy] = {path = "views/Fantasy", lobbybtn = "LobbyFantasy", mainview = "FantasyMain", reddot = "Fantasy", addition = "FantasyAddition", reward = "FantasyReward"},
    }

    -- 礼服季剧情物品ID
    self.GalaStoryItems = {11100401,11100402,11100403}
    -- 开学季剧情物品ID
    self.SchoolStoryItems = {11100404,11100405,11100406}
    -- 兔女郎剧情物品ID
    self.BunnyGirlStoryItems = {11100407,11100408,11100409}
    -- 运动会剧情物品ID
    self.SportsStoryItems = {11100411,11100410,11100412}
end

function P:afterLogin()
    self._start_time = 0
    self._end_time = 0
    self._curPlotId = nil
    self._rewardedPlots = nil
    self._pointRewardList = nil
    self._tasks = nil
    self._inited = nil
end

function P:setConfId(confId)
    self._confId = confId
    bee.emit("evt_getThemeIdCallback")
end

function P:getConfId()
    if not self._confId or 0 == self._confId then
        return ActivityId.HotSpring
    end
    return self._confId
end

function P:getThemeConfId()
    return self._confId
end

function P:getConfData()
    return tpl_theme_activity[self:getConfId()]
end

function P:getItemId()
    local d = tpl_theme_activity[self:getConfId()]
    return d and d.activity_item or 0
end

function P:getPointId()
    local d = tpl_theme_activity[self:getConfId()]
    return d and d.points_item or 0
end

function P:getCurRoleId()
    local id = CharacterModel:getUsingRoleId()
    local d = tpl_theme_activity[self:getConfId()]
    if d and d.player_add then
        for i = 1, #d.player_add - 1, 2 do
            if d.player_add[i] == id then
                return id
            end
        end
    end
    return 0
end

function P:getSkinAddEffectIndex()
    local data = tpl_theme_activity[self:getConfId()]
    local effTimeCount = #data.add_time
    local effIndex = 0

    for i = 1, effTimeCount do
        if bee.getServerTime() > data.add_time[i] then
            effIndex = i
        end
    end

    --test
    if effIndex == 0 then
        effIndex = 1
    end
    if PlayerModel:isEventWhite() then
        effIndex = effTimeCount
    end

    return effIndex
end

function P:getSkinAddEffectList()
    local data = tpl_theme_activity[self:getConfId()]
    local effIndex = self:getSkinAddEffectIndex()
    if data.skin_add then
        return data.skin_add[effIndex]
    else
        return nil
    end
end

function P:getCurSkinAddData()
    local isRandom = DecorationModel:isInGameSchemeRandom()
    local skinList = {}
    if not isRandom then
        local scheme = DecorationModel:getInGameSchemeInfoById(DecorationModel:getInGameSpecifySchemeId())
        if scheme then
            for _,sv in pairs(scheme.skin_id) do
                table.insert(skinList, sv)
            end
        end
    else
        local ids = DecorationModel:getInGameRandomSchemeList()
        for _,v in pairs(ids) do
            local scheme = DecorationModel:getInGameSchemeInfoById(v)
            if scheme then
                for _,sv in pairs(scheme.skin_id) do
                    table.insert(skinList, sv)
                end
            end
        end
    end

    local effList = self:getSkinAddEffectList()
    if effList then
        for i = 1, #effList - 1, 2 do
            for _,v in pairs(skinList) do
                if effList[i] == v then
                    return {effList[i], effList[i + 1]}
                end
            end
        end
    end

    -- local roleId = CharacterModel:getUsingRoleId()
    -- local skinData = CharacterModel:getRoleSkinData(roleId)
    -- local effList = self:getSkinAddEffectList()
    
    -- if effList then
    --     for i = 1, #effList - 1, 2 do
    --         if effList[i] == skinData.id then
    --             return {effList[i], effList[i + 1]}
    --         end
    --     end
    -- end
    return nil
end

function P:getCurPlotId()
    return self._curPlotId or 0
end

function P:isHaveAddtion(gameType)
    if self:isActivityOpen() then
        local d = self:getConfData()
        if d and d.mod then
            for _, v in ipairs(d.mod) do
                if v == gameType then
                    return true
                end
            end
        end
    end
    return false
end

function P:createAddtionButton()
    local id = self:getConfId()
    local data = self.ExpandData[id]
    return bee.createObj(data.path .. "/" .. data.addition)
end

-- 创建活动奖励角标
function P:createRewardTag(id)
    local id = id or self:getConfId()
    local data = self.ExpandData[id]
    return bee.createObj(data.path .. "/" .. data.reward)
end

function P:isPlotRewarded(plotId)
    if self._rewardedPlots then
        for _, v in ipairs(self._rewardedPlots) do
            if v == plotId then
                return true
            end
        end
    end
    return false
end

function P:getStoryData(item_id)
    local data = self:getConfData()
    if not data then return nil end

    local storys = get_tpl_subKey(tpl_theme_storys_list, "group", data.storys)
    for _, v in ipairs(storys) do
        if v.unlock_item and v.unlock_item[1] == item_id then
            return v
        end
    end
    return nil
end

function P:getTasks()
    return self._tasks or {}
end

function P:getTask(taskId)
    if self._tasks then
        for _, v in ipairs(self._tasks) do
            if v.task_id == taskId then
                return v
            end
        end
    end
    return nil
end

function P:getOpenDay()
    local day = math.floor((bee.getServerTime() - self._start_time + 25200) / 86400)
    if day < 0 then day = 0 end
    return day
end

function P:refreshReddot(onlyRefreshData)
    local taskNum = 0
    local tasks = ThemeModel:getTasks()
    for _, v in ipairs(tasks) do
        if v.status == TaskStatus.Completed then
            taskNum = taskNum + 1
        end
    end
    if self:getConfId() == ActivityId.HotSpring then
        RedManager:addTagWithNum(taskNum, RedTag.HotSpringTask)
    elseif self:getConfId() == ActivityId.GalaSeason then
        RedManager:addTagWithNum(taskNum, RedTag.GalaSeasonTask)

        local storyNum = 0
        for _, v in ipairs(self.GalaStoryItems) do
            if ItemModel:getItemNumById(v) > 0 then
                local d = self:getStoryData(v)
                if d and not self:isPlotRewarded(d.id) then
                    storyNum = storyNum + 1
                end
            end
        end
        RedManager:addTagWithNum(storyNum, RedTag.GalaSeasonPlot)
    elseif self:getConfId() == ActivityId.School then
        RedManager:addTagWithNum(taskNum, RedTag.SchoolTask)

        local storyNum = 0
        for _, v in ipairs(self.SchoolStoryItems) do
            if ItemModel:getItemNumById(v) > 0 then
                local d = self:getStoryData(v)
                if d and not self:isPlotRewarded(d.id) then
                    storyNum = storyNum + 1
                end
            end
        end
        RedManager:addTagWithNum(storyNum, RedTag.SchoolPlot)
    elseif self:getConfId() == ActivityId.BunnyGirl then
        RedManager:addTagWithNum(taskNum, RedTag.BunnyGirlTask)

        local storyNum = 0
        for _, v in ipairs(self.BunnyGirlStoryItems) do
            if ItemModel:getItemNumById(v) > 0 then
                local d = self:getStoryData(v)
                if d and not self:isPlotRewarded(d.id) then
                    storyNum = storyNum + 1
                end
            end
        end
        RedManager:addTagWithNum(storyNum, RedTag.BunnyGirlPlot)
    elseif self:getConfId() == ActivityId.Sports then
        RedManager:addTagWithNum(taskNum, RedTag.SportsTask)
        
        local storyNum = 0
        for _, v in ipairs(self.SportsStoryItems) do
            if ItemModel:getItemNumById(v) > 0 then
                local d = self:getStoryData(v)
                if d and not self:isPlotRewarded(d.id) then
                    storyNum = storyNum + 1
                end
            end
        end
        RedManager:addTagWithNum(storyNum, RedTag.SportsPlot)
    elseif self:getConfId() == ActivityId.Sayaka then
        RedManager:addTagWithNum(taskNum, RedTag.SayakaTask)
    elseif self:getConfId() == ActivityId.Matsuri then
        RedManager:addTagWithNum(taskNum, RedTag.MatsuriTask)
    elseif self:getConfId() == ActivityId.Racing then
        RedManager:addTagWithNum(taskNum, RedTag.RacingTask)
    elseif self:getConfId() == ActivityId.Fantasy then
        local itemData = ItemModel:getItem(self:getPointId())
        local points = itemData and itemData.num or 0
        local pointRewards = get_tpl_subKey(tpl_theme_points_rewards_list, "rewards_group", self:getConfId())
        for _,v in pairs(pointRewards) do
            local geted = self:checkPointRewardGeted(v.id)
            if not geted and points >= v.point then
                taskNum = taskNum + 1
            end
        end
        RedManager:addTagWithNum(taskNum, RedTag.FantasyTask)
        if not onlyRefreshData then
            bee.emit("evt_themeRefreshTask")
        end
    end
end

function P:evt_ItemListRSP()
    self:refreshReddot()
end

function P:onActivityStart(d)
    if d[1] and d[2] and d[3] then
        self:setConfId(tonumber(d[1]))
        self._start_time = tonumber(d[2])
        self._end_time = tonumber(d[3])
        self._rewardedPlots = {}
        self._pointRewardList = {}
        self:refreshCurPlotId()
        self:refreshReddot()
        self:reqTaskList()
        bee.emit(EventDef.evt_activity_get, self._actId)
    end
end

function P:reqActivityData()
    if self._inited then
        return
    end
    
    self._confId = nil
	Net:post("/activity/themeActivity", {t = 1}, function(data)
        self._inited = true
		if data.code ~= 0 then
			return
		end

        if data.data then
            self:setConfId(data.data.id)
            self._start_time = data.data.start_ts
            self._end_time = data.data.end_ts
            self._rewardedPlots = data.data.list or {}
            self._pointRewardList = data.data.points_list or {}
        else
            self:setConfId(0)
            self._start_time = 0
            self._end_time = 0
            self._rewardedPlots = {}
            self._pointRewardList = {}
        end
        self:refreshCurPlotId()

        self:refreshReddot()
        self:reqTaskList()

        if tpl_theme_activity[self._confId] and tpl_theme_activity[self._confId].pool_group then
            self:reqThemePool()
        end

        bee.emit(EventDef.evt_activity_get, self._actId)
	end, nil, false)
end

function P:refreshCurPlotId()
    self._curPlotId = 0
    if self._rewardedPlots then
        for _, v in ipairs(self._rewardedPlots) do
            if v > self._curPlotId then
                self._curPlotId = v
            end
        end
    end
end

function P:checkPointRewardGeted(id)
    if self._pointRewardList then
        return table.keyof(self._pointRewardList, id) and true or false
    end
    return false
end

function P:reqSetCurRole(roleId, cb)
    CharacterModel:changeUsingRole(roleId)
end
function P:reqSetCurSkin(skinId)
    CharacterModel:changeUsingSkin(skinId)
end
function P:setCurSkin(skinId)
    DecorationModel:useInGameSkin(skinId)
end

function P:reqPlotReward(plotId, cb)
    for _, v in ipairs(self._rewardedPlots) do
        if v == plotId then
            return false
        end
    end
	Net:post("/activity/recThemeActStoryRw", {id = self:getConfId(), story_id = plotId}, function(data)
		if data.code ~= 0 or not data.item_list then
			return
		end
        table.insert(self._rewardedPlots, plotId)
        self:refreshCurPlotId()
        
        if cb then
            cb()
        end

        self:refreshReddot()

        UiManager:showUI("BackpackClaimResult", {
            items = data.item_list
        })
	end)
    return true
end

function P:reqTaskList(cb)
	Net:post("/task/activityTaskList", {id = self:getConfId()}, function(data)
		if data.code ~= 0 then
			return
		end
        self._tasks = data.list

        self:refreshReddot()
        if cb then
            cb()
        end
	end)
end

function P:reqTaskReward(id, cb, ids)
    local id_arr = ids or {id}
    Net:post("/task/recReward", {id_arr = id_arr, task_cate = 4, all = nil ~= ids, mask = "reward"}, function(data)
        if data.code ~= 0 then
            return
        end

        for _, v in ipairs(self._tasks) do
            if table.indexof(id_arr, v.id) > 0 then
                v.status = TaskStatus.Received
            end
        end

        if cb then
            cb()
        end

        self:refreshReddot()

        if data.item_list then
            UiManager:showUI("BackpackClaimResult", {
                items = data.item_list
            })
        end
    end)
end

function P:checkAutoPop()
end

function P:isActivityOpen(subId)
    -- if bee.isDev then return true end
    if not subId or subId == self:getConfId() then
        if self._start_time > 0 then
            local ct = bee.getServerTime()
            if ct >= self._start_time and ct <= self._end_time then
                return true
            end
        end
    end
    return false
end

--获取对应活动道具图标
function P:getThemeIcon()
    local itemId = self:getItemId()
    return tpl_props[itemId].icon
end

function P:getEndTime(subId)
    if not subId or subId == self:getConfId() then
        return self._end_time or 0
    end
    return 0
end

--检测是否为当前活动的剧情
function P:checkStory(name)
    for _,v in pairs(tpl_theme_storys) do
        if v.res == name and v.group == self:getConfId() then
            return true
        end
    end
    return false
end

function P:evt_serverTimeCrossDay()
	bee.once(math.random(1, 60), function()
        self:reqTaskList()
    end)
end

-- 获取跨天剩余时间
function P:getCrossDayLeftTime()
    local curTime = bee.getServerTime()
    local utcDate = os.date("!*t", curTime)

    -- 把服务器时间换算到目标时区的本地时间
    local targetHour = (utcDate.hour + TimeHelp.targetZone) % 24
    local targetMin = utcDate.min
    local targetSec = utcDate.sec
    local currentTargetSec = targetHour * 3600 + targetMin * 60 + targetSec
    local crossSec = TimeHelp.crossHour * 3600

    if currentTargetSec < crossSec then
        return crossSec - currentTargetSec
    end

    return 24 * 3600 - currentTargetSec + crossSec
end


-- =============================== 抽奖活动 ===============================
-- 获取抽奖数据
function P:reqThemePool()
    if not self._confId then
        return
    end
    Net:post("activity/themePool", {id = self._confId}, function(data)
        if data.code ~= 0 then
            return
        end

        self._theme_pool_id = data.pool_id
        self._theme_pool_list = {}
        if data.data then
            for k,v in pairs(data.data) do
                self._theme_pool_list[tonumber(k)] = tonumber(v)
            end
        end

        bee.emit("evt_updateThemePool")
    end)
end

-- 抽奖
function P:reqThemePoolDraw(num)
    local params = {}
    params.id = self._confId
    params.pool_id = self._theme_pool_id
    params.num = num
    Net:post("activity/themePoolDraw", params, function(data)
        if data.code ~= 0 then
            return
        end

        if data.data then
            for id, num in pairs(data.data) do
                self._theme_pool_list[tonumber(id)] = tonumber(num)
            end
        end

        -- 获得弹窗
        if data.list then
            ShopModel:showRewardView(data.list)
        end

        bee.emit("evt_updateThemePool")
        bee.emit("evt_lotteryEvent")
    end)
end

-- 解锁奖池
function P:reqThemePoolUnlock()
    local id
    for k,v in pairs(tpl_theme_pool_info) do
        if v.pre_pool and v.pre_pool == self._theme_pool_id then
            id = v.id
            break
        end
    end
    Net:post("activity/themePoolUnlock", {id = self._confId, pool_id = id}, function(data)
        if data.code ~= 0 then
            return
        end
        self._theme_pool_id = data.pool_id
        bee.emit("evt_updateThemePool")
    end)
end

function P:getThemePoolId()
    return self._theme_pool_id
end

function P:getThemePoolItemNum(id)
    return self._theme_pool_list[id] or 0
end

function P:getThemePoolRemainNum(poolId)
    local list = get_tpl_subKey(tpl_theme_pool_list, "pool_id", poolId)
    local remainNum = 0
    for k, v in pairs(list) do
        if not v.num then
            return 9999
        else
            remainNum = remainNum + v.num - self:getThemePoolItemNum(v.id)
        end
    end
    return remainNum
end

function P:getThemePoolIsCanRefresh(poolId)
    local list = get_tpl_subKey(tpl_theme_pool_list, "pool_id", poolId)
    for k, v in pairs(list) do
        if v.is_core then
            if self:getThemePoolItemNum(v.id) < v.num then
                return false
            end
        elseif not v.num then
            return false
        end
    end
    return true
end

--领取积分奖励
function P:getThemePointReward()
    Net:post("activity/recThemePointRw", {id = self._confId}, function(data)
        if data.code ~= 0 then
            return
        end

        self._pointRewardList = data.points_list
        UiManager:showUI("BackpackClaimResult", {items = data.list})
        bee.emit("evt_getThemePointRewardCallback")
    end)
end

return P