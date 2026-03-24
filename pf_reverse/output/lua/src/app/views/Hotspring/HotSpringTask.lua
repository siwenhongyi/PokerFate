local P = class("HotSpringTask", require("app.views.Hotspring.HotSpringBase"))


function P:onAwake()
    P.super.onAwake(self)

    self._tips = {"LAB_STORY_DIALOGUE_S1_1005_01", "LAB_STORY_DIALOGUE_S1_1005_02", "LAB_STORY_DIALOGUE_S1_1005_03"}

    self.PiyoList = self:find("PiyoList", self.Right)
    self.Item = self:find("Item", self.PiyoList)
    self.Item:SetActive(false)

    self._pregressSize = self:find("Ani_root/hotspring_pro_bar", self.Item).transform.sizeDelta

    self.ListPlot = UiListEx:create(self.PiyoList)
    self.ListPlot:setWidth(200)
    self.ListPlot:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item)
    end)
    self.ListPlot:setRefreshFunc(function(data, item, isInit, index)
        self:refreshItem(data, item, isInit, index)
    end)
end

function P:onShow()
    P.super.onShow(self)
    bee.invoke(self.CharacterImage, "setSkin", tpl_character_skin[100505], true)

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

    self.ListPlot._list.enabled = false
    self:once(0.15, function()
        self.ListPlot:setDatas(datas)
        self:once(0.7, function()
            self.ListPlot._list.enabled = true
        end)
    end)
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

    bee.setText(self:find("TextName", Ani_root), TaskModel:getTaskDesc(d))
    bee.setIcon(self:find("Icon", Ani_root), tpl_props[d.rewards[1]].icon)
    bee.setText(self:find("TextCount", Ani_root), "x" .. d.rewards[2])

    self:find("TextTip", Ani_root):SetActive(false)
    self:find("btn_go", Ani_root):SetActive(task.status == TaskStatus.InProgress)
    self:find("btn_claim", Ani_root):SetActive(task.status == TaskStatus.Completed)
    self:find("hotspring_mask_2", Ani_root):SetActive(task.status == TaskStatus.Received)

    local cur, sum = task.current_value, task.value[3] or task.value[2] or task.value[1]
    bee.setText(self:find("TextProgress", Ani_root), "" .. cur .. "/" .. sum)
    self:find("hotspring_pro_bar", Ani_root).transform.sizeDelta = bee.v2(self._pregressSize.x * math.min(cur / sum, 1), self._pregressSize.y)

    if task.status == TaskStatus.InProgress then
        self:find("TextTip", Ani_root):SetActive(d.jump == nil)
        self:find("btn_go", Ani_root):SetActive(d.jump ~= nil)
    else
        self:find("TextTip", Ani_root):SetActive(false)
        self:find("btn_go", Ani_root):SetActive(false)
    end

    bee.addClick(self:find("Icon", Ani_root), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(ThemeModel:getItemId(), true), target = self:find("Icon", Ani_root)})
    end, true)
    
    bee.addClick(self:find("btn_go", Ani_root), function()
        Game:playSound("ui_button_confirm")
		ItemModel:jumpView(d.jump)
        bee.logEvent("onsen-task_link", d.task_id)
        if d.task_type == 302 then
            self:hideUI()
        end
    end, true)
    
    bee.addClick(self:find("btn_claim", Ani_root), function()
        if bee.checkCd("HotSpringTask_btn_claim", 1) then
            Game:playSound("ui_button_confirm")
            bee.logEvent("onsen-task_claim", d.task_id)
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

