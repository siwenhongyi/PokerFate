local P = class("SpringFestivalTask", UiDialog)

function P:onAwake()
    local Pannel = self:find("AnimRoot/Center/Pannel")
    self.CloseButton = self:find("CloseButton", Pannel)
    self.RefreshText = self:find("Oneclick/Text", Pannel)
    self.ClaimButton = self:find("Oneclick/ClaimButton", Pannel)
    self.GrayButton = self:find("Oneclick/GrayButton", Pannel)
    self.TaskList = self:find("TaskList", Pannel)
    self.TaskItem = self:find("TaskList/TaskItem", Pannel)

    bee.addClick(self.CloseButton, function()
		Game:playSound("ui_button_confirm")
		self:hideUI()
	end)

    bee.addClick(self.ClaimButton, function()
        Game:playSound("ui_button_confirm")
        self:clearAllCompletedTask()
    end)

    bee.addClick(self.GrayButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showToast(_T("LAB_TASKS_NOREWARDS"))
    end)


    self.List = UiListEx:create(self.TaskList)
    self.List:setWidth(163)
    self.List:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.TaskItem)
    end)
    self.List:setRefreshFunc(function(data, item, isInit, index)
        self:refreshItem(data, item, isInit, index)
    end)

    bee.logEvent("springfestival-task")
end

function P:onShow()
    SpringFestivalModel:reqTaskList()
end

function P:evt_refreshFestivalTaskList()
    local tasks = SpringFestivalModel:getTasks()
    local datas = {}
    local hasCompleted = false
    for _, v in ipairs(tasks) do
        table.insert(datas, v)
        if not hasCompleted and v.status == TaskStatus.Completed then
            hasCompleted = true
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
    self.List:setDatas(datas)

    self.ClaimButton:SetActive(hasCompleted)
    self.GrayButton:SetActive(not hasCompleted)
end

function P:refreshItem(data, itemGo, isInit, index)
    local item = ObjectPool:getCls(itemGo)
    item:refreshItem(data, isInit, index, function(name, root)
        self:playAnimator(name, root)
    end)
end

function P:clearAllCompletedTask()
    local tasks = SpringFestivalModel:getTasks()
    local completedIds = {}
    for _,v in pairs(tasks) do
        if v.status == TaskStatus.Completed then
            table.insert(completedIds, v.id)
        end
    end
    SpringFestivalModel:clearTasks(completedIds)
    bee.logEvent("springfestival-task_all")
end


return P