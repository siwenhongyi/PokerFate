local P = class("SayakaTask", require("app.views.Sayaka.SayakaBase"))

function P:onAwake()
    P.super.onAwake(self)
    self._tips = {"LAB_STORY_DIALOGUE_S6_1007_01","LAB_STORY_DIALOGUE_S6_1007_02","LAB_STORY_DIALOGUE_S6_1007_03"}

    self.TaskList = self:find("TaskList", self.Right)
    self.Item = self:find("item1", self.TaskList)
    self.Item:SetActive(false)

    self.ConfirmButton = self:find("Sum/ConfirmButton", self.Right)
    self.NonButton = self:find("Sum/NonButton", self.Right)

    bee.addClick(self.ConfirmButton, function()
        if bee.checkCd("SayakaTask_ConfirmButton", 1) then
            Game:playSound("ui_button_confirm")
            bee.logEvent("activity-theme-task-all", ActivityId.Sayaka)
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

    self.ListTask = UiListEx:create(self.TaskList)
    self.ListTask:setWidth(162)
    self.ListTask:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item)
    end)
    self.ListTask:setRefreshFunc(function(data, item, isInit, index)
        self:refreshItem(data, item, isInit, index)
    end)
    self.ListTask:setTopBottom(0, 120)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[100706], true)

    ThemeModel:reqTaskList(function()
        self._isInInit = true
        self:refreshTasks()
    end)
end

function P:refreshTasks()
    local tasks = ThemeModel:getTasks()
    local datas = {}
    for _, v in ipairs(tasks) do
        table.insert(datas, v)
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

function P:refreshItem(data, item, isInit, index)
    local Ani_root = self:find("Ani_root", item)
    local d = tpl_theme_task[data.task_id]
    local task = ThemeModel:getTask(data.task_id)

    if self._isInInit and isInit then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_2_HotSpringPlot_PiyoList", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_2_HotSpringPlot_PiyoList_idle", Ani_root)
    end

    local cur, sum = task.current_value, task.value[#task.value]
    cur = math.min(cur, sum)
    local des = TaskModel:getTaskDesc(d)
    local tarStr = des .. string.format(" (%s/%s)", (cur < sum and string.format("<color=#EABB3B>%s</color>", cur) or cur), sum)
    bee.setText(self:find("Text", Ani_root), tarStr)
    local iconObj = self:find("icon_activity_s6_01", Ani_root)
    bee.setIcon(iconObj, tpl_props[d.rewards[1]].icon)
    bee.setText(self:find("Value", Ani_root), "x" .. d.rewards[2])

    -- self:find("TextTip", Ani_root):SetActive(false)
    self:find("GoButton", Ani_root):SetActive(task.status == TaskStatus.InProgress)
    self:find("ConfirmButton", Ani_root):SetActive(task.status == TaskStatus.Completed)
    self:find("sayaka_task_done", Ani_root):SetActive(task.status == TaskStatus.Received)
    self:find("sayaka_task_frame_mask", Ani_root):SetActive(task.status == TaskStatus.Received)

    if task.status == TaskStatus.InProgress then
        -- self:find("TextTip", Ani_root):SetActive(d.jump == nil)
        self:find("GoButton", Ani_root):SetActive(d.jump ~= nil)
    else
        -- self:find("TextTip", Ani_root):SetActive(false)
        self:find("GoButton", Ani_root):SetActive(false)
    end

    bee.addClick(iconObj, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(ThemeModel:getItemId(), true), target = iconObj})
    end, true)
    
    bee.addClick(self:find("GoButton", Ani_root), function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("activity-theme-task-link", ActivityId.Sayaka, data.task_id)
		ItemModel:jumpView(d.jump)
        -- bee.logEvent("galaseason-task_link", d.task_id)
        if d.task_type == 302 then
            if d.value[1] == 20001 then
                self:hideUI()
            end
        end
    end, true)
    
    bee.addClick(self:find("ConfirmButton", Ani_root), function()
        if bee.checkCd("SayakaTask_ConfirmButton", 1) then
            Game:playSound("ui_button_confirm")
            bee.logEvent("activity-theme-task-claim", ActivityId.Sayaka, data.task_id)
            -- bee.logEvent("galaseason-task_claim", d.task_id)
            ThemeModel:reqTaskReward(data.id, function()
                self._isInInit = false
                self:refreshTasks()
            end)
        end
    end, true)
end

function P:evt_buy_Success()
    self:once(1, function()
        ThemeModel:reqTaskList(function()
            self._isInInit = false
            self:refreshTasks()
        end)
    end)
end

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

function P:evt_checkViewCallback()
    bee.once(1, function () self:refreshTasks() end)
end

function P:checkReqTask(taskType, gameType)
    local tasks = ThemeModel:getTasks()
    local reqable = false
    for _,v in pairs(tasks) do
        local cfg = tpl_theme_task[v.task_id]
        if cfg.task_type == taskType and cfg.value[1] == gameType then
            reqable = true
            break
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

function P:hideUI()
    P.super.hideUI(self)
    if self._is_show then
		self:hideTopUI()
	end
end

return P