local P = class("GalaSeasonActivity", require("app.views.GalaSeason.GalaSeasonBase"))

function P:onAwake()
    P.super.onAwake(self)
    self._tips = {"LAB_STORY_DIALOGUE_S2_1010_01","LAB_STORY_DIALOGUE_S2_1010_02","LAB_STORY_DIALOGUE_S2_1010_03"}

    self.TaskList = self:find("TaskList", self.Right)
    self.Item = self:find("Item1", self.TaskList)
    self.Item:SetActive(false)

    self.ConfirmButton = self:find("Sum/ConfirmButton", self.Right)
    self.NonButton = self:find("Sum/NonButton", self.Right)

    self._pregressSize = self:find("Ani_root/Task/galaseason_activity_slider_fill", self.Item).transform.sizeDelta

    bee.addClick(self.ConfirmButton, function()
        if bee.checkCd("HotSpringTask_ConfirmButton", 1) then
            Game:playSound("ui_button_confirm")
            bee.logEvent("galaseason-task_all")
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
    self.ListTask:setWidth(200)
    self.ListTask:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item)
    end)
    self.ListTask:setRefreshFunc(function(data, item, isInit, index)
        self:refreshItem(data, item, isInit, index)
    end)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[101005], true)

    ThemeModel:reqTaskList(function()
        self._isInInit = true
        self:refreshTasks()
    end)
    -- self:refreshTasks()
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
            self:playAnimator("UI_1_GalaSeasonActivity_item", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_GalaSeasonActivity_item_idle", Ani_root)
    end

    bee.setText(self:find("Task/TextName", Ani_root), TaskModel:getTaskDesc(d))
    bee.setIcon(self:find("Item1/gala_main_icon_currency", Ani_root), tpl_props[d.rewards[1]].icon)
    bee.setText(self:find("Item1/TextCount", Ani_root), "x" .. d.rewards[2])

    -- self:find("TextTip", Ani_root):SetActive(false)
    self:find("GoButton", Ani_root):SetActive(task.status == TaskStatus.InProgress)
    self:find("ConfirmButton", Ani_root):SetActive(task.status == TaskStatus.Completed)
    self:find("galaseason_activity_img_mask", Ani_root):SetActive(task.status == TaskStatus.Received)

    local cur, sum = task.current_value, task.value[3] or task.value[2] or task.value[1]
    bee.setText(self:find("Task/TextProgress", Ani_root), "" .. cur .. "/" .. sum)
    self:find("Task/galaseason_activity_slider_fill", Ani_root).transform.sizeDelta = bee.v2(self._pregressSize.x * math.min(cur / sum, 1), self._pregressSize.y)

    if task.status == TaskStatus.InProgress then
        -- self:find("TextTip", Ani_root):SetActive(d.jump == nil)
        self:find("GoButton", Ani_root):SetActive(d.jump ~= nil)
    else
        -- self:find("TextTip", Ani_root):SetActive(false)
        self:find("GoButton", Ani_root):SetActive(false)
    end

    bee.addClick(self:find("Item1", Ani_root), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(ThemeModel:getItemId(), true), target = self:find("Item1/gala_main_icon_currency", Ani_root)})
    end, true)
    
    bee.addClick(self:find("GoButton", Ani_root), function()
        Game:playSound("ui_button_confirm")
		ItemModel:jumpView(d.jump)
        bee.logEvent("galaseason-task_link", d.task_id)
        if d.task_type == 302 then
            self:hideUI()
        end
    end, true)
    
    bee.addClick(self:find("ConfirmButton", Ani_root), function()
        if bee.checkCd("HotSpringTask_ConfirmButton", 1) then
            Game:playSound("ui_button_confirm")
            bee.logEvent("galaseason-task_claim", d.task_id)
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

return P