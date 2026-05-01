local P = class("SpringFestivalTaskItem", Object)

function P:onAwake()
    self.AniRoot = self:find("Ani_root")
    self.RewardIcon = self:find("spring_main_icon_currency", self.AniRoot)
    self.RewardCount = self:find("amount/Value", self.AniRoot)
    self.Title = self:find("Title", self.AniRoot)
    self.Slider = self:find("Progress/TaskSlider", self.AniRoot)
    self.ProgressValue = self:find("Progress/Value", self.AniRoot)
    self.ClaimButton = self:find("ClaimButton", self.AniRoot)
    self.GoButton = self:find("GoButton", self.AniRoot)
    self.Geted = self:find("spring_task_img_gou", self.AniRoot)

end

function P:refreshItem(data, isInit, index, playAnimator)
    if isInit then
        self:once(0.1 * (index - 1), function()
            self.AniRoot:SetActive(true)
            playAnimator("UI_1_SpringFestivalTaskItem", self.AniRoot)
        end)
        self.AniRoot:SetActive(false)
    else
        self.AniRoot:SetActive(true)
        playAnimator("UI_1_SpringFestivalTaskItemIdle", self.AniRoot)
    end

    local cfg = tpl_festival_task[data.task_id]
    bee.setText(self.Title, TaskModel:getTaskDesc(cfg))
    bee.setIcon(self.RewardIcon, tpl_props[data.rewards[1]].icon)
    bee.setText(self.RewardCount, string.format("x%d", data.rewards[2]))
    local needValue = #data.value == 1 and data.value[1] or data.value[2]
    local curValue = math.min(data.current_value, needValue)
    local progress = curValue / needValue
    bee.setSliderValue(self.Slider, progress)
    bee.setText(self.ProgressValue, string.format("%s/%s", curValue, needValue))

    self.Geted:SetActive(data.status == TaskStatus.Received)
    self.ClaimButton:SetActive(data.status == TaskStatus.Completed)
    self.GoButton:SetActive(data.status == TaskStatus.InProgress)

    bee.removeAllClick(self.ClaimButton)
    bee.addClick(self.ClaimButton, function ()
        Game:playSound("ui_button_confirm")
        SpringFestivalModel:clearTasks({data.id})
        bee.logEvent("springfestival-task_claim", data.task_id)
    end)
    bee.removeAllClick(self.GoButton)
    bee.addClick(self.GoButton, function()
        Game:playSound("ui_button_confirm")
		-- 前往跳转
		if cfg.jump then
            ItemModel:jumpView(cfg.jump)
		end
        bee.logEvent("springfestival-task_link", data.task_id)
    end)
end

return P