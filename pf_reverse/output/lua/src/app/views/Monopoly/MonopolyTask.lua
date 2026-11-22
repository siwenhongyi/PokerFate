local P = class("MonopolyTask", UiFullView)

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", AnimRoot)
    self.Pannel = self:find("Pannel", self.Center)
    self.TaskList = self:find("TaskList", self.Pannel)
    self.Item = self:find("Item1", self.TaskList)
    self.Item:SetActive(false)

    self.ConfirmButton = self:find("ClaimButton", self.Pannel)
    self.NonButton = self:find("NoneButton", self.Pannel)

    self.ListTask = UiListEx:create(self.TaskList)
    self.ListTask:setWidth(162)
    self.ListTask:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item)
    end)
    self.ListTask:setRefreshFunc(function(data, item, isInit, index)
        self:refreshItem(data, item, isInit, index)
    end)

    bee.addClick(self.ConfirmButton, function()
        if bee.checkCd("MonopolyTask_ConfirmButton", 1) then
            Game:playSound("ui_button_confirm")
            bee.logEvent("monopoly-task-all")
            local tasks = MonopolyModel:getTasks()
            local ids = {}
            for _, v in ipairs(tasks) do
                if v.status == TaskStatus.Completed then
                    table.insert(ids, v.id)
                end
            end
            MonopolyModel:getTaskReward(nil, function()
                self._isInInit = false
                self:refreshTasks()
            end, ids)
        end
    end)
    bee.addClick(self.NonButton, function()
        UiManager:showToast(_T("LAB_TASKS_NOREWARDS"))
    end)

    bee.addClick(self:find("CloseButton", self.Pannel), function ()
        Game:playSound("ui_button_confirm")
        self:hideUI()
    end)

end

function P:onShow()
    MonopolyModel:reqTaskList(function()
        self._isInInit = true
        self:refreshTasks()
    end)
end

function P:refreshTasks()
    local tasks = MonopolyModel:getTasks()
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
    local tasks = MonopolyModel:getTasks()
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
    local d = tpl_monopoly_task[data.task_id]
    local task = MonopolyModel:getTask(data.task_id)

    if self._isInInit and isInit then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_AchievementMain_item", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_AchievementMain_item_idle", Ani_root)
    end

    local cur, sum = task.current_value, task.value[#task.value]
    cur = math.min(cur, sum)
    local des = TaskModel:getTaskDesc(d)
    local tarStr = des .. string.format(" (%s/%s)", (cur >= sum and string.format("<color=#CE8414>%s</color>", _N2(cur)) or _N2(cur)), _N2(sum))
    bee.setText(self:find("Text", Ani_root), tarStr)
    bee.setIcon(self:find("Icon", Ani_root), tpl_props[d.rewards[1]].icon)
    bee.setText(self:find("Value", Ani_root), "x" .. d.rewards[2])

    -- self:find("TextTip", Ani_root):SetActive(false)
    self:find("GoButton", Ani_root):SetActive(task.status == TaskStatus.InProgress)
    self:find("ClaimButton", Ani_root):SetActive(task.status == TaskStatus.Completed)
    self:find("monopoly_task_done", Ani_root):SetActive(task.status == TaskStatus.Received)
    self:find("monopoly_task_frame_mask", Ani_root):SetActive(task.status == TaskStatus.Received)

    -- if task.status == TaskStatus.InProgress then
    --     self:find("GoButton", Ani_root):SetActive(d.jump ~= nil)
    -- else
    --     self:find("GoButton", Ani_root):SetActive(false)
    -- end

    local iconObj = self:find("Icon", Ani_root)
    bee.addClick(iconObj, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(d.rewards[1], true), target = iconObj})
    end, true)
    
    bee.addClick(self:find("GoButton", Ani_root), function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("monopoly-link", data.task_id)
        if d.jump then
            ItemModel:jumpView(d.jump)
            if d.task_type == 302 then
                if d.value[1] == 20001 then
                    self:hideUI()
                end
            end
        end
    end, true)
    
    bee.addClick(self:find("ClaimButton", Ani_root), function()
        if bee.checkCd("MonopolyTask_ConfirmButton", 1) then
            Game:playSound("ui_button_confirm")
            bee.logEvent("monopoly-task-claim", data.task_id)
            MonopolyModel:getTaskReward(data.id, function()
                self._isInInit = false
                self:refreshTasks()
            end)
        end
    end, true)
end

function P:evt_buy_Success()
    self:once(1, function()
        MonopolyModel:reqTaskList(function()
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
    local tasks = MonopolyModel:getTasks()
    local reqable = false
    for _,v in pairs(tasks) do
        local cfg = tpl_monopoly_task[v.task_id]
        if cfg.task_type == taskType and cfg.value[1] == gameType and v.status <= 1 then
            reqable = true
            break
        end
    end
    if reqable then
        self:once(1, function()
            MonopolyModel:reqTaskList(function()
                self._isInInit = false
                self:refreshTasks()
            end)
        end)
    end
end


return P