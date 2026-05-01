local P = class("AchievementModel", BaseModel)
AchievementModel = P

function P:ctor(logic)
    P.super.ctor(self)

    self.achDic = {}
    self.getedRewardIds = {}
    self.storeKey = ""
    self.newTagDic = {}
    self.clearDic = {}



    self.reddotLink = {
        [101] = RedTag.AchTheme1,
        [201] = RedTag.AchTheme2,
        [301] = RedTag.AchTheme3,
        [401] = RedTag.AchTheme4,
        [501] = RedTag.AchTheme5,
    }
    self.themeLink = {
        [101] = 1,
        [201] = 2,
        [301] = 3,
        [401] = 4,
        [501] = 5,
    }

end

function P:initDatas(dataStr)

end

function P:getTotalNum(ach_level)
    return self.clearDic[ach_level]
end

function P:evt_clearAchievement(msg)
    UiManager:showUI("AchievementTips", {clearIds = msg.clearIds})
    for _,v in pairs(msg.clearIds) do
        local cfg = tpl_achievement_task[v]
        self.clearDic[cfg.ach_level] = self.clearDic[cfg.ach_level] + 1
    end
    RedManager:addTag(RedTag.Achievement)
end

function P:getLocalSaveData()
    local storeKey = "AchievementKey" .. PlayerModel:getUid()
    local saveData = LocalStore:getTableData(storeKey) or {}
    if next(saveData) == nil then
        local data = {}
        for _,v in pairs(self.themeLink) do
            data[v] = {clearList = {}}
        end
        saveData = data
        self:saveLocalSaveData(saveData)
    end
    return saveData
end
function P:saveLocalSaveData(saveData)
    local storeKey = "AchievementKey" .. PlayerModel:getUid()
    LocalStore:saveTableData(storeKey, saveData)
end

--请求成就
function P:requestAchTask()
    Net:post("task/achTaskList", {})
end

--请求成就完成数量
function P:requestAchTaskClearCount()
    Net:post("task/achTaskCount", {}, function (data)
        if data.code ~= 0 then
            return
        end
        local achList = data.list or {}
        self:refreshLobbyRedPoint(achList)
        for i = 1, 3 do
            self.clearDic[i] = 0
        end
        local achLvList = data.level_list or {}
        for _,v in pairs(achLvList) do
            self.clearDic[v.ach] = v.count
        end
    end)
end

function P:refreshLobbyRedPoint(dataList)
    RedManager:removeTag(RedTag.Achievement)
    local saveData = self:getLocalSaveData()

    local redTag = false
    for _,v in pairs(dataList) do
        local themeData = saveData[self.themeLink[v.ach]] or {}
        local subRedTag = false
        --判定数量
        local saveList = themeData.clearList or {}
        if table.nums(saveList) < v.count then
            subRedTag = true
        end
        --成就未领取判定
        if themeData.achGetable and themeData.achGetable > 0 then
            subRedTag = true
        end
        --主题奖励未领取判定
        if themeData.themeGetable then
            subRedTag = true
        end

        --主题红点
        if subRedTag then
            redTag = true
            RedManager:addTag(self.reddotLink[v.ach])
        end
    end

    --成就红点
    if redTag then
        RedManager:addTag(RedTag.Achievement)
    end
end

function P:refreshThemeRedPoint(themeId)
    local redThemeType = self.reddotLink[themeId]
    RedManager:removeTag(redThemeType)
    
    local datas = self.newTagDic[themeId]
    if table.nums(datas.newList) > 0 or table.nums(datas.rewardList) > 0 or datas.themeReward then
        RedManager:addTag(redThemeType)
    end
    bee.emit("evt_refreshAchievementThemeReddot", themeId)
end

--请求成就数据
function P:requestAchTaskList()
    for _,v in pairs(tpl_achievement_theme) do
        self.achDic[v.id] = {}
    end

    Net:post("task/achTaskList", {resp = true}, function (data)
        if data.code ~= 0 then
            return
        end
        for _,v in pairs(data.list) do
            local cfg = tpl_achievement_task[v.task_id]
            table.insert(self.achDic[cfg.ach_type], {data = v, cfg = cfg})
        end
        self.getedRewardIds = data.ids_arr or {}

        bee.emit("evt_refreshAchievement")
    end)
end

--整理数据
function P:arrangeData(themeId)
    local saveData = self:getLocalSaveData()
    local linkThemeId = self.themeLink[themeId]
    local clearList = {}
    if saveData[linkThemeId] and saveData[linkThemeId].clearList then
        clearList = saveData[linkThemeId].clearList
    end

    local achList = self.achDic[themeId]
    self.newTagDic[themeId] = {}
    local newList = {}
    local rewardList = {}
    local themeReward = false
    local unfinished = false
    for _,v in pairs(achList) do
        if (table.keyof(clearList, v.data.task_id) == nil and (v.data.status == 2 or v.data.status == 3)) then --第一次完成
            table.insert(newList, v.data.task_id)
        end
        if v.cfg.rewards and table.nums(v.cfg.rewards) ~= 0 and v.data.status == 2 then  --已完成但奖励未领取
            table.insert(rewardList, v.data.task_id)
        end
        if v.data.status < 2 then
            unfinished = true
        end
    end
    if table.keyof(self.getedRewardIds, themeId) == nil and not unfinished then --所有奖励都完成但主题奖励未领取
        themeReward = true
    end
    self.newTagDic[themeId] = {
        newList = newList,
        rewardList = rewardList,
        themeReward = themeReward,
    }
    
    if saveData[self.themeLink[themeId]] == nil then
        saveData[self.themeLink[themeId]] = {}
        saveData[self.themeLink[themeId]].clearList = {}
    end
    saveData[self.themeLink[themeId]].achGetable = table.nums(rewardList)
    saveData[self.themeLink[themeId]].themeGetable = themeReward
    self:saveLocalSaveData(saveData)
end

--请求最近完成成就
function P:requestRecentlyAchTask()
    Net:post("task/recentlyAchTaskList", {}, function (data)
        if data.code ~= 0 then
            return
        end
        bee.emit("evt_refreshRecentlyAchievement", data.list)
    end)
end

--对应主题id的成就数据
function P:getClearAchievementData(themeId)
    return self.newTagDic[themeId]
end

--刷新完成的成就
function P:refreshClearAchievement()
    -- local clearDic = {
    --     [1] = 0,
    --     [2] = 0,
    --     [3] = 0,
    -- }
    -- local clearCount = 0
    -- local total = 0
    -- for _,v in pairs(self.achDic) do
    --     for _,val in pairs(v) do
    --         total = total + 1
    --         if val.data.status >= 2 then
    --             clearDic[val.cfg.ach_level] = clearDic[val.cfg.ach_level] + 1
    --             clearCount = clearCount + 1
    --         end
    --     end
    -- end

    local clearCount = 0
    for _,v in pairs(self.clearDic) do
        clearCount = clearCount + v
    end
    local total = 0
    for _,v in pairs(self.achDic) do
        total = total + table.nums(v)
    end
    bee.emit("evt_refreshAchievementValue", {dic = self.clearDic, clearCount = clearCount, total = total})
end

--领取主题奖励 
function P:getThemeRewared(themeId)
    local args = {
        ids_arr = {themeId},
    }
    Net:post("task/recAchReward", args, function (data)
        if data.code ~= 0 then
            return
        end
        if data.item_list == nil then
            return
        end

        UiManager:showUI("BackpackClaimResult", {items = data.item_list})
        table.insert(self.getedRewardIds, themeId)
        bee.emit("evt_refreshThemeReward", themeId)
        self:getedThemeReward(themeId)
    end)
end

--领取成就奖励
function P:getAchievementReward(themeId, achId)
    local args = {
        task_id_arr = {achId},
    }
    Net:post("task/recAchReward", args, function (data)
        if data.code ~= 0 then
            return
        end
        if data.item_list == nil then
            return
        end

        UiManager:showUI("BackpackClaimResult", {items = data.item_list})
        local list = self.achDic[themeId]
        for _,v in pairs(list) do
            if v.data.task_id == achId then
                v.data.status = 3
                break
            end
        end
        self:getedAchievementReward(themeId, achId)
        bee.emit("evt_refreshAchievementReward", {themeId = themeId, achId = achId})
    end)
end

--清除新成就
function P:celearThemeNewTag(themeId)
    local newList = self.newTagDic[themeId].newList
    local saveData = self:getLocalSaveData()
    for _,v in pairs(newList) do
        table.insert(saveData[self.themeLink[themeId]].clearList, v)
    end
    self.newTagDic[themeId].newList = {}

    self:saveLocalSaveData(saveData)
    self:refreshThemeRedPoint(themeId)
end
--获得成就奖励
function P:getedAchievementReward(themeId, achId)
    table.removebyvalue(self.newTagDic[themeId].rewardList, achId)
    local saveData = self:getLocalSaveData()
    saveData[self.themeLink[themeId]].achGetable = table.nums(self.newTagDic[themeId].rewardList)

    self:saveLocalSaveData(saveData)
    self:refreshThemeRedPoint(themeId)
end
--获得主题奖励
function P:getedThemeReward(themeId)
    self.newTagDic[themeId].themeReward = false
    local saveData = self:getLocalSaveData()
    saveData[self.themeLink[themeId]].themeGetable = false

    self:saveLocalSaveData(saveData)
    self:refreshThemeRedPoint(themeId)
end

--获取条件值参数
function P:getDesValue(cfg)
    local needValue = #cfg.value == 1 and cfg.value[1] or cfg.value[2]
    if cfg.task_type == 313 then
        needValue = cfg.value[3]
    elseif cfg.task_type == 204 then
        needValue = 1
    end
    local gameStr = ""
    if #cfg.value == 2 then
        if tpl_task_type_info[cfg.value[1]] then
            gameStr = _T(tpl_task_type_info[cfg.value[1]].name)
        end
    end
    return needValue, gameStr
end

--判定全服进度
function P:getAllServerProgress(rate, hasCompleted)
    if rate > 0 then
        return rate * 0.01
    else
        if hasCompleted then
            return 0.01
        else
            return 0
        end
    end
end

return P