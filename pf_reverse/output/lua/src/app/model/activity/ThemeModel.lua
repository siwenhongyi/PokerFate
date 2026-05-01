local P = class("ThemeModel", require("app.model.activity.ActivityBase"))

function P:ctor()
	self.saveData = {}
	P.super.ctor(self, ActivityId.Theme, ActivityType.TimeLimit)

    self._start_time = 0
    self._end_time = 0
    self._curPlotId = nil
    self._rewardedPlots = nil
    self._tasks = nil

    -- 礼服季剧情物品ID
    self.GalaStoryItems = {11100401,11100402,11100403}
    -- 开学季剧情物品ID
    self.SchoolStoryItems = {11100404,11100405,11100406}
    -- 兔女郎剧情物品ID
    self.BunnyGirlStoryItems = {11100407,11100408,11100409}
end

function P:afterLogin()
    self._start_time = 0
    self._end_time = 0
    self._curPlotId = nil
    self._rewardedPlots = nil
    self._tasks = nil
    self._inited = nil
end

function P:setConfId(confId)
    self._confId = confId
end

function P:getConfId()
    if not self._confId or 0 == self._confId then
        return ActivityId.HotSpring
    end
    return self._confId
end

function P:getConfData()
    return tpl_theme_activity[self:getConfId()]
end

function P:getItemId()
    local d = tpl_theme_activity[self:getConfId()]
    return d and d.activity_item or 0
end

function P:getCurRoleId()
    local id = CharacterModel:getUsingRoleId()
    local d = tpl_theme_activity[self:getConfId()]
    if d then
        for i = 1, #d.player_add - 1, 2 do
            if d.player_add[i] == id then
                return id
            end
        end
    end
    return 0
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
    if id == ActivityId.HotSpring then
        return bee.createObj("views/Hotspring/HotSpringAddition")
    elseif id == ActivityId.GalaSeason then
        return bee.createObj("views/GalaSeason/GalaAddition")
    elseif id == ActivityId.School then
        return bee.createObj("views/School/SchoolAddition")
    elseif id == ActivityId.BunnyGirl then
        return bee.createObj("views/BunnyGirl/BunnyGirlAddition")
    end
    return bee.createObj("views/Hotspring/HotSpringAddition")
end

-- 创建活动奖励角标
function P:createRewardTag(id)
    local id = id or self:getConfId()
    if id == ActivityId.HotSpring then
        return bee.createObj("views/GalaSeason/GalaReward")
    elseif id == ActivityId.GalaSeason then
        return bee.createObj("views/GalaSeason/GalaReward")
    elseif id == ActivityId.School then
        return bee.createObj("views/School/SchoolReward")
    elseif id == ActivityId.BunnyGirl then
        return bee.createObj("views/BunnyGirl/BunnyGirlReward")
    end
    return bee.createObj("views/GalaSeason/GalaReward")
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

function P:refreshReddot()
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
    end
end

function P:onActivityStart(d)
    if d[1] and d[2] and d[3] then
        self:setConfId(tonumber(d[1]))
        self._start_time = tonumber(d[2])
        self._end_time = tonumber(d[3])
        self._rewardedPlots = {}
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
        else
            self:setConfId(0)
            self._start_time = 0
            self._end_time = 0
            self._rewardedPlots = {}
        end
        self:refreshCurPlotId()

        self:refreshReddot()
        self:reqTaskList()

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

function P:reqSetCurRole(roleId, cb)
    CharacterModel:changeUsingRole(roleId)
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

function P:evt_serverTimeCrossDay()
	bee.once(math.random(1, 60), function()
        self:reqTaskList()
    end)
end

return P