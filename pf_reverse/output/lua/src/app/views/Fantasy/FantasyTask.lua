local P = class("FantasyTask", require("app.views.Fantasy.FantasyBase"))

function P:onAwake()
    P.super.onAwake(self)
    --self._tips = {"LAB_STORY_DIALOGUE_S8_1020_01","LAB_STORY_DIALOGUE_S8_1020_02","LAB_STORY_DIALOGUE_S8_1020_03"}

    self.dataGeted = false
    self.DayList = self:find("DayList", self.Right)
    self.DayContent = self:find("Viewport/Content", self.DayList)
    self.DayItem = self:find("DayItem", self.DayList)
    self.DayItem:SetActive(false)
    self.TaskList = self:find("TaskList", self.Right)
    self.Item = self:find("item1", self.TaskList)
    self.Item:SetActive(false)

    self.ConfirmButton = self:find("ConfirmButton", self.Right)
    self.NonButton = self:find("NonButton", self.Right)

    self.ProgressMask = self:find("progress", self.Left):GetComponent("RectTransform")
    self.CurPoint = self:find("curPoint", self.Left)
    self.role = self:find("fantasy_task_status_figure/role", self.Left)

    bee.addClick(self.ConfirmButton, function()
        if bee.checkCd("ThemeTask_ConfirmButton", 1) then
            Game:playSound("ui_button_confirm")
            bee.logEvent("activity-theme-task-all", ActivityId.Fantasy)
            local tasks = ThemeModel:getTasks()
            local ids = {}
            for _, v in ipairs(tasks) do
                if v.status == TaskStatus.Completed then
                    table.insert(ids, v.id)
                end
            end
            ThemeModel:reqTaskReward(nil, function()
                self._isInInit = false
                self:refreshTasks()
            end, ids)
        end
    end)
    bee.addClick(self.NonButton, function()
        UiManager:showToast(_T("LAB_TASKS_NOREWARDS"))
    end)

    self.curDisplayDay = -1
    self.DayItemList = {}
    self.RewardList = {}
    self.PointList = {}
    self.taskDic = {}

    self.ListTask = UiListEx:create(self.TaskList)
    self.ListTask:setWidth(140)
    self.ListTask:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item)
    end)
    self.ListTask:setRefreshFunc(function(data, item, isInit, index)
        self:refreshItem(data, item, isInit, index)
    end)

    self.norSize = 111
    self.norProgress = 50
    self.lastSize = 121
    self.lastProgress = 60


    -- self.startPos = -366
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[101306], false)

    self:initTaskBase()

    self.curDisplayDay = -1
    ThemeModel:reqTaskList(function()
        self.dataGeted = true
        self._isInInit = true
        self:inithDays()
        self:initProgress()
        self:refreshTasks()
    end)

    --积分进度特殊处理
    local uiroot = UiManager:getUiRoot():GetComponent("RectTransform")
    if Config.UI_OFFSET_LEFT < -50 and Config.UI_OFFSET_RIGHT > 50 and uiroot.sizeDelta.x < 2100 then
        self.Left.transform.localPosition = self.Left.transform.localPosition - bee.v3(40, 0, 0)
    end
end

function P:initTaskBase()
    for _,v in pairs(tpl_theme_task) do
        if v.group > 9000 and v.group < 10000 then
            if self.taskDic[v.unlock + 1] == nil then
                self.taskDic[v.unlock + 1] = {}
            end
            table.insert(self.taskDic[v.unlock + 1], v)
        end
    end
    -- for _,v in pairs(self.taskDic) do
    --     table.sort(v, function(a, b)
    --         return a.sort < b.sort
    --     end)
    -- end

    local pointRewards = get_tpl_subKey(tpl_theme_points_rewards_list, "rewards_group", ThemeModel:getConfId())
    for _,v in pairs(pointRewards) do
        table.insert(self.PointList, {id = v.id, point = v.point, reward = v.rewards})
    end
    table.sort(self.PointList, function(a, b)
        return a.id < b.id
    end)
end

--初始化天数
function P:inithDays()
    local days = #self.taskDic
    for i = 1, days do
        local item = {}
        item.go = CU.GameObject.Instantiate(self.DayItem)
        item.go.transform:SetParent(self.DayContent.transform)
        item.go.transform.localScale = bee.v3one
        item.go:SetActive(true)
        item.day = i
        item.frameOn = self:find("fantasy_task_frame_time_01", item.go)
        item.frameOff = self:find("fantasy_task_frame_time_02", item.go)
        item.frameLock = self:find("fantasy_task_frame_time_lock", item.go)
        item.reddot = self:find("Reddot", item.go)
        item.unlock = 0
        local dayStr = _F("LAB_THEME_ACTIVITY9_22", item.day)
        bee.setText(self:find("Text", item.frameOn), dayStr)
        bee.setText(self:find("Text", item.frameOff), dayStr)
        bee.addClick(item.go, function ()
            if item.unlock > 0 then
                if item.unlock == 1 then
                    local leftTime = ThemeModel:getCrossDayLeftTime()
                    local remainHour = math.ceil(leftTime / 3600)
                    UiManager:showToast(_F("LAB_THEME_ACTIVITY9_TASK_DEC_15_2", remainHour))
                    return
                end
                UiManager:showToast(_F("LAB_THEME_ACTIVITY9_TASK_DEC_15_1", item.unlock))
                return
            end

            if self.curDisplayDay ~= item.day then
                self._isInInit = true
                self:refreshDays(item.day)
                self:refreshTasks(item.day)
            end
        end)

        table.insert(self.DayItemList, item)
    end
    self:checkUnlockDays()
end
function P:checkUnlockDays()
    local tasks = ThemeModel:getTasks()
    local unlockDay = 0
    for _,v in pairs(tasks) do
        local cfg = tpl_theme_task[v.task_id]
        if cfg.unlock and cfg.unlock > unlockDay then
            unlockDay = cfg.unlock
        end
    end
    -- unlockDay = 2 

    for _,v in pairs(self.DayItemList) do
        v.unlock = (v.day - 1) - unlockDay
        v.frameLock:SetActive(v.unlock > 0)
    end
end

function P:refreshDays(day)
    for _,v in pairs(self.DayItemList) do
        local isSelf = v.day == day
        v.frameOn:SetActive(isSelf)
        v.frameOff:SetActive(not isSelf)
    end
end

function P:refreshReddot()
    local tasks = ThemeModel:getTasks()
    local reddotDic = {}
    for _,v in pairs(tasks) do
        if v.status == TaskStatus.Completed then
            local cfg = tpl_theme_task[v.task_id]
            if reddotDic[cfg.unlock + 1] == nil then
                reddotDic[cfg.unlock + 1] = true
            end
        end
    end

    --分页红点
    for _,v in pairs(self.DayItemList) do
        local reddot = reddotDic[v.day] and true or false
        v.reddot:SetActive(reddot)
    end
end

--刷新任务
function P:refreshTasks(day)
    self:refreshReddot()
    local tasks = ThemeModel:getTasks()
    local netTaskDic = {}
    for _,v in pairs(tasks) do
        local cfg = tpl_theme_task[v.task_id]
        if netTaskDic[cfg.unlock + 1] == nil then
            netTaskDic[cfg.unlock + 1] = {}
        end
        table.insert(netTaskDic[cfg.unlock + 1], v)
    end

    --分页指定
    if day == nil then --无指定分页
        if self.curDisplayDay == -1 then --无缓存分页
            day = 0
            local clearDay = 0
            for k,v in pairs(netTaskDic) do
                if k > day then --当前已开通的最大天数
                    day = k
                end
                for _,vv in pairs(v) do
                    if vv.status == 2 then --有已完成未领取的最小分页
                        if clearDay == 0 or k < clearDay then
                            clearDay = k
                            break
                        end
                    end
                end
            end
            if clearDay ~= 0 then --已完成未领取优先
                day = clearDay
            else
                --已开通最大天数是否有未完成任务
                local maxDayTasks = netTaskDic[day]
                local checkOther = true
                for _,v in pairs(maxDayTasks) do
                    if v.status <= 1 then
                        checkOther = false
                        break
                    end
                end
                --已开通最大天数全部任务已完成
                local cacheDay = day
                if checkOther then
                    for k,v in pairs(netTaskDic) do
                        for _,vv in pairs(v) do
                            if vv.status <= 1 and k < cacheDay then
                                cacheDay = k
                                break
                            end
                        end
                    end
                    day = cacheDay
                end
            end
            self:dayItemMoveToTarget(day)
            self.curDisplayDay = day
        else --有缓存分页
            day = self.curDisplayDay
        end
        self:refreshDays(day)
    else --指定分页
        self.curDisplayDay = day
    end

    local datas = {}
    if netTaskDic[day] then
        for _,v in ipairs(netTaskDic[day]) do
            table.insert(datas, v)
        end
    else
        for _,v in ipairs(self.taskDic[day]) do
            local cacheData = {}
            cacheData.task_id = v.task_id
            cacheData.status = 0
            table.insert(datas, cacheData)
        end
    end
    table.sort(datas, function(a, b)
        if a.status == b.status then
            return a.task_id < b.task_id
        end
        if a.status == TaskStatus.Received or b.status == TaskStatus.Received then
            return a.status < b.status
        end
        return a.status > b.status
    end)

    self.ListTask._list.enabled = false
    self:once(0.15, function()
        self.ListTask:setDatas(datas)
        self:once(0.7, function()
            self.ListTask._list.enabled = true
        end)
    end)

    self:refreshSumButtons()
    self:refreshProgress()
end
function P:refreshSumButtons()
    local tasks = ThemeModel:getTasks()
    for _, v in ipairs(tasks) do
        if v.status == TaskStatus.Completed then
            self.ConfirmButton:SetActive(true)
            self.NonButton:SetActive(false)
            return
        end
    end
    self.ConfirmButton:SetActive(false)
    self.NonButton:SetActive(true)
end

--刷新任务Item
function P:refreshItem(data, item, isInit, index)
    local Ani_root = self:find("Ani_root", item)
    local d = tpl_theme_task[data.task_id]
    local task = ThemeModel:getTask(data.task_id)
    if task == nil then
        task = {}
        task.status = 0
        task.current_value = 0
        task.value = d.value
    end

    if self._isInInit and isInit then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_GalaSeasonShop_item", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_GalaSeasonShop_item_idle", Ani_root)
    end

    local count = #task.value
    local cur, sum = task.current_value, task.value[count]
    cur = math.min(cur, sum)
    local des = TaskModel:getTaskDesc(d)
    local tarStr = des .. string.format(" (%s/%s)", (cur >= sum and string.format("<color=#DF9152>%s</color>", cur) or cur), sum)
    bee.setText(self:find("Text", Ani_root), tarStr)
    bee.setIcon(self:find("icon_activity_s7_01", Ani_root), tpl_props[d.rewards[1]].icon)
    bee.setText(self:find("Value", Ani_root), "x" .. d.rewards[2])

    -- self:find("TextTip", Ani_root):SetActive(false)
    self:find("GoButton", Ani_root):SetActive(task.status == TaskStatus.InProgress)
    self:find("ConfirmButton", Ani_root):SetActive(task.status == TaskStatus.Completed)
    self:find("fantasy_task_done", Ani_root):SetActive(task.status == TaskStatus.Received)
    self:find("fantasy_task_frame_mask", Ani_root):SetActive(task.status == TaskStatus.Received or task.status == 0)

    if task.status == TaskStatus.InProgress then
        -- self:find("TextTip", Ani_root):SetActive(d.jump == nil)
        self:find("GoButton", Ani_root):SetActive(d.jump ~= nil)
    else
        -- self:find("TextTip", Ani_root):SetActive(false)
        self:find("GoButton", Ani_root):SetActive(false)
    end

    local iconObj = self:find("Icon", Ani_root)
    bee.addClick(iconObj, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(ThemeModel:getPointId(), true), target = iconObj})
    end, true)
    
    bee.addClick(self:find("GoButton", Ani_root), function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-task-link", ActivityId.Fantasy, data.task_id)
		ItemModel:jumpView(d.jump)
        -- bee.logEvent("galaseason-task_link", d.task_id)
        if d.jump == 4001 then
            self:hideUI()
            UiManager:hideUI("FantasyMain")
        end
        if d.task_type == 302 then
            if d.value[1] == 20001 then
                self:hideUI()
            end
        end
    end, true)
    
    bee.addClick(self:find("ConfirmButton", Ani_root), function()
        if bee.checkCd("ThemeTask_ConfirmButton", 1) then
            Game:playSound("ui_button_confirm")
            bee.logEvent("activity-theme-task-claim", ActivityId.Fantasy, data.task_id)
            -- bee.logEvent("galaseason-task_claim", d.task_id)
            ThemeModel:reqTaskReward(data.id, function()
                self._isInInit = false
                self:refreshTasks()
            end)
        end
    end, true)
end

--初始化进度内容
function P:initProgress()
    local rewards = #self.PointList
    for i = 1, rewards do
        local index = i
        local id = self.PointList[index].id
        local point = self.PointList[index].point
        local reward = self.PointList[index].reward

        local pt = self:find("pt" .. index, self.Left)
        bee.setText(pt, point)
        local propt = self:find("progress/pt" .. index, self.Left)
        bee.setText(propt, point)
        
        local item = {}
        item.index = index
        item.id = id
        item.go = self:find("item" .. index, self.Left)
        local propCfg = tpl_props[reward[1]]
        bee.setIcon(self:find("common_item_grid_s_06", item.go), string.format("Common[common_item_grid_m_%02d]", propCfg.quality + 1))
        local iconObj = self:find("icon", item.go)
        bee.setIcon(iconObj, propCfg.icon)
        if propCfg.type == GPropKind.Title then
            iconObj.transform.sizeDelta = bee.v2(90, 15)
        end
        bee.setText(self:find("num", item.go), _N2(reward[2]))
        item.mask = self:find("fantasy_item_grid_m_mask", item.go)
        item.mask:SetActive(false)
        item.done = self:find("fantasy_task_done_01", item.go)
        item.done:SetActive(false)
        item.fx = self:find("eff_poker_Fantasy_item_loop", item.go)
        item.fx:SetActive(false)
        bee.addClick(item.go, function ()
            local itemData = ItemModel:getItem(ThemeModel:getPointId())
            local itemNum = itemData and itemData.num or 0
            Game:playSound("ui_button_confirm")
            if itemNum >= point and not ThemeModel:checkPointRewardGeted(id) then
                ThemeModel:getThemePointReward()
                local tarId = 0
                for j = 1, rewards do
                    local cacheId = self.PointList[j].id
                    local cachePoint = self.PointList[j].point
                    if itemNum >= cachePoint then
                        if tarId < cacheId then
                            tarId = cacheId
                        end
                    end
                end
                bee.logEvent("activity-theme-point-reward", ActivityId.Fantasy, tarId)
            else
                UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(reward[1], true), target = item.go})
            end
        end, true)
        table.insert(self.RewardList, item)
    end
    self:refreshPointReward()
end

--刷新进度
function P:refreshProgress()
    local pointId = ThemeModel:getPointId()
    bee.setText(self.CurPoint, 0)
    if pointId == 0 then return end

    local itemData = ItemModel:getItem(pointId)
    local progress = itemData and itemData.num or 0
    bee.setText(self.CurPoint, progress)
    local cacheProgress = 0
    local lastIndex = #self.PointList
    local maskProgress = 0
    local posPorgress = 0
    for k,v in pairs(self.PointList) do
        local pointValue = k < lastIndex and self.norSize or self.lastSize
        local pointProgress = k < lastIndex and self.norProgress or self.lastProgress
        if progress > v.point then
            maskProgress = maskProgress + pointValue
            posPorgress = posPorgress + pointValue
            cacheProgress = v.point
        elseif progress == v.point then
            maskProgress = maskProgress + pointValue
            posPorgress = posPorgress + pointValue
            cacheProgress = v.point
            break
        else
            if progress > 0 then
                local ptVal = pointProgress * ((progress - cacheProgress) / (v.point - cacheProgress))
                maskProgress = maskProgress + ptVal
                posPorgress = posPorgress + ptVal + 23
            end
            break
        end
    end
    self.ProgressMask.sizeDelta = bee.v2(maskProgress, self.ProgressMask.sizeDelta.y)
    self.role.transform.localPosition = bee.v3(posPorgress, self.role.transform.localPosition.y, 0)
end

--物品变动
function P:evt_ItemChangeRSP()
    self:refreshProgress()
    self:refreshPointReward()
end

--积分奖励
function P:evt_getThemePointRewardCallback()
    self:refreshPointReward()
end
function P:refreshPointReward()
    local itemData = ItemModel:getItem(ThemeModel:getPointId())
    local itemNum = itemData and itemData.num or 0

    for _,v in pairs(self.RewardList) do
        local geted = ThemeModel:checkPointRewardGeted(v.id)
        v.mask:SetActive(geted)
        v.done:SetActive(geted)
        local getabel = not geted and itemNum >= self.PointList[v.index].point
        v.fx:SetActive(getabel)
    end
    ThemeModel:refreshReddot(true)
end

function P:evt_themeRefreshTask()
    if self.dataGeted then
        bee.once(0.5, function ()
            self._isInInit = false
            self:refreshTasks()
        end)
    end
end

function P:evt_buy_Success()
    self:once(1, function()
        ThemeModel:reqTaskList(function()
            self._isInInit = false
            self:refreshTasks()
        end)
    end)
end

-- function P:evt_checkViewCallback()
--     bee.once(1, function () self:refreshTasks() end)
-- end

function P:evt_ColorGameActionRSP()
    self:checkReqTask(101, GAME_GAME_TYPE.SIDE_GAME_COLOR_GAME)
end

function P:evt_ColorGameWin()
    self:checkReqTask(104, GAME_GAME_TYPE.SIDE_GAME_COLOR_GAME)
end

function P:evt_PinballActionRSP()
    self:checkReqTask(101, GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME)
end

function P:evt_PinballWin()
    self:checkReqTask(104, GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME)
end

-- function P:evt_lotteryEvent()
--     self:checkReqTask(321, ThemeModel:getThemeConfId())
-- end

-- function P:evt_soccerBet()
--     self:checkReqTask(322)
-- end

function P:checkReqTask(taskType, gameType)
    local tasks = ThemeModel:getTasks()
    local reqable = false
    if next(tasks) == nil then
        reqable = true
    else
        for _,v in pairs(tasks) do
            local cfg = tpl_theme_task[v.task_id]
            if cfg.task_type == taskType and (gameType and cfg.value[1] == gameType or cfg.value[1] == 1) and v.status <= 1 then
                reqable = true
                break
            end
        end
    end
    if reqable then
        self:once(1, function()
            ThemeModel:reqTaskList(function()
                self._isInInit = false
                self:refreshTasks()
            end)
        end)
    end
end

--分页跳转
function P:dayItemMoveToTarget(index)
    local contentTran = self.DayContent:GetComponent("RectTransform")
    bee.once(0.2, function ()
        if index < 5 then
            contentTran.anchoredPosition = bee.v2(0 , 0)
        else
            contentTran.anchoredPosition = bee.v2(-(contentTran.sizeDelta.x - self.DayList:GetComponent("RectTransform").sizeDelta.x), 0)
        end
    end)
end



function P:hideUI()
    P.super.hideUI(self)
    if self._is_show then
		self:hideTopUI()
	end
end

return P